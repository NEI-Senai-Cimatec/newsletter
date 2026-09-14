"""Tests for the scrapers/ package refactor (TDD: written before the move)."""
import importlib
import inspect
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRAPERS_DIR = ROOT / "scrapers"

PORTALS = {
    "thequantuminsider": "thequantuminsider",
    "quantamagazine": "quantamagazine",
    "quantumzeitgeist": "quantumzeitgeist",
    "insidequantumtechnology": "insidequantumtechnology",
}
EXPECTED_PARAMS = ("model", "articles_dict", "ignore_cache", "debug", "min_date",
                   "should_cancel")


def test_portal_entry_points_accept_new_options() -> None:
    for module_name, func_name in PORTALS.items():
        module = importlib.import_module(f"scrapers.{module_name}")
        params = inspect.signature(getattr(module, func_name)).parameters
        for expected in EXPECTED_PARAMS:
            assert expected in params, f"{func_name}() missing parameter {expected!r}"


def test_no_hardcoded_month_filters() -> None:
    for module_name in PORTALS:
        source = (SCRAPERS_DIR / f"{module_name}.py").read_text(encoding="utf-8")
        assert "2026-06" not in source, module_name
        assert "2025-10" not in source, module_name
        assert "is_after_min_date" in source, module_name
        assert "should_cancel" in source, module_name


def test_scrapers_import_from_core_utils() -> None:
    for module_name in PORTALS:
        source = (SCRAPERS_DIR / f"{module_name}.py").read_text(encoding="utf-8")
        assert "from core.utils import" in source, module_name
        assert "from utils import" not in source, module_name


def test_iqt_generates_json() -> None:
    source = (SCRAPERS_DIR / "insidequantumtechnology.py").read_text(encoding="utf-8")
    assert "#generate_content_json" not in source
    assert "generate_content_json(model, article_hash" in source
    assert "generate_content_text(article_hash" in source


def test_legacy_sitemap_tracks_core_utils() -> None:
    source = (ROOT / "legacy" / "sitemap.py").read_text(encoding="utf-8")
    assert "from core.utils import" in source
