# Pipeline B2B — Aveiro (piloto)

Pipeline Python para construir uma base de dados qualificada de empresas no
distrito de Aveiro, para outreach B2B de 3 serviços de IA: assistente
conversacional para website, preparação para pesquisa por IA/GEO, e formação
prática em IA para equipas.

## Estado atual

- ✅ **Fase 1** — Recolha de universo, via importação de CSV curado manualmente
- ✅ **Fase 2** — Descoberta de domínio (Google CSE / Bing + fuzzy match) para empresas do CSV sem site
- ✅ **Fase 3** — Análise de website: deteção de chatbot + classificação via Claude API
- ✅ **Fase 4** — Recolha de emails de contacto (homepage, contacto, sobre)
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

### Progresso da extração manual (fonte: diretorio.informadb.pt)

Os dados do CSV estão a ser recolhidos manualmente a partir do diretório de
empresas do concelho de Aveiro em `diretorio.informadb.pt`, página a página
(URLs no formato `https://diretorio.informadb.pt/Concelho_AVEIRO/Empresas-N.html`).

**Última página extraída: 75** (`.../Concelho_AVEIRO/Empresas-75.html`) —
continuar a partir da página 76 na próxima sessão de recolha.

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

## Fase 2: descoberta de domínio

Para empresas do CSV que não têm site preenchido, a Fase 2 pesquisa
`"{nome} {concelho}"` no motor configurado (`SEARCH_PROVIDER=google` ou
`bing` no `.env`) e valida o melhor resultado por fuzzy match (rapidfuzz)
entre o nome da empresa e o título/domínio devolvidos. Ignora sempre redes
sociais e diretórios de empresas (Facebook, LinkedIn, Racius, etc.) mesmo que
o nome coincida. Abaixo do `--threshold` (default 70/100), a empresa fica
sem domínio válido.

```bash
# preenche GOOGLE_CSE_API_KEY + GOOGLE_CSE_ID (ou BING_SEARCH_API_KEY) no .env primeiro
python scripts/run_fase2.py
python scripts/run_fase2.py --limite 20        # só as primeiras 20 (para testar)
python scripts/run_fase2.py --threshold 65      # ajustar o rigor do match
```

Só processa empresas que ainda não têm nenhuma linha em `dominios` — correr
outra vez não repete pesquisas já feitas (mesmo as que falharam ficam
marcadas com `validado=0`, para o histórico/depuração).

## Fase 3: análise de website e deteção de chatbot

Para empresas com domínio validado (Fase 2), a Fase 3:

1. Visita a homepage e a página de contacto com Playwright (headless).
2. Deteta widgets de chat conhecidos (Intercom, Drift, Tidio, Zendesk,
   Crisp, tawk.to) ou genéricos (`pipeline/analysis/chatbot_detection.py`),
   por assinaturas no HTML.
3. **Best-effort**: se houver widget, tenta abri-lo e enviar uma pergunta
   fora do guião ("Vendem/trabalham também fora de Portugal?"), capturando o
   trecho da página logo a seguir. Cada fornecedor de chat tem uma UI
   diferente, por isso isto usa seletores genéricos e pode falhar em muitos
   sites — quando falha, a análise continua sem essa resposta.
4. Envia os sinais recolhidos (texto da homepage, widget detetado, resposta
   capturada) à Claude API, que devolve `tipo_chatbot`
   (`sem_chatbot` / `chatbot_deterministico` / `chatbot_ia_real`), número de
   serviços listados, se o formulário é qualificado, presença de blog,
   idiomas, e um exemplo concreto do que o chatbot não respondeu bem.

```bash
# preenche ANTHROPIC_API_KEY no .env primeiro
python scripts/run_fase3.py
python scripts/run_fase3.py --limite 10
```

Só processa empresas com domínio validado que ainda não têm análise
registada em `analises_website`.

## Fase 4: recolha de emails de contacto

Para empresas com domínio validado, visita um pequeno conjunto de páginas
típicas (`/`, `/contacto`, `/contactos`, `/contact`, `/sobre`, `/about`,
`/quem-somos`, ...) com `requests` + BeautifulSoup (sem Playwright — não
precisa de JS) e extrai todos os emails encontrados, tanto em texto solto
como em links `mailto:`. Filtra falsos positivos comuns (emails de imagem
tipo `logo@2x.png`, domínios de template/tracker como `sentry.io` ou
`wixpress.com`).

```bash
python scripts/run_fase4.py
python scripts/run_fase4.py --limite 20
```

Guarda **todos** os candidatos encontrados por empresa (pode haver mais que
um) em `emails_candidatos` — a escolha de qual usar fica para o campo manual
`email_contacto` em `outreach` (Fase 7). Só processa empresas ainda sem
nenhuma tentativa registada; se não encontrar nenhum email, grava um marcador
para não reprocessar a mesma empresa em execuções seguintes.

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
  discovery/
    search_provider.py       # abstracao Google CSE / Bing
    domain_discovery.py      # pesquisa + validacao por fuzzy match
  analysis/
    chatbot_detection.py      # deteta widgets de chat por assinatura no HTML
    website_analyzer.py       # Playwright: visita site, tenta interagir com o widget
    claude_classifier.py      # classificacao via Claude API
  contacts/
    email_finder.py            # recolha de emails de contacto (Fase 4)
  emails/               # Fase 6 (a implementar)
scripts/
  import_csv.py               # importa o CSV manual (Fase 1 ativa)
  run_fase2.py                 # CLI da descoberta de dominio (Fase 2)
  run_fase3.py                 # CLI da analise de website/chatbot (Fase 3)
  run_fase4.py                 # CLI da recolha de emails (Fase 4)
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
