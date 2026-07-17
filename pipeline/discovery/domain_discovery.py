"""Fase 2 - Descoberta de dominio para empresas sem site conhecido.

Para cada empresa, pesquisa "{nome} {concelho}" no motor configurado
(Google CSE ou Bing), e valida os resultados por fuzzy match do nome da
empresa contra o titulo e o dominio devolvidos, antes de aceitar.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from rapidfuzz import fuzz

from pipeline.discovery.search_provider import SearchProvider
from pipeline.utils.domains import normalize_domain
from pipeline.utils.logging_config import get_logger

logger = get_logger(__name__)

# Score minimo (0-100) de fuzzy match para aceitar um dominio como valido.
THRESHOLD_DEFAULT = 70

# Dominios que nunca devem ser aceites como "o site da empresa" mesmo que o
# nome coincida (redes sociais, diretorios de empresas, motores de busca).
DOMINIOS_EXCLUIDOS = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "twitter.com",
    "x.com",
    "tiktok.com",
    "racius.com",
    "emis.com",
    "informacaoempresas.pt",
    "empresite.economia3.com",
    "kompass.com",
    "paginasamarelas.pt",
    "google.com",
    "google.pt",
    "wikipedia.org",
    "portugalio.com",
    "cylex.pt",
    "solucoesempresariais.com.pt",
}


@dataclass
class ResultadoDescoberta:
    dominio: Optional[str]
    url_homepage: Optional[str]
    score_fuzzy: float
    validado: bool


def _melhor_score(nome_empresa: str, titulo: str, dominio: str) -> float:
    nome_norm = nome_empresa.lower()
    score_titulo = fuzz.token_set_ratio(nome_norm, titulo.lower())
    score_dominio = fuzz.token_set_ratio(nome_norm, dominio.replace(".", " ").lower())
    return max(score_titulo, score_dominio)


def descobrir_dominio(
    provider: SearchProvider,
    *,
    nome_empresa: str,
    concelho: Optional[str] = None,
    threshold: int = THRESHOLD_DEFAULT,
    num_resultados: int = 5,
) -> ResultadoDescoberta:
    """Pesquisa e valida o melhor candidato a dominio para uma empresa."""
    query = f"{nome_empresa} {concelho}" if concelho else nome_empresa
    resultados = provider.search(query, num_resultados=num_resultados)

    melhor_dominio: Optional[str] = None
    melhor_url: Optional[str] = None
    melhor_score = 0.0

    for resultado in resultados:
        dominio = normalize_domain(resultado.url)
        if not dominio or dominio in DOMINIOS_EXCLUIDOS:
            continue

        score = _melhor_score(nome_empresa, resultado.titulo, dominio)
        if score > melhor_score:
            melhor_score = score
            melhor_dominio = dominio
            melhor_url = resultado.url

    validado = melhor_dominio is not None and melhor_score >= threshold
    return ResultadoDescoberta(
        dominio=melhor_dominio if validado else None,
        url_homepage=melhor_url if validado else None,
        score_fuzzy=melhor_score,
        validado=validado,
    )
