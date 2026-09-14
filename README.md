# GLOBAL QUANTUM INTELLIGENCE – QuIIN

`GLOBAL QUANTUM INTELLIGENCE – QuIIN` · Centro de Competências EMBRAPII CIMATEC em Tecnologias Quânticas · Quantum Industrial Innovation – QuIIN Associação Tecnológica

## 1. Visão geral do produto

O QuIIN é um aplicativo desktop (CustomTkinter) que coleta notícias de portais quânticos via pipeline de scraping + IA e as transforma em inteligência acionável: dashboard analítico com índice de relevância multicritério, documentos pesquisáveis e paginados, geração de newsletter com exportações PDF/WORD, impressão e compartilhamento — tudo com login, papéis (básico/premium/admin) e auditoria, sem exigir permissão de administrador da máquina.

Uso típico: o admin configura o provedor de IA e executa o pipeline; a equipe navega no Dashboard, ajusta os pesos do índice, gera a newsletter e exporta; contas e acessos são governados na tela Contas.

## 2. Registro do software

| Campo | Valor |
|---|---|
| Nome | GLOBAL QUANTUM INTELLIGENCE - QuIIN |
| Criação | 27/04/2025 |
| Publicação | 09/05/2025 |
| Linguagem | Python (web scraping, PLN e automação de relatórios) |
| Campo | IF01 - Informação científica, tecnológica, bibliográfica e estratégica |
| Tipo | IA01 - Inteligência Artificial / GI01 - Gerenciador de Informações |
| Proprietário | Quantum Industrial Innovation |
| Autores | Mabel Diz Marques Mota / João Carlos Passos / Alexandre de Santa Barbara |

(Espelha a seção “Sobre / Registro do Software” em `gui/frames/settings_frame.py`.)

## 3. Estrutura do projeto

```
.
├── main.py                        # entrada desktop (abre o shell QuIIN)
├── run.py                         # CLI: coleta + processamento via IA
├── merge.py                       # CLI auxiliar: consolida documents-data.json
├── core/                          # api_client, audit, config_manager, database,
│                                  # exports, permissions, preflight, repository,
│                                  # scoring, task_runner, utils (+ __init__)
├── gui/
│   ├── app.py                     # shell: sessão, busca global, gating por papel
│   ├── components/                # dialogs, newsletter_dialog, sidebar, status_bar
│   ├── frames/                    # accounts, dashboard, documents, home, login,
│   │                              # log, results, scraper, settings
│   └── theme/colors.py            # título, geometria, paleta QuIIN
├── scrapers/                      # thequantuminsider, quantamagazine,
│                                  # quantumzeitgeist, insidequantumtechnology
├── template/                      # prompts parse_v4, translate_ptbr, html
├── legacy/                        # referência histórica (parse_v3, sitemap)
├── tests/                         # suíte pytest (14 módulos)
├── docs/
│   ├── images/                    # diagramas do pipeline legado
│   └── superpowers/
│       ├── specs/2026-09-14-quiin-design.md
│       └── plans/2026-09-14-quiin-implementation.md
├── requirements.txt
├── requirements-dev.txt
└── .gitignore
```

Dados de execução (`cache/`, `article/`, `content/`, `parse/`, `console.txt`, `documents-data.json`) são gerados no diretório de trabalho e não vão ao repositório. Configuração, usuários, pesos e auditoria vivem em `~/.newsletter_tool/` (pasta do usuário).

## 4. Instalação

Requisito: Python 3.10+ (verificado neste repo com 3.14.3). Nenhuma etapa exige administrador:

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Para desenvolvimento/testes, além do acima:

```
pip install -r requirements-dev.txt
```

Dependências de execução: `selenium`, `webdriver-manager`, `cloudscraper`, `beautifulsoup4`, `lxml`, `customtkinter`, `openai`, `keyring`, `json-repair`, `python-dateutil`, `matplotlib`, `reportlab`, `python-docx`. Dev: `pytest`, `coverage`.

## 5. Primeiro uso

```
python main.py
```

1. **Bootstrap do admin:** na primeira execução o banco (`~/.newsletter_tool/users.db`) está vazio e um assistente pede nome, usuário e senha do administrador inicial. Um **código de recuperação é exibido uma única vez** — guarde-o em local seguro; ele é de **uso único** (apagado após o uso) e recupera o admin.
2. **Login:** entre com usuário e senha. Contas com status `pendente` ou `revogado` são bloqueadas com a mensagem “Conta pendente ou revogada. Aguarde aprovação de um administrador.”
3. **Sign Up:** o botão cria conta `basico` com status `pendente`; um admin precisa aprová-la na tela Contas. “Esqueci minha senha” orienta a contatar um administrador (que redefine pela tela Contas).
4. **Papéis:** `basico` (visualiza), `premium` (visualiza e exporta/imprime/compartilha/gera newsletter), `admin` (tudo, incluindo contas, pesos, IA e pipeline).

Ciclo de vida da conta: `Sign Up → pendente → Aprovar (ativo)`; `Fornecer acesso` (tela Contas) cria usuário já `ativo`; `Cancelar acesso` marca `revogado`; `Redefinir senha` troca a senha. Toda mutação é registrada no audit log (`~/.newsletter_tool/audit.log`).

## 6. Guia por tela + matriz de permissões

Barra lateral: 📊 Dashboard · 📄 Documentos · 🚀 Execução · 📊 Resultados · 🧾 Logs · 👥 Contas (só admin) · ⚙️ Configurações. Busca global no cabeçalho filtra Dashboard e Documentos.

| Tela | O que faz | Capacidade exigida |
|---|---|---|
| Login | Entrar, Sign Up, recuperação (admin informa o usuário e usa o código de uso único; demais contatam um admin), bootstrap do admin | — (aberta) |
| 📊 Dashboard | cards, gráficos, filtros, tabela, índice multicritério (botão Editar), newsletter Automática/Personalizada, Imprimir, Compartilhar | ver/buscar: todos; `edit_weights`: admin; `generate_newsletter`, `print`, `share`: premium+admin (botões desabilitados sem permissão) |
| 📄 Documentos | lista paginada (20/página), detalhe com indicadores, Exportar PDF/WORD do documento, adicionar notícia manual | ver/buscar: todos; `export`: premium+admin; `add_news`: admin |
| 🚀 Execução | pré-voo (navegador, driver, internet, chave, provedor, diretórios, templates), opções e ▶ Iniciar Pipeline em thread dedicada | `run_pipeline`: admin (botão Iniciar desabilitado + motivo na barra de status sem a capacidade) |
| 📊 Resultados | base consolidada (`documents-data.json`), Exportar CSV | ver: todos; `export`: premium+admin (botão desabilitado sem a capacidade) |
| 🧾 Logs | logs da execução em tempo real (`console.txt` na raiz) | ver: todos |
| 👥 Contas | tabela Nome \| Username \| Tipo \| Organização \| Interno/Externo \| Status; Fornecer acesso; Aprovar / Cancelar acesso / Redefinir senha | `manage_accounts`: admin (tela oculta dos demais) |
| ⚙️ Configurações | bloco IA (provedor, chave, modelo, Testar Conexão), portais/parâmetros do LLM/filtro de coleta, Perfil (nome/organização), editor de pesos, Sobre/Registro | `configure_ai`: admin (bloco IA — sem ela, Salvar não toca provedor/modelo/endpoint/chave); `run_pipeline`: admin (portais, LLM e data mínima — sem ela, Salvar não os toca); `edit_weights`: admin (pesos); perfil: próprio usuário, salva sempre; botão Salvar desabilitado quando o papel nada tem de gravável |

Matriz de permissões (`core/permissions.py`, `CAN`):

| Capacidade | basico | premium | admin |
|---|---|---|---|
| `view`, `search` | ✓ | ✓ | ✓ |
| `export`, `print`, `share`, `generate_newsletter` | — | ✓ | ✓ |
| `add_news`, `edit_weights`, `manage_accounts`, `configure_ai`, `run_pipeline` | — | — | ✓ |

## 7. Índice multicritério

Pesos padrão (`core/scoring.py`, `DEFAULT_WEIGHTS`): `negocios=35, mercado=35, cientifica=15, tecnologica=15` (soma obrigatória = 100; cada peso inteiro 0–100; persistem em `~/.newsletter_tool/weights.json`, só admin edita).

Indicadores por documento (0–1, limitados com `clip01`):

- `negocios = classification_weight.Business / 35`
- `mercado = min(1, (nº financial_activity + nº event + nº breakthrough) / 3)`
- `cientifica = classification_weight.Scientific / 15`
- `tecnologica = classification_weight.Technological / 35`

Relevância (`relevance`):

```
relevância = round(100 × Σ (peso[k]/100) × indicador[k])   → inteiro 0–100
```

Área do documento (`area_of`): maior entre Business→Negócio/Economia, Technological→Tecnológico, Scientific→Científico, Others→Outros.

## 8. Pipeline de IA

Provedores (`core/config_manager.py`, `PROVIDERS`): `groq` (padrão, `llama-3.3-70b-versatile`), `openrouter`, `nvidia` (NIM), `openai` (`gpt-4o-mini`) e `custom` (endpoint personalizado). Modelos alternativos por provedor e `Testar Conexão` na tela Configurações.

Chaves: cofre nativo do SO via `keyring` (serviço `newsletter_tool`); sem backend utilizável, fallback em `~/.newsletter_tool/.credentials` (JSON, permissão só do dono). Config geral em `~/.newsletter_tool/config.json` (provedor, modelo, portais, `min_date`, etc.).

Execução headless (lê o config, sobrescreve por flags):

```
python run.py [--provider ... --model ... --api-key ... --min-date AAAA-MM-DD --portals thequantuminsider,quantamagazine] [--ignore-cache] [--debug]
python merge.py
```

Sempre `run.py` antes de `merge.py`. Pela GUI: Configurações → Testar Conexão → Execução → ▶ Iniciar Pipeline (pré-voo precisa estar verde).

## 9. Exportações PDF / WORD / impressão / compartilhamento

A newsletter (`core/exports.py`, `build_newsletter`) ordena os documentos por relevância e monta seções com título, resumo, pontos-chave, área, relevância, organizações, países e URL. Modos: **Automático** (top-N pelos pesos) e **Personalizado** (modal de seleção/ordenação — a ordem do modal é preservada no arquivo).

- **PDF** (`export_pdf`, reportlab A4): diálogo “salvar como”, nome padrão da newsletter.
- **WORD** (`export_word`, python-docx): `.docx` com títulos, resumo e bullets (somente `.docx` gera WORD; outra extensão cai no PDF).
- **Imprimir** (`print_pdf`): no Windows envia à impressora; sem impressora, abre o PDF no visualizador.
- **Compartilhar** (`share_package`): grava `newsletter.md` numa pasta e a abre no explorador (não copia nada para a área de transferência).
- **Documento avulso** (tela Documentos): Exportar PDF / Exportar WORD do item selecionado; **CSV** da base na tela Resultados.

Exportações rodam em threads dedicadas (a interface não congela) e os botões são desabilitados para quem não tem a capacidade (`Sem permissão: requer '…'`, visível na barra de status).

## 10. Testes

```
.venv\Scripts\python -m pytest tests -q
```

→ `118 passed`. Cobertura do gate RNF-07 (novos módulos `core/` ≥ 80%):

```
.venv\Scripts\python -m coverage run -m pytest tests -q
.venv\Scripts\python -m coverage report --include="core/scoring.py,core/repository.py,core/database.py,core/permissions.py,core/audit.py,core/exports.py"
```

→ `audit 100% · database 100% · exports 100% · permissions 100% · repository 100% · scoring 98%` (total 99%). Verificação E2E (não-admin, ambos os papéis, PDFs/WORD com magic bytes, botões desabilitados para básico): 32/32. Nada fora de user-space: escrita só em `~/.newsletter_tool/`, pastas de dados do diretório de trabalho e pasta de exportação escolhida pelo usuário.

## 11. Limitações conhecidas + roadmap

- Gráficos/top-5 países ficam esparsos até o pipeline rodar e popular `documents-data.json` (base atual pequena — esperado).
- Pesos precisam somar 100 (inteiros 0–100); fora disso a validação rejeita.
- Código ISO3 de país desconhecido exibe o próprio código (fallback).
- Sem impressora no Windows, Imprimir abre o PDF em vez de falhar.
- Gráficos matplotlib são computados em worker e renderizados via `after` (a GUI não congela; testado com 2k docs sintéticos).
- Roadmap: rodar o pipeline para adensar a base; novos portais via `scrapers/`; evoluções de newsletter (templates em `template/`); manter `core/utils.py`/`task_runner.py` intocados sem justificativa escrita.

Especificação e plano: `docs/superpowers/specs/2026-09-14-quiin-design.md`, `docs/superpowers/plans/2026-09-14-quiin-implementation.md`.

## 12. Changelog (fase QuIIN)

- `refactor: move profile update into core database API`
- `feat: add accounts governance and extended settings`
- `feat: add paginated documents screen with detail`
- `feat: add automatic and custom newsletter exports`
- `feat: add QuIIN analytics dashboard`
- `fix: harden QuIIN auth shell per review (gating registry, pack order, cached search, session allowlist, bootstrap guard)`
- `feat: add QuIIN auth shell with session and global search`
- `test: top up QuIIN core coverage to RNF-07 gate`
- `feat: add newsletter exports (PDF, WORD, print, share)`
- `feat: add role matrix and audit log with tests`
- `fix: harden database auth (strip secrets, constant-time compare, single-use recovery)`
- `feat: add SQLite user store with bootstrap and recovery`
- `feat: add pure document repository with tests`
- `feat: add pure multicriteria scoring with tests`
- `feat: add QuIIN GUI deps (matplotlib, reportlab, python-docx, coverage)`
- `docs: QuIIN implementation plan (FASE 0-8, tasks com testes)`
- `docs: spec QuIIN GLOBAL QUANTUM INTELLIGENCE (design aprovado, abordagem A hibrida)`
