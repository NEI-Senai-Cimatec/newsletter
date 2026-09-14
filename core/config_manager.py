# core/config_manager.py
"""Persistent user configuration and secure API-key storage.

Everything lives in user-space (no admin rights required):
- General settings: JSON file at ``~/.newsletter_tool/config.json``.
- API keys: OS-native vault via ``keyring``; if keyring has no usable
  backend, falls back to ``~/.newsletter_tool/.credentials`` (JSON,
  owner-only permissions).
"""
from __future__ import annotations

import copy
import json
import logging
import os
from pathlib import Path
from typing import Any

import keyring

logger = logging.getLogger(__name__)

SERVICE_NAME = "newsletter_tool"

PROVIDERS: dict[str, dict[str, Any]] = {
    "groq": {
        "name": "Groq",
        "base_url": "https://api.groq.com/openai/v1",
        "default_model": "llama-3.3-70b-versatile",
        "models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "gemma2-9b-it",
            "mixtral-8x7b-32768",
        ],
        "docs_url": "https://console.groq.com/keys",
    },
    "openrouter": {
        "name": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "default_model": "meta-llama/llama-3.3-70b-instruct",
        "models": [
            "meta-llama/llama-3.3-70b-instruct",
            "google/gemma-2-27b-it",
            "mistralai/mistral-large-latest",
            "qwen/qwen-2.5-72b-instruct",
        ],
        "docs_url": "https://openrouter.ai/keys",
    },
    "nvidia": {
        "name": "NVIDIA NIM",
        "base_url": "https://integrate.api.nvidia.com/v1",
        "default_model": "meta/llama-3.3-70b-instruct",
        "models": [
            "meta/llama-3.3-70b-instruct",
            "meta/llama-3.1-405b-instruct",
            "google/gemma-2-27b-it",
            "mistralai/mistral-large-2-instruct",
        ],
        "docs_url": "https://build.nvidia.com/explore/discover",
    },
    "openai": {
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "default_model": "gpt-4o-mini",
        "models": [
            "gpt-4o-mini",
            "gpt-4o",
            "gpt-4-turbo",
        ],
        "docs_url": "https://platform.openai.com/api-keys",
    },
    "custom": {
        "name": "Endpoint Personalizado",
        "base_url": "",
        "default_model": "",
        "models": [],
        "docs_url": "",
    },
}


class ConfigManager:
    """Loads/saves user settings and stores API keys securely."""

    CONFIG_DIR = Path.home() / ".newsletter_tool"
    CONFIG_FILE = CONFIG_DIR / "config.json"
    CREDENTIALS_FILE = CONFIG_DIR / ".credentials"

    DEFAULT_CONFIG: dict[str, Any] = {
        "provider": "groq",
        "model": "",
        "custom_endpoint": "",
        "portals": {
            "thequantuminsider": True,
            "quantamagazine": False,
            "quantumzeitgeist": False,
            "insidequantumtechnology": False,
        },
        "llm_settings": {
            "max_tokens": 10000,
            "temperature": 0.8,
            "top_p": 0.95,
        },
        "scraper_settings": {
            "ignore_cache": False,
            "debug": False,
            "min_date": "",
        },
        "language": "en",
        "last_run": "",
    }

    def __init__(self, config_dir: Path | str | None = None) -> None:
        """Args:
            config_dir: Override for the settings directory (used by tests).
                Defaults to ``~/.newsletter_tool``.
        """
        self.config_dir = Path(config_dir) if config_dir is not None else self.CONFIG_DIR
        self.config_file = self.config_dir / "config.json"
        self.credentials_file = self.config_dir / ".credentials"

    def load(self) -> dict[str, Any]:
        """Return the stored config merged over the defaults.

        Never touches the disk (read-only): a missing or corrupt file
        yields the default configuration.
        """
        config: dict[str, Any] = copy.deepcopy(self.DEFAULT_CONFIG)
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                stored = json.load(f)
        except FileNotFoundError:
            return config
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Ignoring unreadable config file {self.config_file}: {e}")
            return config
        if not isinstance(stored, dict):
            logger.warning(f"Ignoring invalid config file {self.config_file}: not an object")
            return config
        return self._merge_defaults(config, stored)

    def save(self, config: dict[str, Any]) -> None:
        """Persist ``config`` to disk, creating the directory if needed."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved configuration to {self.config_file}")

    def get_api_key(self, provider: str) -> str | None:
        """Return the stored API key for ``provider``, or None."""
        try:
            stored = keyring.get_password(SERVICE_NAME, provider)
        except Exception as e:  # No usable keyring backend: use fallback.
            logger.warning(f"keyring unavailable, using fallback credentials file: {e}")
            return self._fallback_credentials().get(provider)
        if stored is not None:
            return stored
        return self._fallback_credentials().get(provider)

    def set_api_key(self, provider: str, key: str) -> None:
        """Store the API key for ``provider`` (keyring, else fallback file)."""
        try:
            keyring.set_password(SERVICE_NAME, provider, key)
            return
        except Exception as e:
            logger.warning(f"keyring unavailable, using fallback credentials file: {e}")
        creds = self._fallback_credentials()
        creds[provider] = key
        self._save_fallback_credentials(creds)

    def delete_api_key(self, provider: str) -> None:
        """Remove the stored API key for ``provider`` (both storages)."""
        try:
            keyring.delete_password(SERVICE_NAME, provider)
        except Exception as e:
            logger.debug(f"keyring delete skipped: {e}")
        creds = self._fallback_credentials()
        if provider in creds:
            del creds[provider]
            self._save_fallback_credentials(creds)

    @staticmethod
    def _merge_defaults(defaults: dict[str, Any], stored: dict[str, Any]) -> dict[str, Any]:
        """Deep-merge ``stored`` over ``defaults`` (unknown keys kept)."""
        merged = copy.deepcopy(defaults)
        for key, value in stored.items():
            if isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = ConfigManager._merge_defaults(merged[key], value)
            else:
                merged[key] = value
        return merged

    def _fallback_credentials(self) -> dict[str, str]:
        """Read the fallback credentials file (empty dict if missing)."""
        try:
            with open(self.credentials_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return {}

    def _save_fallback_credentials(self, creds: dict[str, str]) -> None:
        """Write the fallback credentials file with owner-only permissions."""
        self.config_dir.mkdir(parents=True, exist_ok=True)
        with open(self.credentials_file, "w", encoding="utf-8") as f:
            json.dump(creds, f, indent=2)
        try:
            os.chmod(self.credentials_file, 0o600)
        except OSError as e:
            logger.warning(f"Could not restrict permissions on {self.credentials_file}: {e}")
