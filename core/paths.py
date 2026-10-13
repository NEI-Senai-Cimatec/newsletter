# core/paths.py
"""Runtime path resolution for dev checkouts and frozen (PyInstaller) builds.

Resources (templates/prompts) are read-only bundled data; in a frozen app
they are extracted to ``sys._MEIPASS``. Writable data lives next to the exe
when that folder is writable (portable folder) and otherwise falls back to
the user profile (``~/.newsletter_tool/data``). In a dev checkout both roots
are the repository root, preserving every current path.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    """True when running from a PyInstaller bundle."""
    return bool(getattr(sys, "frozen", False))


def resource_root() -> Path:
    """Root for read-only bundled resources (templates/prompts)."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS"))
    return _REPO_ROOT


def data_root() -> Path:
    """Root for writable runtime data.

    Precedence: writable ``QUIIN_DATA_DIR`` -> frozen: writable folder of the
    executable, else ``~/.newsletter_tool/data`` -> dev: repository root.
    """
    override = os.environ.get("QUIIN_DATA_DIR", "").strip()
    if override and _is_writable(Path(override)):
        return Path(override)
    if is_frozen():
        exe_dir = Path(sys.executable).resolve().parent
        if _is_writable(exe_dir):
            return exe_dir
        return Path.home() / ".newsletter_tool" / "data"
    return _REPO_ROOT


def _is_writable(directory: Path) -> bool:
    """True when *directory* exists (or can be created) and accepts a file write."""
    try:
        directory.mkdir(parents=True, exist_ok=True)
        probe = directory / f".quiin_write_probe_{os.getpid()}"
        probe.write_text("", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False
