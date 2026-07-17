from pipeline.discovery.domain_discovery import descobrir_dominio
from pipeline.discovery.search_provider import SearchResult


class FakeProvider:
    nome = "fake"

    def __init__(self, resultados: list[SearchResult]):
        self._resultados = resultados

    def search(self, query: str, num_resultados: int = 5) -> list[SearchResult]:
        return self._resultados


def test_descobrir_dominio_aceita_match_forte():
    provider = FakeProvider(
        [
            SearchResult(
                titulo="RIAMOLDE - Engenharia e Sistemas",
                url="https://www.riamolde.com/",
                snippet="Moldes de injecao...",
            )
        ]
    )
    resultado = descobrir_dominio(provider, nome_empresa="RIAMOLDE - ENGENHARIA E SISTEMAS S.A.", concelho="Cacia")

    assert resultado.validado is True
    assert resultado.dominio == "riamolde.com"
    assert resultado.score_fuzzy >= 70


def test_descobrir_dominio_rejeita_match_fraco():
    provider = FakeProvider(
        [
            SearchResult(titulo="Noticias de Aveiro", url="https://www.jornaldeaveiro.pt/noticia-1", snippet="...")
        ]
    )
    resultado = descobrir_dominio(provider, nome_empresa="RIAMOLDE - ENGENHARIA E SISTEMAS S.A.", concelho="Cacia")

    assert resultado.validado is False
    assert resultado.dominio is None


def test_descobrir_dominio_ignora_redes_sociais_e_diretorios():
    provider = FakeProvider(
        [
            SearchResult(titulo="Riamolde Engenharia e Sistemas SA", url="https://www.facebook.com/riamolde", snippet="..."),
            SearchResult(titulo="Riamolde - Engenharia e Sistemas", url="https://www.riamolde.com/contactos", snippet="..."),
        ]
    )
    resultado = descobrir_dominio(provider, nome_empresa="RIAMOLDE - ENGENHARIA E SISTEMAS S.A.", concelho="Cacia")

    assert resultado.dominio == "riamolde.com"


def test_descobrir_dominio_sem_resultados():
    provider = FakeProvider([])
    resultado = descobrir_dominio(provider, nome_empresa="EMPRESA SEM SITE", concelho="Ovar")

    assert resultado.validado is False
    assert resultado.dominio is None
    assert resultado.score_fuzzy == 0
