# tests/test_quiin_core_extra.py
"""RNF-07 top-up coverage for new QuIIN core modules (tmp_path only)."""
from __future__ import annotations

import json
import os
import platform
import sqlite3
import subprocess
from pathlib import Path

import pytest

from core import database
from core.audit import log_event
from core.exports import build_newsletter, print_pdf, share_package
from core.permissions import can
from core.repository import (
    add_manual_news,
    load_documents,
    search,
    sort_documents,
    stats_area_share,
    stats_countries,
    stats_monthly,
)
from core.scoring import DEFAULT_WEIGHTS, area_of, load_weights, save_weights, validate_weights


def _weights(**over):
    w = dict(DEFAULT_WEIGHTS)
    w.update(over)
    return w


def _doc(title="T", business=35, date="2026-09-01", **over):
    d = {
        "title": title,
        "newsletter": title,
        "summary": "Resumo.",
        "key_points": ["p1"],
        "organization": [],
        "event": [],
        "breakthrough": [],
        "financial_activity": [],
        "related_country": [],
        "classification_weight": {
            "Business": business,
            "Technological": 0,
            "Scientific": 0,
            "Others": 0,
        },
        "date": date,
        "published": date,
    }
    d.update(over)
    return d


# --- core/scoring.py: load_weights / save_weights / validate_weights ---

def test_weights_roundtrip_default(tmp_path):
    p = tmp_path / "weights.json"
    save_weights(DEFAULT_WEIGHTS, p)
    assert load_weights(p) == DEFAULT_WEIGHTS


def test_weights_roundtrip_custom(tmp_path):
    p = tmp_path / "sub" / "w.json"
    custom = {"negocios": 40, "mercado": 30, "cientifica": 20, "tecnologica": 10}
    save_weights(custom, p)
    assert load_weights(p) == custom
    assert json.loads(p.read_text(encoding="utf-8")) == custom


def test_load_weights_missing_returns_default(tmp_path):
    assert load_weights(tmp_path / "nope.json") == DEFAULT_WEIGHTS


def test_load_weights_bad_json_returns_default(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not-json{{{", encoding="utf-8")
    assert load_weights(p) == DEFAULT_WEIGHTS


def test_load_weights_wrong_sum_returns_default(tmp_path):
    p = tmp_path / "w.json"
    p.write_text(json.dumps({"negocios": 10, "mercado": 10, "cientifica": 10, "tecnologica": 10}), encoding="utf-8")
    assert load_weights(p) == DEFAULT_WEIGHTS


def test_load_weights_wrong_keys_returns_default(tmp_path):
    p = tmp_path / "w.json"
    p.write_text(json.dumps({"a": 25, "b": 25, "c": 25, "d": 25}), encoding="utf-8")
    assert load_weights(p) == DEFAULT_WEIGHTS


def test_load_weights_json_scalar_returns_default(tmp_path):
    p = tmp_path / "w.json"
    p.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    assert load_weights(p) == DEFAULT_WEIGHTS


def test_validate_weights_rejects_bad_keys():
    with pytest.raises(ValueError):
        validate_weights({"negocios": 25, "mercado": 25, "cientifica": 25, "wrong": 25})


def test_validate_weights_rejects_non_int():
    with pytest.raises(ValueError):
        validate_weights({"negocios": "35", "mercado": 35, "cientifica": 15, "tecnologica": 15})


def test_validate_weights_rejects_out_of_range():
    with pytest.raises(ValueError):
        validate_weights({"negocios": 101, "mercado": 0, "cientifica": 0, "tecnologica": -1})


def test_save_weights_rejects_invalid(tmp_path):
    with pytest.raises(ValueError):
        save_weights({"negocios": 1, "mercado": 1, "cientifica": 1, "tecnologica": 1}, tmp_path / "w.json")


def test_area_of_each_branch():
    assert area_of({"classification_weight": {"Business": 0, "Technological": 35, "Scientific": 0, "Others": 0}}) == "Tecnológico"
    assert area_of({"classification_weight": {"Business": 0, "Technological": 0, "Scientific": 15, "Others": 0}}) == "Científico"
    assert area_of({"classification_weight": {"Business": 0, "Technological": 0, "Scientific": 0, "Others": 9}}) == "Outros"


# --- core/repository.py ---

def test_load_documents_valid_list(tmp_path):
    docs = [_doc("A"), _doc("B")]
    p = tmp_path / "docs.json"
    p.write_text(json.dumps(docs), encoding="utf-8")
    assert load_documents(p) == docs


def test_load_documents_non_list_returns_empty(tmp_path):
    p = tmp_path / "docs.json"
    p.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
    assert load_documents(p) == []


def test_load_documents_missing_returns_empty(tmp_path):
    assert load_documents(tmp_path / "missing.json") == []


def test_load_documents_bad_json_returns_empty(tmp_path):
    p = tmp_path / "docs.json"
    p.write_text("{{{bad", encoding="utf-8")
    assert load_documents(p) == []


def test_search_empty_query_returns_copy():
    docs = [_doc("A"), _doc("B")]
    out = search(docs, "")
    assert out == docs
    assert out is not docs
    assert search(docs, "   ") == docs


def test_search_matches_org_and_event_names():
    docs = [
        _doc("doc1", organization=[{"name": "Acme Quantum"}]),
        _doc("doc2", event=[{"name": "QConf Berlin"}]),
        _doc("doc3"),
    ]
    assert [d["title"] for d in search(docs, "acme")] == ["doc1"]
    assert [d["title"] for d in search(docs, "qconf")] == ["doc2"]


def test_stats_monthly_counts_and_skips_undated():
    biz = {"Business": 35, "Technological": 0, "Scientific": 0, "Others": 0}
    tech = {"Business": 0, "Technological": 35, "Scientific": 0, "Others": 0}
    docs = [
        {"classification_weight": biz, "date": "2026-01-15"},
        {"classification_weight": tech, "date": "2026-01-20"},
        {"classification_weight": biz, "published": "2026-02-05"},
        {"classification_weight": biz, "modified": "2026-03-01"},
        {"classification_weight": biz},  # no date fields -> skipped
        {"classification_weight": biz, "date": "bad-date"},  # malformed -> skipped
    ]
    areas = ["Negócio/Economia", "Tecnológico", "Científico", "Outros"]
    table = stats_monthly(docs, areas)
    assert table["2026-01"] == {"Negócio/Economia": 1, "Tecnológico": 1, "Científico": 0, "Outros": 0}
    assert table["2026-02"]["Negócio/Economia"] == 1
    assert table["2026-03"]["Negócio/Economia"] == 1
    assert len(table) == 3


def test_stats_monthly_truncates_to_recent_six():
    docs = [
        _doc(f"m{i}", business=35, date=f"2026-{i:02d}-10",
             published=f"2026-{i:02d}-10")
        for i in range(1, 9)
    ]
    areas = ["Negócio/Economia", "Tecnológico", "Científico", "Outros"]
    table = stats_monthly(docs, areas)
    assert sorted(table) == [f"2026-{i:02d}" for i in range(3, 9)]
    assert len(table) == 6


def test_stats_area_share_empty():
    assert stats_area_share([]) == {
        "Negócio/Economia": 0.0, "Tecnológico": 0.0, "Científico": 0.0, "Outros": 0.0
    }


def test_stats_countries_known_names_and_top():
    docs = [
        {"related_country": ["USA", "BRA"]},
        {"related_country": ["USA"]},
        {"related_country": []},
        {},
    ]
    assert stats_countries(docs) == [("Estados Unidos", 2), ("Brasil", 1)]
    assert stats_countries(docs, top=1) == [("Estados Unidos", 2)]
    assert stats_countries([], top=5) == []


def test_sort_by_area():
    tech = _doc("tech", business=0, classification_weight={"Business": 0, "Technological": 35, "Scientific": 0, "Others": 0})
    biz = _doc("biz", business=35)
    asc = sort_documents([tech, biz], key="area", desc=False)
    desc = sort_documents([tech, biz], key="area", desc=True)
    assert [d["title"] for d in asc] != [d["title"] for d in desc]
    assert sorted([d["title"] for d in asc]) == ["biz", "tech"]


def test_sort_by_date_asc_desc():
    old = _doc("old", date="2026-01-01", published="2026-01-01")
    new = _doc("new", date="2026-09-01", published="2026-09-01")
    assert [d["title"] for d in sort_documents([new, old], key="date", desc=True)] == ["new", "old"]
    assert [d["title"] for d in sort_documents([new, old], key="date", desc=False)] == ["old", "new"]


def test_sort_by_date_falls_back_to_published():
    a = {"title": "a", "summary": "", "key_points": [], "organization": [], "event": [],
         "classification_weight": {"Business": 1, "Technological": 0, "Scientific": 0, "Others": 0},
         "published": "2026-05-01", "related_country": []}
    b = {"title": "b", "summary": "", "key_points": [], "organization": [], "event": [],
         "classification_weight": {"Business": 1, "Technological": 0, "Scientific": 0, "Others": 0},
         "published": "2026-06-01", "related_country": []}
    assert [d["title"] for d in sort_documents([a, b], key="date", desc=False)] == ["a", "b"]


def test_sort_invalid_key_raises():
    with pytest.raises(ValueError):
        sort_documents([_doc()], key="nope")


def test_sort_relevance_custom_weights():
    low = _doc("low", business=5)
    high = _doc("high", business=35)
    custom = {"negocios": 100, "mercado": 0, "cientifica": 0, "tecnologica": 0}
    ordered = sort_documents([low, high], key="relevance", desc=True, weights=custom)
    assert [d["title"] for d in ordered] == ["high", "low"]


def test_add_manual_news_other_areas():
    for area, key in [("Tecnológico", "Technological"), ("Científico", "Scientific"), ("Outros", "Others")]:
        rec = add_manual_news({"url": f"https://exemplo.test/{key}", "title": f"T-{key}",
                               "area": area, "date": "2026-09-14", "summary": "R."})
        assert rec["classification_weight"][key] > 0
        assert rec["source"] == "Manual"
    fallback = add_manual_news({"url": "https://exemplo.test/unk", "title": "U",
                                "area": "AreaInexistente", "date": "2026-09-14", "summary": "R."})
    assert fallback["classification_weight"] == {"Business": 0, "Technological": 0, "Scientific": 0, "Others": 15}
    no_date = add_manual_news({"url": "https://exemplo.test/nodate", "title": "ND",
                               "area": "Outros", "summary": "R."})
    assert no_date["date"] != ""


# --- core/database.py extra branches ---

def test_create_user_rejects_bad_role_and_status(tmp_path):
    db = tmp_path / "users.db"
    with pytest.raises(ValueError):
        database.create_user(db, "u1", "U1", "Q", True, "super", "pw")
    with pytest.raises(ValueError):
        database.create_user(db, "u1", "U1", "Q", True, "basico", "pw", status="weird")


def test_create_user_duplicate_raises(tmp_path):
    db = tmp_path / "users.db"
    database.bootstrap_admin(db, "Admin", "admin", "pw-admin")
    database.create_user(db, "dup", "Dup", "Q", True, "basico", "pw")
    with pytest.raises(ValueError):
        database.create_user(db, "dup", "Dup2", "Q", True, "basico", "pw2")


def test_authenticate_unknown_returns_none(tmp_path):
    db = tmp_path / "users.db"
    database.bootstrap_admin(db, "Admin", "admin", "pw")
    assert database.authenticate(db, "ghost", "pw") is None


def test_set_status_rejects_bad_status(tmp_path):
    db = tmp_path / "users.db"
    database.bootstrap_admin(db, "Admin", "admin", "pw")
    with pytest.raises(ValueError):
        database.set_status(db, "admin", "weird")


def test_set_status_unknown_user_raises(tmp_path):
    db = tmp_path / "users.db"
    database.bootstrap_admin(db, "Admin", "admin", "pw")
    with pytest.raises(ValueError):
        database.set_status(db, "ghost", "ativo")


def test_set_password_unknown_user_raises(tmp_path):
    db = tmp_path / "users.db"
    database.bootstrap_admin(db, "Admin", "admin", "pw")
    with pytest.raises(ValueError):
        database.set_password(db, "ghost", "newpw")


def test_list_users_ordered_by_name(tmp_path):
    db = tmp_path / "users.db"
    database.bootstrap_admin(db, "Zeta", "zeta", "pw")
    database.create_user(db, "anna", "Anna", "Q", True, "basico", "pw")
    users = database.list_users(db)
    assert [u["username"] for u in users] == ["anna", "zeta"]
    assert "password_hash" not in users[0]
    assert users[0]["name"] == "Anna"


def test_bootstrap_nonempty_raises(tmp_path):
    db = tmp_path / "users.db"
    database.bootstrap_admin(db, "Admin", "admin", "pw")
    with pytest.raises(ValueError):
        database.bootstrap_admin(db, "Admin2", "admin2", "pw2")


def test_reset_no_meta_returns_false(tmp_path):
    db = tmp_path / "users.db"
    database.init_db(db)  # no meta row, no users
    assert database.reset_admin_via_recovery_code(db, "whatever", "new") is False


def test_reset_no_admin_returns_false(tmp_path):
    db = tmp_path / "users.db"
    database.init_db(db)
    with sqlite3.connect(str(db)) as conn:
        h = "deadbeef"
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('admin_recovery', ?)", (h,))
    # meta points at nothing valid and there are no admins
    assert database.reset_admin_via_recovery_code(db, "wrong-code", "new") is False


def test_reset_valid_code_but_no_admin_returns_false(tmp_path):
    import hashlib

    db = tmp_path / "users.db"
    database.init_db(db)
    code = "valid-code-no-admin"
    code_hash = hashlib.sha256(code.encode()).hexdigest()
    with sqlite3.connect(str(db)) as conn:
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES('admin_recovery', ?)", (code_hash,))
    assert database.reset_admin_via_recovery_code(db, code, "new") is False


# --- core/permissions.py + core/audit.py ---

def test_can_unknown_capability_is_false():
    assert can("admin", "no-such-cap") is False
    assert can("ghost-role", "view") is False
    assert can("basico", "generate_newsletter") is False
    assert can("premium", "generate_newsletter") is True


def test_log_event_second_line(tmp_path):
    log = tmp_path / "audit.log"
    log_event("u1", "view", "d1", log_path=log)
    rec = log_event("u2", "export", "d2", log_path=log)
    assert rec["user"] == "u2"
    lines = log.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[1])["action"] == "export"


# --- core/exports.py: share_package + print_pdf (monkeypatched OS effects only) ---

def _structure():
    docs = [_doc("My Title", business=35)]
    return build_newsletter(docs, DEFAULT_WEIGHTS, "automatico", {"title": "Newsletter Title XYZ"})


def test_share_package_md_content(tmp_path, monkeypatch):
    monkeypatch.setattr(os, "startfile", lambda *a, **k: None, raising=False)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: None)
    structure = _structure()
    md = share_package(structure, tmp_path / "pkg")
    text = Path(md).read_text(encoding="utf-8")
    assert Path(md).exists()
    assert "Newsletter Title XYZ" in text
    assert "My Title" in text


def test_share_package_darwin_branch(tmp_path, monkeypatch):
    import core.exports as ex

    calls = {}
    monkeypatch.setattr(ex.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(ex.subprocess, "Popen", lambda cmd: calls.setdefault("cmd", cmd))
    structure = _structure()
    md = share_package(structure, tmp_path / "pkg-mac")
    assert Path(md).exists()
    assert calls["cmd"] == ["open", str(tmp_path / "pkg-mac")]


def test_share_package_linux_branch(tmp_path, monkeypatch):
    import core.exports as ex

    calls = {}
    monkeypatch.setattr(ex.platform, "system", lambda: "Linux")
    monkeypatch.setattr(ex.subprocess, "Popen", lambda cmd: calls.setdefault("cmd", cmd))
    structure = _structure()
    md = share_package(structure, tmp_path / "pkg-linux")
    assert Path(md).exists()
    assert calls["cmd"] == ["xdg-open", str(tmp_path / "pkg-linux")]


def test_share_package_open_failure_swallowed(tmp_path, monkeypatch):
    import core.exports as ex

    def boom(*a, **k):
        raise OSError("cannot open folder")

    monkeypatch.setattr(ex.platform, "system", lambda: "Windows")
    monkeypatch.setattr(os, "startfile", boom, raising=False)
    structure = _structure()
    md = share_package(structure, tmp_path / "pkg-fail")
    assert Path(md).exists()
    assert "Newsletter Title XYZ" in Path(md).read_text(encoding="utf-8")


def test_print_pdf_printed_branch(monkeypatch):
    import core.exports as ex

    monkeypatch.setattr(ex.platform, "system", lambda: "Windows")
    monkeypatch.setattr(os, "startfile", lambda *a, **k: None, raising=False)
    called = []
    monkeypatch.setattr(ex.webbrowser, "open", lambda url: called.append(url))
    assert print_pdf("C:/tmp/n.pdf") == "printed"
    assert called == []


def test_print_pdf_opened_fallback(monkeypatch):
    import core.exports as ex

    def boom(*a, **k):
        raise OSError("no printer")

    monkeypatch.setattr(ex.platform, "system", lambda: "Windows")
    monkeypatch.setattr(os, "startfile", boom, raising=False)
    seen = []
    monkeypatch.setattr(ex.webbrowser, "open", lambda url: seen.append(url))
    assert print_pdf("C:/tmp/n.pdf") == "opened"
    assert seen == ["C:/tmp/n.pdf"]


def test_print_pdf_non_windows(monkeypatch):
    import core.exports as ex

    monkeypatch.setattr(ex.platform, "system", lambda: "Linux")
    seen = []
    monkeypatch.setattr(ex.webbrowser, "open", lambda url: seen.append(url))
    assert print_pdf("/tmp/n.pdf") == "opened"
    assert seen == ["/tmp/n.pdf"]
