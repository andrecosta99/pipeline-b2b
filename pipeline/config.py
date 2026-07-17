"""Configuracao central do pipeline, carregada a partir de variaveis de ambiente (.env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(value: str | None, default: int) -> int:
    try:
        return int(value) if value else default
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    # Anthropic
    anthropic_api_key: str = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", ""))
    anthropic_model: str = field(default_factory=lambda: os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6"))

    # Motores de pesquisa (Fase 2)
    search_provider: str = field(default_factory=lambda: os.getenv("SEARCH_PROVIDER", "google"))
    google_cse_api_key: str = field(default_factory=lambda: os.getenv("GOOGLE_CSE_API_KEY", ""))
    google_cse_id: str = field(default_factory=lambda: os.getenv("GOOGLE_CSE_ID", ""))
    bing_search_api_key: str = field(default_factory=lambda: os.getenv("BING_SEARCH_API_KEY", ""))

    # Base de dados
    database_path: Path = field(
        default_factory=lambda: BASE_DIR / os.getenv("DATABASE_PATH", "data/pipeline.db")
    )

    # Rate limiting
    rate_limit_min_seconds: float = field(
        default_factory=lambda: float(os.getenv("RATE_LIMIT_MIN_SECONDS", "3"))
    )
    rate_limit_max_seconds: float = field(
        default_factory=lambda: float(os.getenv("RATE_LIMIT_MAX_SECONDS", "5"))
    )

    # Fase 1 - Portal da Justica
    mj_distrito: str = field(default_factory=lambda: os.getenv("MJ_DISTRITO", "Aveiro"))
    mj_distrito_codigo: str = field(default_factory=lambda: os.getenv("MJ_DISTRITO_CODIGO", "01"))
    mj_data_inicio: str = field(default_factory=lambda: os.getenv("MJ_DATA_INICIO", ""))
    mj_data_fim: str = field(default_factory=lambda: os.getenv("MJ_DATA_FIM", ""))
    mj_max_paginas: int | None = field(
        default_factory=lambda: (_int(os.getenv("MJ_MAX_PAGINAS"), 0) or None)
    )

    # Playwright
    playwright_headless: bool = field(
        default_factory=lambda: _bool(os.getenv("PLAYWRIGHT_HEADLESS"), default=False)
    )
    playwright_user_data_dir: Path = field(
        default_factory=lambda: BASE_DIR / os.getenv("PLAYWRIGHT_USER_DATA_DIR", "data/playwright_profile")
    )

    # HTTP
    http_user_agent: str = field(
        default_factory=lambda: os.getenv(
            "HTTP_USER_AGENT",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
        )
    )

    # Diretorios
    raw_html_dir: Path = field(default_factory=lambda: BASE_DIR / "data" / "raw_html")
    logs_dir: Path = field(default_factory=lambda: BASE_DIR / "data" / "logs")
    schema_path: Path = field(default_factory=lambda: BASE_DIR / "schema.sql")

    def ensure_dirs(self) -> None:
        self.raw_html_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.playwright_user_data_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
settings.ensure_dirs()
