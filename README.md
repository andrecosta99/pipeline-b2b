# Pipeline B2B — Aveiro (piloto)

Pipeline Python para construir uma base de dados qualificada de empresas no
distrito de Aveiro, para outreach B2B de 3 serviços de IA: assistente
conversacional para website, preparação para pesquisa por IA/GEO, e formação
prática em IA para equipas.

## Estado atual

- ✅ **Fase 1** — Recolha de universo (Portal da Justiça, publicacoes.mj.pt)
- ⏳ Fase 2 — Descoberta de domínio
- ⏳ Fase 3 — Análise de website / deteção de chatbot
- ⏳ Fase 4 — Recolha de email
- ⏳ Fase 5 — Classificação e ordenação de serviços
- ⏳ Fase 6 — Geração de sequência de emails
- ⏳ Fase 7 — Output final

## Aviso importante: reCAPTCHA no Portal da Justiça

A pesquisa em `publicacoes.mj.pt` está protegida por **reCAPTCHA invisível da
Google**. O scraper da Fase 1 (`pipeline/scrapers/mj_portal.py`) usa
Playwright com um **browser visível** (não headless por definição) e um
perfil persistente (`data/playwright_profile/`), para reter a confiança da
sessão entre execuções.

Se a Google exigir um desafio de captcha visível, o script **pausa** e pede
para o resolveres manualmente na janela do Chromium; depois de resolvido,
prime ENTER no terminal e a automação (pesquisa, paginação, parsing)
continua sozinha. Não há qualquer tentativa de bypass automático do
captcha.

### Calibração do parser (primeira execução)

A estrutura exata da tabela de resultados não pôde ser inspecionada antes de
resolver o captcha manualmente, por isso `pipeline/scrapers/mj_portal_parser.py`
assume uma estrutura típica de ASP.NET GridView (NIF, Nome, CAE, Concelho,
Data do Ato, Estado, por esta ordem). **Depois da primeira execução real**,
confirma a estrutura com:

```bash
python scripts/inspect_raw_html.py data/raw_html/mj_aveiro_pagina001_*.html
```

Se as colunas não corresponderem, ajusta o dicionário `COLUNAS` em
`pipeline/scrapers/mj_portal_parser.py`.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# edita .env e preenche ANTHROPIC_API_KEY, GOOGLE_CSE_API_KEY/GOOGLE_CSE_ID (ou BING_SEARCH_API_KEY)
```

A base de dados SQLite é criada automaticamente (schema em `schema.sql`) na
primeira execução, em `data/pipeline.db` (caminho configurável via
`DATABASE_PATH`).

## Executar a Fase 1

```bash
# janela de datas default = últimos 30 dias
python scripts/run_fase1.py

# janela de datas explícita
python scripts/run_fase1.py --data-inicio 2026-06-01 --data-fim 2026-07-17

# limitar a N páginas de resultados (útil para testar)
python scripts/run_fase1.py --max-paginas 2
```

Cada página de resultados é guardada como HTML raw em `data/raw_html/`
**antes** de ser parseada — se o parser falhar ou precisar de ajustes, os
pedidos não precisam de ser repetidos, basta re-processar os ficheiros
guardados.

Logs em `data/logs/pipeline.log` (rotativo, consola + ficheiro).

## Configuração (.env)

| Variável | Descrição |
|---|---|
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Claude API (Fases 3, 5, 6) |
| `SEARCH_PROVIDER` | `google` ou `bing` (Fase 2) |
| `GOOGLE_CSE_API_KEY`, `GOOGLE_CSE_ID` | Google Custom Search |
| `BING_SEARCH_API_KEY` | Bing Search (alternativa) |
| `DATABASE_PATH` | Caminho do SQLite |
| `RATE_LIMIT_MIN_SECONDS`, `RATE_LIMIT_MAX_SECONDS` | Intervalo aleatório entre pedidos |
| `MJ_DISTRITO`, `MJ_DISTRITO_CODIGO` | Distrito alvo (Aveiro = `01`) |
| `MJ_DATA_INICIO`, `MJ_DATA_FIM` | Janela de datas da pesquisa (AAAA-MM-DD) |
| `MJ_MAX_PAGINAS` | Limite de segurança de páginas (vazio = sem limite) |
| `PLAYWRIGHT_HEADLESS` | `false` recomendado (para poder resolver captcha) |
| `PLAYWRIGHT_USER_DATA_DIR` | Perfil persistente do browser |

## Testes

```bash
pytest tests/ -v
```

Os testes de parsing usam um fixture HTML local (`tests/fixtures/`) e não
dependem de acesso à rede nem ao Playwright.

## Estrutura do projeto

```
pipeline/
  config.py           # configuração central (.env)
  db/database.py       # schema, conexão, upsert
  scrapers/
    mj_portal.py            # automação Playwright (Fase 1)
    mj_portal_parser.py     # parsing HTML -> dados (testável isoladamente)
  discovery/           # Fase 2 (a implementar)
  analysis/             # Fase 3 (a implementar)
  emails/               # Fase 6 (a implementar)
  utils/
    logging_config.py
    rate_limiter.py
scripts/
  run_fase1.py               # CLI da Fase 1
  inspect_raw_html.py        # ajuda a calibrar o parser
schema.sql              # schema SQLite (preparado para migrar para Postgres)
tests/
data/
  raw_html/             # HTML raw guardado (gitignored)
  logs/                 # logs (gitignored)
  pipeline.db           # SQLite (gitignored)
```

## Notas de migração para Postgres

O `schema.sql` foi desenhado para migrar facilmente:
- `INTEGER PRIMARY KEY AUTOINCREMENT` → `GENERATED ALWAYS AS IDENTITY`
- Colunas `TEXT` com JSON → `JSONB`
- Datas em `TEXT` (ISO-8601) → `TIMESTAMP`/`DATE`
- `CHECK (... IN (...))` → manter ou converter para `ENUM`
