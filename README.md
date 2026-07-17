# Pipeline B2B — Aveiro (piloto)

Pipeline Python para construir uma base de dados qualificada de empresas no
distrito de Aveiro, para outreach B2B de 3 serviços de IA: assistente
conversacional para website, preparação para pesquisa por IA/GEO, e formação
prática em IA para equipas.

## Estado atual

- ✅ **Fase 1** — Recolha de universo, via importação de CSV curado manualmente
- ⏳ Fase 2 — Descoberta de domínio (para empresas do CSV sem site)
- ⏳ Fase 3 — Análise de website / deteção de chatbot
- ⏳ Fase 4 — Recolha de email
- ⏳ Fase 5 — Classificação e ordenação de serviços
- ⏳ Fase 6 — Geração de sequência de emails
- ⏳ Fase 7 — Output final

## Fonte de dados da Fase 1: CSV manual (não o scraper do Portal da Justiça)

A ideia inicial era raspar `publicacoes.mj.pt` automaticamente. Na prática
isso mostrou-se pouco fiável: a pesquisa está protegida por reCAPTCHA
invisível da Google e, mesmo com o captcha resolvido manualmente numa janela
de browser visível, os pedidos de um browser automatizado (Playwright) foram
rejeitados silenciosamente pelo servidor (a pesquisa nunca era submetida,
mesmo sem mostrar erro).

**Por isso, a fonte principal da Fase 1 passou a ser um CSV preenchido/curado
manualmente**, com o essencial: nome da empresa, distrito, concelho (e/ou
freguesia), site, e NIF quando disponível. Exemplo de linha:

```
RIAMOLDE - ENGENHARIA E SISTEMAS S.A.,AVEIRO,CACIA,www.riamolde.com,
```

O código do scraper Playwright (`pipeline/scrapers/mj_portal.py` +
`mj_portal_parser.py`) fica no repositório para o caso de valer a pena
retomar essa via mais tarde (ex: com resolução de captcha por serviço
externo, ou encontrando um endpoint alternativo sem captcha), mas **não é a
via ativa**.

### Importar o CSV

```bash
python scripts/import_csv.py caminho/para/empresas.csv
```

Colunas reconhecidas no cabeçalho (case-insensitive, aceita variantes):

| Campo | Nomes de coluna aceites |
|---|---|
| nome | `nome`, `empresa`, `entidade`, `designacao` |
| distrito | `distrito` |
| concelho | `concelho` |
| freguesia | `freguesia`, `localidade` |
| site | `site`, `website`, `dominio`, `url` |
| nif | `nif`, `nipc` |
| cae | `cae` |

Se o ficheiro não tiver cabeçalho reconhecível, assume a ordem posicional
`nome, distrito, concelho, site, nif` (nif opcional).

- O delimitador é detetado automaticamente (`,`, `;` ou tab); força-se com `--delimiter ";"`.
- **Idempotente**: podes correr o mesmo CSV várias vezes sem duplicar — a
  deduplicação usa o NIF quando presente, senão nome+concelho.
- Sites são normalizados para domínio simples (`www.riamolde.com` → `riamolde.com`)
  e gravados já como domínio validado (fase 2 só corre para quem não tiver site no CSV).
- Linhas sem nome são ignoradas com aviso no log; sites que não parecem domínios válidos são ignorados (empresa fica sem domínio, a preencher na Fase 2).

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium   # só necessário se vieres a reativar o scraper do MJ

cp .env.example .env
# edita .env e preenche ANTHROPIC_API_KEY, GOOGLE_CSE_API_KEY/GOOGLE_CSE_ID (ou BING_SEARCH_API_KEY)
```

A base de dados SQLite é criada automaticamente (schema em `schema.sql`) na
primeira execução, em `data/pipeline.db` (caminho configurável via
`DATABASE_PATH`).

Logs em `data/logs/pipeline.log` (rotativo, consola + ficheiro).

## Configuração (.env)

| Variável | Descrição |
|---|---|
| `ANTHROPIC_API_KEY` / `ANTHROPIC_MODEL` | Claude API (Fases 3, 5, 6) |
| `SEARCH_PROVIDER` | `google` ou `bing` (Fase 2) |
| `GOOGLE_CSE_API_KEY`, `GOOGLE_CSE_ID` | Google Custom Search |
| `BING_SEARCH_API_KEY` | Bing Search (alternativa) |
| `DATABASE_PATH` | Caminho do SQLite |
| `RATE_LIMIT_MIN_SECONDS`, `RATE_LIMIT_MAX_SECONDS` | Intervalo aleatório entre pedidos (Fases 2-4) |
| `MJ_*`, `PLAYWRIGHT_*` | Só relevantes se reativares o scraper do Portal da Justiça |

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
  db/database.py       # schema, conexão, upsert (empresas + dominios)
  utils/
    domains.py              # normalização de dominios/URLs
    logging_config.py
    rate_limiter.py
  scrapers/
    mj_portal.py             # automação Playwright do Portal da Justica (INATIVO, ver acima)
    mj_portal_parser.py      # parsing HTML -> dados (testável isoladamente)
  discovery/           # Fase 2 (a implementar)
  analysis/             # Fase 3 (a implementar)
  emails/               # Fase 6 (a implementar)
scripts/
  import_csv.py               # importa o CSV manual (Fase 1 ativa)
  run_fase1.py                # CLI do scraper do MJ (inativo por agora)
  inspect_raw_html.py         # ajuda a calibrar o parser do MJ, se reativado
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
