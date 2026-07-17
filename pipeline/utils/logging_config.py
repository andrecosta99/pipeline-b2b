"""Configuracao de logging partilhada por todos os modulos do pipeline."""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from pipeline.config import settings

_CONFIGURED = False


def get_logger(name: str) -> logging.Logger:
    """Devolve um logger configurado com output para consola e ficheiro rotativo."""
    _configure_root_once()
    return logging.getLogger(name)


def _configure_root_once() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger("pipeline")
    root.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    root.addHandler(console_handler)

    log_file = settings.logs_dir / "pipeline.log"
    file_handler = RotatingFileHandler(log_file, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    _CONFIGURED = True
