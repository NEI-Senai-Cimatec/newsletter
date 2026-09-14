"""Tests for core.utils refactor (TDD: written before the refactor edits).

Covers only NEW/CHANGED behavior; untouched logic (validation, cache,
scraping helpers) is preserved byte-for-byte from the original utils.py.
"""
import json
import sys
from pathlib import Path

import pytest

import core.utils as cu
from core.api_client import APIError


class _FakeModel:
    """Stands in for APIClient: respond() pops from script (str or exception)."""

    def __init__(self, script: list) -> None:
        self._script = list(script)
        self.calls: list = []

    def respond(self, prompt: str, response_format=None) -> str:
        self.calls.append({"prompt": prompt, "response_format": response_format})
        item = self._script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def _valid_payload() -> dict:
    return {
        "newsletter": "Quantum breakthrough promises faster computing",
        "summary": "x" * 300,
        "overview": "y" * 800,
        "key_points": ["First key point here"],
        "classification_weight": {
            "Business": 10,
            "Technological": 20,
            "Scientific": 5,
            "Others": 0,
        },
        "organization": [{"name": "ABC Corp", "location": "New York, USA"}],
        "event": [],
        "breakthrough": ["A relevant breakthrough description"],
        "financial_activity": [],
        "related_country": ["USA"],
    }


@pytest.fixture()
def work_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    content = tmp_path / "content"
    parse = tmp_path / "parse"
    content.mkdir()
    parse.mkdir()
    monkeypatch.setattr(cu, "CONTENT_DIR", str(content))
    monkeypatch.setattr(cu, "PARSE_DIR", str(parse))
    monkeypatch.setattr("time.sleep", lambda s: None)
    return tmp_path


def test_no_lmstudio_remnants() -> None:
    assert "lmstudio" not in sys.modules
    assert not hasattr(cu, "initialize_model")
    assert not hasattr(cu, "LLM_IDENTIFIER")
    assert not hasattr(cu, "LLM_SETUP")
    # Kept as the default settings source for APIClient:
    assert cu.LLM_CONFIG == {"maxTokens": 10000, "temperature": 0.8, "topP": 0.95}
    assert cu.LLM_MAX_INPUT_LENGHT == 24576


def test_paths_anchored_at_app_root() -> None:
    assert cu.APP_ROOT == Path("core").resolve().parent
    for attr in ("TEMPLATE_DIR", "CACHE_DIR", "ARTICLE_DIR", "CONTENT_DIR", "PARSE_DIR"):
        value = getattr(cu, attr)
        assert Path(value).is_absolute(), attr
        assert Path(value).parent == cu.APP_ROOT, attr


def test_is_after_min_date() -> None:
    assert cu.is_after_min_date("2026-09-14T10:00:00", "2026-09-01") is True
    assert cu.is_after_min_date("2026-08-31T23:59:59", "2026-09-01") is False
    assert cu.is_after_min_date("2026-09-14T10:00:00", "2026-09") is True
    assert cu.is_after_min_date("2026-08-14T10:00:00", "2026-09") is False
    assert cu.is_after_min_date("2026-08-14T10:00:00", "") is True
    assert cu.is_after_min_date("2026-08-14T10:00:00", None) is True
    assert cu.is_after_min_date(None, "2026-09-01") is True  # no date -> process


def test_merge_json_files_keeps_only_valid(tmp_path: Path) -> None:
    articles = [
        {"hash": "aaa", "title": "One"},
        {"hash": "bbb", "title": "Two"},
        {"title": "NoHash"},
        {"hash": "ccc", "title": "Three"},
    ]
    article_file = tmp_path / "articles.json"
    article_file.write_text(json.dumps(articles), encoding="utf-8")
    parse_dir = tmp_path / "parse"
    parse_dir.mkdir()
    (parse_dir / "aaa_en.json").write_text(json.dumps({"newsletter": "x"}), encoding="utf-8")
    (parse_dir / "ccc_en.json").write_text("{broken", encoding="utf-8")
    out = tmp_path / "out.json"

    cu.merge_json_files(str(article_file), "en", str(parse_dir), str(out))

    merged = json.loads(out.read_text(encoding="utf-8"))
    assert len(merged) == 1
    assert merged[0]["hash"] == "aaa"
    assert merged[0]["newsletter"] == "x"


def test_generate_content_json_success(work_dirs: Path) -> None:
    article_hash = "abc123"
    (work_dirs / "content" / f"{article_hash}.txt").write_text(
        "Some article text. " * 50, encoding="utf-8"
    )
    model = _FakeModel([json.dumps(_valid_payload())])

    result = cu.generate_content_json(model, article_hash, "en", max_retries=2)

    assert result is not None
    assert Path(result).name == f"{article_hash}_en.json"
    saved = json.loads(Path(result).read_text(encoding="utf-8"))
    assert "error" not in saved
    assert saved["total_score"] == 35
    # respond() called WITHOUT the legacy config= kwarg:
    assert set(model.calls[0]) == {"prompt", "response_format"}


def test_generate_content_json_model_error_writes_error_file(work_dirs: Path) -> None:
    article_hash = "def456"
    (work_dirs / "content" / f"{article_hash}.txt").write_text(
        "Some article text. " * 50, encoding="utf-8"
    )
    model = _FakeModel([APIError("boom")])

    result = cu.generate_content_json(model, article_hash, "en", max_retries=1)

    assert result is not None
    assert Path(result).name == f"error_{article_hash}_en.json"
    saved = json.loads(Path(result).read_text(encoding="utf-8"))
    assert saved["error"] == "boom"


def test_generate_content_json_garbage_retries_then_error_file(work_dirs: Path) -> None:
    article_hash = "ghi789"
    (work_dirs / "content" / f"{article_hash}.txt").write_text(
        "Some article text. " * 50, encoding="utf-8"
    )
    model = _FakeModel(["not json at all", "still not json"])

    result = cu.generate_content_json(model, article_hash, "en", max_retries=2)

    assert result is not None
    assert Path(result).name == f"error_{article_hash}_en.json"
    assert len(model.calls) == 2
