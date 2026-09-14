# QuIIN Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the existing CustomTkinter desktop GUI into the QuIIN product (auth, dashboard analytics, newsletter exports, accounts) with zero pipeline regression.

**Architecture:** Pure-function core layer (`core/scoring, repository, database, permissions, exports, audit`) built first with pytest coverage; thin GUI frames on top that call core from worker threads and render via `after()`, following the existing `scraper_frame`/`settings_frame` patterns.

**Tech Stack:** Python 3.10+ (verified on 3.14.3 in `.venv`), CustomTkinter 6.0.0, matplotlib, reportlab, python-docx, sqlite3 (stdlib), keyring, pytest + coverage.

**Spec:** `docs/superpowers/specs/2026-09-14-quiin-design.md`

## Global Constraints

- All Python/pytest/pip commands use `.venv/Scripts/python` (system Python lacks deps). Example: `.venv/Scripts/python -m pytest tests -q`.
- Never rewrite `core/utils.py`, `scrapers/*`, `core/task_runner.py` beyond the strictly necessary; any touch needs a written justification.
- New persistence only in `~/.newsletter_tool/` (`users.db`, `weights.json`, `audit.log`) or a user-chosen export folder. Nothing in Program Files. No admin rights required.
- No network, heavy disk I/O, or export on the Tk main thread — worker thread + `after()`.
- UI 100% pt-BR; institutional strings exactly as in the spec section 10.
- On conflict with constraints or the existing pytest suite: stop, describe, propose an alternative. Do not improvise.
- Commits per task with conventional messages (`feat:`, `test:`, `docs:`).
- Weights default `{"negocios": 35, "mercado": 35, "cientifica": 15, "tecnologica": 15}`; sums must equal 100.

---

## File Structure

New files and their single responsibility:

- `core/scoring.py` — pure multicriteria math: `indicators`, `relevance`, `area_of`, `validate_weights`, `load_weights`/`save_weights`. No I/O except the weights JSON helpers. No GUI imports.
- `core/repository.py` — pure document queries over `documents-data.json` lists: load, search, monthly stats, area share, top countries, sort, manual-news factory. No GUI imports.
- `core/database.py` — SQLite user store in `~/.newsletter_tool/users.db` (stdlib `sqlite3` + `hashlib.pbkdf2_hmac`). No GUI imports.
- `core/permissions.py` — role matrix `CAN` + `can(role, capability)`. No I/O, no GUI imports.
- `core/audit.py` — JSON-lines append to `~/.newsletter_tool/audit.log`. No GUI imports.
- `core/exports.py` — newsletter intermediate structure + PDF/WORD/print/share writers. No Tk calls (clipboard handled by caller).
- `gui/frames/login_frame.py` — `LoginFrame`: user/password, Sign Up, password recovery, first-run admin bootstrap wizard.
- `gui/frames/dashboard_frame.py` — `DashboardFrame`: cards, 2 matplotlib charts, advanced-stats checkboxes, top-5 countries, sortable table, weights editor, newsletter buttons, Print/Share.
- `gui/frames/documents_frame.py` — `DocumentsFrame`: paginated list, detail panel with per-indicator contribution, manual-news modal, per-document PDF/WORD.
- `gui/frames/accounts_frame.py` — `AccountsFrame` (admin only): user table, provision/approve/revoke/reset actions.
- Modified: `gui/app.py` (Session, QuIIN header, hybrid sidebar, global search, Log Out), `gui/frames/settings_frame.py` (keep AI block intact; add Perfil/Pesos/Sobre), `gui/theme/colors.py` (QuIIN palette + title), `requirements.txt`, `requirements-dev.txt`.
- Tests: `tests/test_scoring.py`, `tests/test_repository.py`, `tests/test_database.py`, `tests/test_permissions.py`, `tests/test_exports.py`.

---

### Task 1: FASE 0 — Baseline verde + novas dependências

**Files:**
- Modify: `requirements.txt`, `requirements-dev.txt`

**Interfaces:**
- Consumes: nothing.
- Produces: `.venv` with `matplotlib`, `reportlab`, `python-docx`, `coverage` installed; full suite green.

- [ ] **Step 1: Run the baseline suite**

Run: `.venv/Scripts/python -m pytest tests -q`
Expected: `47 passed` (proves the starting point before any change).

- [ ] **Step 2: Append new runtime dependencies**

In `requirements.txt`, append exactly:

```
# GUI QuIIN: gráficos e exportações
matplotlib
reportlab
python-docx
```

- [ ] **Step 3: Append coverage to dev dependencies**

In `requirements-dev.txt`, append exactly:

```
coverage
```

- [ ] **Step 4: Install new dependencies into .venv**

Run: `.venv/Scripts/python -m pip install matplotlib reportlab python-docx coverage`
Expected: all four install successfully, no errors.

- [ ] **Step 5: Re-run the full suite**

Run: `.venv/Scripts/python -m pytest tests -q`
Expected: `47 passed` (new libs must not break the pipeline suite).

- [ ] **Step 6: Commit**

```bash
git add requirements.txt requirements-dev.txt
git commit -m "feat: add QuIIN GUI deps (matplotlib, reportlab, python-docx, coverage)"
```

---

### Task 2: `core/scoring.py` + tests (funções puras)

**Files:**
- Create: `core/scoring.py`
- Test: `tests/test_scoring.py`

**Interfaces:**
- Consumes: document dicts from `documents-data.json` (keys `classification_weight`, `financial_activity`, `event`, `breakthrough`).
- Produces: `clip01(x: float) -> float`; `indicators(doc: dict) -> dict[str, float]`; `relevance(doc: dict, weights: dict[str, int]) -> int`; `area_of(doc: dict) -> str` (one of `"Negócio/Economia"`, `"Tecnológico"`, `"Científico"`, `"Outros"`); `validate_weights(weights: dict[str, int]) -> bool` (returns `True`, raises `ValueError` otherwise); `load_weights(path=WEIGHTS_FILE) -> dict[str, int]`; `save_weights(weights, path=WEIGHTS_FILE) -> None`; constants `INDICADORES`, `LABELS`, `DEFAULT_WEIGHTS`, `WEIGHTS_FILE`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scoring.py
from core.scoring import (
    DEFAULT_WEIGHTS, area_of, indicators, relevance, validate_weights,
)

FULL_DOC = {
    "classification_weight": {"Business": 35, "Technological": 35, "Scientific": 15, "Others": 0},
    "financial_activity": [{"description": "x" * 200, "currency": "Real Brasileiro (BRL), Brasil"}],
    "event": [{"name": "E", "location": "São Paulo, Brasil", "type": "Evento", "description": "y" * 200}],
    "breakthrough": ["avanço relevante"],
}

def test_full_doc_scores_100_with_default_weights():
    assert relevance(FULL_DOC, DEFAULT_WEIGHTS) == 100

def test_missing_weights_yield_zero():
    doc = {}
    assert indicators(doc) == {"negocios": 0.0, "mercado": 0.0, "cientifica": 0.0, "tecnologica": 0.0}
    assert relevance(doc, DEFAULT_WEIGHTS) == 0

def test_default_weights_validate():
    assert validate_weights(DEFAULT_WEIGHTS) is True

def test_area_tiebreak_prefers_business():
    doc = {"classification_weight": {"Business": 20, "Technological": 20, "Scientific": 0, "Others": 0}}
    assert area_of(doc) == "Negócio/Economia"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_scoring.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.scoring'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/scoring.py
"""Pure multicriteria relevance scoring (no I/O except weights helpers)."""
from __future__ import annotations

import json
from pathlib import Path

INDICADORES: tuple[str, ...] = ("negocios", "mercado", "cientifica", "tecnologica")

LABELS: dict[str, str] = {
    "negocios": "Relevância para negócios (Investimentos)",
    "mercado": "Impacto no mercado (Casos de uso)",
    "cientifica": "Produção científica",
    "tecnologica": "Produção tecnológica",
}

DEFAULT_WEIGHTS: dict[str, int] = {"negocios": 35, "mercado": 35, "cientifica": 15, "tecnologica": 15}

WEIGHTS_FILE: Path = Path.home() / ".newsletter_tool" / "weights.json"

AREAS_PTBR = ("Negócio/Economia", "Tecnológico", "Científico", "Outros")


def clip01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def indicators(doc: dict) -> dict[str, float]:
    cw = doc.get("classification_weight") or {}
    fin = doc.get("financial_activity") or []
    events = doc.get("event") or []
    breakthroughs = doc.get("breakthrough") or []
    return {
        "negocios": clip01((cw.get("Business", 0)) / 35),
        "mercado": clip01(min(1.0, (len(fin) + len(events) + len(breakthroughs)) / 3)),
        "cientifica": clip01((cw.get("Scientific", 0)) / 15),
        "tecnologica": clip01((cw.get("Technological", 0)) / 35),
    }


def validate_weights(weights: dict[str, int]) -> bool:
    if set(weights) != set(INDICADORES):
        raise ValueError(f"Weights must have exactly {INDICADORES}")
    for key, value in weights.items():
        if not isinstance(value, int) or not 0 <= value <= 100:
            raise ValueError(f"Weight {key!r} must be an int in 0..100")
    if sum(weights.values()) != 100:
        raise ValueError(f"Weights must sum to 100, got {sum(weights.values())}")
    return True


def relevance(doc: dict, weights: dict[str, int]) -> int:
    validate_weights(weights)
    inds = indicators(doc)
    return int(round(100 * sum((weights[k] / 100) * inds[k] for k in INDICADORES)))


def area_of(doc: dict) -> str:
    cw = doc.get("classification_weight") or {}
    ranked = [
        ("Negócio/Economia", cw.get("Business", 0)),
        ("Tecnológico", cw.get("Technological", 0)),
        ("Científico", cw.get("Scientific", 0)),
        ("Outros", cw.get("Others", 0)),
    ]
    best_value = max(value for _, value in ranked)
    for label, value in ranked:
        if value == best_value:
            return label
    return "Outros"


def load_weights(path: Path | str = WEIGHTS_FILE) -> dict[str, int]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        validate_weights(data)
        return dict(data)
    except (FileNotFoundError, ValueError):
        return dict(DEFAULT_WEIGHTS)


def save_weights(weights: dict[str, int], path: Path | str = WEIGHTS_FILE) -> None:
    validate_weights(weights)
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "w", encoding="utf-8") as f:
        json.dump(weights, f, indent=2, ensure_ascii=False)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_scoring.py -q`
Expected: `4 passed`.

- [ ] **Step 5: Add boundary tests (invalid weights, partial doc, reproducibility)**

```python
import pytest

from core.scoring import DEFAULT_WEIGHTS, relevance, validate_weights


def test_weights_sum_not_100_rejected():
    with pytest.raises(ValueError):
        validate_weights({"negocios": 35, "mercado": 35, "cientifica": 15, "tecnologica": 14})


def test_partial_doc_proportional():
    doc = {"classification_weight": {"Business": 17, "Technological": 0, "Scientific": 0, "Others": 0}}
    assert relevance(doc, DEFAULT_WEIGHTS) == round(100 * 0.35 * (17 / 35))


def test_scoring_reproducible_three_runs():
    doc = {"classification_weight": {"Business": 18, "Technological": 32, "Scientific": 7, "Others": 13},
           "event": [], "breakthrough": ["b1", "b2"], "financial_activity": []}
    assert relevance(doc, DEFAULT_WEIGHTS) == relevance(doc, DEFAULT_WEIGHTS) == relevance(doc, dict(DEFAULT_WEIGHTS))
```

- [ ] **Step 6: Run full suite**

Run: `.venv/Scripts/python -m pytest tests -q`
Expected: all pass (`47 + new`).

- [ ] **Step 7: Commit**

```bash
git add core/scoring.py tests/test_scoring.py
git commit -m "feat: add pure multicriteria scoring with tests"
```

---

### Task 3: `core/repository.py` + tests (funções puras)

**Files:**
- Create: `core/repository.py`
- Test: `tests/test_repository.py`

**Interfaces:**
- Consumes: `core/scoring.py` (`area_of`, `relevance`).
- Produces: `ISO3_PTBR: dict[str, str]` (60+ codes); `load_documents(path: str | Path) -> list[dict]`; `search(docs: list[dict], query: str) -> list[dict]`; `stats_monthly(docs, areas: list[str]) -> dict[str, dict[str, int]]`; `stats_area_share(docs) -> dict[str, float]` (sums to 100.0); `stats_countries(docs, top: int = 5) -> list[tuple[str, int]]`; `sort_documents(docs, key: str, desc: bool = True) -> list[dict]` with key in `("date", "area", "relevance")`; `add_manual_news(fields: dict) -> dict`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_repository.py
from core.repository import add_manual_news, search, sort_documents, stats_area_share


def _doc(title, business, date="2026-09-01"):
    return {"title": title, "summary": "", "key_points": [],
            "organization": [], "event": [],
            "classification_weight": {"Business": business, "Technological": 0, "Scientific": 0, "Others": 0},
            "date": date, "published": date, "related_country": []}


def test_search_case_insensitive():
    docs = [_doc("Quantum startup raises $30M", 20), _doc("Photonic sensors", 5)]
    assert [d["title"] for d in search(docs, "QUANTUM")] == ["Quantum startup raises $30M"]


def test_area_share_sums_100():
    share = stats_area_share([_doc("a", 35), _doc("b", 0)])
    assert abs(sum(share.values()) - 100.0) < 1e-6


def test_manual_news_is_compatible():
    record = add_manual_news({"url": "https://exemplo.test/n1", "title": "N1",
                              "area": "Negócio/Economia", "date": "2026-09-14", "summary": "Resumo."})
    assert record["source"] == "Manual"
    assert len(record["hash"]) == 64
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_repository.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.repository'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/repository.py
"""Pure document queries over lists of documents-data.json records."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

from core.scoring import DEFAULT_WEIGHTS, area_of, relevance

AREAS = ("Negócio/Economia", "Tecnológico", "Científico", "Outros")

ISO3_PTBR: dict[str, str] = {
    "USA": "Estados Unidos", "BRA": "Brasil", "CHN": "China", "JPN": "Japão",
    "DEU": "Alemanha", "FRA": "França", "GBR": "Reino Unido", "CAN": "Canadá",
    "CHE": "Suíça", "NLD": "Países Baixos", "SWE": "Suécia", "FIN": "Finlândia",
    "DNK": "Dinamarca", "NOR": "Noruega", "IRL": "Irlanda", "AUT": "Áustria",
    "BEL": "Bélgica", "ESP": "Espanha", "ITA": "Itália", "PRT": "Portugal",
    "POL": "Polônia", "CZE": "Chéquia", "HUN": "Hungria", "GRC": "Grécia",
    "IND": "Índia", "KOR": "Coreia do Sul", "TWN": "Taiwan", "SGP": "Singapura",
    "AUS": "Austrália", "NZL": "Nova Zelândia", "ISR": "Israel", "ARE": "Emirados Árabes Unidos",
    "SAU": "Arábia Saudita", "QAT": "Catar", "TUR": "Turquia", "ZAF": "África do Sul",
    "MEX": "México", "ARG": "Argentina", "CHL": "Chile", "COL": "Colômbia",
    "RUS": "Rússia", "UKR": "Ucrânia", "EGY": "Egito", "NGA": "Nigéria",
    "KEN": "Quênia", "MYS": "Malásia", "THA": "Tailândia", "VNM": "Vietnã",
    "IDN": "Indonésia", "PHL": "Filipinas", "PAK": "Paquistão", "BGD": "Bangladesh",
    "LUX": "Luxemburgo", "ISL": "Islândia", "EST": "Estônia", "LVA": "Letônia",
    "LTU": "Lituânia", "SVN": "Eslovênia", "SVK": "Eslováquia", "ROU": "Romênia",
    "BGR": "Bulgária", "HRV": "Croácia", "URY": "Uruguai", "PER": "Peru",
}


def load_documents(path: str | Path) -> list[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _haystack(doc: dict) -> str:
    parts = [doc.get("title", ""), doc.get("summary", "")]
    parts.extend(doc.get("key_points") or [])
    for org in doc.get("organization") or []:
        parts.append((org or {}).get("name", ""))
    for event in doc.get("event") or []:
        parts.append((event or {}).get("name", ""))
    return "\n".join(parts).casefold()


def search(docs: list[dict], query: str) -> list[dict]:
    needle = (query or "").strip().casefold()
    if not needle:
        return list(docs)
    return [d for d in docs if needle in _haystack(d)]


def _month_key(doc: dict) -> str | None:
    for field in ("date", "published", "modified"):
        raw = (doc.get(field) or "")[:7]
        if len(raw) == 7 and raw[4] == "-":
            return raw
    return None


def stats_monthly(docs: list[dict], areas: list[str]) -> dict[str, dict[str, int]]:
    table: dict[str, dict[str, int]] = {}
    for doc in docs:
        month = _month_key(doc)
        if month is None:
            continue
        table.setdefault(month, {a: 0 for a in areas})
        table[month][area_of(doc)] += 1
    recent = sorted(table)[-6:]
    return {month: table[month] for month in recent}


def stats_area_share(docs: list[dict]) -> dict[str, float]:
    counts = Counter(area_of(d) for d in docs)
    total = sum(counts.values())
    if total == 0:
        return {a: 0.0 for a in AREAS}
    return {a: round(100.0 * counts.get(a, 0) / total, 1) for a in AREAS}


def stats_countries(docs: list[dict], top: int = 5) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for doc in docs:
        for code in doc.get("related_country") or []:
            counts[code] += 1
    return [(ISO3_PTBR.get(code, code), n) for code, n in counts.most_common(top)]


def _sort_value(doc: dict, key: str, weights: dict) -> tuple:
    if key == "relevance":
        return (relevance(doc, weights),)
    if key == "area":
        return (area_of(doc),)
    return (doc.get("date") or doc.get("published") or "",)


def sort_documents(docs: list[dict], key: str, desc: bool = True,
                   weights: dict | None = None) -> list[dict]:
    if key not in ("date", "area", "relevance"):
        raise ValueError(f"sort key must be date/area/relevance, got {key!r}")
    active = weights or DEFAULT_WEIGHTS
    return sorted(docs, key=lambda d: _sort_value(d, key, active), reverse=desc)


AREA_TO_WEIGHT = {
    "Negócio/Economia": {"Business": 35, "Technological": 0, "Scientific": 0, "Others": 0},
    "Tecnológico": {"Business": 0, "Technological": 35, "Scientific": 0, "Others": 0},
    "Científico": {"Business": 0, "Technological": 0, "Scientific": 15, "Others": 0},
    "Outros": {"Business": 0, "Technological": 0, "Scientific": 0, "Others": 15},
}


def add_manual_news(fields: dict) -> dict:
    url = fields.get("url", "") or fields.get("title", "")
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return {
        "url": fields.get("url", ""),
        "title": fields.get("title", ""),
        "category": ["Manual"],
        "author": "",
        "date": fields.get("date", datetime.now().strftime("%Y-%m-%d")),
        "published": fields.get("date", ""),
        "modified": "",
        "timestamp": datetime.now().isoformat(),
        "keywords": [],
        "hash": digest,
        "source": "Manual",
        "newsletter": fields.get("title", ""),
        "summary": fields.get("summary", ""),
        "overview": fields.get("summary", ""),
        "key_points": [],
        "classification_weight": dict(AREA_TO_WEIGHT.get(fields.get("area", "Outros"),
                                                         AREA_TO_WEIGHT["Outros"])),
        "organization": [],
        "event": [],
        "breakthrough": [],
        "financial_activity": [],
        "related_country": [],
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_repository.py -q`
Expected: `3 passed`.

- [ ] **Step 5: Add country-fallback and sort tests**

```python
from core.repository import sort_documents, stats_countries


def test_unknown_country_code_falls_back_to_code():
    docs = [{"related_country": ["XX1"]}]
    assert stats_countries(docs) == [("XX1", 1)]


def test_sort_by_relevance_desc():
    def _doc(title, business):
        return {"title": title, "summary": "", "key_points": [], "organization": [],
                "event": [], "date": "2026-09-01",
                "classification_weight": {"Business": business, "Technological": 0,
                                          "Scientific": 0, "Others": 0}}
    ordered = sort_documents([_doc("low", 5), _doc("high", 35)], key="relevance", desc=True)
    assert [d["title"] for d in ordered] == ["high", "low"]
```

- [ ] **Step 6: Run full suite**

Run: `.venv/Scripts/python -m pytest tests -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add core/repository.py tests/test_repository.py
git commit -m "feat: add pure document repository with tests"
```

---

### Task 4: `core/database.py` + tests (SQLite user-space)

**Files:**
- Create: `core/database.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Consumes: stdlib `sqlite3`, `hashlib`, `os`, `secrets`.
- Produces: `DB_FILE: Path`; `init_db(db_path=DB_FILE) -> None`; `create_user(db_path, username, name, org, internal, role, password, created_by="system") -> int` (raises `ValueError` on duplicate/role); `authenticate(db_path, username, password) -> dict | None` (dict includes `status`; `None` only on bad credentials); `set_status(db_path, username, status) -> None`; `set_password(db_path, username, new_password) -> None`; `list_users(db_path) -> list[dict]`; `bootstrap_admin(db_path, name, username, password) -> str` (recovery code, single display); `reset_admin_via_recovery_code(db_path, code, new_password) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_database.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.database'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/database.py
"""SQLite user store in user-space (stdlib only)."""
from __future__ import annotations

import hashlib
import os
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
    if _hash(password, user["salt"]) != user["password_hash"]:
        return None
    return user


def set_status(db_path: Path | str, username: str, status: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}")
    with _connect(db_path) as conn:
        cursor = conn.execute("UPDATE users SET status = ? WHERE username = ?",
                              (status, username))
        if cursor.rowcount == 0:
            raise ValueError(f"unknown username {username!r}")


def set_password(db_path: Path | str, username: str, new_password: str) -> None:
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
        if row is None or row["value"] != code_hash:
            return False
        admin = conn.execute("SELECT username FROM users WHERE role = 'admin'"
                             " ORDER BY id LIMIT 1").fetchone()
        if admin is None:
            return False
    set_password(db_path, admin["username"], new_password)
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_database.py -q`
Expected: `2 passed`.

- [ ] **Step 5: Add pending-approve-revoke-reset tests**

```python
from core import database


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
```

- [ ] **Step 6: Run full suite**

Run: `.venv/Scripts/python -m pytest tests -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add core/database.py tests/test_database.py
git commit -m "feat: add SQLite user store with bootstrap and recovery"
```

---

### Task 5: `core/permissions.py` + `core/audit.py` + tests

**Files:**
- Create: `core/permissions.py`, `core/audit.py`
- Test: `tests/test_permissions.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `CAPABILITIES: tuple[str, ...]`; `CAN: dict[str, set[str]]`; `can(role: str, capability: str) -> bool`; `AUDIT_FILE: Path`; `log_event(user: str, action: str, detail: str = "", log_path=None) -> dict` (record with `ts`, `user`, `action`, `detail`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_permissions.py
import json

from core.audit import log_event
from core.permissions import can


def test_basic_cannot_export_but_admin_can():
    assert can("basico", "view") is True
    assert can("basico", "export") is False
    assert can("premium", "export") is True
    assert can("admin", "manage_accounts") is True
    assert can("premium", "manage_accounts") is False


def test_audit_appends_json_line(tmp_path):
    log = tmp_path / "audit.log"
    record = log_event("admin", "edit_weights", "35/35/15/15", log_path=log)
    assert record["user"] == "admin"
    assert json.loads(log.read_text(encoding="utf-8").strip())["action"] == "edit_weights"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_permissions.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.permissions'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/permissions.py
"""Role matrix: basico views, premium exports, admin manages."""
from __future__ import annotations

VIEWER = {"basico", "premium", "admin"}
EXPORTER = {"premium", "admin"}
ADMIN = {"admin"}

CAN: dict[str, set[str]] = {
    "view": set(VIEWER),
    "search": set(VIEWER),
    "export": set(EXPORTER),
    "print": set(EXPORTER),
    "share": set(EXPORTER),
    "generate_newsletter": set(EXPORTER),
    "add_news": set(ADMIN),
    "edit_weights": set(ADMIN),
    "manage_accounts": set(ADMIN),
    "configure_ai": set(ADMIN),
    "run_pipeline": set(ADMIN),
}

CAPABILITIES: tuple[str, ...] = tuple(CAN)


def can(role: str, capability: str) -> bool:
    return role in CAN.get(capability, set())
```

```python
# core/audit.py
"""Local JSON-lines audit log in user-space."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

AUDIT_FILE: Path = Path.home() / ".newsletter_tool" / "audit.log"


def log_event(user: str, action: str, detail: str = "",
              log_path: Path | str | None = None) -> dict:
    record = {"ts": datetime.now(timezone.utc).isoformat(),
              "user": user, "action": action, "detail": detail}
    target = Path(log_path) if log_path is not None else AUDIT_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    return record
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_permissions.py -q`
Expected: `2 passed`.

- [ ] **Step 5: Run full suite**

Run: `.venv/Scripts/python -m pytest tests -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add core/permissions.py core/audit.py tests/test_permissions.py
git commit -m "feat: add role matrix and audit log with tests"
```

---

### Task 6: `core/exports.py` + tests (PDF/WORD/print/share)

**Files:**
- Create: `core/exports.py`
- Test: `tests/test_exports.py`

**Interfaces:**
- Consumes: `core/scoring.py` (`area_of`, `relevance`).
- Produces: `build_newsletter(docs: list[dict], weights: dict, mode: str, meta: dict) -> dict` (keys `title`, `generated_at`, `mode`, `weights`, `sections`); `export_pdf(structure: dict, path) -> str`; `export_word(structure: dict, path) -> str`; `print_pdf(path) -> str` (`"printed"` or `"opened"`); `share_package(structure: dict, dir) -> str` (returns the `.md` path; also copies it to the clipboard only when called from the GUI layer).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_exports.py
from core.exports import build_newsletter, export_pdf, export_word, share_package
from core.scoring import DEFAULT_WEIGHTS


def _doc():
    return {"title": "T", "newsletter": "N", "summary": "Resumo.",
            "key_points": ["p1"], "organization": [], "event": [],
            "breakthrough": [], "financial_activity": [], "related_country": ["USA"],
            "classification_weight": {"Business": 35, "Technological": 0,
                                      "Scientific": 0, "Others": 0}}


def test_build_newsletter_orders_by_relevance():
    low = _doc()
    high = dict(_doc(), summary="Resumo relevante.")
    structure = build_newsletter([low, high], DEFAULT_WEIGHTS, "automatico", {})
    assert structure["mode"] == "automatico"
    assert len(structure["sections"]) == 2


def test_pdf_and_word_magic_bytes(tmp_path):
    structure = build_newsletter([_doc()], DEFAULT_WEIGHTS, "automatico", {"title": "Q"})
    pdf = export_pdf(structure, tmp_path / "n.pdf")
    assert open(pdf, "rb").read(4) == b"%PDF"
    docx = export_word(structure, tmp_path / "n.docx")
    assert open(docx, "rb").read(2) == b"PK"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/Scripts/python -m pytest tests/test_exports.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'core.exports'`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/exports.py
"""Newsletter intermediate structure plus PDF/WORD/print/share writers."""
from __future__ import annotations

import os
import subprocess
import platform
import webbrowser
from datetime import datetime, timezone
from pathlib import Path

from core.scoring import area_of, relevance

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
except ImportError:  # pragma: no cover - import error surfaces in Task 1 install
    A4 = None

try:
    from docx import Document
except ImportError:  # pragma: no cover
    Document = None


def build_newsletter(docs: list[dict], weights: dict, mode: str, meta: dict) -> dict:
    ranked = sorted(docs, key=lambda d: relevance(d, weights), reverse=True)
    sections = [{
        "title": d.get("newsletter") or d.get("title", ""),
        "summary": d.get("summary", ""),
        "key_points": list(d.get("key_points") or []),
        "area": area_of(d),
        "relevance": relevance(d, weights),
        "organizations": [o.get("name", "") for o in d.get("organization") or []],
        "countries": list(d.get("related_country") or []),
        "url": d.get("url", ""),
    } for d in ranked]
    return {"title": meta.get("title", "GLOBAL QUANTUM INTELLIGENCE – QuIIN"),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "mode": mode, "weights": dict(weights), "sections": sections}


def export_pdf(structure: dict, path: Path | str) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    story = [Paragraph(structure["title"], styles["Title"]), Spacer(1, 12)]
    for section in structure["sections"]:
        story.append(Paragraph(f"{section['title']} — {section['area']}"
                               f" ({section['relevance']})", styles["Heading2"]))
        story.append(Paragraph(section["summary"], styles["BodyText"]))
        for point in section["key_points"]:
            story.append(Paragraph(f"• {point}", styles["BodyText"]))
        story.append(Spacer(1, 12))
    SimpleDocTemplate(str(target), pagesize=A4).build(story)
    return str(target)


def export_word(structure: dict, path: Path | str) -> str:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    document = Document()
    document.add_heading(structure["title"], level=0)
    for section in structure["sections"]:
        document.add_heading(f"{section['title']} — {section['area']}"
                             f" ({section['relevance']})", level=1)
        document.add_paragraph(section["summary"])
        for point in section["key_points"]:
            document.add_paragraph(point, style="List Bullet")
    document.save(str(target))
    return str(target)


def print_pdf(path: Path | str) -> str:
    if platform.system() == "Windows":
        try:
            os.startfile(str(path), "print")  # noqa: S606
            return "printed"
        except OSError:
            pass
    webbrowser.open(str(path))
    return "opened"


def share_package(structure: dict, dir: Path | str) -> str:
    target_dir = Path(dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"# {structure['title']}", ""]
    for section in structure["sections"]:
        lines.append(f"## {section['title']} — {section['area']} ({section['relevance']})")
        lines.append("")
        lines.append(section["summary"])
        lines.append("")
        lines.extend(f"- {point}" for point in section["key_points"])
        lines.append("")
    md_path = target_dir / "newsletter.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    try:
        if platform.system() == "Windows":
            os.startfile(str(target_dir))  # noqa: S606
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(target_dir)])
        else:
            subprocess.Popen(["xdg-open", str(target_dir)])
    except (OSError, subprocess.SubprocessError):
        pass
    return str(md_path)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/Scripts/python -m pytest tests/test_exports.py -q`
Expected: pass (reportlab/python-docx installed in Task 1).

- [ ] **Step 5: Run coverage over the new core modules (RNF-07 ≥80%)**

Run: `.venv/Scripts/python -m coverage run -m pytest tests/test_scoring.py tests/test_repository.py tests/test_database.py tests/test_permissions.py tests/test_exports.py -q; if ($?) { .venv/Scripts/python -m coverage report --include="core/scoring.py,core/repository.py,core/database.py,core/permissions.py,core/audit.py,core/exports.py" }`
Expected: each file ≥80%; full suite still green via `.venv/Scripts/python -m pytest tests -q`.

- [ ] **Step 6: Commit**

```bash
git add core/exports.py tests/test_exports.py
git commit -m "feat: add newsletter exports (PDF, WORD, print, share)"
```

---

### Task 7: FASE 2 — Login, bootstrap, sessão e shell QuIIN

**Files:**
- Create: `gui/frames/login_frame.py`
- Modify: `gui/app.py`, `gui/components/sidebar.py`, `gui/theme/colors.py`

**Interfaces:**
- Consumes: `core/database.py` (`init_db`, `bootstrap_admin`, `authenticate`, `create_user`, `reset_admin_via_recovery_code`), `core/repository.py` (`search`), `core/permissions.py` (`can`).
- Produces: `LoginFrame(master, app)` with `on_show`; `App.session: dict | None`; hybrid sidebar items `dashboard, documents, scraper, results, logs, accounts, settings`; header with `GLOBAL QUANTUM INTELLIGENCE`, welcome/org/ID, live search entry, `Log Out`.

- [ ] **Step 1: Rebrand theme constants**

In `gui/theme/colors.py` set `APP_TITLE = "GLOBAL QUANTUM INTELLIGENCE – QuIIN"` and add `QUIIN_PRIMARY = "#1F4E79"`, `QUIIN_LIGHT = "#2E75B6"`, `QUIIN_ACCENT = "#9DC3E6"`, `QUIIN_BG = "#101418"`. Keep all existing font/size constants untouched.

- [ ] **Step 2: Create `LoginFrame`**

```python
# gui/frames/login_frame.py
import customtkinter as ctk

from core import database
from core.database import DB_FILE


class LoginFrame(ctk.CTkFrame):
    """Auth gate: login, Sign Up (basico/pendente), recovery, admin bootstrap."""

    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color="transparent")
        self.app = app
        ctk.CTkLabel(self, text="GLOBAL QUANTUM INTELLIGENCE",
                     font=ctk.CTkFont(size=22, weight="bold")).pack(pady=(32, 4))
        ctk.CTkLabel(self, text="Centro de Competências EMBRAPII CIMATEC em Tecnologias Quânticas").pack()
        ctk.CTkLabel(self, text="Quantum Industrial Innovation – QuIIN Associação Tecnológica").pack(pady=(0, 24))
        self.user_entry = ctk.CTkEntry(self, width=280, placeholder_text="Usuário")
        self.user_entry.pack(pady=6)
        self.pass_entry = ctk.CTkEntry(self, width=280, placeholder_text="Password", show="*")
        self.pass_entry.pack(pady=6)
        ctk.CTkButton(self, text="Entrar", width=280, command=self._login).pack(pady=(12, 6))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(pady=6)
        ctk.CTkButton(row, text="Esqueci minha senha", width=136, fg_color="transparent",
                      command=self._recovery).pack(side="left", padx=4)
        ctk.CTkButton(row, text="Sign Up", width=136, fg_color="transparent",
                      command=self._signup).pack(side="left", padx=4)
        self.msg = ctk.CTkLabel(self, text="")
        self.msg.pack(pady=8)

    def on_show(self) -> None:
        database.init_db(DB_FILE)
        if not database.list_users(DB_FILE):
            self._bootstrap_wizard()

    def _fail(self, text: str) -> None:
        self.msg.configure(text=text)

    def _login(self) -> None:
        user = database.authenticate(DB_FILE, self.user_entry.get().strip(),
                                     self.pass_entry.get())
        if user is None:
            self._fail("Usuário ou senha inválidos.")
            return
        if user["status"] != "ativo":
            self._fail("Conta pendente ou revogada. Aguarde aprovação de um administrador.")
            return
        self.app.login(user)

    def _signup(self) -> None:
        try:
            database.create_user(DB_FILE, self.user_entry.get().strip(), self.user_entry.get().strip(),
                                 "QuIIN", True, "basico", self.pass_entry.get(),
                                 created_by="signup", status="pendente")
        except ValueError:
            self._fail("Nome de usuário já existe.")
            return
        self._fail("Conta criada. Aguarde aprovação de um administrador.")

    def _recovery(self) -> None:
        self._fail("Contate um administrador para redefinir sua senha.")

    def _bootstrap_wizard(self) -> None:
        dialog = ctk.CTkToplevel(self)
        dialog.title("Criar administrador inicial")
        dialog.geometry("420x360")
        name = ctk.CTkEntry(dialog, placeholder_text="Nome completo")
        name.pack(padx=20, pady=8, fill="x")
        username = ctk.CTkEntry(dialog, placeholder_text="Usuário")
        username.pack(padx=20, pady=8, fill="x")
        password = ctk.CTkEntry(dialog, placeholder_text="Senha", show="*")
        password.pack(padx=20, pady=8, fill="x")

        def _create() -> None:
            code = database.bootstrap_admin(DB_FILE, name.get().strip(),
                                            username.get().strip(), password.get())
            dialog.destroy()
            done = ctk.CTkToplevel(self)
            done.title("Guarde este código")
            done.geometry("460x200")
            ctk.CTkLabel(done, text="Código de recuperação (exibido uma única vez):").pack(padx=20, pady=8)
            ctk.CTkLabel(done, text=code, font=ctk.CTkFont(size=14, weight="bold")).pack(padx=20, pady=8)
            ctk.CTkLabel(done, text="Guarde em local seguro. Ele recupera o admin.").pack(padx=20, pady=8)

        ctk.CTkButton(dialog, text="Criar administrador", command=_create).pack(padx=20, pady=12)
```

- [ ] **Step 3: Rework `App` into session shell**

```python
# gui/app.py — session + hybrid sidebar (applied inside the existing App class)
from core.permissions import can
from gui.frames.login_frame import LoginFrame

HYBRID_NAV = [
    ("dashboard", "📊 Dashboard"),
    ("documents", "📄 Documentos"),
    ("scraper", "🚀 Execução"),
    ("results", "📊 Resultados"),
    ("logs", "🧾 Logs"),
    ("accounts", "👥 Contas"),
    ("settings", "⚙️ Configurações"),
]

def login(self, user: dict) -> None:
    self.session = user
    self._rebuild_frames()
    self.show_frame("dashboard")

def logout(self) -> None:
    self.session = None
    self._rebuild_frames()
    self.show_frame("login")

def _visible_nav(self) -> list[tuple[str, str]]:
    if self.session is not None and self.session.get("role") == "admin":
        return list(HYBRID_NAV)
    return [item for item in HYBRID_NAV if item[0] != "accounts"]
```

Header (added above the container): title label `GLOBAL QUANTUM INTELLIGENCE`, labels `Bem vindo, {name}` / `{org}` / `ID: {id}`, `CTkEntry(placeholder_text="Pesquise aqui")` whose key-release handler calls `repository.search(loaded_docs, text)` and forwards the filtered list to the dashboard + documents frames, and a `Log Out` button calling `logout()`. Export-capable buttons check `can(session["role"], capability)` and render disabled with a tooltip when `False`. The app starts on the `login` frame when `session is None`.

- [ ] **Step 4: Manual QA**

| Check | Esperado | Obtido | Status |
|---|---|---|---|
| Login errado | bloqueia com mensagem | | |
| Conta pendente | bloqueia com mensagem de aguardo | | |
| Admin vê Contas; básico não vê | conforme papel | | |
| Básico com export desabilitado | botões PDF/WORD/Print/Share desabilitados | | |
| Log Out | limpa sessão e volta ao login | | |
| Busca "quantum" | filtra dashboard + documentos ao digitar | | |

Run: `.venv/Scripts/python -m pytest tests -q` (Expected: all pass — GUI adds no regressions).

- [ ] **Step 5: Commit**

```bash
git add gui/frames/login_frame.py gui/app.py gui/components/sidebar.py gui/theme/colors.py
git commit -m "feat: add QuIIN auth shell with session and global search"
```

---

### Task 8: FASE 3 — Dashboard analítico

**Files:**
- Create: `gui/frames/dashboard_frame.py`

**Interfaces:**
- Consumes: `core/repository.py` (`load_documents`, `stats_monthly`, `stats_area_share`, `stats_countries`, `sort_documents`), `core/scoring.py` (`LABELS`, `load_weights`, `save_weights`, `validate_weights`), `core/permissions.py` (`can`), `core/exports.py` (`export_pdf`, `share_package`), `core/audit.py` (`log_event`), `DOCUMENTS_JSON` path from `core/utils.py`.
- Produces: `DashboardFrame(master, app)` with `on_show` refresh; charts computed in a worker thread, rendered via `after()`.

- [ ] **Step 1: Build cards + charts + panels**

Cards (concrete refresh logic, same source as `HomeFrame`):

```python
def _refresh_cards(self) -> None:
    docs = repository.load_documents(DOCUMENTS_JSON)
    self.card_values["docs"].configure(text=str(len(docs)))
    active = sum(1 for on in self.app.config.get("portals", {}).values() if on)
    self.card_values["portals"].configure(text=str(active))
    provider_key = self.app.config.get("provider", "groq")
    self.card_values["provider"].configure(
        text=PROVIDERS.get(provider_key, {}).get("name", provider_key))
```

Chart embedding (compute in worker, render via `after()` — never matplotlib on the main thread):

```python
import matplotlib
matplotlib.use("Agg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

def _render_bar(self, monthly: dict) -> None:
    figure = Figure(figsize=(5, 3), dpi=100)
    axes = figure.add_subplot(111)
    months = list(monthly)
    width = 0.2
    for i, area in enumerate(AREAS):
        axes.bar([x + i * width for x in range(len(months))],
                 [monthly[m][area] for m in months], width=width, label=area)
    axes.set_xticks([x + width * 1.5 for x in range(len(months))])
    axes.set_xticklabels(months, rotation=30, ha="right")
    axes.legend()
    canvas = FigureCanvasTkAgg(figure, master=self.bar_box)
    canvas.draw()
    canvas.get_tk_widget().pack(fill="both", expand=True)
```

Donut from `stats_area_share` (asserts `abs(sum - 100.0) < 0.6` after rounding). `Estatística avançada`: 4 `CTkCheckBox` labels from `LABELS`; unchecking zeroes that indicator's weight in the *view* (renormalize the rest) and refreshes table/charts. `Localização das notícias`: top-5 from `stats_countries`. Table `Data | Área | Relevância` with clickable headers cycling asc/desc via `sort_documents`. `Print`/`Share` gated by `can()`. `Índice de seleção multicritério`: 4 rows `{LABEL}: {peso}` + `Editar` (admin) → modal with 4 entries, `validate_weights`, `save_weights` + `log_event`. `Gerar Newsletter`: `Automático`/`Personalizado` buttons (Task 9 implements the flows; here they call into it).

- [ ] **Step 2: Manual QA**

| Check | Esperado | Obtido | Status |
|---|---|---|---|
| Donut soma | 100% | | |
| Ordenar alterna | asc→desc→asc por coluna | | |
| Peso soma≠100 | rejeitado com mensagem | | |
| Charts/pesos com 2k docs | sem congelar, render ≤2s | | |
| Básico sem export | Print/Share desabilitados | | |

Run: `.venv/Scripts/python -m pytest tests -q` (Expected: all pass).

- [ ] **Step 3: Commit**

```bash
git add gui/frames/dashboard_frame.py
git commit -m "feat: add QuIIN analytics dashboard"
```

---

### Task 9: FASE 4 — Newsletter Automático/Personalizado + PDF/WORD

**Files:**
- Modify: `gui/frames/dashboard_frame.py` (wire the two buttons), optionally create `gui/components/newsletter_dialog.py` for the manual pick-and-order modal.

**Interfaces:**
- Consumes: `core/exports.py` (`build_newsletter`, `export_pdf`, `export_word`), active filters (search query + indicator checkboxes + weights).
- Produces: Automático exports top-20 by relevance under active filters; Personalizado modal preserves the user-chosen order in the exported file.

- [ ] **Step 1: Implement Automático flow**

Take filtered docs, `build_newsletter(docs[:20], weights, "automatico", {"title": ...})`, ask save path via `filedialog`, run `export_pdf`/`export_word` in a worker thread, `log_event`.

- [ ] **Step 2: Implement Personalizado modal**

`CTkToplevel` with scrollable checkbox list of filtered docs in relevance order + up/down ordering; confirm → `build_newsletter` in the chosen order (`mode="personalizado"`) → same export path as Automático.

- [ ] **Step 3: Manual QA**

| Check | Esperado | Obtido | Status |
|---|---|---|---|
| PDF abre | magic `%PDF`, abre no leitor | | |
| WORD abre | magic `PK`, abre no Word/LibreOffice | | |
| Automático respeita filtros | só docs filtrados, top-20 relevância | | |
| Personalizado preserva ordem | ordem do modal == ordem no arquivo | | |

Run: `.venv/Scripts/python -m pytest tests -q` (Expected: all pass).

- [ ] **Step 4: Commit**

```bash
git add gui/frames/dashboard_frame.py gui/components/newsletter_dialog.py
git commit -m "feat: add automatic and custom newsletter exports"
```

---

### Task 10: FASE 5 — Documentos (lista, detalhe, manual)

**Files:**
- Create: `gui/frames/documents_frame.py`

**Interfaces:**
- Consumes: `core/repository.py` (`load_documents`, `search`, `add_manual_news`, `sort_documents`), `core/scoring.py` (`indicators`, `relevance`), `core/exports.py` (`build_newsletter`, `export_pdf`, `export_word`), `core/permissions.py` (`can`).
- Produces: `DocumentsFrame(master, app)` with 20-per-page list + `Mostrar mais documentos (+20)`; detail panel with `I_k` and `w_k·I_k` contribution rows plus organization/event/breakthrough/financial fields; `Adicionar Notícia` (admin) modal writing a `source="Manual"` record.

- [ ] **Step 1: Build list + detail + modals**

Pagination state and page rendering (concrete logic):

```python
PAGE_SIZE = 20

def _render_page(self) -> None:
    for child in self.list_box.winfo_children():
        child.destroy()
    page = self.filtered[: self.shown]
    for doc in page:
        title = doc.get("newsletter") or doc.get("title", "(sem título)")
        ctk.CTkButton(self.list_box, text=f"{doc.get('date', '')} · {title}",
                      anchor="w", fg_color="transparent",
                      command=lambda d=doc: self._show_detail(d)).pack(fill="x", padx=4, pady=1)
    self.more_button.configure(
        text=f"Mostrar mais documentos ({len(self.filtered) - self.shown} restantes)",
        state="normal" if self.shown < len(self.filtered) else "disabled")

def _show_more(self) -> None:
    self.shown += PAGE_SIZE
    self._render_page()
```

Columns `Data | Fonte | Área | Título | Relevância` (row text `"{date} | {source} | {area} | {title} | {relevance}"`); selection renders the detail panel; per-document `PDF`/`WORD` export the single selected doc via `build_newsletter([doc], ...)` in a worker thread.

- [ ] **Step 2: Manual QA**

| Check | Esperado | Obtido | Status |
|---|---|---|---|
| Mostrar mais | +20 itens por clique | | |
| Notícia manual | aparece com `source` Manual e score calculado | | |
| Detalhe | exibe `I_k` e `w_k·I_k` por indicador | | |

Run: `.venv/Scripts/python -m pytest tests -q` (Expected: all pass).

- [ ] **Step 3: Commit**

```bash
git add gui/frames/documents_frame.py
git commit -m "feat: add paginated documents screen with detail"
```

---

### Task 11: FASE 6 — Contas + Configurações + Sobre

**Files:**
- Create: `gui/frames/accounts_frame.py`
- Modify: `gui/frames/settings_frame.py`

**Interfaces:**
- Consumes: `core/database.py` (`list_users`, `create_user`, `set_status`, `set_password`), `core/audit.py` (`log_event`), `core/scoring.py` (`load_weights`, `save_weights`), `core/permissions.py` (`can`).
- Produces: `AccountsFrame` (admin only) + extended settings with `Perfil`, `Índice multicritério`, `Sobre / Registro do Software` sections.

- [ ] **Step 1: Build AccountsFrame**

```python
# gui/frames/accounts_frame.py — row action wiring (inside AccountsFrame)
from core import database
from core.audit import log_event
from core.database import DB_FILE

ROLE_LABELS = {"admin": "Administrador", "premium": "Premium", "basico": "Básico"}

def _approve(self, username: str) -> None:
    database.set_status(DB_FILE, username, "ativo")
    log_event(self.app.session["username"], "approve_user", username)
    self.on_show()

def _revoke(self, username: str) -> None:
    database.set_status(DB_FILE, username, "revogado")
    log_event(self.app.session["username"], "revoke_user", username)
    self.on_show()

def _reset_password(self, username: str, new_password: str) -> None:
    database.set_password(DB_FILE, username, new_password)
    log_event(self.app.session["username"], "reset_password", username)
    self.on_show()
```

Table `Nome | Username | Tipo | Organização | Interno/Externo | Status`; `Fornecer acesso` form (new user, password, radios `Administrador (edita, visualiza e imprime) / Premium (visualiza e imprime) / Básico (visualiza)`, requester = logged user read-only); row actions `Aprovar` (pending), `Cancelar acesso`, `Redefinir senha`; every action calls `log_event`.

- [ ] **Step 2: Extend settings without touching the AI block**

Keep every existing provider widget/method intact; add sections `Perfil` (name, org saved to `users.db` for the current user), `Índice multicritério` (same editor as dashboard), `Sobre / Registro do Software` with the exact strings from spec section 10 (project name, 27/04/2025, 09/05/2025, Python web scraping/PLN/relatórios, IF01, IA01/GI01, Quantum Industrial Innovation, Mabel Diz Marques Mota / João Carlos Passos / Alexandre de Santa Barbara). Gate the AI block and pipeline settings behind `can(role, "configure_ai")` / `can(role, "run_pipeline")`.

- [ ] **Step 3: Manual QA**

| Check | Esperado | Obtido | Status |
|---|---|---|---|
| Fornecer acesso | cria pendente/ativo conforme papel | | |
| Cancelar acesso | status revogado, login bloqueado | | |
| Redefinir senha | nova senha autentica | | |
| audit.log | registra todas as ações com usuário+timestamp | | |
| Bloco IA | intacto e testável (Testar Conexão funciona) | | |

Run: `.venv/Scripts/python -m pytest tests -q` (Expected: all pass).

- [ ] **Step 4: Commit**

```bash
git add gui/frames/accounts_frame.py gui/frames/settings_frame.py
git commit -m "feat: add accounts governance and extended settings"
```

---

### Task 12: FASE 7 — Regressão E2E e user-space

**Files:** none (verification only).

- [ ] **Step 1: Full suite green**

Run: `.venv/Scripts/python -m pytest tests -q`
Expected: all pass (47 baseline + all new tests).

- [ ] **Step 2: Coverage gate (RNF-07)**

Run: `.venv/Scripts/python -m coverage run -m pytest tests -q; if ($?) { .venv/Scripts/python -m coverage report --include="core/scoring.py,core/repository.py,core/database.py,core/permissions.py,core/audit.py,core/exports.py" }`
Expected: each new `core/` module ≥80%.

- [ ] **Step 3: Manual E2E as non-admin**

Login → dashboard → generate newsletter (PDF+WORD) → documents → logout, as a `basico` and a `premium` user. Record the QA table (both roles, every row green).

- [ ] **Step 4: User-space check**

Run: `git status --short` (Expected: no stray data files) and confirm no code path writes outside `~/.newsletter_tool/`, the repo workdir data folders, or the user-chosen export folder (grep for `Program Files`, `C:\\Windows`, hard-coded absolute writes).

---

### Task 13: FASE 8 — README reescrito (13 seções, substitui o antigo)

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: final directory tree (`git ls-files`), spec sections 10–11, permission matrix, weights formula.
- Produces: README with exactly: 1) title + `GLOBAL QUANTUM INTELLIGENCE – QuIIN` badge line; 2) product overview; 3) software registry table; 4) real post-phase tree; 5) install (venv, no admin); 6) first use (bootstrap admin, login, roles); 7) per-screen guide + permission matrix; 8) multicriteria index (formula + defaults); 9) AI pipeline (providers, keyring, run); 10) PDF/WORD/Print/Share exports; 11) tests (pytest + coverage commands); 12) known limitations + roadmap; 13) feat changelog. Old content replaced, not appended.

- [ ] **Step 1: Rewrite README**

Replace the full file content following the 13-section structure above (no obsolete pipeline-only sections retained).

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for QuIIN product phase"
```
