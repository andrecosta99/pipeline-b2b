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


def upsert_empresa(
    conn: sqlite3.Connection,
    *,
    nif: str,
    nome: str,
    cae: Optional[str] = None,
    concelho: Optional[str] = None,
    distrito: str = "Aveiro",
    data_ato: Optional[str] = None,
    tipo_ato: Optional[str] = None,
    estado: Optional[str] = None,
    fonte_url: Optional[str] = None,
    raw_html_path: Optional[str] = None,
) -> int:
    """Insere ou atualiza uma empresa pelo NIF. Devolve o id da linha."""
    conn.execute(
        """
        INSERT INTO empresas (nif, nome, cae, concelho, distrito, data_ato, tipo_ato, estado, fonte_url, raw_html_path)
        VALUES (:nif, :nome, :cae, :concelho, :distrito, :data_ato, :tipo_ato, :estado, :fonte_url, :raw_html_path)
        ON CONFLICT(nif) DO UPDATE SET
            nome = excluded.nome,
            cae = COALESCE(excluded.cae, empresas.cae),
            concelho = COALESCE(excluded.concelho, empresas.concelho),
            data_ato = COALESCE(excluded.data_ato, empresas.data_ato),
            tipo_ato = COALESCE(excluded.tipo_ato, empresas.tipo_ato),
            estado = COALESCE(excluded.estado, empresas.estado),
            fonte_url = COALESCE(excluded.fonte_url, empresas.fonte_url),
            raw_html_path = COALESCE(excluded.raw_html_path, empresas.raw_html_path),
            atualizado_em = datetime('now')
        """,
        {
            "nif": nif,
            "nome": nome,
            "cae": cae,
            "concelho": concelho,
            "distrito": distrito,
            "data_ato": data_ato,
            "tipo_ato": tipo_ato,
            "estado": estado,
            "fonte_url": fonte_url,
            "raw_html_path": raw_html_path,
        },
    )
    row = conn.execute("SELECT id FROM empresas WHERE nif = ?", (nif,)).fetchone()
    return row["id"]


def count_empresas(conn: sqlite3.Connection) -> int:
    return conn.execute("SELECT COUNT(*) AS n FROM empresas").fetchone()["n"]
