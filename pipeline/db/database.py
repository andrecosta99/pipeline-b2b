"""Acesso a base de dados SQLite do pipeline."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Optional

from pipeline.config import settings
from pipeline.utils.logging_config import get_logger

logger = get_logger(__name__)


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    path = db_path or settings.database_path
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Aplica o schema.sql (idempotente, usa CREATE TABLE IF NOT EXISTS)."""
    path = db_path or settings.database_path
    sql = settings.schema_path.read_text(encoding="utf-8")
    with get_connection(path) as conn:
        conn.executescript(sql)
    logger.info("Base de dados inicializada em %s", path)


@contextmanager
def db_session(db_path: Optional[Path] = None) -> Iterator[sqlite3.Connection]:
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _encontrar_empresa_existente(
    conn: sqlite3.Connection, *, nif: Optional[str], nome: str, concelho: Optional[str]
) -> Optional[sqlite3.Row]:
    """Localiza uma empresa existente por NIF (se presente) ou por nome+concelho."""
    if nif:
        row = conn.execute("SELECT id FROM empresas WHERE nif = ?", (nif,)).fetchone()
        if row:
            return row
    return conn.execute(
        "SELECT id FROM empresas WHERE nome = ? AND concelho IS ?", (nome, concelho)
    ).fetchone()


def upsert_empresa(
    conn: sqlite3.Connection,
    *,
    nome: str,
    nif: Optional[str] = None,
    cae: Optional[str] = None,
    concelho: Optional[str] = None,
    freguesia: Optional[str] = None,
    distrito: str = "Aveiro",
    data_ato: Optional[str] = None,
    tipo_ato: Optional[str] = None,
    estado: Optional[str] = None,
    fonte: str = "csv_manual",
    fonte_url: Optional[str] = None,
    raw_html_path: Optional[str] = None,
) -> int:
    """Insere ou atualiza uma empresa. Deduplica por NIF quando presente,
    caso contrario por (nome, concelho). Devolve o id da linha."""
    existente = _encontrar_empresa_existente(conn, nif=nif, nome=nome, concelho=concelho)

    if existente:
        conn.execute(
            """
            UPDATE empresas SET
                nif = COALESCE(:nif, nif),
                nome = :nome,
                cae = COALESCE(:cae, cae),
                concelho = COALESCE(:concelho, concelho),
                freguesia = COALESCE(:freguesia, freguesia),
                data_ato = COALESCE(:data_ato, data_ato),
                tipo_ato = COALESCE(:tipo_ato, tipo_ato),
                estado = COALESCE(:estado, estado),
                fonte_url = COALESCE(:fonte_url, fonte_url),
                raw_html_path = COALESCE(:raw_html_path, raw_html_path),
                atualizado_em = datetime('now')
            WHERE id = :id
            """,
            {
                "id": existente["id"],
                "nif": nif,
                "nome": nome,
                "cae": cae,
                "concelho": concelho,
                "freguesia": freguesia,
                "data_ato": data_ato,
                "tipo_ato": tipo_ato,
                "estado": estado,
                "fonte_url": fonte_url,
                "raw_html_path": raw_html_path,
            },
        )
        return existente["id"]

    cursor = conn.execute(
        """
        INSERT INTO empresas
            (nif, nome, cae, concelho, freguesia, distrito, data_ato, tipo_ato, estado, fonte, fonte_url, raw_html_path)
        VALUES
            (:nif, :nome, :cae, :concelho, :freguesia, :distrito, :data_ato, :tipo_ato, :estado, :fonte, :fonte_url, :raw_html_path)
        """,
        {
            "nif": nif,
            "nome": nome,
            "cae": cae,
            "concelho": concelho,
            "freguesia": freguesia,
            "distrito": distrito,
            "data_ato": data_ato,
            "tipo_ato": tipo_ato,
            "estado": estado,
            "fonte": fonte,
            "fonte_url": fonte_url,
            "raw_html_path": raw_html_path,
        },
    )
    return cursor.lastrowid


def upsert_dominio(
    conn: sqlite3.Connection,
    *,
    empresa_id: int,
    dominio: str,
    url_homepage: Optional[str] = None,
    metodo_busca: str = "csv_manual",
    score_fuzzy: Optional[float] = None,
    validado: bool = True,
) -> int:
    """Insere ou atualiza o dominio de uma empresa (chave unica = empresa_id)."""
    conn.execute(
        """
        INSERT INTO dominios (empresa_id, dominio, url_homepage, metodo_busca, score_fuzzy, validado)
        VALUES (:empresa_id, :dominio, :url_homepage, :metodo_busca, :score_fuzzy, :validado)
        ON CONFLICT(empresa_id) DO UPDATE SET
            dominio = excluded.dominio,
            url_homepage = COALESCE(excluded.url_homepage, dominios.url_homepage),
            metodo_busca = excluded.metodo_busca,
            score_fuzzy = COALESCE(excluded.score_fuzzy, dominios.score_fuzzy),
            validado = excluded.validado
        """,
        {
            "empresa_id": empresa_id,
            "dominio": dominio,
            "url_homepage": url_homepage,
            "metodo_busca": metodo_busca,
            "score_fuzzy": score_fuzzy,
            "validado": int(validado),
        },
    )
    row = conn.execute("SELECT id FROM dominios WHERE empresa_id = ?", (empresa_id,)).fetchone()
    return row["id"]


def count_empresas(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM empresas").fetchone()["n"]
