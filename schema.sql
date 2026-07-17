-- Schema SQLite do piloto (distrito de Aveiro).
-- Desenhado para migrar para Postgres sem grandes alteracoes:
--   - INTEGER PRIMARY KEY AUTOINCREMENT -> SERIAL / GENERATED ALWAYS AS IDENTITY
--   - TEXT com JSON -> JSONB
--   - TEXT para datas ISO-8601 -> TIMESTAMP / DATE
--   - CHECK ... IN (...) -> manter ou converter para ENUM em Postgres

PRAGMA foreign_keys = ON;

-- Fase 1: universo de empresas recolhido do Portal da Justica
CREATE TABLE IF NOT EXISTS empresas (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    nif             TEXT NOT NULL UNIQUE,
    nome            TEXT NOT NULL,
    cae             TEXT,
    concelho        TEXT,
    distrito        TEXT NOT NULL DEFAULT 'Aveiro',
    data_ato        TEXT,              -- data do ato publicado (ISO-8601)
    tipo_ato        TEXT,
    estado          TEXT,              -- estado da publicacao/empresa no portal
    fonte_url       TEXT,              -- URL da publicacao de origem
    raw_html_path   TEXT,              -- caminho local do HTML raw guardado (Fase 1)
    criado_em       TEXT NOT NULL DEFAULT (datetime('now')),
    atualizado_em   TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_empresas_concelho ON empresas(concelho);
CREATE INDEX IF NOT EXISTS idx_empresas_cae ON empresas(cae);

-- Fase 2: dominio descoberto por empresa
CREATE TABLE IF NOT EXISTS dominios (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id          INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    dominio             TEXT,
    url_homepage        TEXT,
    metodo_busca        TEXT,          -- google | bing
    score_fuzzy         REAL,          -- score de validacao nome vs titulo/dominio
    validado            INTEGER NOT NULL DEFAULT 0,  -- 0/1 (BOOLEAN em Postgres)
    criado_em           TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(empresa_id)
);

-- Fase 3: analise do website (chatbot, sinais, servicos)
CREATE TABLE IF NOT EXISTS analises_website (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id              INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    tipo_chatbot            TEXT CHECK (tipo_chatbot IN (
                                'sem_chatbot', 'chatbot_deterministico', 'chatbot_ia_real'
                            )),
    widget_detectado        TEXT,      -- nome do widget: intercom, drift, tidio, zendesk, crisp, tawk.to, generico, null
    exemplo_falha_chatbot   TEXT,      -- exemplo concreto de pergunta mal respondida
    sinais_json             TEXT,      -- JSON: nº servicos, formulario qualificado, blog, idiomas, etc.
    analisado_em            TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(empresa_id)
);

-- Fase 4: candidatos a email encontrados por dominio
CREATE TABLE IF NOT EXISTS emails_candidatos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id      INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    email           TEXT NOT NULL,
    origem_pagina   TEXT,              -- /contacto, /sobre, footer, ...
    criado_em       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(empresa_id, email)
);

-- Fase 5: ordenacao e justificacao dos 3 servicos
CREATE TABLE IF NOT EXISTS servicos_ordenados (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id          INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    ordem_servicos_json TEXT,          -- JSON array ordenado: ["assistente_website", "geo", "formacao"]
    justificacoes_json  TEXT,          -- JSON: {servico: justificacao}
    criado_em           TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(empresa_id)
);

-- Fase 6: sequencia de emails gerada
CREATE TABLE IF NOT EXISTS sequencias_email (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id      INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    email_1         TEXT,
    email_2         TEXT,
    email_3         TEXT,
    gerado_em       TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(empresa_id)
);

-- Fase 7: estado de contacto / outreach (dados manuais/operacionais)
CREATE TABLE IF NOT EXISTS outreach (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    empresa_id          INTEGER NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    email_contacto      TEXT,          -- email escolhido de emails_candidatos
    decisor              TEXT,          -- nome/cargo do decisor (preenchimento manual)
    estado_contacto     TEXT NOT NULL DEFAULT 'por_contactar' CHECK (estado_contacto IN (
                            'por_contactar', 'email_1_enviado', 'email_2_enviado',
                            'email_3_enviado', 'respondeu', 'reuniao_marcada',
                            'sem_interesse', 'convertido'
                        )),
    notas               TEXT,
    atualizado_em        TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(empresa_id)
);

-- View de conveniencia: linha unica por empresa com o essencial para outreach
CREATE VIEW IF NOT EXISTS v_empresas_outreach AS
SELECT
    e.id,
    e.nif,
    e.nome,
    d.dominio,
    e.concelho,
    e.cae,
    a.tipo_chatbot,
    a.sinais_json,
    a.exemplo_falha_chatbot,
    s.ordem_servicos_json,
    s.justificacoes_json,
    se.email_1,
    se.email_2,
    se.email_3,
    o.email_contacto,
    o.decisor,
    o.estado_contacto
FROM empresas e
LEFT JOIN dominios d ON d.empresa_id = e.id
LEFT JOIN analises_website a ON a.empresa_id = e.id
LEFT JOIN servicos_ordenados s ON s.empresa_id = e.id
LEFT JOIN sequencias_email se ON se.empresa_id = e.id
LEFT JOIN outreach o ON o.empresa_id = e.id;
