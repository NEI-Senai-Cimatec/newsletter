"""Tests for core.api_client (TDD: written before implementation)."""
from types import SimpleNamespace

import httpx2 as httpx  # openai>=3 uses httpx2 for Request/Response objects
import openai
import pytest

import core.api_client as ac
from core.api_client import (
    APIAuthenticationError,
    APIClient,
    APIConnectionError,
    APIError,
    APIRateLimitError,
)
from core.config_manager import PROVIDERS


class _FakeResponse:
    def __init__(self, content: str) -> None:
        self.choices = [SimpleNamespace(message=SimpleNamespace(content=content))]


def _scripted_openai(script: list):
    """Build a fake OpenAI class; create() pops from ``script`` (items or exceptions)."""

    class _FakeCompletions:
        def __init__(self) -> None:
            self.calls: list = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            item = script.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item

    class _FakeChat:
        def __init__(self) -> None:
            self.completions = _FakeCompletions()

    class _FakeOpenAI:
        last_instance = None

        def __init__(self, **kwargs) -> None:
            self.init_kwargs = kwargs
            self.chat = _FakeChat()
            _FakeOpenAI.last_instance = self

    _FakeOpenAI.last_instance = None
    return _FakeOpenAI


def _http_error(cls, status: int, message: str):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(status, request=request, json={"error": {"message": message}})
    return cls(message, response=response, body=None)


@pytest.fixture()
def patch_openai(monkeypatch: pytest.MonkeyPatch):
    def _patch(script: list):
        fake = _scripted_openai(list(script))
        monkeypatch.setattr(ac, "OpenAI", fake)
        return fake

    return _patch


def test_constructor_resolves_base_url_and_default_model(patch_openai) -> None:
    fake = patch_openai([_FakeResponse("hi")])
    client = APIClient(provider="groq", api_key="k", model="")
    assert client.model == PROVIDERS["groq"]["default_model"]
    assert fake.last_instance.init_kwargs["base_url"] == PROVIDERS["groq"]["base_url"]
    assert fake.last_instance.init_kwargs["api_key"] == "k"


def test_constructor_maps_legacy_and_default_settings(patch_openai) -> None:
    fake = patch_openai([_FakeResponse("x")])
    client = APIClient(provider="groq", api_key="k", model="m", maxTokens=10000, topP=0.95)
    assert client.respond("hello") == "x"
    call = fake.last_instance.chat.completions.calls[0]
    assert call["max_tokens"] == 10000
    assert call["top_p"] == 0.95
    assert call["temperature"] == 0.8
    assert call["messages"] == [{"role": "user", "content": "hello"}]


def test_constructor_rejects_missing_key_and_bad_provider(patch_openai) -> None:
    patch_openai([])
    with pytest.raises(ValueError):
        APIClient(provider="groq", api_key="", model="m")
    with pytest.raises(ValueError):
        APIClient(provider="custom", api_key="k", model="m")  # no base_url
    with pytest.raises(ValueError):
        APIClient(provider="nope", api_key="k", model="m")


def test_respond_includes_system_prompt(patch_openai) -> None:
    fake = patch_openai([_FakeResponse("ok")])
    client = APIClient(provider="openai", api_key="k", model="gpt-4o-mini")
    assert client.respond("ping", system_prompt="sys") == "ok"
    call = fake.last_instance.chat.completions.calls[0]
    assert call["messages"] == [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "ping"},
    ]


def test_respond_wraps_raw_schema_and_falls_back_to_json_object(patch_openai) -> None:
    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    err = _http_error(openai.BadRequestError, 400, "response_format json_schema not supported")
    fake = patch_openai([err, _FakeResponse('{"a": "1"}')])
    client = APIClient(
        provider="custom", api_key="k", model="m", base_url="https://x.test/v1"
    )
    assert client.respond("p", response_format=schema) == '{"a": "1"}'
    calls = fake.last_instance.chat.completions.calls
    assert len(calls) == 2
    assert calls[0]["response_format"] == {
        "type": "json_schema",
        "json_schema": {"name": "article_parse", "schema": schema},
    }
    assert calls[1]["response_format"] == {"type": "json_object"}


def test_respond_drops_format_after_rejections(patch_openai) -> None:
    script = [
        _http_error(openai.BadRequestError, 400, "response_format unsupported"),
        _http_error(openai.BadRequestError, 400, "json_object unsupported"),
        _FakeResponse("plain"),
    ]
    fake = patch_openai(script)
    client = APIClient(
        provider="custom", api_key="k", model="m", base_url="https://x.test/v1"
    )
    assert client.respond("p", response_format={"type": "object"}) == "plain"
    calls = fake.last_instance.chat.completions.calls
    assert len(calls) == 3
    assert "response_format" not in calls[2]


def test_respond_retries_with_max_completion_tokens(patch_openai) -> None:
    err = _http_error(
        openai.BadRequestError,
        400,
        "'max_tokens' is not supported with this model, use 'max_completion_tokens'",
    )
    fake = patch_openai([err, _FakeResponse("ok")])
    client = APIClient(provider="openai", api_key="k", model="gpt-5-mini")
    assert client.respond("p") == "ok"
    calls = fake.last_instance.chat.completions.calls
    assert calls[0]["max_tokens"] == 10000
    assert "max_tokens" not in calls[1]
    assert calls[1]["max_completion_tokens"] == 10000


def test_respond_translates_auth_rate_and_connection_errors(patch_openai) -> None:
    conn_err = openai.APIConnectionError(
        message="down", request=httpx.Request("POST", "https://x.test/v1")
    )
    cases = [
        (_http_error(openai.AuthenticationError, 401, "bad key"), APIAuthenticationError),
        (_http_error(openai.RateLimitError, 429, "slow down"), APIRateLimitError),
        (conn_err, APIConnectionError),
    ]
    for err, exc in cases:
        fake = patch_openai([err])
        client = APIClient(provider="groq", api_key="k", model="m")
        with pytest.raises(exc):
            client.respond("p")


def test_test_connection_success_and_failure(patch_openai) -> None:
    patch_openai([_FakeResponse("ok")])
    client = APIClient(provider="groq", api_key="k", model="")
    ok, msg = client.test_connection()
    assert ok is True
    assert client.model in msg

    patch_openai([_http_error(openai.AuthenticationError, 401, "bad key")])
    client2 = APIClient(provider="groq", api_key="bad", model="m")
    ok, msg = client2.test_connection()
    assert ok is False
    assert msg


def test_custom_provider_invalid_url_raises_connection_error() -> None:
    client = APIClient(
        provider="custom", api_key="k", model="m", base_url="http://127.0.0.1:9/v1",
        timeout=5,  # bound the wait for the refused connection
    )
    with pytest.raises(APIConnectionError):
        client.respond("hello")
