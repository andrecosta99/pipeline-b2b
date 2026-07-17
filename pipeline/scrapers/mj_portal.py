"""Fase 1 - Recolha de universo de empresas no Portal da Justica (publicacoes.mj.pt).

A pesquisa neste portal esta protegida por reCAPTCHA invisivel da Google. Este
scraper usa Playwright com um perfil de browser persistente (para reter a
confianca da sessao entre execucoes) e, caso a Google exija um desafio visivel
de captcha, PAUSA e pede para o resolveres manualmente na janela do browser
antes de continuar a automacao da pesquisa e da paginacao. Nao ha nenhuma
tentativa de resolucao automatica/bypass do captcha.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from pipeline.config import settings
from pipeline.db.database import db_session, init_db, upsert_empresa
from pipeline.scrapers.mj_portal_parser import has_next_page, parse_results_page
from pipeline.utils.logging_config import get_logger
from pipeline.utils.rate_limiter import RateLimiter

logger = get_logger(__name__)

PESQUISA_URL = "https://publicacoes.mj.pt/Pesquisa.aspx"

SEL_DISTRITO = "#ctl00_ContentPlaceHolderMain_comboDadosPubDistrito"
SEL_DATA_INICIO = "#ctl00_ContentPlaceHolderMain_txtDataInit"
SEL_DATA_FIM = "#ctl00_ContentPlaceHolderMain_txtDataFim"
SEL_BOTAO_PESQUISAR = "#ctl00_ContentPlaceHolderMain_btSearch"
SEL_RECAPTCHA_IFRAME = "iframe[src*='recaptcha']"


@dataclass
class Fase1Stats:
    paginas_percorridas: int = 0
    empresas_guardadas: int = 0
    linhas_invalidas: int = 0


def _formatar_data_pt(iso_date: str) -> str:
    """Converte AAAA-MM-DD para dd-mm-aaaa (formato usado nos campos do portal)."""
    dt = datetime.strptime(iso_date, "%Y-%m-%d")
    return dt.strftime("%d-%m-%Y")


def _janela_datas_default() -> tuple[str, str]:
    hoje = datetime.now()
    inicio = hoje - timedelta(days=30)
    return inicio.strftime("%d-%m-%Y"), hoje.strftime("%d-%m-%Y")


def _aguardar_resolucao_captcha_se_necessario(page: Page, timeout_s: int = 5) -> None:
    """Se a Google exigir um desafio visivel de captcha, pausa para resolucao manual."""
    try:
        page.wait_for_selector(SEL_RECAPTCHA_IFRAME, timeout=timeout_s * 1000, state="visible")
    except PlaywrightTimeoutError:
        return  # nenhum desafio visivel detetado, provavelmente passou no modo invisivel

    logger.warning("Desafio de reCAPTCHA detetado. Resolve-o manualmente na janela do browser.")
    input(">> Resolve o captcha na janela do Chrome/Chromium e prime ENTER aqui para continuar... ")


def _guardar_raw_html(html: str, distrito: str, indice_pagina: int) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    nome_ficheiro = f"mj_{distrito.lower()}_pagina{indice_pagina:03d}_{timestamp}.html"
    caminho = settings.raw_html_dir / nome_ficheiro
    caminho.write_text(html, encoding="utf-8")
    logger.info("HTML raw guardado em %s", caminho)
    return caminho


def _preencher_formulario_pesquisa(page: Page, data_inicio: str, data_fim: str) -> None:
    page.goto(PESQUISA_URL, wait_until="networkidle")

    page.select_option(SEL_DISTRITO, value=settings.mj_distrito_codigo)
    # A selecao do distrito despoleta um postback (__doPostBack) que recarrega o
    # combo de concelhos; aguardamos que a rede estabilize antes de continuar.
    page.wait_for_load_state("networkidle")

    page.fill(SEL_DATA_INICIO, data_inicio)
    page.fill(SEL_DATA_FIM, data_fim)

    page.click(SEL_BOTAO_PESQUISAR)
    page.wait_for_load_state("networkidle")
    _aguardar_resolucao_captcha_se_necessario(page)
    # Depois de resolver o captcha manualmente (ou se nao foi necessario),
    # aguarda que a navegacao/postback dos resultados estabilize.
    page.wait_for_load_state("networkidle")


def _avancar_pagina(page: Page) -> bool:
    """Tenta clicar no link de 'proxima pagina'. Devolve False se nao existir."""
    for texto in ["Seguinte", "Próximo", "Proximo", ">", "»"]:
        link = page.get_by_text(texto, exact=True)
        try:
            if link.count() > 0 and link.first.is_visible():
                link.first.click()
                page.wait_for_load_state("networkidle")
                return True
        except PlaywrightTimeoutError:
            continue
    return False


def run_fase1(
    *,
    data_inicio: Optional[str] = None,
    data_fim: Optional[str] = None,
    max_paginas: Optional[int] = None,
) -> Fase1Stats:
    """Executa a Fase 1 completa: pesquisa, paginacao, guarda raw HTML, parse e grava na DB."""
    init_db()

    if data_inicio and data_fim:
        data_inicio_pt = _formatar_data_pt(data_inicio)
        data_fim_pt = _formatar_data_pt(data_fim)
    else:
        data_inicio_pt, data_fim_pt = _janela_datas_default()

    max_paginas = max_paginas if max_paginas is not None else settings.mj_max_paginas
    rate_limiter = RateLimiter(settings.rate_limit_min_seconds, settings.rate_limit_max_seconds)
    stats = Fase1Stats()

    logger.info(
        "Fase 1: a pesquisar distrito=%s entre %s e %s",
        settings.mj_distrito,
        data_inicio_pt,
        data_fim_pt,
    )

    with sync_playwright() as p:
        contexto = p.chromium.launch_persistent_context(
            user_data_dir=str(settings.playwright_user_data_dir),
            headless=settings.playwright_headless,
            user_agent=settings.http_user_agent,
        )
        page = contexto.new_page()

        try:
            _preencher_formulario_pesquisa(page, data_inicio_pt, data_fim_pt)

            indice_pagina = 1
            with db_session() as conn:
                while True:
                    html = page.content()
                    _guardar_raw_html(html, settings.mj_distrito, indice_pagina)

                    resultados = parse_results_page(html, fonte_url=page.url)
                    for resultado in resultados:
                        upsert_empresa(
                            conn,
                            nif=resultado.nif,
                            nome=resultado.nome,
                            cae=resultado.cae,
                            concelho=resultado.concelho,
                            distrito=settings.mj_distrito,
                            data_ato=resultado.data_ato,
                            estado=resultado.estado,
                            fonte_url=resultado.fonte_url,
                        )
                        stats.empresas_guardadas += 1

                    stats.paginas_percorridas += 1
                    conn.commit()

                    if max_paginas and indice_pagina >= max_paginas:
                        logger.info("Limite de paginas (%d) atingido, a parar.", max_paginas)
                        break

                    if not has_next_page(html):
                        logger.info("Sem mais paginas de resultados.")
                        break

                    rate_limiter.wait()
                    avancou = _avancar_pagina(page)
                    if not avancou:
                        logger.info("Nao foi possivel avancar para a proxima pagina, a parar.")
                        break
                    indice_pagina += 1

        except Exception:
            logger.exception("Erro na Fase 1 durante a automacao do browser")
            raise
        finally:
            contexto.close()

    logger.info(
        "Fase 1 concluida: %d paginas, %d empresas guardadas",
        stats.paginas_percorridas,
        stats.empresas_guardadas,
    )
    return stats
