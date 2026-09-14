"""Tests for core.preflight (TDD: written before implementation)."""
import shutil
import socket

import pytest

import core.preflight as pf

EXPECTED_CHECKS = [
    "Chrome Browser",
    "ChromeDriver",
    "Conexão com a internet",
    "API Key",
    "Provedor de IA",
    "Diretórios de trabalho",
    "Templates de prompt",
    "Filtro de data",
]


def _ok(message: str = "fine"):
    return lambda *args: {"check": "?", "status": "ok", "message": message}


def _patch_all_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pf, "check_chrome", _ok())
    monkeypatch.setattr(pf, "check_chromedriver", _ok())
    monkeypatch.setattr(pf, "check_internet", _ok())
    monkeypatch.setattr(pf, "check_api_key", _ok())
    monkeypatch.setattr(pf, "check_provider", _ok())
    monkeypatch.setattr(pf, "check_work_directories", _ok())
    monkeypatch.setattr(pf, "check_templates", _ok())
    monkeypatch.setattr(pf, "check_min_date", _ok())


def test_run_preflight_collects_all_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_all_ok(monkeypatch)
    results = pf.run_preflight_checks({"provider": "groq"}, "k")
    assert [r["check"] for r in results] == EXPECTED_CHECKS
    assert all(r["status"] == "ok" for r in results)
    for r in results:
        assert set(r) == {"check", "status", "message"}


def test_helper_exception_becomes_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_all_ok(monkeypatch)

    def boom(*args):
        raise RuntimeError("kaput")

    monkeypatch.setattr(pf, "check_chrome", boom)
    results = pf.run_preflight_checks({}, "")
    chrome = [r for r in results if r["check"] == "Chrome Browser"][0]
    assert chrome["status"] == "error"
    assert "kaput" in chrome["message"]
    assert len(results) == len(EXPECTED_CHECKS)


def test_check_api_key() -> None:
    assert pf.check_api_key("")["status"] == "error"
    assert pf.check_api_key("   ")["status"] == "error"
    assert pf.check_api_key("k")["status"] == "ok"


def test_check_templates(tmp_path) -> None:
    assert pf.check_templates(tmp_path)["status"] == "error"
    for name in ("html.txt", "parse_v4.txt", "parse_v4.json", "translate_ptbr.txt",
                 "translate_ptbr.json"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    result = pf.check_templates(tmp_path)
    assert result["status"] == "ok"


def test_check_work_directories(tmp_path) -> None:
    result = pf.check_work_directories(tmp_path)
    assert result["status"] == "ok"
    for dirname in ("cache", "article", "content", "parse"):
        assert (tmp_path / dirname).is_dir()


def test_check_min_date() -> None:
    assert pf.check_min_date("")["status"] == "warning"
    assert pf.check_min_date("2026-09-01")["status"] == "ok"


def test_check_chrome_found_and_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda *a, **k: "C:/chrome.exe")
    assert pf.check_chrome()["status"] == "ok"

    monkeypatch.setattr(shutil, "which", lambda *a, **k: None)
    monkeypatch.setattr(pf, "_default_chrome_path", lambda: None)
    assert pf.check_chrome()["status"] == "error"


def test_check_chromedriver_cached(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(pf, "_find_cached_driver", lambda: tmp_path / "chromedriver.exe")
    assert pf.check_chromedriver()["status"] == "ok"


def test_check_chromedriver_downloadable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pf, "_find_cached_driver", lambda: None)
    result = pf.check_chromedriver()
    assert result["status"] == "ok"
    assert "baixado" in result["message"].lower()


def test_check_internet(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeSocket:
        def close(self) -> None:
            pass

    monkeypatch.setattr(socket, "create_connection", lambda *a, **k: FakeSocket())
    assert pf.check_internet()["status"] == "ok"

    def boom(*a, **k):
        raise OSError("down")

    monkeypatch.setattr(socket, "create_connection", boom)
    assert pf.check_internet()["status"] == "error"


def test_check_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        def __init__(self, **kwargs) -> None:
            pass

        def test_connection(self):
            return True, "Conexão OK — Modelo: m"

    monkeypatch.setattr(pf, "APIClient", FakeClient)
    result = pf.check_provider({"provider": "groq", "model": "m"}, "k")
    assert result["status"] == "ok"

    class BadClient:
        def __init__(self, **kwargs) -> None:
            raise ValueError("bad config")

    monkeypatch.setattr(pf, "APIClient", BadClient)
    assert pf.check_provider({}, "")["status"] == "error"
