#!/usr/bin/env python3
"""CLI para executar a Fase 1 (recolha de universo no Portal da Justica, distrito de Aveiro).

Uso:
    python scripts/run_fase1.py
    python scripts/run_fase1.py --data-inicio 2026-06-01 --data-fim 2026-07-17
    python scripts/run_fase1.py --max-paginas 3
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.scrapers.mj_portal import run_fase1  # noqa: E402
from pipeline.utils.logging_config import get_logger  # noqa: E402

logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-inicio", help="AAAA-MM-DD (default: hoje - 30 dias)")
    parser.add_argument("--data-fim", help="AAAA-MM-DD (default: hoje)")
    parser.add_argument("--max-paginas", type=int, help="Limite de seguranca de paginas a percorrer")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        stats = run_fase1(
            data_inicio=args.data_inicio,
            data_fim=args.data_fim,
            max_paginas=args.max_paginas,
        )
    except KeyboardInterrupt:
        logger.warning("Interrompido pelo utilizador")
        return 130
    except Exception:
        logger.exception("Fase 1 terminou com erro")
        return 1

    print(f"\nPaginas percorridas: {stats.paginas_percorridas}")
    print(f"Empresas guardadas/atualizadas: {stats.empresas_guardadas}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
