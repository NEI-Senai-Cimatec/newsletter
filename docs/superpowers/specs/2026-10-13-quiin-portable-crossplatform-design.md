# GLOBAL QUANTUM INTELLIGENCE – QuIIN — Spec: Portátil macOS + Linux (via GitHub Actions)

- Data: 2026-10-13
- Status: aprovado pelo usuário em 2026-10-13 (CI como mecanismo oficial; Linux `tar.gz`; macOS arm64 + x86_64)
- Origem: pedido "criar uma versão executável em mac e linux (Ubuntu), sem instalação, mesma filosofia do portátil Windows"
- Relacionado: `docs/superpowers/specs/2026-10-13-quiin-portable-design.md` (base Windows já implementada)

## 1. Contexto verificado

- Não existe compilação cruzada: binário macOS só é produzido em macOS; esta máquina não tem WSL (Linux também não sai localmente). Repo `NEI-Senai-Cimatec/newsletter` é **público** → GitHub Actions gratuito, incluindo runners macOS.
- `core/paths.py` (Windows) resolve `resource_root()`/`data_root()`; no macOS, `sys.executable` fica em `QuIIN.app/Contents/MacOS/QuIIN` — dados ao lado do executável cairiam **dentro do bundle** (errado).
- `core/exports.py:130-166` e `gui/frames/results_frame.py:173-184` já têm fallbacks `open`/`xdg-open`; keyring já tem fallback `.credentials` (`core/config_manager.py`).
- Gaps: preflight sem caminho padrão do Chrome no macOS (`core/preflight.py:175-180` é Windows-only); `packaging/smoke_test.py` usa `FindWindowW` (Windows-only) e caminhos fixos de `QuIIN.exe`; `packaging/quiin.spec` não gera `.app`; não há scripts Linux/macOS nem workflow.
- `tests/test_utils.py:74-79` e os testes de `tests/test_paths.py` travam o comportamento dev/Windows.

## 2. Decisões aprovadas

1. **GitHub Actions é o mecanismo oficial de build/release** (matrix de 4 alvos). Ao publicar tag `v*`, os 4 artefatos são anexados automaticamente à release; `workflow_dispatch` existe para builds manuais (nota: só aparece na UI quando o arquivo estiver na default branch — mitigado pelo trigger de `push` na branch).
2. **Linux**: `tar.gz` da pasta (espelho do zip Windows). Sem AppImage (exige `libfuse2` no Ubuntu 22.04+, contra "sem instalação").
3. **macOS**: builds separados **arm64** (`macos-14`) e **x86_64** (`macos-13`); sem universal2 (wheels são por arquitetura).
4. **macOS sem assinatura/notarização** (sem conta Apple Developer): Gatekeeper exige right-click→Abrir ou `xattr -cr` na 1ª execução — documentado no README e nas release notes.
5. **Python**: 3.14 no Windows/mac (`actions/setup-python`); no Linux, Python do sistema + `python3-tk` + `python3-venv` (o Python do setup-python no Linux não traz `_tkinter` de forma confiável).
6. **Dados no macOS**: a pasta candidata é **a que contém o `QuIIN.app`** (portátil: dados viajam junto); não gravável → `~/.newsletter_tool/data`. `QUIIN_DATA_DIR` continua mandando em todos os SOs.

## 3. Restrições invioláveis

- R1. Comportamento dev idêntico em todos os SOs; suíte existente (203) continua verde.
- R2. Fluxo Windows atual (`.ps1` + smoke) não regride.
- R3. O smoke deve provar em cada SO: app sobe, marcador de data root correto no log, e **stack gráfica funcional** (selfcheck cria/destrói uma janela `CTk()`); Linux roda sob `xvfb-run`.
- R4. Workflow sem segredos extras: apenas `GITHUB_TOKEN` padrão com `permissions: contents: write`.
- R5. Nomes de artefato: `QuIIN-Portable-Windows-x64.zip`, `QuIIN-Portable-Linux-x64.tar.gz`, `QuIIN-Portable-macOS-arm64.zip`, `QuIIN-Portable-macOS-x86_64.zip`.

## 4. Mudanças

### 4.1 `core/paths.py`
- Novo `_mac_app_container(exe: Path) -> Path | None`: detecta `.../<X>.app/Contents/MacOS/<bin>` e retorna a pasta **acima** do `.app`; `None` se não for bundle.
- `data_root()`: no ramo frozen, `darwin` → candidato = container do `.app` (ou `exe.parent` se não for bundle); gravável → candidato, senão perfil. Demais SOs inalterados.

### 4.2 `core/preflight.py`
- `_default_chrome_path()`: `Darwin` → `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`; `Windows` → comportamento atual; demais → `None` (Linux já resolve via `shutil.which`).

### 4.3 `core/selfcheck.py`
- Depois de keyring/reportlab/docx, cria e destrói uma janela real: `root = ctk.CTk(); root.update_idletasks(); root.destroy()`. Mantém o log final `QUIIN SMOKE OK`.

### 4.4 `packaging/smoke_test.py`
- Caminhos por plataforma: `win32` → `dist/QuIIN/QuIIN.exe` + log ao lado; `linux` → `dist/QuIIN/QuIIN` + log ao lado; `darwin` → `dist/QuIIN.app/Contents/MacOS/QuIIN` + log em `dist/` (container).
- Assert do data root esperado por SO (substring no log).
- Checagem de janela via `FindWindowW`: **somente win32**; mac/Linux confiam em vivo + marcadores + selfcheck (que agora abre janela Tk).
- Mantém: cwd disjunto, `QUIIN_DATA_DIR` removido do env, timeouts 180s/60s.

### 4.5 `packaging/quiin.spec`
- `sys.platform == "darwin"` → `BUNDLE(coll, name="QuIIN.app", bundle_identifier="br.org.senai.cimatec.quiin")`. Windows/Linux inalterados.

### 4.6 `packaging/build_portable.sh` (novo)
- Build local em Linux/macOS: cria `.venv-build`, instala `requirements.txt` + `requirements-build.txt`, roda PyInstaller, smoke (Linux via `xvfb-run`), empacota (`tar -czf` no Linux; `ditto -c -k --keepParent` no macOS).
- `.gitignore`: adicionar `/.venv-build/`.

### 4.7 `.github/workflows/portable-release.yml` (novo)
- Disparo: `push` em `main` e `feat/portable-macos-linux` + tags `v*`; `workflow_dispatch`.
- Matrix: `windows-latest`, `ubuntu-22.04`, `macos-14` (arm64), `macos-13` (x86_64).
- Passos por SO: checkout → Python (setup-python 3.14 em win/mac; apt `python3-venv python3-tk xvfb` + venv no Linux) → deps → PyInstaller → smoke → empacotar.
- `actions/upload-artifact` sempre; `softprops/action-gh-release` quando `refs/tags/v*` (4 jobs anexam seus arquivos à mesma release).

### 4.8 `README.md`
- Seção portátil ganha macOS/Linux e o fluxo de release via tag/CI (com o aviso do Gatekeeper e `xattr -cr`).

## 5. Testes e validação

- `tests/test_paths.py` (TDD): darwin + bundle → container; darwin sem bundle → `exe.parent`; darwin container não gravável → perfil (monkeypatch `sys.platform`, `sys.executable`, `Path.home`, `paths._is_writable`).
- `tests/test_preflight.py` (TDD): `_default_chrome_path` no darwin; `None` no linux; windows inalterado.
- Local (Windows): `pytest tests -q` verde; rebuild + smoke Windows verde (regressão do fluxo atual).
- Remoto: push da branch → 4 jobs verdes no Actions = evidência de build+smoke reais em cada SO. Falha → ajustar e re-push.

## 6. Riscos aceitos

- `macos-13` (Intel) pode ter sido aposentado — se o leg falhar por runner inexistente, a matriz é ajustada (arm64 only ou runner Intel vigente) com decisão registrada.
- Gatekeeper/quarentena no mac sem assinatura (documentado).
- Tamanhos: Linux/mac ~150–250 MB comprimidos.
- Primeira execução de cada artefato pode disparar scan do SO (lentidão), como no Windows.

## 7. Fora de escopo

- Assinatura/notarização Apple, AppImage, auto-update, Linux ARM, mover a tag `v1.0.0` (nota: ela aponta para o commit inicial; correção manual posterior, se desejado).
