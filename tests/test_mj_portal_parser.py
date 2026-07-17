from pathlib import Path

from pipeline.scrapers.mj_portal_parser import has_next_page, parse_results_page

FIXTURE = Path(__file__).parent / "fixtures" / "mj_resultados_exemplo.html"


def test_parse_results_page_extrai_publicacoes_validas():
    html = FIXTURE.read_text(encoding="utf-8")
    resultados = parse_results_page(html, fonte_url="https://publicacoes.mj.pt/Pesquisa.aspx")

    assert len(resultados) == 2

    primeiro = resultados[0]
    assert primeiro.nif == "500123456"
    assert primeiro.nome == "Metalurgica Aveirense, Lda"
    assert primeiro.cae == "25110"
    assert primeiro.concelho == "Aveiro"
    assert primeiro.data_ato == "10-07-2026"
    assert primeiro.estado == "Ativa"
    assert primeiro.fonte_url == "https://publicacoes.mj.pt/Pesquisa.aspx"


def test_parse_results_page_ignora_linhas_sem_nif_ou_nome():
    html = FIXTURE.read_text(encoding="utf-8")
    resultados = parse_results_page(html)
    nifs = [r.nif for r in resultados]
    assert "" not in nifs


def test_has_next_page_deteta_link_seguinte():
    html = FIXTURE.read_text(encoding="utf-8")
    assert has_next_page(html) is True


def test_has_next_page_sem_link_devolve_false():
    html = "<html><body><table><tr><td>x</td></tr></table></body></html>"
    assert has_next_page(html) is False
