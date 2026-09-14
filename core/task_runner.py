# core/task_runner.py
"""Background pipeline orchestration for the GUI.

Runs the full collect → process → merge pipeline in a worker thread so the
CustomTkinter main loop never blocks. Progress and logs travel back to the
GUI through two queues, which the frames poll with ``after()``.
"""
from __future__ import annotations

import importlib
import json
import logging
import queue
import re
import threading
from typing import Any, Callable

from core.api_client import APIClient
from core.utils import (
    ARTICLES_JSON,
    DOCUMENTS_JSON,
    PARSE_DIR,
    clean_legacy_cache,
    ensure_directories,
    load_existing_articles,
    merge_json_files,
    save_articles,
)

logger = logging.getLogger(__name__)

PORTAL_ORDER = (
    "thequantuminsider",
    "quantamagazine",
    "quantumzeitgeist",
    "insidequantumtechnology",
)

PORTAL_RUNNERS = {
    "thequantuminsider": (
        "The Quantum Insider",
        "scrapers.thequantuminsider",
        "thequantuminsider",
    ),
    "quantamagazine": ("Quanta Magazine", "scrapers.quantamagazine", "quantamagazine"),
    "quantumzeitgeist": (
        "Quantum Zeitgeist",
        "scrapers.quantumzeitgeist",
        "quantumzeitgeist",
    ),
    "insidequantumtechnology": (
        "Inside Quantum Technology",
        "scrapers.insidequantumtechnology",
        "insidequantumtechnology",
    ),
}


class QueueHandler(logging.Handler):
    """Forwards log records to the GUI log queue (and parses article progress)."""

    ARTICLE_RE = re.compile(r"Current URL:\s*(\d+)\s*/\s*(\d+)")

    def __init__(self, log_queue: queue.Queue, progress_queue: queue.Queue | None = None) -> None:
        super().__init__()
        self.log_queue = log_queue
        self.progress_queue = progress_queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = self.format(record)
            self.log_queue.put({"level": record.levelname, "message": message})
            if self.progress_queue is not None:
                match = self.ARTICLE_RE.search(message)
                if match:
                    self.progress_queue.put({
                        "type": "article",
                        "current": int(match.group(1)),
                        "total": int(match.group(2)),
                        "message": message,
                    })
        except Exception:
            self.handleError(record)


def _resolve_portal_runner(portal_key: str) -> tuple[str, Callable]:
    """Return ``(display_name, entry_function)`` for a portal key."""
    display, module_name, func_name = PORTAL_RUNNERS[portal_key]
    module = importlib.import_module(module_name)
    return display, getattr(module, func_name)


class TaskRunner:
    """Executes the newsletter pipeline in a background thread."""

    def __init__(self, progress_queue: queue.Queue, log_queue: queue.Queue) -> None:
        self.progress_queue = progress_queue
        self.log_queue = log_queue
        self._cancel_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self, model: APIClient, config: dict) -> threading.Thread:
        """Launch :meth:`run_pipeline` in a daemon thread and return it."""
        self._cancel_event.clear()
        self._thread = threading.Thread(
            target=self.run_pipeline,
            args=(model, config),
            daemon=True,
            name="newsletter-pipeline",
        )
        self._thread.start()
        return self._thread

    def run_pipeline(self, model: APIClient, config: dict) -> None:
        """Run collect → process → merge synchronously (worker entry point)."""
        handler = QueueHandler(self.log_queue, self.progress_queue)
        handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        try:
            self._run(model, config)
        finally:
            root_logger.removeHandler(handler)

    def cancel(self) -> None:
        """Signal cancellation; honored between portals and between articles."""
        self._cancel_event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _emit(self, stage: str, message: str, **extra: Any) -> None:
        item: dict[str, Any] = {"type": "stage", "stage": stage, "message": message}
        item.update(extra)
        self.progress_queue.put(item)
        logger.info(message)

    def _run(self, model: APIClient, config: dict) -> None:
        scraper_settings = config.get("scraper_settings", {})
        ignore_cache = scraper_settings.get("ignore_cache", False)
        debug = scraper_settings.get("debug", False)
        min_date = scraper_settings.get("min_date", "")
        language = config.get("language", "en")

        self._emit("init", "Preparando diretórios e carregando base existente...")
        try:
            ensure_directories()
            clean_legacy_cache()
        except Exception as e:
            logger.exception("Pipeline setup failed")
            self._emit("error", f"Falha na preparação: {e}")
            return

        articles_dict: dict = {}
        load_existing_articles(articles_dict, ARTICLES_JSON)

        errors = 0
        for portal_key in PORTAL_ORDER:
            if not config.get("portals", {}).get(portal_key):
                continue
            if self.is_cancelled:
                break
            display, portal_fn = _resolve_portal_runner(portal_key)
            self._emit("portal_start", f"Processando {display}...", portal=display)
            try:
                portal_fn(
                    model,
                    articles_dict,
                    ignore_cache=ignore_cache,
                    debug=debug,
                    min_date=min_date,
                    should_cancel=self._cancel_event.is_set,
                )
            except Exception as e:
                errors += 1
                logger.exception(f"Portal {display} failed")
                self._emit("portal_error", f"Erro em {display}: {e}", portal=display)
                continue
            self._emit("portal_done", f"{display} concluído.", portal=display)

        save_articles(articles_dict, sort_order="desc", output_file=ARTICLES_JSON)

        if self.is_cancelled:
            self._emit("cancelled", "Pipeline cancelado pelo usuário. Resultados parciais salvos.")
            return

        self._emit("merge", "Consolidando base final...")
        merge_json_files(ARTICLES_JSON, language, PARSE_DIR, DOCUMENTS_JSON)

        total = self._count_final_articles(articles_dict)
        message = f"Concluído! {total} notícias na base final."
        if errors:
            message += f" ({errors} portal(is) com erro.)"
        self._emit("done", message)

    @staticmethod
    def _count_final_articles(articles_dict: dict) -> int:
        try:
            with open(DOCUMENTS_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)
            return len(data) if isinstance(data, list) else len(articles_dict)
        except (OSError, ValueError):
            return len(articles_dict)
