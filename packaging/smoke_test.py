# packaging/smoke_test.py
"""Smoke test for the frozen build (Windows).

Run 1 (launch): starts ``QuIIN.exe`` from a disjoint working directory with
``QUIIN_DATA_DIR`` scrubbed from the environment; the app must stay alive,
write ``console.txt`` next to itself naming the data root (frozen path
resolution independent of cwd/env) and open its Tk window
(``FindWindowW`` on the app title).

Run 2 (self check): starts the same exe with ``QUIIN_SMOKE=1``; the banner
self-check (keyring/reportlab/docx/customtkinter) must exit 0 and append
``QUIIN SMOKE OK`` to the log.

Usage: ``python smoke_test.py [APP_DIR]`` (defaults to ``dist/QuIIN``).
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
APP_DIR = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "dist" / "QuIIN"
EXE = APP_DIR / "QuIIN.exe"
LOG = APP_DIR / "console.txt"
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


def _run_launch(cwd: str) -> int:
    proc = subprocess.Popen([str(EXE)], cwd=cwd, env=_launch_env())
    try:
        marker_deadline = time.time() + LAUNCH_TIMEOUT_SECONDS
        while time.time() < marker_deadline:
            if proc.poll() is not None:
                print(f"FAIL: QuIIN.exe exited early with code {proc.returncode}")
                return 1
            if str(APP_DIR) in _read_log():
                break
            time.sleep(0.5)
        else:
            print("FAIL: timeout waiting for the data-root log line")
            return 1

        window_deadline = time.time() + WINDOW_TIMEOUT_SECONDS
        while time.time() < window_deadline:
            if proc.poll() is not None:
                print(f"FAIL: QuIIN.exe exited before opening its window (code {proc.returncode})")
                return 1
            if ctypes.windll.user32.FindWindowW(None, APP_TITLE):
                time.sleep(3)
                if proc.poll() is None:
                    return 0
                print(f"FAIL: QuIIN.exe exited right after opening the window (code {proc.returncode})")
                return 1
            time.sleep(0.5)
        print("FAIL: timeout waiting for the QuIIN window title")
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
        print("OK: QuIIN.exe launched (data root next to exe, window shown) and self check passed")
    return code


if __name__ == "__main__":
    sys.exit(main())
