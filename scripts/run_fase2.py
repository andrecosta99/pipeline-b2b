#!/usr/bin/env python3
"""CLI para executar a Fase 2 (descoberta de dominio para empresas sem site).

So processa empresas que ainda nao tem nenhuma linha em `dominios` (ou seja,
nao tenta de novo automaticamente empresas ja processadas, mesmo que a
tentativa anterior tenha falhado - usa --retry-falhados para isso).

Uso:
    python scripts/run_fase2.py
    python scripts/run_fase2.py --limite 20
    python scripts/run_fase2.py --threshold 65
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import settings  # noqa: E402
from pipeline.db.database import (  # noqa: E402
    db_session,
    empresas_sem_dominio,
    init_db,
    upsert_dominio,
)
from pipeline.discovery.domain_discovery import THRESHOLD_DEFAULT, descobrir_dominio  # noqa: E402
from pipeline.discovery.search_provider import get_search_provider  # noqa: E402
from pipeline.utils.logging_config import get_logger  # noqa: E402
from pipeline.utils.rate_limiter import RateLimiter  # noqa: E402

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limite", type=int, help="Numero maximo de empresas a processar nesta execucao")
    parser.add_argument(
        "--threshold", type=int, default=THRESHOLD_DEFAULT, help=f"Score minimo de fuzzy match (default: {THRESHOLD_DEFAULT})"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    init_db()

    try:
        provider = get_search_provider()
    except ValueError as exc:
        logger.error("Configuracao do motor de pesquisa invalida: %s", exc)
        return 1

    logger.info("Fase 2: a usar o motor de pesquisa '%s'", provider.nome)

    rate_limiter = RateLimiter(settings.rate_limit_min_seconds, settings.rate_limit_max_seconds)

    with db_session() as conn:
        empresas = empresas_sem_dominio(conn)
        if args.limite:
            empresas = empresas[: args.limite]

        total = len(empresas)
        logger.info("%d empresas sem dominio a processar", total)

        validados = 0
        for i, empresa in enumerate(empresas, start=1):
            logger.info("[%d/%d] %s (%s)", i, total, empresa["nome"], empresa["concelho"])

            try:
                resultado = descobrir_dominio(
                    provider,
                    nome_empresa=empresa["nome"],
                    concelho=empresa["concelho"],
                    threshold=args.threshold,
                )
            except Exception:
                logger.exception("Erro ao pesquisar dominio para '%s'", empresa["nome"])
                if i < total:
                    rate_limiter.wait()
                continue

            upsert_dominio(
                conn,
                empresa_id=empresa["id"],
                dominio=resultado.dominio,
                url_homepage=resultado.url_homepage,
                metodo_busca=provider.nome,
                score_fuzzy=resultado.score_fuzzy,
                validado=resultado.validado,
            )
            conn.commit()

            if resultado.validado:
                validados += 1
                logger.info("  -> dominio: %s (score %.0f)", resultado.dominio, resultado.score_fuzzy)
            else:
                logger.info("  -> sem dominio valido (melhor score: %.0f)", resultado.score_fuzzy)

            if i < total:
                rate_limiter.wait()

    print(f"\nEmpresas processadas: {total}")
    print(f"Dominios validados: {validados}")
    print(f"Sem dominio valido: {total - validados}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
