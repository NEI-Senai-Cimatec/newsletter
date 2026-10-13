# packaging/smoke_test.py
"""Smoke test for the frozen build (Windows, Linux and macOS).

Run 1 (launch): starts the built executable from a disjoint working
directory with ``QUIIN_DATA_DIR`` scrubbed from the environment; the app
must stay alive and write ``console.txt`` in the expected data root
(Windows/Linux: next to the executable; macOS: next to ``QuIIN.app``)
naming that root. On Windows it must also open its window
(``FindWindowW`` on the app title); on Linux/macOS the run-2 self check
proves the GUI stack instead.

Run 2 (self check): starts the same executable with ``QUIIN_SMOKE=1``;
the banner self-check (keyring/reportlab/docx/real Tk window) must exit 0
and append ``QUIIN SMOKE OK`` to the log. On headless Linux run the whole
script under ``xvfb-run``.

Exit code 0 on success, 1 on failure. Developer/CI helper — not shipped.
"""
from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_TARGETS = {
    "win32": (ROOT / "dist" / "QuIIN" / "QuIIN.exe", ROOT / "dist" / "QuIIN"),
    "darwin": (ROOT / "dist" / "QuIIN.app" / "Contents" / "MacOS" / "QuIIN",
               ROOT / "dist"),
}
EXE, DATA_ROOT = _TARGETS.get(
    sys.platform, (ROOT / "dist" / "QuIIN" / "QuIIN", ROOT / "dist" / "QuIIN"))
LOG = DATA_ROOT / "console.txt"
APP_TITLE = "GLOBAL QUANTUM INTELLIGENCE – QuIIN"
LAUNCH_TIMEOUT_SECONDS = 180
SMOKE_TIMEOUT_SECONDS = 60
WINDOW_TIMEOUT_SECONDS = 15


def _launch_env() -> dict:
    env = os.environ.copy()
    env.pop("QUIIN_DATA_DIR", None)
    return env


def _read_log() -> str:
    try:
        return LOG.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _window_shown() -> bool:
    if sys.platform != "win32":
        return True
    return bool(ctypes.windll.user32.FindWindowW(None, APP_TITLE))


def _run_launch(cwd: str) -> int:
    proc = subprocess.Popen([str(EXE)], cwd=cwd, env=_launch_env())
    try:
        marker_deadline = time.time() + LAUNCH_TIMEOUT_SECONDS
        while time.time() < marker_deadline:
            if proc.poll() is not None:
                print(f"FAIL: {EXE.name} exited early with code {proc.returncode}")
                return 1
            if str(DATA_ROOT) in _read_log():
                break
            time.sleep(0.5)
        else:
            print("FAIL: timeout waiting for the data-root log line")
            return 1

        if sys.platform == "win32":
            window_deadline = time.time() + WINDOW_TIMEOUT_SECONDS
            while time.time() < window_deadline:
                if proc.poll() is not None:
                    print(f"FAIL: {EXE.name} exited before opening its window (code {proc.returncode})")
                    return 1
                if _window_shown():
                    break
                time.sleep(0.5)
            else:
                print("FAIL: timeout waiting for the QuIIN window title")
                return 1

        time.sleep(3)
        if proc.poll() is None:
            return 0
        print(f"FAIL: {EXE.name} exited right after startup (code {proc.returncode})")
        return 1
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


def _run_self_check(cwd: str) -> int:
    env = _launch_env()
    env["QUIIN_SMOKE"] = "1"
    proc = subprocess.Popen([str(EXE)], cwd=cwd, env=env)
    try:
        code = proc.wait(timeout=SMOKE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        print("FAIL: self check did not exit in time")
        return 1
    if code != 0:
        print(f"FAIL: self check exit code {code}")
        return 1
    if "QUIIN SMOKE OK" not in _read_log():
        print("FAIL: self check did not report OK in the log")
        return 1
    return 0


def main() -> int:
    if not EXE.is_file():
        print(f"FAIL: {EXE} not found")
        return 1
    if LOG.exists():
        LOG.unlink()
    with tempfile.TemporaryDirectory(prefix="quiin-smoke-") as cwd:
        code = _run_launch(cwd)
        if code == 0:
            code = _run_self_check(cwd)
    if code == 0:
        print(f"OK: {EXE.name} launched (data root {DATA_ROOT}) and self check passed")
    return code


if __name__ == "__main__":
    sys.exit(main())
