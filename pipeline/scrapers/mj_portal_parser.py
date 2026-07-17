"""Parsing do HTML de resultados de publicacoes.mj.pt (Portal da Justica).

NOTA IMPORTANTE SOBRE CALIBRACAO
---------------------------------
A pesquisa em publicacoes.mj.pt esta protegida por reCAPTCHA invisivel, pelo que
nao foi possivel inspecionar uma pagina de resultados real sem resolver o captcha
manualmente. Este parser foi escrito com base na estrutura tipica de um
ASP.NET GridView (a mesma tecnologia usada no resto do site) e assume:

  - Uma tabela de resultados cujo id/class contem "grid" (case-insensitive),
    ou, em alternativa, a maior <table> dentro do painel de conteudo principal.
  - Uma linha de cabecalho seguida de uma linha por publicacao.
  - Colunas, por ordem, com: NIF, Nome/Entidade, CAE, Concelho, Data do Ato, Estado.

Apos a primeira execucao real (pipeline/scrapers/mj_portal.py em modo interativo,
com o browser visivel), usa `scripts/inspect_raw_html.py <ficheiro.html>` para
confirmar a estrutura real da tabela e ajustar `COLUNAS` e `_localizar_tabela_resultados`
abaixo se necessario.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup, Tag

from pipeline.utils.logging_config import get_logger

logger = get_logger(__name__)

# Mapeamento posicional das colunas da tabela de resultados (indice baseado em 0).
# AJUSTAR apos confirmar a estrutura real da tabela (ver nota acima).
COLUNAS = {
    "nif": 0,
    "nome": 1,
    "cae": 2,
    "concelho": 3,
    "data_ato": 4,
    "estado": 5,
}


@dataclass
class PublicacaoResult:
    nif: str
    nome: str
    cae: Optional[str] = None
    concelho: Optional[str] = None
    data_ato: Optional[str] = None
    estado: Optional[str] = None
    fonte_url: Optional[str] = None

    def is_valid(self) -> bool:
        return bool(self.nif and self.nome)


def _localizar_tabela_resultados(soup: BeautifulSoup) -> Optional[Tag]:
    candidatos = soup.find_all("table")
    if not candidatos:
        return None

    # 1. Preferir tabela cujo id/class sugira ser a grid de resultados.
    for tabela in candidatos:
        identificador = " ".join([tabela.get("id", ""), " ".join(tabela.get("class", []))]).lower()
        if "grid" in identificador or "result" in identificador:
            return tabela

    # 2. Fallback: maior tabela por numero de linhas (assume ser a de resultados).
    maior = max(candidatos, key=lambda t: len(t.find_all("tr")))
    if len(maior.find_all("tr")) > 1:
        return maior

    return None


def _texto_celula(celulas: list[Tag], indice: int) -> str:
    if indice >= len(celulas):
        return ""
    return celulas[indice].get_text(strip=True)


def parse_results_page(html: str, fonte_url: Optional[str] = None) -> list[PublicacaoResult]:
    """Extrai a lista de publicacoes de uma pagina de resultados (HTML raw)."""
    soup = BeautifulSoup(html, "lxml")
    tabela = _localizar_tabela_resultados(soup)
    if tabela is None:
        logger.warning("Nenhuma tabela de resultados encontrada na pagina")
        return []

    linhas = tabela.find_all("tr")
    resultados: list[PublicacaoResult] = []

    for linha in linhas:
        celulas = linha.find_all(["td"])
        if not celulas:
            continue  # provavelmente a linha de cabecalho (th) ou linha de paginacao

        resultado = PublicacaoResult(
            nif=_texto_celula(celulas, COLUNAS["nif"]),
            nome=_texto_celula(celulas, COLUNAS["nome"]),
            cae=_texto_celula(celulas, COLUNAS["cae"]) or None,
            concelho=_texto_celula(celulas, COLUNAS["concelho"]) or None,
            data_ato=_texto_celula(celulas, COLUNAS["data_ato"]) or None,
            estado=_texto_celula(celulas, COLUNAS["estado"]) or None,
            fonte_url=fonte_url,
        )

        if resultado.is_valid():
            resultados.append(resultado)
        else:
            logger.debug("Linha ignorada por falta de NIF/Nome: %s", [c.get_text(strip=True) for c in celulas])

    logger.info("Parseadas %d publicacoes da pagina", len(resultados))
    return resultados


def has_next_page(html: str) -> bool:
    """Deteta se existe um link de paginacao 'seguinte' na pagina (heuristica generica)."""
    soup = BeautifulSoup(html, "lxml")
    for link in soup.find_all("a"):
        texto = link.get_text(strip=True).lower()
        if texto in {"seguinte", "próximo", "proximo", ">", "»"}:
            return True
    return False
