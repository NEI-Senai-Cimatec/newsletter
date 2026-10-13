# GLOBAL QUANTUM INTELLIGENCE – QuIIN — Spec: Distribuição Portátil

- Data: 2026-10-13
- Status: aprovado pelo usuário em 2026-10-13 (formato B: pasta portátil; dados híbridos C)
- Origem: pedido "tornar a execução do aplicativo mais fácil ao usuário — algo como um simples executável portátil"

## 1. Contexto verificado

- App desktop Python/CustomTkinter (`main.py`); CLIs `run.py`/`merge.py` são ferramentas de dev.
- `.venv` com Python 3.14.3. PyInstaller ≥ 6.15 suporta 3.14 (Nuitka 4.2 também — descartado por atrito com dados de pacote do customtkinter/matplotlib e builds longos).
- `core/utils.py:30` ancora tudo em `APP_ROOT = Path(__file__).resolve().parent.parent`; templates carregados no import (`core/utils.py:57-133`); `core/briefs.py:27` lê `template/brief_ptbr.txt` via `__file__`.
- `main.py:22` grava `console.txt` no `APP_ROOT`; `gui/frames/results_frame.py:16,175` abre `APP_ROOT` no explorador (importa de `core/utils`).
- Config, banco de usuários, pesos e auditoria vivem em `~/.newsletter_tool/` (`core/config_manager.py:86`, `core/database.py:12`, `core/scoring.py:19`, `core/audit.py:8`) — permanecem.
- `tests/test_utils.py:74-79` trava o comportamento dev: `APP_ROOT` = raiz do repo e diretórios de dados sob ele.
- Pré-voo (`core/preflight.py`) já checa Chrome, ChromeDriver (webdriver-manager baixa para `~/.wdm`), internet, API key, diretórios e templates.
- Sem `pyinstaller` instalado; sem `.spec`, `.ico` ou script de build no repo.

## 2. Decisões aprovadas

1. Entrega: **PyInstaller `onedir`** → `dist/QuIIN/` (`QuIIN.exe` + `_internal/`) compactado em `QuIIN-Portable-<AAAA-MM-DD>.zip`. Sem instalador nesta fase.
2. Dados de trabalho híbridos: tenta **ao lado do exe**; não gravável → fallback `~/.newsletter_tool/data/`.
3. Override opcional por variável de ambiente `QUIIN_DATA_DIR`.
4. Config/usuários/auditoria continuam em `~/.newsletter_tool/` (cofre do Windows, por usuário).
5. CLI não vai no pacote; sem assinatura de código; ícone custom fica para depois (não há `.ico` no repo).

## 3. Restrições invioláveis

- R1. Comportamento dev idêntico: suíte atual (157 passed) continua verde; em dev `APP_ROOT` = raiz do repo e `TEMPLATE_DIR` sob ela.
- R2. Escrita nova só ao lado do exe, em `~/.newsletter_tool/` ou pasta escolhida pelo usuário — nada em Program Files.
- R3. `core/utils.py` só é tocado com justificativa escrita (roadmap do README §11): a mudança necessária é redirecionar `APP_ROOT`/`TEMPLATE_DIR` para `core/paths.py` em modo empacotado.
- R4. Templates/prompts entram no pacote como dados; em modo frozen, recursos de leitura resolvem via `sys._MEIPASS`.
- R5. Build roda no `.venv` existente; `pyinstaller>=6.15` em `requirements-build.txt`.

## 4. Arquitetura alvo

```
main.py ──► core/paths.py ──► resource_root()  (frozen: sys._MEIPASS | dev: raiz do repo)  → templates/prompts
                             └► data_root()      (QUIIN_DATA_DIR | frozen: pasta do exe se gravável, senão
                                                 ~/.newsletter_tool/data | dev: raiz do repo) → cache/article/
                                                 content/parse/JSONs/console.txt
core/utils.py: APP_ROOT = data_root(); TEMPLATE_DIR = resource_root()/"template"; demais constantes inalteradas
core/briefs.py: BRIEF_PROMPT_FILE = resource_root()/"template"/"brief_ptbr.txt"
core/preflight.py: defaults de run_preflight_checks usam paths (diretórios de trabalho já validam escrita)
main.py: console.txt = data_root()/"console.txt"
```

## 5. Componentes

### 5.1 `core/paths.py` (novo)

- `is_frozen() -> bool`: `getattr(sys, "frozen", False)`.
- `resource_root() -> Path`: frozen → `Path(sys._MEIPASS)`; dev → raiz do repo (`Path(__file__).resolve().parent.parent`).
- `data_root() -> Path`: ordem — 1) `QUIIN_DATA_DIR` (se definida e gravável); 2) frozen → pasta de `sys.executable` se gravável, senão `Path.home()/".newsletter_tool"/"data"`; 3) dev → raiz do repo.
- `_is_writable(dir) -> bool`: tenta criar e apagar um arquivo temporário; nunca levanta.
- Sem cache interno (chamadas apenas em import/inicialização; facilita monkeypatch nos testes).

### 5.2 `tests/test_paths.py` (novo)

- Dev: `data_root()`/`resource_root()` = raiz do repo; `is_frozen()` False.
- Frozen gravável: monkeypatch `sys.frozen=True`, `sys.executable` em `tmp_path` → `data_root()` = pasta do exe; `resource_root()` via `sys._MEIPASS` monkeypatched.
- Frozen não gravável: monkeypatch de `paths._is_writable` → `False` → fallback `Path.home()/".newsletter_tool"/"data"` (home monkeypatched).
- `QUIIN_DATA_DIR` definida e gravável → vence em ambos os modos; definida e não gravável → é ignorada (fallback segue).
- `_is_writable`: True em `tmp_path`, False em caminho inexistente/inválido.

### 5.3 Ligações

- `core/utils.py`: `APP_ROOT`/`TEMPLATE_DIR` via `core.paths`; nenhuma outra constante muda. Em dev o resultado é byte-idêntico ao atual (R1/R3).
- `core/briefs.py`, `core/preflight.py`, `main.py` conforme seção 4.
- `gui/frames/results_frame.py`: sem mudança (herda `APP_ROOT` de `core/utils`).

## 6. Build

- `requirements-build.txt`: `pyinstaller>=6.15`.
- `packaging/quiin.spec`: `Analysis(['main.py'], datas=[('template','template')], hiddenimports=collect_submodules('webdriver_manager'), excludes=['pytest','coverage'])`; `EXE(console=False, name='QuIIN')` + `COLLECT` (onedir).
- `packaging/build_portable.ps1`: `pip install -r requirements-build.txt` → `pyinstaller --clean --noconfirm packaging/quiin.spec` → smoke → `Compress-Archive dist/QuIIN` → `dist/QuIIN-Portable-<AAAA-MM-DD>.zip`.

## 7. Testes e validação

- `pytest tests -q` → 157 atuais + novos de `test_paths.py`, todos verdes.
- Pós-build: lançar `QuIIN.exe`, confirmar processo vivo, `console.txt` e pastas de dados criados ao lado do exe; encerrar.
- Checklist manual: bootstrap do admin, login, Dashboard abre, pré-voo verde nos itens locais, pipeline real com Chrome.
- Fallback: coberto por teste unitário (pasta não gravável é difícil de simular de forma confiável no Windows).

## 8. Riscos aceitos

- Pipeline exige Chrome instalado + internet (não embutível); driver baixado na 1ª execução para `~/.wdm`; pré-voo comunica isso.
- Zip ~250–350 MB (matplotlib/reportlab/lxml/tk).
- SmartScreen/antivírus podem alertar (sem assinatura de código).

## 9. Fora de escopo

- Instalador (Inno Setup), assinatura de código, auto-update, CLI empacotado, ícone/janela customizados, empacotamento macOS/Linux.
