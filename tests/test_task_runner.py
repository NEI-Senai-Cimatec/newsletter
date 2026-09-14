"""Tests for core.task_runner (TDD: written before implementation)."""
import json
import logging
from queue import Queue

import pytest

import core.task_runner as tr


def _drain(queue: Queue) -> list:
    items = []
    while not queue.empty():
        items.append(queue.get_nowait())
    return items


@pytest.fixture()
def config() -> dict:
    return {
        "provider": "groq",
        "model": "m",
        "custom_endpoint": "",
        "portals": {
            "thequantuminsider": True,
            "quantamagazine": False,
            "quantumzeitgeist": True,
            "insidequantumtechnology": False,
        },
        "llm_settings": {"max_tokens": 100, "temperature": 0.1, "top_p": 0.9},
        "scraper_settings": {"ignore_cache": True, "debug": False, "min_date": "2026-09-01"},
        "language": "en",
    }


@pytest.fixture()
def runner_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """TaskRunner with all heavy dependencies faked; paths redirected to tmp."""
    progress: Queue = Queue()
    logs: Queue = Queue()
    runner = tr.TaskRunner(progress, logs)
    calls: list = []

    monkeypatch.setattr(tr, "ARTICLES_JSON", str(tmp_path / "quantum_articles.json"))
    monkeypatch.setattr(tr, "DOCUMENTS_JSON", str(tmp_path / "documents-data.json"))
    monkeypatch.setattr(tr, "PARSE_DIR", str(tmp_path / "parse"))
    monkeypatch.setattr(tr, "ensure_directories", lambda: calls.append("ensure"))
    monkeypatch.setattr(tr, "clean_legacy_cache", lambda: calls.append("clean"))
    monkeypatch.setattr(
        tr, "load_existing_articles", lambda d, f: calls.append(("load", f))
    )
    monkeypatch.setattr(
        tr, "save_articles",
        lambda d, sort_order="desc", output_file="": calls.append(("save", output_file)),
    )

    def fake_merge(article_file, language, parse_dir, output_file):
        calls.append(("merge", output_file))
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump([{"hash": "a"}, {"hash": "b"}], f)

    monkeypatch.setattr(tr, "merge_json_files", fake_merge)

    portal_calls: list = []

    def fake_portal(model, articles_dict, **kwargs):
        portal_calls.append(kwargs)
        articles_dict["http://x"] = {"hash": "a"}

    monkeypatch.setattr(
        tr, "_resolve_portal_runner",
        lambda key: (f"Portal {key}", fake_portal),
    )
    return runner, progress, logs, calls, portal_calls


def test_queue_handler_routes_logs_and_article_progress() -> None:
    log_q: Queue = Queue()
    prog_q: Queue = Queue()
    handler = tr.QueueHandler(log_q, prog_q)
    handler.setFormatter(logging.Formatter("%(levelname)s - %(message)s"))

    handler.emit(logging.LogRecord("t", logging.WARNING, __file__, 1,
                                   "Current URL: 3 / 10", None, None))
    assert log_q.get_nowait() == {"level": "WARNING",
                                  "message": "WARNING - Current URL: 3 / 10"}
    item = prog_q.get_nowait()
    assert (item["type"], item["current"], item["total"]) == ("article", 3, 10)

    handler.emit(logging.LogRecord("t", logging.INFO, __file__, 1, "hello", None, None))
    assert log_q.get_nowait()["level"] == "INFO"
    assert prog_q.empty()


def test_run_pipeline_executes_enabled_portals_in_order(runner_env, config) -> None:
    runner, progress, _logs, calls, portal_calls = runner_env
    model = object()

    runner.run_pipeline(model, config)

    assert calls[0] == "ensure"
    assert "clean" in calls
    stages = _drain(progress)
    portal_starts = [m for m in stages if m.get("stage") == "portal_start"]
    assert [m["portal"] for m in portal_starts] == [
        "Portal thequantuminsider", "Portal quantumzeitgeist"]
    assert len(portal_calls) == 2
    for kwargs in portal_calls:
        assert kwargs["ignore_cache"] is True
        assert kwargs["debug"] is False
        assert kwargs["min_date"] == "2026-09-01"
        assert callable(kwargs["should_cancel"])
        assert kwargs["should_cancel"]() is False
    # merge wrote 2 articles -> final message carries the count
    done = [m for m in stages if m.get("stage") == "done"]
    assert len(done) == 1
    assert "2 notícias" in done[0]["message"]


def test_run_pipeline_continues_after_portal_error(runner_env, config, monkeypatch) -> None:
    runner, progress, _logs, calls, _portal_calls = runner_env
    seen: list = []

    def resolver(key):
        def run(model, articles_dict, **kwargs):
            seen.append(key)
            if key == "thequantuminsider":
                raise RuntimeError("portal down")
        return f"Portal {key}", run

    monkeypatch.setattr(tr, "_resolve_portal_runner", resolver)
    runner.run_pipeline(model := object(), config)

    assert seen == ["thequantuminsider", "quantumzeitgeist"]  # second still ran
    stages = _drain(progress)
    assert any(m.get("stage") == "portal_error" for m in stages)
    done = [m for m in stages if m.get("stage") == "done"][0]
    assert "com erro" in done["message"]


def test_cancel_stops_before_next_portal(runner_env, config) -> None:
    runner, progress, _logs, calls, portal_calls = runner_env
    runner.cancel()
    assert runner.is_cancelled is True

    runner.run_pipeline(object(), config)

    assert portal_calls == []
    assert ("merge", tr.DOCUMENTS_JSON) not in calls  # no merge when cancelled
    assert any(c[0] == "save" for c in calls)  # partial results preserved
    stages = _drain(progress)
    assert any(m.get("stage") == "cancelled" for m in stages)


def test_init_failure_aborts_pipeline(runner_env, config, monkeypatch) -> None:
    runner, progress, _logs, _calls, portal_calls = runner_env

    def boom():
        raise OSError("no disk")

    monkeypatch.setattr(tr, "ensure_directories", boom)
    runner.run_pipeline(object(), config)

    assert portal_calls == []
    stages = _drain(progress)
    assert any(m.get("stage") == "error" for m in stages)


def test_start_runs_in_background_thread(runner_env, config) -> None:
    runner, progress, _logs, _calls, _portal_calls = runner_env
    thread = runner.start(object(), config)
    thread.join(timeout=30)
    assert not thread.is_alive()
    assert runner.is_running is False
    stages = _drain(progress)
    assert any(m.get("stage") == "done" for m in stages)


def test_resolve_portal_runner_returns_real_functions() -> None:
    display, func = tr._resolve_portal_runner("thequantuminsider")
    assert display == "The Quantum Insider"
    assert callable(func)
    assert "min_date" in func.__code__.co_varnames
