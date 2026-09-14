# core/preflight.py
"""Pre-execution checks: browser, driver, network, credentials, dirs, templates.

Every check returns ``{"check", "status", "message"}`` where status is one
of ``"ok"``, ``"warning"`` or ``"error"``. Nothing here requires admin
rights. ``run_preflight_checks()`` never raises: a crashing check becomes
an ``"error"`` entry so the GUI can display all results at once.
"""
from __future__ import annotations

import logging
import os
import shutil
import socket
from pathlib import Path
from typing import Any, Callable

from core.api_client import APIClient, APIError

logger = logging.getLogger(__name__)

REQUIRED_TEMPLATES = (
    "html.txt",
    "parse_v4.txt",
    "parse_v4.json",
    "translate_ptbr.txt",
    "translate_ptbr.json",
)
WORK_DIRS = ("cache", "article", "content", "parse")


def check_chrome() -> dict:
    """Detect a Chrome/Chromium binary on PATH or in the default location."""
    for candidate in ("chrome", "chrome.exe", "chromium", "google-chrome",
                      "google-chrome-stable"):
        found = shutil.which(candidate)
        if found:
            return {"check": "Chrome Browser", "status": "ok",
                    "message": f"Chrome detectado: {found}"}
    default = _default_chrome_path()
    if default is not None and default.exists():
        return {"check": "Chrome Browser", "status": "ok",
                "message": f"Chrome detectado: {default}"}
    return {"check": "Chrome Browser", "status": "error",
            "message": "Chrome/Chromium não encontrado. Instale o Google Chrome."}


def check_chromedriver() -> dict:
    """Report a cached driver, else confirm webdriver-manager can fetch one."""
    cached = _find_cached_driver()
    if cached is not None:
        return {"check": "ChromeDriver", "status": "ok",
                "message": f"ChromeDriver em cache: {cached}"}
    try:
        import webdriver_manager  # noqa: F401
    except ImportError:
        return {"check": "ChromeDriver", "status": "error",
                "message": "webdriver-manager não instalado (pip install -r requirements.txt)."}
    return {"check": "ChromeDriver", "status": "ok",
            "message": "ChromeDriver será baixado na primeira execução (pasta do usuário)."}


def check_internet() -> dict:
    """Verify outbound connectivity with a short TCP probe."""
    try:
        sock = socket.create_connection(("8.8.8.8", 53), timeout=5)
        sock.close()
    except OSError as e:
        return {"check": "Conexão com a internet", "status": "error",
                "message": f"Sem conexão com a internet: {e}"}
    return {"check": "Conexão com a internet", "status": "ok",
            "message": "Conexão com a internet OK"}


def check_api_key(api_key: str | None) -> dict:
    """Verify an API key was configured."""
    if not api_key or not api_key.strip():
        return {"check": "API Key", "status": "error",
                "message": "API key não configurada. Cadastre-a em Configurações."}
    return {"check": "API Key", "status": "ok",
            "message": "API key configurada"}


def check_provider(config: dict, api_key: str | None) -> dict:
    """Build the API client and test the provider connection."""
    try:
        client = APIClient(
            provider=config.get("provider", "groq"),
            api_key=(api_key or ""),
            model=config.get("model", ""),
            base_url=config.get("custom_endpoint") or None,
            **config.get("llm_settings", {}),
        )
    except ValueError as e:
        return {"check": "Provedor de IA", "status": "error",
                "message": f"Configuração inválida: {e}"}
    try:
        connected, message = client.test_connection()
    except APIError as e:
        return {"check": "Provedor de IA", "status": "error", "message": f"Erro: {e}"}
    return {"check": "Provedor de IA",
            "status": "ok" if connected else "error",
            "message": message}


def check_work_directories(base_dir: Path | str) -> dict:
    """Create the pipeline working directories (user-space, no admin)."""
    try:
        root = Path(base_dir)
        for dirname in WORK_DIRS:
            (root / dirname).mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {"check": "Diretórios de trabalho", "status": "error",
                "message": f"Não foi possível criar diretórios em {base_dir}: {e}"}
    return {"check": "Diretórios de trabalho", "status": "ok",
            "message": f"Diretórios de trabalho OK em {root}"}


def check_templates(template_dir: Path | str) -> dict:
    """Verify every prompt/schema template file exists."""
    missing = [name for name in REQUIRED_TEMPLATES
               if not (Path(template_dir) / name).is_file()]
    if missing:
        return {"check": "Templates de prompt", "status": "error",
                "message": f"Templates ausentes em {template_dir}: {', '.join(missing)}"}
    return {"check": "Templates de prompt", "status": "ok",
            "message": "Templates de prompt encontrados"}


def check_min_date(min_date: str | None) -> dict:
    """Warn when no minimum date is set (full sitemap sweep)."""
    if not min_date or not str(min_date).strip():
        return {"check": "Filtro de data", "status": "warning",
                "message": "Sem data mínima: serão processados todos os artigos novos do sitemap."}
    return {"check": "Filtro de data", "status": "ok",
            "message": f"Processando artigos a partir de {min_date}"}


def run_preflight_checks(
    config: dict,
    api_key: str | None,
    *,
    base_dir: Path | str | None = None,
    template_dir: Path | str | None = None,
) -> list[dict]:
    """Run every check and return the ordered list of results."""
    root = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent.parent
    templates = Path(template_dir) if template_dir is not None else root / "template"
    min_date = config.get("scraper_settings", {}).get("min_date", "") if isinstance(config, dict) else ""
    steps: list[tuple[str, Callable, tuple]] = [
        ("Chrome Browser", check_chrome, ()),
        ("ChromeDriver", check_chromedriver, ()),
        ("Conexão com a internet", check_internet, ()),
        ("API Key", check_api_key, (api_key,)),
        ("Provedor de IA", check_provider, (config, api_key)),
        ("Diretórios de trabalho", check_work_directories, (root,)),
        ("Templates de prompt", check_templates, (templates,)),
        ("Filtro de data", check_min_date, (min_date,)),
    ]
    results = []
    for name, func, args in steps:
        try:
            outcome = func(*args)
            results.append({
                "check": name,
                "status": outcome.get("status", "error"),
                "message": outcome.get("message", ""),
            })
        except Exception as e:  # never let one check abort the whole preflight
            logger.exception(f"Preflight check {name} crashed")
            results.append({"check": name, "status": "error", "message": f"{name}: {e}"})
    return results


def _default_chrome_path() -> Path | None:
    """Default Chrome install path on Windows; None on other systems."""
    program_files = os.environ.get("ProgramFiles")
    if not program_files:
        return None
    return Path(program_files) / "Google" / "Chrome" / "Application" / "chrome.exe"


def _find_cached_driver() -> Path | None:
    """Return a previously downloaded chromedriver under ~/.wdm, if any."""
    candidates = sorted((Path.home() / ".wdm").rglob("chromedriver*"))
    for candidate in candidates:
        if candidate.is_file() and candidate.suffix != ".lock":
            return candidate
    return None
