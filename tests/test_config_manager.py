"""Tests for core.config_manager (TDD: written before implementation)."""
import json
from pathlib import Path

import pytest

from core.config_manager import PROVIDERS, ConfigManager


@pytest.fixture()
def manager(tmp_path: Path) -> ConfigManager:
    return ConfigManager(config_dir=tmp_path / ".newsletter_tool")


def test_load_returns_defaults_when_no_config_file(manager: ConfigManager, tmp_path: Path) -> None:
    config = manager.load()
    assert config == ConfigManager.DEFAULT_CONFIG
    # load() must be read-only: it must not create anything on disk.
    assert not (tmp_path / ".newsletter_tool").exists()


def test_save_creates_user_space_dir_and_roundtrips(manager: ConfigManager) -> None:
    config = manager.load()
    config["provider"] = "openai"
    config["model"] = "gpt-4o-mini"
    config["portals"]["quantamagazine"] = True
    config["scraper_settings"]["min_date"] = "2026-09-01"
    manager.save(config)

    assert manager.config_dir.is_dir()
    reloaded = ConfigManager(config_dir=manager.config_dir).load()
    assert reloaded == config


def test_load_merges_new_defaults_over_old_file(manager: ConfigManager) -> None:
    manager.config_dir.mkdir(parents=True)
    manager.config_file.write_text(json.dumps({"provider": "nvidia"}), encoding="utf-8")

    config = manager.load()

    assert config["provider"] == "nvidia"
    assert config["model"] == ConfigManager.DEFAULT_CONFIG["model"]
    assert config["portals"] == ConfigManager.DEFAULT_CONFIG["portals"]
    assert "min_date" in config["scraper_settings"]


def test_load_ignores_corrupt_file(manager: ConfigManager) -> None:
    manager.config_dir.mkdir(parents=True)
    manager.config_file.write_text("{not json", encoding="utf-8")
    assert manager.load() == ConfigManager.DEFAULT_CONFIG


def test_api_key_roundtrip(manager: ConfigManager) -> None:
    assert manager.get_api_key("test_provider") is None
    manager.set_api_key("test_provider", "secret-123")
    assert manager.get_api_key("test_provider") == "secret-123"
    manager.delete_api_key("test_provider")
    assert manager.get_api_key("test_provider") is None


def test_api_key_fallback_when_keyring_unavailable(
    manager: ConfigManager, monkeypatch: pytest.MonkeyPatch
) -> None:
    import core.config_manager as cm

    class BrokenKeyring:
        def __getattr__(self, name: str):  # noqa: ANN204
            raise RuntimeError("no backend")

    monkeypatch.setattr(cm, "keyring", BrokenKeyring())

    manager.set_api_key("groq", "fallback-secret")
    assert manager.get_api_key("groq") == "fallback-secret"
    assert manager.credentials_file.exists()
    manager.delete_api_key("groq")
    assert manager.get_api_key("groq") is None


def test_providers_constant_structure() -> None:
    for key in ("groq", "openrouter", "nvidia", "openai", "custom"):
        assert key in PROVIDERS
        for field in ("name", "base_url", "default_model", "models", "docs_url"):
            assert field in PROVIDERS[key]
    assert PROVIDERS["groq"]["base_url"] == "https://api.groq.com/openai/v1"
