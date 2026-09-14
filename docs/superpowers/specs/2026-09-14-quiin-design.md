# GLOBAL QUANTUM INTELLIGENCE – QuIIN — Design Spec

- Data: 2026-09-14
- Branch: `feat-global-quantum-intelligence` (o nome `feat-gui` do prompt-mestre foi descartado; esta branch é a correta)
- Status: aprovado pelo usuário em 2026-09-14 (abordagem A híbrida)
- Origem: tradução do PDF de design (telas login, shell, dashboard, documentos, contas, configurações) em necessidades N1–N8 e RF-01–RF-25

## 1. Contexto verificado

- Entry: `main.py` (CustomTkinter). Shell: `gui/app.py` + `Sidebar(home/settings/scraper/results/logs)` + `StatusBar`.
- Frames atuais: `home_frame` (contadores), `settings_frame` (provedor de IA + keyring + teste de conexão — preservar integralmente), `scraper_frame` (pré-voo + pipeline em worker thread + `after()`), `results_frame` (lê `documents-data.json`, detalhe + export CSV), `log_frame`.
- `core/`: `api_client` (Groq/OpenRouter/NVIDIA/OpenAI/custom), `config_manager` (`~/.newsletter_tool/config.json` + keyring com fallback), `preflight`, `task_runner` (threads + queues), `utils` (cache/scraping/validação/merge).
- Baseline: `47 passed` com `.venv/Scripts/python -m pytest tests -q` (Python 3.14.3, `.venv` com customtkinter 6.0.0, pytest 9.1.1, dateutil, keyring, openai). O Python de sistema não tem as deps — todos os comandos pytest/pip desta spec usam `.venv/Scripts/python`.
- `documents-data.json`: 7 registros no momento; campos confirmados: `url, title, category, author, date, published, modified, timestamp, keywords, hash, source, newsletter, summary, overview, key_points, classification_weight {Business, Technological, Scientific, Others}, organization[], event[], breakthrough[], financial_activity[], related_country[] (ISO3), classification, total_score`.
- `core/utils.py` define `max_weights Business 35 / Technological 35 / Scientific 15 / Others 15` — compatível com o default do índice 35/35/15/15. Nenhum campo novo do LLM é exigido.

## 2. Decisões aprovadas

1. Sidebar híbrida (não os 4 itens secos do PDF): `Dashboard, Documentos, Execução, Resultados, Logs, Contas (admin), Configurações`. O pipeline (pré-voo + Iniciar) mora em `Execução`; `Resultados` é mantido como visão legada até `Documentos` cobrir tudo.
2. Novas dependências aprovadas: `matplotlib` (charts), `reportlab` (PDF), `python-docx` (WORD). Instalação no `.venv`, sem admin.
3. Donut do PDF soma 120% (40+60+10+10) — tratado como erro de mock. Implementação normaliza `stats_area_share` para 100% e o QA verifica a soma.
4. Auth single-machine multi-usuário em SQLite user-space (sem servidor, sem AD/LDAP nesta fase).
5. `os.startfile(..., "print")` no Windows com fallback `webbrowser.open`; Share copia caminho para clipboard e abre a pasta.

## 3. Restrições invioláveis

- R1. Não reescrever `core/utils.py`, `scrapers/*`, `core/task_runner.py` além do estrito necessário; mudanças exigem justificativa escrita.
- R2. Persistência nova só em `~/.newsletter_tool/` (`users.db`, `weights.json`, `audit.log`) ou pasta escolhida pelo usuário (exports). Nada em Program Files.
- R3. Nenhuma rede/disco pesado/export na main thread do Tk — worker thread + `after()`, seguindo `scraper_frame`/`settings_frame`.
- R4. UI 100% pt-BR; textos institucionais exatos da seção 8.
- R5. Conflito com R1–R4 ou com a suíte pytest → parar, descrever, propor alternativa. Não improvisar.
- R6. Commits por fase (`feat:`, `test:`, `docs:`).

## 4. Arquitetura alvo

```
main.py → gui/app.py (Session + header + sidebar híbrida + busca + Log Out)
├── gui/frames/login_frame.py      (auth + bootstrap + Sign Up + recovery)
├── gui/frames/dashboard_frame.py  (cards + 2 charts + estatística + top-5 + tabela + pesos + newsletter)
├── gui/frames/documents_frame.py  (lista paginada + detalhe + adicionar + PDF/WORD por doc)
├── gui/frames/accounts_frame.py   (admin only)
├── gui/frames/settings_frame.py   (bloco IA preservado + Perfil + Pesos + Sobre)
├── gui/frames/scraper_frame.py    (inalterado, só gating por papel)
├── gui/frames/results_frame.py    (inalterado, só gating por papel)
├── gui/frames/log_frame.py        (inalterado)
core/database.py, scoring.py, repository.py, permissions.py, exports.py, audit.py (novos)
~/.newsletter_tool/users.db, weights.json, audit.log, config.json (existente)
```

Data flow: pipeline existente gera `documents-data.json` → `repository.load_documents` → `scoring.relevance` com `weights.json` → dashboard/documentos/newsletter → `exports` → arquivos na pasta do usuário + `audit.log`.

## 5. S1 — Camada de dados nova (`core/`)

### 5.1 `core/database.py`
- SQLite stdlib em `~/.newsletter_tool/users.db`.
- `users(id INTEGER PK, username TEXT UNIQUE, name TEXT, org TEXT, internal INTEGER, role TEXT CHECK(role IN ('basico','premium','admin')), status TEXT CHECK(status IN ('pendente','ativo','revogado')), password_hash TEXT, salt TEXT, created_at TEXT, created_by TEXT)`.
- `meta(key TEXT PRIMARY KEY, value TEXT)` guarda o hash do recovery code.
- Senha: `hashlib.pbkdf2_hmac('sha256', senha, salt, 120000)`; salt 16 bytes (`os.urandom`); armazenar hex de ambos.
- Funções: `create_user, authenticate, set_status, set_password, list_users, bootstrap_admin(name, username, password) -> recovery_code, reset_admin_via_recovery_code(code, new_password)`.
- `bootstrap_admin` só funciona com tabela vazia; recovery exibido uma única vez na GUI.

### 5.2 `core/scoring.py` (puro, sem I/O)
- `INDICADORES = ("negocios","mercado","cientifica","tecnologica")`.
- `LABELS`: negocios `Relevância para negócios (Investimentos)`, mercado `Impacto no mercado (Casos de uso)`, cientifica `Produção científica`, tecnologica `Produção tecnológica`.
- `DEFAULT_WEIGHTS = {"negocios":35,"mercado":35,"cientifica":15,"tecnologica":15}`.
- `indicators(doc)`: `negocios=clip01(cw["Business"]/35)`, `mercado=clip01(min(1,(len(financial_activity)+len(event)+len(breakthrough))/3))`, `cientifica=clip01(cw["Scientific"]/15)`, `tecnologica=clip01(cw["Technological"]/35)`; ausências = 0; `clip01` limita a [0,1].
- `relevance(doc, weights) = round(100*Σ(w_k/100)*I_k)` → int 0–100.
- `area_of(doc)`: argmax de `cw`, desempate `Business > Technological > Scientific > Others`; rótulos pt-BR `Negócio/Economia, Tecnológico, Científico, Outros`.
- `validate_weights`: cada 0–100 e soma == 100.

### 5.3 `core/repository.py` (puro sobre lista de docs)
- `load_documents(path)`, `search(docs, query)` em `title, summary, key_points, organization[].name, event[].name` (case-insensitive).
- `stats_monthly(docs, areas)`: últimos 6 meses com dados → `{mes: {area: n}}` (usa `date`/`published`, parse tolerante).
- `stats_area_share(docs)`: `{area: pct}` normalizado para 100.0.
- `stats_countries(docs, top=5)`: de `related_country` (ISO3), mapa ISO3→pt-BR embutido (mínimo 60 códigos; fallback = código).
- `sort_documents(docs, key, desc)`, key em `(date, area, relevance)`.
- `add_manual_news(fields)`: registro compatível (`source="Manual"`, `hash=sha256(url ou título)`, `classification_weight` sintético da área escolhida).

### 5.4 `core/permissions.py`
- `CAN = {"view":{"basico","premium","admin"}, "search":{...todos}, "export":{"premium","admin"}, "print":{"premium","admin"}, "share":{"premium","admin"}, "generate_newsletter":{"premium","admin"}, "add_news":{"admin"}, "edit_weights":{"admin"}, "manage_accounts":{"admin"}, "configure_ai":{"admin"}, "run_pipeline":{"admin"}}`.
- `can(role, capability) -> bool`. Básico visualiza/busca; Premium +export/print/share/newsletter; Admin tudo.

### 5.5 `core/exports.py`
- `build_newsletter(docs, weights, mode, meta)`: dict intermediário (capa + seções por doc: newsletter, summary, key_points, área, relevância, organizações, países).
- `export_pdf(structure, path)` (reportlab platypus), `export_word(structure, path)` (python-docx), `print_pdf(path)` (`os.startfile` verb print no Windows; fallback `webbrowser.open`), `share_package(structure, dir)` (grava `.md`, copia caminho via clipboard CTk/pyperclip, abre pasta do SO).
- Chamadas GUI sempre em thread.

### 5.6 `core/audit.py`
- `log_event(user, action, detail)`: append JSON-line em `~/.newsletter_tool/audit.log` com `ts, user, action, detail`. Ações: concessões/revogações, aprovações, redefinições, edição de pesos, exports.

## 6. S2 — Autenticação e shell (`gui/`)

- `gui/frames/login_frame.py`: `Usuário`, `Password (show="*")`, `Esqueci minha senha`, `Sign Up`, branding `GLOBAL QUANTUM INTELLIGENCE / Centro de Competências EMBRAPII CIMATEC em Tecnologias Quânticas / Quantum Industrial Innovation – QuIIN Associação Tecnológica`. Sign Up cria `basico/pendente` + mensagem de aguardo. Esqueci: instrui contatar admin; se username for admin, fluxo de recovery code. Bootstrap (db vazio): wizard de criação do admin + exibição única do recovery com aviso de guarda.
- `gui/app.py`: header (`GLOBAL QUANTUM INTELLIGENCE`, `Bem vindo, {name}`, `{org}`, `ID: {user_id}`, `Pesquise aqui`, `Log Out`); sidebar híbrida (seção 2); `Contas` visível só para admin; demais itens com gating `CAN` (desabilitar + tooltip quando negado); `Session` em memória; Log Out limpa sessão e volta ao login.
- Busca global: `repository.search` sobre `documents-data.json` com filtro vivo, aplicada no Dashboard e em Documentos.

## 7. S3 — Dashboard (`gui/frames/dashboard_frame.py`)

- Cards: total de documentos, portais ativos, provedor ativo.
- Gráfico 1 (matplotlib `FigureCanvasTkAgg`): barras agrupadas mês × área (RF-08). Gráfico 2: donut % por área somando 100% (RF-09). Cálculo em worker, render via `after`; nunca na main thread.
- `Estatística avançada`: 4 `CTkCheckBox` dos indicadores; desmarcar zera o peso na view (renormalizando os demais) e atualiza tabela/gráficos.
- `Localização das notícias`: top-5 países com contagens.
- Tabela `Data | Área | Relevância` + `Ordenar` (cicla asc/desc por coluna clicada).
- `Print`/`Share` (gated `CAN`).
- `Índice de seleção multicritério`: 4 linhas `{LABEL}: {peso}` + `Editar` (admin) → modal 4 sliders/entries, validação soma=100, persiste `weights.json` + audit.
- `Gerar Newsletter`: botões `Automático` e `Personalizado` (detalhe na seção 8).

## 8. S4 — Newsletter + exports

- Automático: top-20 por relevância respeitando filtros ativos (busca + indicadores + pesos).
- Personalizado: modal de seleção/ordenação manual; ordem escolhida preservada no documento.
- Exportação PDF (reportlab) e WORD (python-docx) com capa institucional. QA: validar magic bytes `%PDF` e `PK` (zip do docx) e abertura dos arquivos.

## 9. S5 — Documentos (`gui/frames/documents_frame.py`)

- Lista paginada 20/página + `Mostrar mais documentos (+20)`; colunas `Data | Fonte | Área | Título | Relevância`; busca global aplicada.
- Detalhe: todos os campos extraídos + contribuição por indicador (`I_k` e `w_k·I_k`) + organizações/eventos/breakthroughs/financial.
- `Adicionar Notícia` (admin): modal (url, título, área, data, resumo) → `add_manual_news`.
- Botões `PDF`/`WORD` exportam o documento selecionado.

## 10. S6 — Contas + Configurações

- `gui/frames/accounts_frame.py` (admin only): tabela `Nome | Username | Tipo | Organização | Interno/Externo | Status`; `Fornecer acesso` (novo usuário, password, tipo via radios `Administrador (edita, visualiza e imprime) / Premium (visualiza e imprime) / Básico (visualiza)`, solicitante = logado read-only); ações por linha `Aprovar / Cancelar acesso / Redefinir senha`; tudo em audit.
- `settings_frame.py`: bloco de IA existente preservado integralmente (gated `configure_ai`); novas seções `Perfil` (nome, org), `Índice multicritério` (mesmo editor), `Sobre / Registro do Software`: Nome `GLOBAL QUANTUM INTELLIGENCE – QuIIN`, Criação `27/04/2025`, Publicação `09/05/2025`, Linguagem `Python (web scraping, PLN e automação de relatórios)`, Campo `IF01 – Informação científica, tecnológica, bibliográfica e estratégica`, Tipo `IA01 – Inteligência Artificial / GI01 – Gerenciador de Informações`, Proprietário `Quantum Industrial Innovation`, Autores `Mabel Diz Marques Mota / João Carlos Passos / Alexandre de Santa Barbara`.

## 11. S7 — Tema (`gui/theme/`)

- Azul primário `#1F4E79`, azul claro `#2E75B6`, acento `#9DC3E6`, fundo dark `#101418`; `APP_TITLE = "GLOBAL QUANTUM INTELLIGENCE – QuIIN"`; logotipo textual no header; tipografia/espaçamentos consistentes.

## 12. RNF e protocolo de fases

- RNF-01 zero privilégio admin; RNF-02 suíte `tests/` verde; RNF-03 pt-BR + identidade QuIIN; RNF-04 sem congelar (threads), render ≤2s p/ ≤2k docs; RNF-05 PBKDF2 + keyring, sem segredo em log; RNF-06 Python 3.10+ (verificado em 3.14.3 no `.venv`); RNF-07 novos módulos `core/` com cobertura ≥80%; RNF-08 scoring/repositório puros sem GUI.
- Loop por fase: (a) testes, (b) implementação, (c) `.venv/Scripts/python -m pytest tests -q` completo, (d) checklist QA, (e) tabela `[Check | Esperado | Obtido | Status]`, (f) só avança 100% verde; 3 iterações sem resolver → parar e escalar.
- FASE 0 baseline (sem mudar `utils/task_runner`); FASE 1 dados + testes (fronteiras: cw ausente, soma≠100, doc Manual; scoring reproduzível 3 runs); FASE 2 auth/shell; FASE 3 dashboard; FASE 4 newsletter; FASE 5 documentos; FASE 6 contas/config/sobre; FASE 7 regressão E2E sem admin + nada fora de user-space; FASE 8 README reescrito nos 13 itens (substituir, não acumular).
- Dependências novas: `matplotlib, reportlab, python-docx`; dev: adicionar `coverage` se ausente.

## 13. Riscos e mitigação

- Matplotlib + Tk: computar em worker, renderizar via `after`; testar com 2k docs sintéticos.
- Impressora ausente: fallback abre o PDF.
- ISO3 desconhecido: fallback exibe o código.
- Dataset atual com 7 docs: gráficos/top-5 esparsos até o pipeline rodar — esperado.
- `core/utils.py`/`task_runner.py`: qualquer toque exige justificativa escrita (R1).
