# core/database.py
"""SQLite user store in user-space (stdlib only)."""
from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_FILE: Path = Path.home() / ".newsletter_tool" / "users.db"

ROLES = ("basico", "premium", "admin")
STATUSES = ("pendente", "ativo", "revogado")
_ITERATIONS = 120_000


def _connect(db_path: Path | str) -> sqlite3.Connection:
    target = Path(db_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path | str = DB_FILE) -> None:
    with _connect(db_path) as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                org TEXT NOT NULL DEFAULT '',
                internal INTEGER NOT NULL DEFAULT 1,
                role TEXT NOT NULL CHECK(role IN ('basico','premium','admin')),
                status TEXT NOT NULL CHECK(status IN ('pendente','ativo','revogado')),
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL,
                created_by TEXT NOT NULL DEFAULT 'system')"""
        )
        conn.execute("CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL)")


def _hash(password: str, salt_hex: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt_hex), _ITERATIONS)
    return digest.hex()


def create_user(db_path: Path | str, username: str, name: str, org: str,
                internal: bool, role: str, password: str,
                created_by: str = "system", status: str = "ativo") -> int:
    if not (username or "").strip():
        raise ValueError("username must be non-empty")
    if not (password or ""):
        raise ValueError("password must be non-empty")
    if role not in ROLES:
        raise ValueError(f"role must be one of {ROLES}")
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    init_db(db_path)
    salt = secrets.token_hex(16)
    with _connect(db_path) as conn:
        try:
            cursor = conn.execute(
                "INSERT INTO users(username, name, org, internal, role, status,"
                " password_hash, salt, created_at, created_by)"
                " VALUES(?,?,?,?,?,?,?,?,?,?)",
                (username, name, org, int(bool(internal)), role, status,
                 _hash(password, salt), salt,
                 datetime.now(timezone.utc).isoformat(), created_by),
            )
        except sqlite3.IntegrityError as e:
            raise ValueError(f"username {username!r} already exists") from e
        return int(cursor.lastrowid)


def authenticate(db_path: Path | str, username: str, password: str) -> dict | None:
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?",
                           (username,)).fetchone()
    if row is None:
        return None
    user = dict(row)
    if not hmac.compare_digest(_hash(password, user["salt"]), user["password_hash"]):
        return None
    user.pop("password_hash", None)
    user.pop("salt", None)
    return user


def set_status(db_path: Path | str, username: str, status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    init_db(db_path)
    with _connect(db_path) as conn:
        cursor = conn.execute("UPDATE users SET status = ? WHERE username = ?",
                              (status, username))
        if cursor.rowcount == 0:
            raise ValueError(f"unknown username {username!r}")


def set_password(db_path: Path | str, username: str, new_password: str) -> None:
    init_db(db_path)
    salt = secrets.token_hex(16)
    with _connect(db_path) as conn:
        cursor = conn.execute("UPDATE users SET password_hash = ?, salt = ? WHERE username = ?",
                              (_hash(new_password, salt), salt, username))
        if cursor.rowcount == 0:
            raise ValueError(f"unknown username {username!r}")


def list_users(db_path: Path | str) -> list[dict]:
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT id, username, name, org, internal, role, status,"
                            " created_at, created_by FROM users ORDER BY name").fetchall()
    return [dict(r) for r in rows]


def bootstrap_admin(db_path: Path | str, name: str, username: str, password: str) -> str:
    init_db(db_path)
    with _connect(db_path) as conn:
        # NOTA: verificação-then-inserção (TOCTOU) — assume processo único;
        # o UNIQUE(username) continua valendo como salvaguarda concorrente.
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count:
            raise ValueError("users table is not empty")
    create_user(db_path, username, name, "QuIIN", True, "admin", password,
                created_by="bootstrap", status="ativo")
    code = secrets.token_urlsafe(24)
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    with _connect(db_path) as conn:
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('admin_recovery', ?)",
                     (code_hash,))
    return code


def reset_admin_via_recovery_code(db_path: Path | str, code: str, new_password: str) -> bool:
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    with _connect(db_path) as conn:
        row = conn.execute("SELECT value FROM meta WHERE key = 'admin_recovery'").fetchone()
        if row is None:
            return False
        if not hmac.compare_digest(row["value"], code_hash):
            return False
        admin = conn.execute("SELECT username FROM users WHERE role = 'admin'"
                             " ORDER BY id LIMIT 1").fetchone()
        if admin is None:
            return False
    set_password(db_path, admin["username"], new_password)
    with _connect(db_path) as conn:
        conn.execute("DELETE FROM meta WHERE key = 'admin_recovery'")
    return True


def is_admin_user(db_path: Path | str, username: str) -> bool:
    """Tell whether ``username`` belongs to an admin (for recovery gating)."""
    if not (username or "").strip():
        return False
    init_db(db_path)
    with _connect(db_path) as conn:
        row = conn.execute("SELECT role FROM users WHERE username = ?",
                           (username.strip(),)).fetchone()
    return row is not None and row["role"] == "admin"


def update_profile(db_path: Path | str, username: str, name: str, org: str) -> None:
    if not (name or "").strip():
        raise ValueError("name must be non-empty")
    init_db(db_path)
    with _connect(db_path) as conn:
        cursor = conn.execute("UPDATE users SET name = ?, org = ? WHERE username = ?",
                              (name.strip(), (org or "").strip(), username))
        if cursor.rowcount == 0:
            raise ValueError(f"unknown username {username!r}")
