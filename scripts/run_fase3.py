#!/usr/bin/env python3
"""CLI para executar a Fase 3 (analise de website: deteccao de chatbot + sinais).

So processa empresas com dominio validado (Fase 2) que ainda nao tem analise
registada em `analises_website`.

Uso:
    python scripts/run_fase3.py
    python scripts/run_fase3.py --limite 10
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.analysis.claude_classifier import classificar_website  # noqa: E402
from pipeline.analysis.website_analyzer import analisar_website  # noqa: E402
from pipeline.config import settings  # noqa: E402
from pipeline.db.database import (  # noqa: E402
    db_session,
    empresas_com_dominio_sem_analise,
    init_db,
    upsert_analise_website,
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

    if not settings.anthropic_api_key:
        logger.error("ANTHROPIC_API_KEY nao configurada no .env")
        return 1

    rate_limiter = RateLimiter(settings.rate_limit_min_seconds, settings.rate_limit_max_seconds)

    with db_session() as conn:
        empresas = empresas_com_dominio_sem_analise(conn)
        if args.limite:
            empresas = empresas[: args.limite]

        total = len(empresas)
        logger.info("%d empresas com dominio a analisar", total)

        analisadas = 0
        for i, empresa in enumerate(empresas, start=1):
            logger.info("[%d/%d] %s (%s)", i, total, empresa["nome"], empresa["dominio"])

            try:
                raw = analisar_website(empresa["id"], empresa["dominio"])
                if raw.erro:
                    logger.warning("  -> nao foi possivel analisar o site: %s", raw.erro)
                    if i < total:
                        rate_limiter.wait()
                    continue

                classificacao = classificar_website(raw, empresa["nome"])
            except Exception:
                logger.exception("Erro ao analisar '%s'", empresa["nome"])
                if i < total:
                    rate_limiter.wait()
                continue

            upsert_analise_website(
                conn,
                empresa_id=empresa["id"],
                tipo_chatbot=classificacao.tipo_chatbot,
                widget_detectado=raw.widget_detectado,
                exemplo_falha_chatbot=classificacao.exemplo_falha_chatbot,
                sinais_json=json.dumps(classificacao.sinais, ensure_ascii=False),
            )
            conn.commit()
            analisadas += 1
            logger.info("  -> tipo_chatbot: %s (widget: %s)", classificacao.tipo_chatbot, raw.widget_detectado)

            if i < total:
                rate_limiter.wait()

    print(f"\nEmpresas processadas: {total}")
    print(f"Analises guardadas: {analisadas}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
