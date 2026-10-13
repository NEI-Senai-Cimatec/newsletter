# QuIIN Cross-Platform Portable (macOS + Linux) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build portable QuIIN artifacts for macOS (arm64 + x86_64) and Linux (x64) via a GitHub Actions matrix, with data-folder behavior equivalent to the Windows portable (next to the executable / next to the `.app`), keeping every existing test green.

**Architecture:** Small platform branches on top of the existing `core/paths.py` (macOS `.app` container detection), `core/preflight.py` (macOS Chrome path), `core/selfcheck.py` (real Tk window) and `packaging/smoke_test.py` (per-OS paths, Windows-only window check). Packaging: `quiin.spec` gains a `BUNDLE` branch for Darwin; new `build_portable.sh`; new workflow builds and smokes all four targets and attaches artifacts to tag releases.

**Tech Stack:** Python 3.14 (win/mac) / system Python 3.10+ with `python3-tk` (Linux), PyInstaller >= 6.15, pytest, GitHub Actions (`actions/setup-python`, `actions/upload-artifact`, `softprops/action-gh-release`), `xvfb-run`, `ditto`, `tar`.

**Spec:** `docs/superpowers/specs/2026-10-13-quiin-portable-crossplatform-design.md`

## Global Constraints

- All Python/pytest commands use `.venv\Scripts\python` on this Windows dev machine.
- Windows dev behavior unchanged; full suite (203) stays green; Windows smoke keeps passing.
- macOS data root = folder that CONTAINS `QuIIN.app`; Linux = folder of the executable; `QUIIN_DATA_DIR` wins in all OSes when writable.
- Smoke must prove the GUI stack on every OS (selfcheck creates/destroys a real `CTk()` window); Linux runs it under `xvfb-run`.
- Workflow uses only the default `GITHUB_TOKEN` (`permissions: contents: write`); no secrets.
- Artifact names: `QuIIN-Portable-Windows-x64.zip`, `QuIIN-Portable-Linux-x64.tar.gz`, `QuIIN-Portable-macOS-arm64.zip`, `QuIIN-Portable-macOS-x86_64.zip`.
- Commits go only to `feat/portable-macos-linux`; no merges/tags/releases without the human partner asking.
- Git Bash is available for `bash -n` syntax checks; PyYAML may not be installed (fall back to careful manual review + CI validation).

## Review Focus

- macOS `.app` placed in a read-only parent (e.g., mounted DMG): must fall back to `~/.newsletter_tool/data` and still start.
- `QuIIN.app` NOT in a bundle layout (loose binary): data must go next to the binary, not crash.
- Windows regression: `data_root()`/smoke must behave exactly as before the platform branch was added.
- Linux CI without xvfb: smoke must not hang forever (timeouts) — and with xvfb the selfcheck window must be created successfully.
- `macos-13` runner retired: the leg must fail fast and visibly (matrix entry that can be adjusted), not silently skip.

---

## File Structure

- `tests/test_paths.py` (modify) — add macOS bundle/non-bundle/fallback cases.
- `core/paths.py` (modify) — `_mac_app_container()` + darwin branch in `data_root()`.
- `tests/test_preflight.py` (modify) — `_default_chrome_path` darwin/windows/linux cases.
- `core/preflight.py` (modify) — platform-aware default path.
- `core/selfcheck.py` (modify) — real `CTk()` window create/destroy.
- `packaging/smoke_test.py` (modify) — per-OS exe/log/data-root; Windows-only window check.
- `packaging/quiin.spec` (modify) — `BUNDLE` for darwin.
- `packaging/build_portable.sh` (new) — Linux/macOS local build script.
- `.gitignore` (modify) — `/.venv-build/`.
- `.github/workflows/portable-release.yml` (new) — matrix build + release attach.
- `README.md` (modify) — cross-platform portable section.

---

### Task 1: macOS `.app` data root (TDD)

**Files:**
- Modify: `core/paths.py`
- Test: `tests/test_paths.py`

**Interfaces:**
- Consumes: existing `is_frozen()`, `data_root()`, `_is_writable()`.
- Produces: `paths._mac_app_container(exe: Path) -> Path | None`; `data_root()` on `sys.platform == "darwin"` frozen → container of `<X>.app` if writable, else `exe.parent` if writable, else `~/.newsletter_tool/data`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_paths.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_paths.py -q`
Expected: FAIL — `AttributeError: module 'core.paths' has no attribute '_mac_app_container'` and darwin cases falling into exe-dir/profile logic.

- [ ] **Step 3: Implement in `core/paths.py`**

Add:

```python
def _mac_app_container(exe: Path) -> Path | None:
    """Return the folder holding ``<X>.app`` for an executable inside it."""
    parts = exe.parts
    for index, part in enumerate(parts):
        if part.endswith(".app"):
            if (index + 2 < len(parts) and parts[index + 1] == "Contents"
                    and parts[index + 2] == "MacOS"):
                return Path(*parts[:index])
            return None
    return None
```

In `data_root()`, replace the frozen branch with:

```python
    if is_frozen():
        exe = Path(sys.executable).resolve()
        candidate = exe.parent
        if sys.platform == "darwin":
            container = _mac_app_container(exe)
            if container is not None:
                candidate = container
        if _is_writable(candidate):
            return candidate
        return Path.home() / ".newsletter_tool" / "data"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_paths.py -q`
Expected: `13 passed`.

- [ ] **Step 5: Commit**

```powershell
git add core/paths.py tests/test_paths.py
git commit -m "feat: resolve macOS .app container as portable data root"
```

---

### Task 2: macOS Chrome detection in preflight (TDD)

**Files:**
- Modify: `core/preflight.py`
- Test: `tests/test_preflight.py`

**Interfaces:**
- Consumes: existing `_default_chrome_path()` used by `check_chrome()`.
- Produces: Darwin → `Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")`; Windows → existing ProgramFiles path; other OSes → `None`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_preflight.py`:

```python
def test_default_chrome_path_macos(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(pf.platform, "system", lambda: "Darwin")
    assert pf._default_chrome_path() == Path(
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")


def test_default_chrome_path_linux(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pf.platform, "system", lambda: "Linux")
    assert pf._default_chrome_path() is None


def test_default_chrome_path_windows(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setattr(pf.platform, "system", lambda: "Windows")
    monkeypatch.setenv("ProgramFiles", str(tmp_path))
    assert pf._default_chrome_path() == tmp_path / "Google" / "Chrome" / "Application" / "chrome.exe"
```

Add `from pathlib import Path` to the imports of `tests/test_preflight.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_preflight.py -q`
Expected: FAIL on the Darwin case (`AttributeError: module 'core.preflight' has no attribute 'platform'` or wrong path) and Linux case (`ProgramFiles` lookup instead of `None`).

- [ ] **Step 3: Implement in `core/preflight.py`**

Add `import platform` to the imports and replace `_default_chrome_path` with:

```python
def _default_chrome_path() -> Path | None:
    """Default Chrome install path on macOS/Windows; None elsewhere."""
    if platform.system() == "Darwin":
        return Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
    if platform.system() != "Windows":
        return None
    program_files = os.environ.get("ProgramFiles")
    if not program_files:
        return None
    return Path(program_files) / "Google" / "Chrome" / "Application" / "chrome.exe"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv\Scripts\python -m pytest tests/test_preflight.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```powershell
git add core/preflight.py tests/test_preflight.py
git commit -m "feat: detect macOS Chrome install path in preflight"
```

---

### Task 3: Tk self-check + platform-aware smoke + Windows regression

**Files:**
- Modify: `core/selfcheck.py`, `packaging/smoke_test.py`

**Interfaces:**
- Consumes: `packaging/quiin.spec` build output for the CURRENT platform.
- Produces: smoke paths — win32: exe=`dist/QuIIN/QuIIN.exe`, data root=`dist/QuIIN`; linux: exe=`dist/QuIIN/QuIIN`, data root=`dist/QuIIN`; darwin: exe=`dist/QuIIN.app/Contents/MacOS/QuIIN`, data root=`dist`.

- [ ] **Step 1: Add real Tk window to `core/selfcheck.py`**

Replace the `import customtkinter  # noqa: F401` line with a real window round-trip:

```python
    import customtkinter as ctk

    root = ctk.CTk()
    root.update_idletasks()
    root.destroy()
```

(Keep keyring/reportlab/docx blocks and the final `QUIIN SMOKE OK` log line; mention `customtkinter` in that line already exists.)

- [ ] **Step 2: Rewrite path resolution in `packaging/smoke_test.py`**

Replace the constants and `main()` guard with platform-aware values, and make the window check Windows-only:

```python
ROOT = Path(__file__).resolve().parent.parent
_TARGETS = {
    "win32": (ROOT / "dist" / "QuIIN" / "QuIIN.exe", ROOT / "dist" / "QuIIN"),
    "darwin": (ROOT / "dist" / "QuIIN.app" / "Contents" / "MacOS" / "QuIIN",
               ROOT / "dist"),
}
EXE, DATA_ROOT = _TARGETS.get(
    sys.platform, (ROOT / "dist" / "QuIIN" / "QuIIN", ROOT / "dist" / "QuIIN"))
LOG = DATA_ROOT / "console.txt"
```

In `_run_launch`, assert `str(DATA_ROOT)` in the log (instead of `str(APP_DIR)`) and apply the window check only on `sys.platform == "win32"` (on other OSes stay alive 3s after the marker). Remove the `argv` override and `APP_DIR`.

- [ ] **Step 3: Verify locally on Windows (rebuild + smoke)**

Run: `powershell -ExecutionPolicy Bypass -File packaging\build_portable.ps1`
Expected: PyInstaller OK, smoke `OK: QuIIN.exe launched (data root next to exe, window shown) and self check passed` (the rebuilt exe now also opens/destroys a `CTk()` window in the self-check), zip produced. This proves the Windows regression path.

- [ ] **Step 4: Run the suite**

Run: `.venv\Scripts\python -m pytest tests -q`
Expected: all green (213 with the new path/preflight tests).

- [ ] **Step 5: Commit**

```powershell
git add core/selfcheck.py packaging/smoke_test.py
git commit -m "feat: cross-platform smoke and real Tk window self-check"
```

---

### Task 4: macOS bundle spec + local build script

**Files:**
- Modify: `packaging/quiin.spec`, `.gitignore`
- Create: `packaging/build_portable.sh`

**Interfaces:**
- Consumes: `quiin.spec` existing `Analysis/EXE/COLLECT`.
- Produces: on darwin, `dist/QuIIN.app`; `build_portable.sh` builds + smokes + packages natively on Linux (`dist/QuIIN-Portable-Linux-x64.tar.gz`) and macOS (`dist/QuIIN-Portable-macOS-<arch>.zip`).

- [ ] **Step 1: Add the Darwin branch to `packaging/quiin.spec`**

After the `coll = COLLECT(...)` block append:

```python
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="QuIIN.app",
        icon=None,
        bundle_identifier="br.org.senai.cimatec.quiin",
    )
```

Add `import sys` at the top of the spec (next to `from pathlib import Path`).

- [ ] **Step 2: Create `packaging/build_portable.sh`**

```bash
#!/usr/bin/env bash
# Builds the portable QuIIN artifact on Linux or macOS:
#   Linux: dist/QuIIN-Portable-Linux-x64.tar.gz  (run smoke under xvfb-run)
#   macOS: dist/QuIIN-Portable-macOS-<arch>.zip  (QuIIN.app, symlinks preserved)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 -m venv .venv-build
.venv-build/bin/python -m pip install --upgrade pip
.venv-build/bin/python -m pip install -r requirements.txt -r requirements-build.txt
.venv-build/bin/python -m PyInstaller --clean --noconfirm packaging/quiin.spec

if [[ "$(uname)" == "Darwin" ]]; then
    .venv-build/bin/python packaging/smoke_test.py
    ARCH="$(uname -m)"
    rm -f "dist/QuIIN-Portable-macOS-${ARCH}.zip"
    ditto -c -k --keepParent "dist/QuIIN.app" "dist/QuIIN-Portable-macOS-${ARCH}.zip"
    echo "Portable package ready: dist/QuIIN-Portable-macOS-${ARCH}.zip"
else
    xvfb-run -a .venv-build/bin/python packaging/smoke_test.py
    rm -f dist/QuIIN-Portable-Linux-x64.tar.gz
    tar -C dist -czf dist/QuIIN-Portable-Linux-x64.tar.gz QuIIN
    echo "Portable package ready: dist/QuIIN-Portable-Linux-x64.tar.gz"
fi
```

- [ ] **Step 3: Ignore the build venv**

Append to `.gitignore`:

```
# Venv do build portátil Linux/macOS
/.venv-build/
```

- [ ] **Step 4: Syntax-check the script**

Run (Git Bash): `bash -n packaging/build_portable.sh`
Expected: no output, exit 0.

- [ ] **Step 5: Commit**

```powershell
git add packaging/quiin.spec packaging/build_portable.sh .gitignore
git commit -m "build: macOS .app bundle and Linux/macOS portable build script"
```

---

### Task 5: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/portable-release.yml`

**Interfaces:**
- Consumes: `packaging/quiin.spec`, `packaging/smoke_test.py`, `requirements*.txt`.
- Produces: artifacts for the 4 targets; on tag `v*`, attaches each to the release via `GITHUB_TOKEN`.

- [ ] **Step 1: Create the workflow**

```yaml
name: Portable builds

on:
  push:
    branches: [main, feat/portable-macos-linux]
    tags: ['v*']
  workflow_dispatch:

permissions:
  contents: write

jobs:
  build:
    strategy:
      fail-fast: false
      matrix:
        include:
          - os: windows-latest
            artifact: QuIIN-Portable-Windows-x64.zip
          - os: ubuntu-22.04
            artifact: QuIIN-Portable-Linux-x64.tar.gz
          - os: macos-14
            artifact: QuIIN-Portable-macOS-arm64.zip
          - os: macos-13
            artifact: QuIIN-Portable-macOS-x86_64.zip
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python (Windows/macOS)
        if: runner.os != 'Linux'
        uses: actions/setup-python@v5
        with:
          python-version: '3.14'

      - name: Install Linux build deps
        if: runner.os == 'Linux'
        run: |
          sudo apt-get update
          sudo apt-get install -y python3-venv python3-tk xvfb

      - name: Build (Windows)
        if: runner.os == 'Windows'
        shell: pwsh
        run: |
          python -m pip install -r requirements.txt -r requirements-build.txt
          python -m PyInstaller --clean --noconfirm packaging/quiin.spec
          python packaging/smoke_test.py
          tar.exe -a -c -f "dist/${{ matrix.artifact }}" -C dist QuIIN

      - name: Build (Linux)
        if: runner.os == 'Linux'
        run: |
          python3 -m venv .venv-build
          .venv-build/bin/python -m pip install --upgrade pip
          .venv-build/bin/python -m pip install -r requirements.txt -r requirements-build.txt
          .venv-build/bin/python -m PyInstaller --clean --noconfirm packaging/quiin.spec
          xvfb-run -a .venv-build/bin/python packaging/smoke_test.py
          tar -C dist -czf "dist/${{ matrix.artifact }}" QuIIN

      - name: Build (macOS)
        if: runner.os == 'macOS'
        run: |
          python -m pip install -r requirements.txt -r requirements-build.txt
          python -m PyInstaller --clean --noconfirm packaging/quiin.spec
          python packaging/smoke_test.py
          ditto -c -k --keepParent dist/QuIIN.app "dist/${{ matrix.artifact }}"

      - name: Upload workflow artifact
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.artifact }}
          path: dist/${{ matrix.artifact }}

      - name: Attach to release
        if: startsWith(github.ref, 'refs/tags/v')
        uses: softprops/action-gh-release@v2
        with:
          files: dist/${{ matrix.artifact }}
```

- [ ] **Step 2: Validate the YAML parses**

Run: `.venv\Scripts\python -c "import yaml, sys; yaml.safe_load(open(r'.github/workflows/portable-release.yml', encoding='utf-8')); print('yaml ok')"`
Expected: `yaml ok` (if PyYAML is unavailable in the venv, install it locally only for the check or review manually — CI will parse it on first run).

- [ ] **Step 3: Commit**

```powershell
git add .github/workflows/portable-release.yml
git commit -m "ci: portable matrix builds and tag releases"
```

---

### Task 6: README

**Files:**
- Modify: `README.md`

**Interfaces:**
- Consumes: artifact names and behaviors from Tasks 3-5.
- Produces: user-facing instructions.

- [ ] **Step 1: Extend the portable section in README §4**

After the Windows portable subsection, add:

```markdown
#### macOS e Linux (build no GitHub Actions)

As builds de macOS e Linux rodam no CI (não há compilação cruzada). Ao publicar uma tag `v*`, o workflow `Portable builds` compila e anexa à release:

- `QuIIN-Portable-Linux-x64.tar.gz` — extraia e rode `QuIIN/QuIIN` (o `tar` preserva a permissão de execução)
- `QuIIN-Portable-macOS-arm64.zip` / `QuIIN-Portable-macOS-x86_64.zip` — extraia e abra `QuIIN.app`

Builds manuais: aba **Actions → Portable builds → Run workflow** (ou push na branch) geram os mesmos arquivos como artifacts do workflow.

No macOS (sem assinatura de código), o Gatekeeper bloqueia a 1ª abertura: clique com o botão direito → **Abrir** (ou `xattr -cr QuIIN.app`). Os dados ficam na pasta **que contém** o `QuIIN.app` (coloque o app numa pasta só dele); sem permissão de escrita, usa `~/.newsletter_tool/data/`.

No Linux, o pipeline exige Chrome/Chromium instalado (`google-chrome` ou `chromium` via PATH). Sem chaveiro de desktop, a chave de API cai no fallback `~/.newsletter_tool/.credentials` (JSON, só o dono lê).
```

- [ ] **Step 2: Commit**

```powershell
git add README.md
git commit -m "docs: portable macOS and Linux instructions"
```

---

### Task 7: Push and validate the CI on the remote

**Files:** none (remote validation).

**Interfaces:**
- Consumes: all commits on `feat/portable-macos-linux`.
- Produces: four green CI jobs or a recorded failure iteration.

- [ ] **Step 1: Push the branch**

```powershell
git push -u origin feat/portable-macos-linux
```

- [ ] **Step 2: Poll the workflow runs (public API, no auth needed)**

```powershell
$runs = Invoke-RestMethod "https://api.github.com/repos/NEI-Senai-Cimatec/newsletter/actions/runs?branch=feat/portable-macos-linux&per_page=5" -Headers @{ "User-Agent" = "opencode" }
$runs.workflow_runs | Select-Object name, status, conclusion, html_url
```

Expected: the newest run for `Portable builds`; wait until all 4 jobs are `completed`, conclusion `success`. Example of a healthy result: `status=completed`, `conclusion=success`.

- [ ] **Step 3: On failure, fetch the job list and iterate**

```powershell
$run = (Invoke-RestMethod "https://api.github.com/repos/NEI-Senai-Cimatec/newsletter/actions/runs?branch=feat/portable-macos-linux&per_page=1" -Headers @{ "User-Agent" = "opencode" }).workflow_runs[0]
(Invoke-RestMethod $run.jobs_url -Headers @{ "User-Agent" = "opencode" }).jobs | Select-Object name, conclusion
```

If a leg fails and the logs are needed, ask the human partner to either paste the failing step output from the run page (`$run.html_url`) or install/auth `gh` CLI for log access. Likely fixes: `macos-13` runner retired → remove/replace that matrix entry (record the ruling); `_tkinter` missing somewhere → adjust the Python provisioning step for that OS.

- [ ] **Step 4: Report**

Report the run URL, the 4 conclusions, and any ruling made.

---

## Self-Review Notes

- Spec coverage: macOS container (Task 1), Chrome detection (Task 2), Tk proof + per-OS smoke (Task 3), `.app` + Linux/mac scripts (Task 4), workflow (Task 5), docs (Task 6), remote validation (Task 7).
- Type consistency: `_mac_app_container(exe: Path) -> Path | None`, `_default_chrome_path() -> Path | None`, `DATA_ROOT`, `LOG` used identically across tasks and spec.
- Review Focus mapping: read-only container → `test_frozen_mac_readonly_container_falls_back_to_profile`; non-bundle → `test_frozen_mac_non_bundle_uses_exe_dir`; Windows regression → existing tests + Task 3 Step 3 smoke; no-xvfb hang → smoke timeouts (180s/60s) unchanged; retired `macos-13` → Task 7 Step 3 explicit iteration.
