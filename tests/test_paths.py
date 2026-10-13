# tests/test_paths.py
"""Runtime path resolution matrix: dev, frozen, env override, fallback."""
import sys
from pathlib import Path

from core import paths

REPO_ROOT = Path(__file__).resolve().parent.parent


def _enter_frozen(tmp_path, monkeypatch, exe_dir: Path):
    monkeypatch.delenv("QUIIN_DATA_DIR", raising=False)
    exe_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe_dir / "QuIIN.exe"))
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "internal"), raising=False)


def test_dev_mode_uses_repo_root(monkeypatch):
    monkeypatch.delenv("QUIIN_DATA_DIR", raising=False)
    assert paths.is_frozen() is False
    assert paths.resource_root() == REPO_ROOT
    assert paths.data_root() == REPO_ROOT


def test_frozen_writable_uses_exe_dir(tmp_path, monkeypatch):
    exe_dir = tmp_path / "QuIIN"
    _enter_frozen(tmp_path, monkeypatch, exe_dir)
    assert paths.is_frozen() is True
    assert paths.data_root() == exe_dir
    assert paths.resource_root() == tmp_path / "internal"


def test_frozen_readonly_falls_back_to_profile(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    exe_dir = tmp_path / "QuIIN"
    _enter_frozen(tmp_path, monkeypatch, exe_dir)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(paths, "_is_writable",
                        lambda directory: Path(directory) != exe_dir)
    assert paths.data_root() == home / ".newsletter_tool" / "data"


def test_env_override_wins_when_writable(tmp_path, monkeypatch):
    override = tmp_path / "data"
    monkeypatch.setenv("QUIIN_DATA_DIR", str(override))
    assert paths.data_root() == override


def test_env_override_ignored_when_not_writable(tmp_path, monkeypatch):
    monkeypatch.setenv("QUIIN_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setattr(paths, "_is_writable", lambda directory: False)
    assert paths.data_root() == REPO_ROOT


def test_is_writable_true_in_tmp_path(tmp_path):
    assert paths._is_writable(tmp_path) is True


def test_is_writable_false_when_mkdir_fails(tmp_path, monkeypatch):
    def boom(self, *args, **kwargs):
        raise OSError("denied")

    monkeypatch.setattr(Path, "mkdir", boom)
    assert paths._is_writable(tmp_path / "nope") is False


def test_consumers_use_paths_module():
    import core.briefs as briefs
    import core.utils as cu

    assert cu.APP_ROOT == paths.data_root()
    assert cu.TEMPLATE_DIR == str(paths.resource_root() / "template")
    assert briefs.BRIEF_PROMPT_FILE == paths.resource_root() / "template" / "brief_ptbr.txt"


def test_mac_bundle_container_detected(tmp_path):
    exe = tmp_path / "portable" / "QuIIN.app" / "Contents" / "MacOS" / "QuIIN"
    assert paths._mac_app_container(exe) == tmp_path / "portable"


def test_mac_non_bundle_returns_none(tmp_path):
    assert paths._mac_app_container(tmp_path / "bin" / "QuIIN") is None


def test_frozen_mac_bundle_uses_container(tmp_path, monkeypatch):
    monkeypatch.delenv("QUIIN_DATA_DIR", raising=False)
    app_dir = tmp_path / "portable" / "QuIIN.app" / "Contents" / "MacOS"
    app_dir.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "executable", str(app_dir / "QuIIN"))
    assert paths.data_root() == tmp_path / "portable"


def test_frozen_mac_non_bundle_uses_exe_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("QUIIN_DATA_DIR", raising=False)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "executable", str(bin_dir / "QuIIN"))
    assert paths.data_root() == bin_dir


def test_frozen_mac_readonly_container_falls_back_to_profile(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    app_dir = tmp_path / "portable" / "QuIIN.app" / "Contents" / "MacOS"
    app_dir.mkdir(parents=True)
    monkeypatch.delenv("QUIIN_DATA_DIR", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(sys, "executable", str(app_dir / "QuIIN"))
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    monkeypatch.setattr(paths, "_is_writable",
                        lambda directory: Path(directory) != tmp_path / "portable")
    assert paths.data_root() == home / ".newsletter_tool" / "data"
