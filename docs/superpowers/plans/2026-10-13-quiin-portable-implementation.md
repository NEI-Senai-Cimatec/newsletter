# QuIIN Portable Distribution Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship QuIIN as a portable Windows folder (`dist/QuIIN/` with `QuIIN.exe`) built by PyInstaller, with writable data next to the exe (falling back to the user profile), without changing dev behavior.

**Architecture:** A new `core/paths.py` resolves two roots: `resource_root()` (read-only bundled files: `sys._MEIPASS` when frozen, repo root in dev) and `data_root()` (writable state: exe folder when writable, else `~/.newsletter_tool/data`, repo root in dev). `core/utils.py`, `core/briefs.py`, `core/preflight.py` and `main.py` consume it. PyInstaller `onedir` spec + PowerShell build script + launch smoke test produce and verify the zip.

**Tech Stack:** Python 3.14.3 (`.venv`), PyInstaller >= 6.15, pytest, PowerShell 5.1 (`Compress-Archive`).

**Spec:** `docs/superpowers/specs/2026-10-13-quiin-portable-design.md`

## Global Constraints

- All Python/pytest/pip commands use `.venv\Scripts\python` (system Python lacks deps). Example: `.venv\Scripts\python -m pytest tests -q`.
- Do NOT commit: the human partner reviews and commits.
- Dev behavior must stay byte-identical: existing suite (157 passed) stays green; in dev `APP_ROOT` = repo root and `TEMPLATE_DIR` under it (`tests/test_utils.py:74-79` pins this).
- New writes only next to the exe, under `~/.newsletter_tool/`, or a user-chosen folder. Nothing in Program Files. No admin rights.
- `core/utils.py` is touched only for the `APP_ROOT`/`TEMPLATE_DIR` redirection (written justification: frozen/portable build, README §11).
- Templates/prompts are bundled read-only data; frozen reads resolve via `sys._MEIPASS`.
- `QUIIN_DATA_DIR` env var: used only when the pointed path is writable; otherwise silently ignored.
- `requirements-build.txt` pins `pyinstaller>=6.15` (first PyInstaller line with Python 3.14 support).

## Review Focus

- Running `QuIIN.exe` from a read-only folder: must fall back to `~/.newsletter_tool/data` and still start (log file + data writes land there).
- `QUIIN_DATA_DIR` pointing to a non-writable location: ignored; app still starts with the normal hybrid resolution.
- First frozen launch with no `~/.newsletter_tool/data` present: `main.py` must create the log directory before opening `console.txt` (FileHandler does not create parents).
- Launching from a different working directory (shortcut, terminal elsewhere): data still resolves next to `sys.executable`, templates from `sys._MEIPASS` — resolution must never use `os.getcwd()`.
- Stale artifacts: `--clean` build and pre-smoke `console.txt` deletion so the smoke proves *this* build started.

---

## File Structure

- `core/paths.py` (new) — runtime path resolution only; imports `os`, `sys`, `pathlib`. No other core imports.
- `tests/test_paths.py` (new) — dev/frozen/env-override matrix + `_is_writable` + consumer wiring.
- `core/utils.py` (modify lines 30-33) — `APP_ROOT`/`TEMPLATE_DIR` from `core.paths`; nothing else.
- `core/briefs.py` (modify line 27) — prompt path from `resource_root()`.
- `core/preflight.py` (modify lines 146-148) — default `base_dir`/`template_dir` from `core.paths`.
- `main.py` (modify lines 14-25) — log dir from `data_root()`, created before `FileHandler`.
- `requirements-build.txt` (new) — PyInstaller pin.
- `packaging/quiin.spec` (new) — PyInstaller onedir build definition.
- `packaging/smoke_test.py` (new) — launches the frozen exe, waits for `console.txt`, terminates it.
- `packaging/build_portable.ps1` (new) — install build deps, build, smoke, zip.
- `.gitignore` (modify) — ignore `/build/` and `/dist/`.
- `README.md` (modify §4) — portable build/distribution instructions.

---

### Task 1: `core/paths.py` (TDD)

**Files:**
- Create: `core/paths.py`
- Test: `tests/test_paths.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `paths.is_frozen() -> bool`
  - `paths.resource_root() -> Path`
  - `paths.data_root() -> Path`
  - `paths._is_writable(directory: Path) -> bool` (probe helper; tests monkeypatch it)
  - Semantics: `data_root()` precedence = writable `QUIIN_DATA_DIR` → frozen+writable exe dir → frozen fallback `Path.home()/".newsletter_tool"/"data"` → dev repo root. `resource_root()` = `Path(sys._MEIPASS)` frozen, repo root dev. No caching (import-time/one-shot calls; keeps monkeypatching trivial).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_paths.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_paths.py -q`
Expected: FAIL/ERROR with `ModuleNotFoundError: No module named 'core.paths'` (and `test_consumers_use_paths_module` failing on the briefs path once paths exists — it must fail before Task 2 too).

- [ ] **Step 3: Implement `core/paths.py`**

```python
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

    Precedence: writable ``QUIIN_DATA_DIR`` → frozen: writable folder of the
    executable, else ``~/.newsletter_tool/data`` → dev: repository root.
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_paths.py -q`
Expected: `7 passed` (the wiring test still fails until Task 2 — if so, leave it failing and proceed; Task 2 turns it green). If run as part of Task 1 gate, expect exactly `test_consumers_use_paths_module` failing only for `briefs`/`utils` before Task 2.

- [ ] **Step 5: Commit** — skipped per Global Constraints (no commits without explicit request).

---

### Task 2: Wire `core.paths` into consumers

**Files:**
- Modify: `core/utils.py:22-33` (imports + `APP_ROOT`/`TEMPLATE_DIR`)
- Modify: `core/briefs.py:16-27` (import + `BRIEF_PROMPT_FILE`)
- Modify: `core/preflight.py:139-148` (defaults in `run_preflight_checks`)
- Modify: `main.py:9-25` (log dir)
- Test: `tests/test_paths.py` (already written in Task 1)

**Interfaces:**
- Consumes: `paths.resource_root()`, `paths.data_root()` from Task 1.
- Produces: unchanged public names — `core.utils.APP_ROOT`, `core.utils.TEMPLATE_DIR`, `core.briefs.BRIEF_PROMPT_FILE`, `core.preflight.run_preflight_checks(config, api_key)` defaults; `main.py` logs to `data_root()/console.txt`.

- [ ] **Step 1: Update `core/utils.py`**

Add the import next to the other core imports (`from core.api_client import APIError`):

```python
from core import paths
```

Replace:

```python
APP_ROOT = Path(__file__).resolve().parent.parent
```

with (keep the surrounding comment block, extend it with the justification):

```python
# APP_ROOT anchors writable data. In a frozen (PyInstaller) build it follows
# core/paths.py: next to the exe when writable, else ~/.newsletter_tool/data;
# in dev it stays the repository root (justification for touching this file,
# README §11: portable distribution).
APP_ROOT = paths.data_root()

# Templates/prompts are read-only bundled resources: sys._MEIPASS when frozen.
TEMPLATE_DIR = str(paths.resource_root() / "template")
```

Nothing else in the file changes (`CACHE_DIR`, JSONs, etc. keep deriving from `APP_ROOT`).

- [ ] **Step 2: Update `core/briefs.py`**

Add after `from pathlib import Path`:

```python
from core import paths
```

Replace line 27:

```python
BRIEF_PROMPT_FILE = paths.resource_root() / "template" / "brief_ptbr.txt"
```

- [ ] **Step 3: Update `core/preflight.py`**

Add next to the other core imports:

```python
from core import paths
```

In `run_preflight_checks`, replace:

```python
    root = Path(base_dir) if base_dir is not None else Path(__file__).resolve().parent.parent
    templates = Path(template_dir) if template_dir is not None else root / "template"
```

with:

```python
    root = Path(base_dir) if base_dir is not None else paths.data_root()
    templates = (Path(template_dir) if template_dir is not None
                 else paths.resource_root() / "template")
```

- [ ] **Step 4: Update `main.py`**

Add after the existing imports:

```python
from core import paths
```

Replace the `APP_ROOT` constant and `logging.basicConfig` block so the log directory is created before `FileHandler` opens it:

```python
def main() -> None:
    log_dir = paths.data_root()
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(os.path.join(str(log_dir), "console.txt"), encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
```

(The `sys.path.insert(...)` line and `APP_ROOT` constant are removed; nothing else used them.)

- [ ] **Step 5: Run the paths tests and the full suite**

Run: `.venv\Scripts\python -m pytest tests/test_paths.py -q`
Expected: `7 passed`

Run: `.venv\Scripts\python -m pytest tests -q`
Expected: `165 passed` (157 baseline + 8 new; adjust if baseline differs, but zero failures).

- [ ] **Step 6: Commit** — skipped per Global Constraints.

---

### Task 3: PyInstaller spec, build script, smoke test

**Files:**
- Create: `requirements-build.txt`
- Create: `packaging/quiin.spec`
- Create: `packaging/smoke_test.py`
- Create: `packaging/build_portable.ps1`
- Modify: `.gitignore` (add `/build/`, `/dist/`)

**Interfaces:**
- Consumes: `main.py` entry point; `template/` data files; `core.paths` resolution from Tasks 1-2.
- Produces: `packaging/build_portable.ps1` → `dist\QuIIN\QuIIN.exe` + `dist\QuIIN-Portable-<AAAA-MM-DD>.zip`.

- [ ] **Step 1: Create `requirements-build.txt`**

```
# Empacotamento portátil (Python 3.14): PyInstaller >= 6.15 é a primeira
# versão com suporte a Python 3.14.
pyinstaller>=6.15
```

- [ ] **Step 2: Create `packaging/quiin.spec`**

```python
# packaging/quiin.spec
"""PyInstaller onedir build for the portable QuIIN folder."""
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

ROOT = Path(SPECPATH).resolve().parent

datas = [(str(ROOT / "template"), "template")]
datas += collect_data_files("customtkinter")
datas += copy_metadata("webdriver-manager")

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=collect_submodules("webdriver_manager"),
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "coverage", "_pytest"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="QuIIN",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="QuIIN",
)
```

- [ ] **Step 3: Create `packaging/smoke_test.py`**

```python
# packaging/smoke_test.py
"""Smoke test for the frozen build.

Launches ``dist/QuIIN/QuIIN.exe``, waits until it stays alive and creates
``console.txt`` next to itself (proves path resolution + file logging in the
frozen app), then terminates it. Exit code 0 on success, 1 on failure.
Developer/CI helper — not shipped in the package.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "dist" / "QuIIN"
EXE = APP_DIR / "QuIIN.exe"
LOG = APP_DIR / "console.txt"
TIMEOUT_SECONDS = 90


def main() -> int:
    if not EXE.is_file():
        print(f"FAIL: {EXE} not found")
        return 1
    if LOG.exists():
        LOG.unlink()
    proc = subprocess.Popen([str(EXE)], cwd=str(APP_DIR))
    try:
        deadline = time.time() + TIMEOUT_SECONDS
        while time.time() < deadline:
            if proc.poll() is not None:
                print(f"FAIL: QuIIN.exe exited early with code {proc.returncode}")
                return 1
            if LOG.exists():
                time.sleep(3)
                if proc.poll() is None:
                    print("OK: QuIIN.exe alive and console.txt created")
                    return 0
            time.sleep(0.5)
        print("FAIL: timeout waiting for console.txt")
        return 1
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Create `packaging/build_portable.ps1`**

```powershell
# Builds the portable QuIIN folder (PyInstaller onedir), runs the launch
# smoke test and zips dist\QuIIN to dist\QuIIN-Portable-<AAAA-MM-DD>.zip.
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Push-Location $root
try {
    & ".venv\Scripts\python.exe" -m pip install -r requirements-build.txt
    if (-not $?) { throw "pip install failed" }

    & ".venv\Scripts\python.exe" -m PyInstaller --clean --noconfirm packaging\quiin.spec
    if (-not $?) { throw "PyInstaller build failed" }

    & ".venv\Scripts\python.exe" packaging\smoke_test.py
    if (-not $?) { throw "Smoke test failed" }

    $stamp = Get-Date -Format "yyyy-MM-dd"
    $zip = "dist\QuIIN-Portable-$stamp.zip"
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip }
    Compress-Archive -Path "dist\QuIIN" -DestinationPath $zip
    Write-Host "Portable package ready: $zip"
}
finally {
    Pop-Location
}
```

- [ ] **Step 5: Update `.gitignore`**

Append:

```
# Empacotamento portátil (PyInstaller)
/build/
/dist/
```

- [ ] **Step 6: Run the build**

Run: `powershell -ExecutionPolicy Bypass -File packaging\build_portable.ps1`
Expected: PyInstaller finishes with `Building COLLECT ... completed successfully`, smoke prints `OK: QuIIN.exe alive and console.txt created`, then `Portable package ready: dist\QuIIN-Portable-<data>.zip`.

Troubleshooting if the exe fails to start or misses assets: check `build\QuIIN\warn-QuIIN.txt` for missing modules; if a module is missing, add it to `hiddenimports` in the spec and rebuild. If `copy_metadata("webdriver-manager")` raises, drop that line (only needed if webdriver-manager reads its own metadata at runtime) and rebuild.

- [ ] **Step 7: Commit** — skipped per Global Constraints.

---

### Task 4: README + final validation

**Files:**
- Modify: `README.md` §4 (Instalação)

**Interfaces:**
- Consumes: `packaging/build_portable.ps1` and data-root behavior from Tasks 1-3.
- Produces: user-facing instructions + spec/plan links.

- [ ] **Step 1: Add the portable section to README §4**

Append after the dev-install block (before `Dependências de execução` list or right after it):

```markdown
### Executável portátil (Windows, sem Python no alvo)

```
powershell -ExecutionPolicy Bypass -File packaging\build_portable.ps1
```

Gera `dist\QuIIN\` (pasta portátil com `QuIIN.exe`) e `dist\QuIIN-Portable-<AAAA-MM-DD>.zip`; o script também roda um smoke test que confirma que o exe abre. Basta extrair o zip e dar duplo clique em `QuIIN.exe` — não exige instalar Python nem permissão de administrador.

- Na primeira execução o app cria `cache\`, `article\`, `content\`, `parse\`, os JSONs e `console.txt` **ao lado do exe**; se a pasta não for gravável, usa `~/.newsletter_tool/data/` (a tela Execução mostra o caminho no pré-voo). `QUIIN_DATA_DIR` força um local específico.
- O pipeline continua exigindo **Google Chrome instalado + internet** (o driver é baixado na 1ª execução para `~/.wdm`); a tela Execução avisa o que falta.
- Config, usuários, pesos e auditoria permanecem em `~/.newsletter_tool/`.
```

Then update the spec/plan line in §11 to also cite the portable pair:

```markdown
Especificação e plano: `docs/superpowers/specs/2026-09-14-quiin-design.md`, `docs/superpowers/plans/2026-09-14-quiin-implementation.md`; empacotamento portátil: `docs/superpowers/specs/2026-10-13-quiin-portable-design.md`, `docs/superpowers/plans/2026-10-13-quiin-portable-implementation.md`.
```

- [ ] **Step 2: Final validation**

Run: `.venv\Scripts\python -m pytest tests -q`
Expected: all green (157 baseline + new path tests).

Run: `powershell -ExecutionPolicy Bypass -File packaging\build_portable.ps1`
Expected: build + smoke + zip OK.

Manual checklist (needs a human at the machine for the GUI): extract `dist\QuIIN-Portable-<data>.zip` somewhere writable, double-click `QuIIN.exe`, confirm the login/bootstrap window appears, the `Execução` screen preflight is green for local items (Chrome/API key depend on the machine) and `cache\`/`console.txt` appear next to the exe.

- [ ] **Step 3: Commit** — skipped per Global Constraints.

---

## Self-Review Notes

- Spec coverage: paths module (Task 1), wiring (Task 2), build+smoke+zip (Task 3), docs+validation (Task 4); env override, hybrid fallback and dev invariance each have a named test.
- Type consistency: `paths.is_frozen/resource_root/data_root/_is_writable` names used identically in Tasks 1-3 and the spec; `APP_ROOT`/`TEMPLATE_DIR`/`BRIEF_PROMPT_FILE` names unchanged.
- Review Focus lines each map to a test or build step: read-only fallback (`test_frozen_readonly_falls_back_to_profile`), env override ignored (`test_env_override_ignored_when_not_writable`), log dir creation (`main.py` Step 4 + smoke), cwd independence (frozen tests use `sys.executable`, never cwd), stale artifacts (`--clean` + smoke deletes `console.txt`).
