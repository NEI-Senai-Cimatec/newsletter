# tests/test_database.py
from core import database


def test_bootstrap_then_login(tmp_path):
    db = tmp_path / "users.db"
    code = database.bootstrap_admin(db, "Mabel Mota", "mabel.mota", "s3nha-forte")
    assert isinstance(code, str) and len(code) >= 12
    user = database.authenticate(db, "mabel.mota", "s3nha-forte")
    assert user is not None and user["role"] == "admin" and user["status"] == "ativo"


def test_wrong_password_returns_none(tmp_path):
    db = tmp_path / "users.db"
    database.bootstrap_admin(db, "Admin", "admin", "correta")
    assert database.authenticate(db, "admin", "errada") is None


def test_signup_pending_then_approve_then_revoke(tmp_path):
    db = tmp_path / "users.db"
    database.bootstrap_admin(db, "Admin", "admin", "pw-admin")
    database.create_user(db, "novo", "Novo Usuário", "QuIIN", True,
                         "basico", "pw-novo", created_by="admin", status="pendente")
    assert database.authenticate(db, "novo", "pw-novo")["status"] == "pendente"
    database.set_status(db, "novo", "ativo")
    database.set_password(db, "novo", "nova-senha")
    assert database.authenticate(db, "novo", "nova-senha")["status"] == "ativo"
    database.set_status(db, "novo", "revogado")
    assert database.authenticate(db, "novo", "nova-senha")["status"] == "revogado"


def test_recovery_code_resets_admin(tmp_path):
    db = tmp_path / "users.db"
    code = database.bootstrap_admin(db, "Admin", "admin", "antiga")
    assert database.reset_admin_via_recovery_code(db, "codigo-errado", "x") is False
    assert database.reset_admin_via_recovery_code(db, code, "nova") is True
    assert database.authenticate(db, "admin", "nova") is not None
