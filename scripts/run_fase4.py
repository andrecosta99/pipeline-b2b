#!/usr/bin/env python3
"""CLI para executar a Fase 4 (recolha de emails de contacto).

So processa empresas com dominio validado (Fase 2) que ainda nao tem
nenhuma tentativa registada em `emails_candidatos`.

Uso:
    python scripts/run_fase4.py
    python scripts/run_fase4.py --limite 20
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import settings  # noqa: E402
from pipeline.contacts.email_finder import procurar_emails  # noqa: E402
from pipeline.db.database import (  # noqa: E402
    db_session,
    empresas_com_dominio_sem_email,
    init_db,
    registar_emails_candidatos,
)
from pipeline.utils.logging_config import get_logger  # noqa: E402
from pipeline.utils.rate_limiter import RateLimiter  # noqa: E402

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limite", type=int, help="Numero maximo de empresas a processar nesta execucao")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()

    rate_limiter = RateLimiter(settings.rate_limit_min_seconds, settings.rate_limit_max_seconds)

    with db_session() as conn:
        empresas = empresas_com_dominio_sem_email(conn)
        if args.limite:
            empresas = empresas[: args.limite]

        total = len(empresas)
        logger.info("%d empresas com dominio a processar", total)

        com_email = 0
        total_emails = 0
        for i, empresa in enumerate(empresas, start=1):
            logger.info("[%d/%d] %s (%s)", i, total, empresa["nome"], empresa["dominio"])

            try:
                candidatos = procurar_emails(empresa["dominio"])
            except Exception:
                logger.exception("Erro ao procurar emails para '%s'", empresa["nome"])
                if i < total:
                    rate_limiter.wait()
                continue

            n = registar_emails_candidatos(
                conn,
                empresa_id=empresa["id"],
                candidatos=[(c.email, c.origem_pagina) for c in candidatos],
            )
            conn.commit()

            if n:
                com_email += 1
                total_emails += n
                logger.info("  -> %d email(s) encontrado(s): %s", n, ", ".join(c.email for c in candidatos))
            else:
                logger.info("  -> nenhum email encontrado")

            if i < total:
                rate_limiter.wait()

    print(f"\nEmpresas processadas: {total}")
    print(f"Empresas com pelo menos 1 email: {com_email}")
    print(f"Total de emails candidatos gravados: {total_emails}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
