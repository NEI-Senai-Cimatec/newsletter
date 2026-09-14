# core/api_client.py
"""Unified LLM client over OpenAI-compatible HTTP APIs.

Replaces the local LM Studio integration (``lmstudio.llm`` /
``model.respond``). All target providers (Groq, OpenRouter, NVIDIA NIM,
OpenAI, plus any custom endpoint) implement ``POST /chat/completions``,
so a single client covers them all.
"""
from __future__ import annotations

import logging
from typing import Any

import openai
from openai import OpenAI

from core.config_manager import PROVIDERS

logger = logging.getLogger(__name__)

SCHEMA_NAME = "article_parse"
DEFAULT_TIMEOUT = 180.0


class APIError(Exception):
    """Base class for all API client errors."""


class APIConnectionError(APIError):
    """Could not reach the provider endpoint."""


class APIAuthenticationError(APIError):
    """The API key was rejected (invalid, expired, or missing)."""


class APIRateLimitError(APIError):
    """Provider rate limit exceeded."""


class APIClient:
    """Sends prompts to any OpenAI-compatible provider.

    Drop-in replacement for ``lms.llm()``: ``respond()`` returns the
    model's text directly (equivalent of the old ``result.content``).
    """

    def __init__(
        self,
        provider: str,
        api_key: str,
        model: str,
        base_url: str | None = None,
        **llm_settings: Any,
    ) -> None:
        """Args:
            provider: Provider key (e.g. ``"groq"``, ``"custom"``).
            api_key: Provider API key.
            model: Model name; falls back to the provider default when empty.
            base_url: Required when ``provider == "custom"``; otherwise the
                provider default is used unless overridden here.
            **llm_settings: ``max_tokens`` (or legacy ``maxTokens``),
                ``temperature``, ``top_p`` (or legacy ``topP``), ``timeout``.
        Raises:
            ValueError: On unknown provider, missing key/model/URL.
        """
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider: {provider!r}")
        if not api_key:
            raise ValueError("An API key is required")
        info = PROVIDERS[provider]
        resolved_model = model or info["default_model"]
        if not resolved_model:
            raise ValueError(f"A model name is required for provider {provider!r}")
        resolved_url = (base_url if base_url is not None else info["base_url"]).strip()
        if provider == "custom" and not resolved_url:
            raise ValueError("A base_url is required for the custom provider")
        resolved_url = resolved_url.rstrip("/")

        self.provider = provider
        self.model = resolved_model
        self.base_url = resolved_url
        self.max_tokens = int(llm_settings.get("max_tokens", llm_settings.get("maxTokens", 10000)))
        self.temperature = float(llm_settings.get("temperature", 0.8))
        self.top_p = float(llm_settings.get("top_p", llm_settings.get("topP", 0.95)))
        self.timeout = float(llm_settings.get("timeout", DEFAULT_TIMEOUT))

        self._client = OpenAI(
            api_key=api_key,
            base_url=resolved_url,
            timeout=self.timeout,
            max_retries=0,  # retries are handled by the pipeline with logging
        )

    def respond(
        self,
        prompt: str,
        system_prompt: str | None = None,
        response_format: dict | None = None,
    ) -> str:
        """Send ``prompt`` to the model and return its text response.

        ``response_format`` may be a raw JSON Schema (as stored in
        ``template/*.json``) or a full OpenAI response-format object.
        Providers that reject structured output are retried automatically
        with ``json_object`` and then with plain text, trusting the
        regex/JSON extraction already present in ``core.utils``.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        format_attempts = self._format_attempts(response_format)
        token_key: str = "max_tokens"
        index = 0
        while index < len(format_attempts):
            current_format = format_attempts[index]
            try:
                return self._create(messages, current_format, token_key)
            except openai.BadRequestError as e:
                text = str(e).lower()
                if (
                    token_key == "max_tokens"
                    and "max_tokens" in text
                    and "max_completion_tokens" in text
                ):
                    logger.warning("Provider requires max_completion_tokens; retrying")
                    token_key = "max_completion_tokens"
                    continue
                if current_format is not None and (
                    "response_format" in text or "json_schema" in text or "json_object" in text
                ):
                    logger.warning(f"Structured output rejected ({e}); simplifying format")
                    index += 1
                    continue
                raise self._translate(e) from e
            except openai.OpenAIError as e:
                raise self._translate(e) from e
        raise APIError("No response format attempts left")  # pragma: no cover

    def test_connection(self) -> tuple[bool, str]:
        """Send a minimal prompt; return ``(True, msg)`` or ``(False, msg)``."""
        try:
            self.respond("Reply with exactly: ok")
        except APIError as e:
            return False, f"Erro: {e}"
        return True, f"Conexão OK — Modelo: {self.model}"

    def _create(self, messages: list, response_format: dict | None, token_key: str) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "top_p": self.top_p,
            token_key: self.max_tokens,
        }
        if response_format is not None:
            kwargs["response_format"] = response_format
        try:
            completion = self._client.chat.completions.create(**kwargs)
            content = completion.choices[0].message.content or ""
        except (AttributeError, IndexError, KeyError) as e:
            raise APIError(f"Malformed API response: {e}")
        return content.strip()

    @staticmethod
    def _format_attempts(response_format: dict | None) -> list:
        if response_format is None:
            return [None]
        if response_format.get("type") in ("json_schema", "json_object", "text"):
            first = response_format
            rest = [] if first["type"] == "json_object" else [{"type": "json_object"}]
            return [first, *rest, None]
        wrapped = {
            "type": "json_schema",
            "json_schema": {"name": SCHEMA_NAME, "schema": response_format},
        }
        return [wrapped, {"type": "json_object"}, None]

    @staticmethod
    def _translate(error: openai.OpenAIError) -> APIError:
        if isinstance(error, openai.APIConnectionError):
            return APIConnectionError(str(error))
        if isinstance(error, openai.AuthenticationError):
            return APIAuthenticationError(str(error))
        if isinstance(error, openai.RateLimitError):
            return APIRateLimitError(str(error))
        return APIError(str(error))
