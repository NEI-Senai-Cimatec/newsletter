# tests/test_briefs.py
"""Unit tests for core/briefs.py (newsletter brief: pt-BR single paragraph)."""
import pytest

from core.briefs import (BRIEF_MAX_CHARS, BRIEF_MAX_WORDS, build_brief,
                         build_client_from_config, hard_trim, validate_brief)


class _StubClient:
    """Deterministic stand-in for APIClient.respond (no network)."""

    def __init__(self, responses=None, error=None, error_on=None):
        self._responses = list(responses or [])
        self._error = error
        self._error_on = error_on
        self.calls: list[str] = []

    def respond(self, prompt, system_prompt=None, response_format=None):
        self.calls.append(prompt)
        if self._error is not None:
            raise self._error
        if self._error_on is not None and len(self.calls) == self._error_on:
            raise RuntimeError("retry boom")
        assert self._responses, "stub ran out of canned responses"
        return self._responses.pop(0)


def _doc(**over):
    base = {
        "title": "IonQ Secures $28 Million DARPA Contract",
        "url": "https://example.com/ionq-darpa",
        "overview": ("IonQ has secured a $28 million extension from DARPA. "
                     "It will deliver 125 optical clocks. "
                     "The program targets radar and geolocation."),
        "summary": "IonQ secured DARPA funding for optical clocks.",
        "key_points": ["$28 million extension", "125 units"],
    }
    base.update(over)
    return base


VALID_PTBR = ("A IonQ garantiu uma extensão de US$ 28 milhões da DARPA para "
              "relógios ópticos, com entrega de 125 unidades.")


# --- validate_brief --------------------------------------------------------

def test_validate_accepts_valid_body():
    ok, reason = validate_brief(VALID_PTBR, "https://example.com/x")
    assert ok, reason


def test_validate_rejects_overlong_body():
    ok, _ = validate_brief("palavra " * 200, "https://example.com/x")
    assert not ok


def test_validate_rejects_too_many_words():
    ok, _ = validate_brief(" ".join(f"w{i}" for i in range(101)),
                           "https://example.com/x")
    assert not ok


def test_validate_rejects_newlines_and_empty():
    ok, _ = validate_brief("linha um\nlinha dois", "https://example.com/x")
    assert not ok
    ok, _ = validate_brief("   ", "https://example.com/x")
    assert not ok


# --- hard_trim --------------------------------------------------------------

def test_hard_trim_respects_both_limits_on_word_boundary():
    # word cap binds with short words: exactly 100 words survive
    out = hard_trim(" ".join(f"w{i}" for i in range(300)))
    assert len(out) <= BRIEF_MAX_CHARS
    assert len(out.split()) == BRIEF_MAX_WORDS
    # char cap binds with long words: cut lands on a word boundary
    text = " ".join(f"palavra{i:03d}" for i in range(300))
    out = hard_trim(text)
    assert len(out) <= BRIEF_MAX_CHARS
    assert len(out.split()) <= BRIEF_MAX_WORDS
    assert text[len(out)] == " "  # cut exactly at a word boundary


def test_hard_trim_short_text_untouched():
    assert hard_trim("curto e direto") == "curto e direto"


# --- _select_source priority (via build_brief without API) -------------------

def test_prefers_existing_ptbr_fields_and_skips_api():
    client = _StubClient(responses=["NUNCA USADO"])
    doc = _doc(summary_ptbr="Resumo pronto em português, curto.")
    out = build_brief(doc, client)
    assert client.calls == []
    assert out.startswith("Resumo pronto em português, curto.")
    assert out.endswith("Fonte: https://example.com/ionq-darpa")


def test_falls_back_to_title_and_key_points_without_api():
    out = build_brief({"title": "Título", "key_points": ["ponto um"],
                       "url": "https://example.com/u"})
    assert "Título" in out and "ponto um" in out
    assert out.endswith("Fonte: https://example.com/u")


# --- build_brief with API ----------------------------------------------------

def test_api_success_returns_single_paragraph_with_source():
    client = _StubClient(responses=[VALID_PTBR])
    out = build_brief(_doc(), client)
    body, _, source = out.rpartition("\n")
    assert "\n" not in body
    assert source == "Fonte: https://example.com/ionq-darpa"
    assert len(client.calls) == 1


def test_api_invalid_then_retry_success():
    client = _StubClient(responses=["primeira\ncom quebra", VALID_PTBR])
    out = build_brief(_doc(), client)
    assert len(client.calls) == 2
    assert out.startswith(VALID_PTBR)


def test_api_failure_falls_back_and_never_raises():
    client = _StubClient(error=RuntimeError("boom"))
    out = build_brief(_doc(), client)
    assert out.endswith("Fonte: https://example.com/ionq-darpa")
    body = out.rpartition("\n")[0]
    assert "\n" not in body
    assert len(body) <= BRIEF_MAX_CHARS
    assert len(body.split()) <= BRIEF_MAX_WORDS


def test_api_invalid_twice_falls_back():
    client = _StubClient(responses=["x" * 900, "y" * 900])
    out = build_brief(_doc(), client)
    assert len(client.calls) == 2
    body = out.rpartition("\n")[0]
    assert len(body) <= BRIEF_MAX_CHARS


def test_fallback_is_deterministic():
    doc = _doc()
    assert build_brief(doc) == build_brief(doc)


def test_brief_always_ends_with_source_line():
    docs = [_doc(), {"title": "Só título", "url": "https://example.com/s"},
            _doc(summary_ptbr="pt pronto")]
    for doc in docs:
        url = doc.get("url", "")
        assert build_brief(doc).endswith(f"Fonte: {url}")


def test_limits_constants_match_sdd():
    assert BRIEF_MAX_CHARS == 700
    assert BRIEF_MAX_WORDS == 100


def test_fallback_stops_at_first_overlong_sentence():
    doc = _doc(overview="Sentence one here. " + "word " * 200 + "Last.")
    body = build_brief(doc).rpartition("\n")[0]
    assert body == "Sentence one here."


def test_fallback_trims_single_overlong_sentence():
    doc = _doc(overview="z" * 900)
    body = build_brief(doc).rpartition("\n")[0]
    assert len(body) == BRIEF_MAX_CHARS


def test_empty_source_still_appends_source_line():
    out = build_brief({"url": "https://example.com/e"})
    assert out.endswith("Fonte: https://example.com/e")


def test_unexpected_doc_shape_never_raises():
    assert build_brief(None).endswith("Fonte: ")


def test_retry_error_falls_back():
    client = _StubClient(responses=["bad\nresponse"], error_on=2)
    out = build_brief(_doc(), client)
    assert len(client.calls) == 2
    assert out.endswith("Fonte: https://example.com/ionq-darpa")


def test_missing_template_falls_back(monkeypatch, tmp_path):
    monkeypatch.setattr("core.briefs.BRIEF_PROMPT_FILE",
                        tmp_path / "missing.txt")
    client = _StubClient(responses=[VALID_PTBR])
    out = build_brief(_doc(), client)
    assert client.calls == []  # no API without the prompt file
    assert out.endswith("Fonte: https://example.com/ionq-darpa")


class _KeyStore:
    def __init__(self, keys):
        self._keys = keys

    def get_api_key(self, provider):
        return self._keys.get(provider)


def test_build_client_none_without_key():
    assert build_client_from_config({"provider": "groq"},
                                    _KeyStore({})) is None


def test_build_client_from_config_with_key():
    client = build_client_from_config({"provider": "groq", "model": ""},
                                      _KeyStore({"groq": "k"}))
    assert client.provider == "groq"
    assert client.model == "llama-3.3-70b-versatile"


def test_build_client_unknown_provider_returns_none():
    assert build_client_from_config({"provider": "nope"},
                                    _KeyStore({"nope": "k"})) is None
