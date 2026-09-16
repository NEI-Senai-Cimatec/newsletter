# core/briefs.py
"""Newsletter briefs: one running pt-BR paragraph per document + source line.

Every export surface (PDF/WORD/share, dashboard and single-document
flows) renders ``build_brief`` output as::

    {title} — {área} ({relevância})
    <single paragraph, <=700 chars and <=100 words>
    Fonte: {url}

Generation never raises and never blocks on the network when there is
no client: without an ``api_client`` (or when the API fails even after
one retry) an extractive, deterministic fallback keeps the original
language (acceptable per RF-N2 "quando possível").
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

BRIEF_MAX_CHARS = 700
BRIEF_MAX_WORDS = 100

BRIEF_PROMPT_FILE = Path(__file__).resolve().parent.parent / "template" / "brief_ptbr.txt"
RETRY_SUFFIX = ("\n\nResponda em no máximo 700 caracteres e 100 palavras, "
                "em um único parágrafo, sem quebras de linha.")

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def _normalize(text: str) -> str:
    """Collapse all whitespace/newlines into single spaces."""
    return " ".join(str(text or "").split())


def hard_trim(text: str, max_chars: int = BRIEF_MAX_CHARS,
              max_words: int = BRIEF_MAX_WORDS) -> str:
    """Deterministic cut honoring BOTH limits on a word boundary."""
    collapsed = _normalize(text)
    words = collapsed.split(" ")
    if len(words) > max_words:
        collapsed = " ".join(words[:max_words])
    if len(collapsed) > max_chars:
        head = collapsed[:max_chars]
        collapsed = head.rsplit(" ", 1)[0] if " " in head else head
    return collapsed


def validate_brief(body: str, url: str) -> tuple[bool, str]:
    """Check the brief BODY (before the Fonte line is appended)."""
    if not body or not body.strip():
        return False, "brief vazio"
    if "\n" in body or "\r" in body:
        return False, "brief contém quebra de linha"
    if len(body) > BRIEF_MAX_CHARS:
        return False, (f"brief excede {BRIEF_MAX_CHARS} caracteres "
                       f"({len(body)})")
    if len(body.split()) > BRIEF_MAX_WORDS:
        return False, (f"brief excede {BRIEF_MAX_WORDS} palavras "
                       f"({len(body.split())})")
    final = f"{body}\nFonte: {url}"
    if not final.endswith(f"Fonte: {url}"):
        return False, "texto final não termina com a linha Fonte"
    return True, "ok"


def _select_source(doc: dict) -> tuple[str, bool]:
    """Return ``(base_text, already_ptbr)`` by priority chain.

    1. Stored pt-BR fields (when the merge ran with ptbr parses);
    2. English ``overview``/``summary`` (current documents-data.json);
    3. Last resort: title + key_points concatenated.
    """
    for key in ("overview_ptbr", "summary_ptbr"):
        if doc.get(key):
            return str(doc[key]), True
    for key in ("overview", "summary"):
        if doc.get(key):
            return str(doc[key]), False
    parts = [str(doc.get("title", ""))]
    parts.extend(str(p) for p in (doc.get("key_points") or []) if p)
    return " ".join(p for p in parts if p), False


def _load_brief_prompt() -> str:
    with open(BRIEF_PROMPT_FILE, "r", encoding="utf-8") as f:
        return f.read()


def _doc_title(doc: dict) -> str:
    return str(doc.get("newsletter") or doc.get("title") or "(sem título)")


def _warn_fallback(doc: dict, reason: str) -> None:
    logger.warning("[API] Falha condensando '%s': %s. "
                   "Fallback extrativo aplicado.", _doc_title(doc), reason)


def _extractive_fallback(source: str) -> str:
    """First sentences of ``source`` up to the limits (deterministic)."""
    normalized = _normalize(source)
    if not normalized:
        return ""
    sentences = [s for s in _SENTENCE_SPLIT.split(normalized) if s]
    if not sentences:
        return hard_trim(normalized)
    kept: list[str] = []
    for sentence in sentences:
        candidate = " ".join([*kept, sentence])
        if (len(candidate) > BRIEF_MAX_CHARS
                or len(candidate.split()) > BRIEF_MAX_WORDS):
            break
        kept.append(sentence)
    if not kept:
        return hard_trim(sentences[0])
    return " ".join(kept)


def _brief_via_api(doc: dict, source: str, api_client) -> str | None:
    """One API call plus one instructed retry; ``None`` on any failure."""
    try:
        template = _load_brief_prompt()
    except OSError as exc:
        _warn_fallback(doc, f"template brief_ptbr.txt indisponível: {exc}")
        return None
    prompt = template.replace("{content}", source)
    try:
        candidate = api_client.respond(prompt).strip()
    except Exception as exc:  # export must never fail because of the API
        _warn_fallback(doc, exc)
        return None
    ok, _ = validate_brief(candidate, doc.get("url", ""))
    if ok:
        return candidate
    try:
        retry = api_client.respond(prompt + RETRY_SUFFIX).strip()
    except Exception as exc:
        _warn_fallback(doc, exc)
        return None
    ok, reason = validate_brief(retry, doc.get("url", ""))
    if ok:
        return retry
    _warn_fallback(doc, f"resposta inválida após retry: {reason}")
    return None


def build_brief(doc: dict, api_client=None) -> str:
    """Return ``body + "\\nFonte: " + url`` for one document.

    Pure fallback (no client or failed API) keeps the source language.
    Never raises: an unexpected error degrades to a trimmed extract.
    """
    try:
        url = str((doc or {}).get("url", ""))
        source, already_ptbr = _select_source(doc)
        body: str | None = None
        if already_ptbr:
            body = hard_trim(source)
        elif api_client is not None:
            body = _brief_via_api(doc, source, api_client)
        if body is None:
            body = _extractive_fallback(source)
        return f"{hard_trim(body)}\nFonte: {url}"
    except Exception as exc:  # last-resort guard for export flows
        logger.warning("[API] Falha inesperada no brief de '%s': %s.",
                       _doc_title(doc if isinstance(doc, dict) else {}), exc)
        safe = doc if isinstance(doc, dict) else {}
        return (f"{hard_trim(_normalize(safe.get('summary', '')))}"
                f"\nFonte: {safe.get('url', '')}")


def build_client_from_config(config: dict | None, config_manager):
    """Build an ``APIClient`` from app config, or ``None`` without a key.

    ``config_manager`` is the app's ``ConfigManager`` (keyring access).
    MUST be called from a worker thread: key storage access is I/O and
    must never run on the Tk main thread (R2).
    """
    from core.api_client import APIClient
    from core.config_manager import PROVIDERS

    try:
        cfg = config or {}
        provider = cfg.get("provider", "groq")
        api_key = config_manager.get_api_key(provider)
        if not api_key:
            return None
        info = PROVIDERS.get(provider, {})
        model = cfg.get("model", "") or info.get("default_model", "")
        base_url = ((cfg.get("custom_endpoint", "") or None)
                    if provider == "custom" else None)
        llm = cfg.get("llm_settings", {}) or {}
        return APIClient(
            provider=provider, api_key=api_key, model=model,
            base_url=base_url,
            max_tokens=llm.get("max_tokens", 10000),
            temperature=llm.get("temperature", 0.8),
            top_p=llm.get("top_p", 0.95))
    except Exception:
        logger.debug("Brief API client unavailable", exc_info=True)
        return None
