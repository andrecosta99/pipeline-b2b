"""Abstracao do motor de pesquisa usado na Fase 2 (descoberta de dominio).

Permite trocar entre Google Custom Search API e Bing Search API via a
variavel de ambiente SEARCH_PROVIDER, sem alterar o resto do pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import requests

from pipeline.config import settings
from pipeline.utils.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class SearchResult:
    titulo: str
    url: str
    snippet: str = ""


class SearchProvider(Protocol):
    nome: str

    def search(self, query: str, num_resultados: int = 5) -> list[SearchResult]: ...


class GoogleCSEProvider:
    nome = "google"
    _ENDPOINT = "https://www.googleapis.com/customsearch/v1"

    def __init__(self, api_key: str, cse_id: str):
        if not api_key or not cse_id:
            raise ValueError("GOOGLE_CSE_API_KEY e GOOGLE_CSE_ID sao obrigatorios para o provider 'google'")
        self.api_key = api_key
        self.cse_id = cse_id

    def search(self, query: str, num_resultados: int = 5) -> list[SearchResult]:
        params = {
            "key": self.api_key,
            "cx": self.cse_id,
            "q": query,
            "num": min(num_resultados, 10),
            "gl": "pt",
            "hl": "pt-PT",
        }
        resposta = requests.get(self._ENDPOINT, params=params, timeout=15)
        resposta.raise_for_status()
        dados = resposta.json()

        resultados = []
        for item in dados.get("items", []):
            resultados.append(
                SearchResult(
                    titulo=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                )
            )
        return resultados


class BingSearchProvider:
    nome = "bing"
    _ENDPOINT = "https://api.bing.microsoft.com/v7.0/search"

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("BING_SEARCH_API_KEY e obrigatorio para o provider 'bing'")
        self.api_key = api_key

    def search(self, query: str, num_resultados: int = 5) -> list[SearchResult]:
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        params = {"q": query, "count": num_resultados, "mkt": "pt-PT"}
        resposta = requests.get(self._ENDPOINT, headers=headers, params=params, timeout=15)
        resposta.raise_for_status()
        dados = resposta.json()

        resultados = []
        for item in dados.get("webPages", {}).get("value", []):
            resultados.append(
                SearchResult(
                    titulo=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                )
            )
        return resultados


def get_search_provider() -> SearchProvider:
    """Instancia o provider configurado em SEARCH_PROVIDER (google | bing)."""
    provider = settings.search_provider.lower()
    if provider == "google":
        return GoogleCSEProvider(settings.google_cse_api_key, settings.google_cse_id)
    if provider == "bing":
        return BingSearchProvider(settings.bing_search_api_key)
    raise ValueError(f"SEARCH_PROVIDER desconhecido: {provider!r} (usa 'google' ou 'bing')")
