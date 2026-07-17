"""Fase 3 (parte 1) - Visita o website de uma empresa e recolhe sinais brutos:
HTML da homepage e da pagina de contacto, deteccao de widget de chatbot, e
(best-effort) uma resposta capturada a uma pergunta fora do guiao enviada ao
widget, se um for encontrado.

A interacao com o widget de chat e heuristica/best-effort: cada fornecedor
de chat usa uma UI diferente, por isso os seletores usados aqui sao
genericos e podem nao funcionar em todos os sites. Quando a interacao falha,
a analise continua na mesma, so sem `resposta_chatbot` (a Fase 3 parte 2,
a classificacao via Claude, usa entao so o conteudo da homepage).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, sync_playwright

from pipeline.analysis.chatbot_detection import detect_widget
from pipeline.config import settings
from pipeline.utils.logging_config import get_logger

logger = get_logger(__name__)

PERGUNTA_FORA_GUIAO = "Vendem/trabalham também fora de Portugal?"

TEXTOS_LINK_CONTACTO = ["contacto", "contactos", "contact", "sobre", "about", "quem somos"]

SELETORES_LAUNCHER_CHAT = [
    "iframe[title*='chat' i]",
    "button[aria-label*='chat' i]",
    "[class*='launcher' i]",
    "[id*='launcher' i]",
    "[class*='chat-widget' i]",
    "[id*='chat-widget' i]",
]

SELETORES_INPUT_CHAT = ["textarea", "input[type='text']", "[contenteditable='true']"]


@dataclass
class AnaliseWebsiteRaw:
    empresa_id: int
    homepage_html: str = ""
    homepage_texto: str = ""
    contacto_html: Optional[str] = None
    widget_detectado: Optional[str] = None
    resposta_chatbot: Optional[str] = None
    erro: Optional[str] = None


def _encontrar_href_contacto(page) -> Optional[str]:
    for texto in TEXTOS_LINK_CONTACTO:
        try:
            link = page.get_by_role("link", name=re.compile(texto, re.IGNORECASE))
            if link.count() > 0:
                href = link.first.get_attribute("href")
                if href:
                    return href
        except Exception:
            continue
    return None


def _resolver_url(base: str, href: str) -> str:
    if href.startswith("http"):
        return href
    return base.rstrip("/") + "/" + href.lstrip("/")


def _clicar_launcher_chat(page) -> bool:
    for seletor in SELETORES_LAUNCHER_CHAT:
        try:
            elemento = page.locator(seletor).first
            if elemento.is_visible(timeout=2000):
                elemento.click(timeout=3000)
                return True
        except Exception:
            continue
    return False


def _enviar_pergunta_e_capturar_resposta(page, pergunta: str) -> Optional[str]:
    for seletor in SELETORES_INPUT_CHAT:
        try:
            campo = page.locator(seletor).last
            if not campo.is_visible(timeout=2000):
                continue
            campo.click()
            campo.fill(pergunta)
            page.keyboard.press("Enter")
            page.wait_for_timeout(4000)  # espera best-effort pela resposta, sem deteccao de streaming
            texto_pagina = page.inner_text("body")
            return texto_pagina[-1500:]
        except Exception:
            continue
    return None


def analisar_website(empresa_id: int, dominio: str) -> AnaliseWebsiteRaw:
    """Visita a homepage + pagina de contacto de uma empresa e recolhe sinais brutos."""
    url_homepage = f"https://{dominio}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(user_agent=settings.http_user_agent)

        try:
            try:
                page.goto(url_homepage, wait_until="networkidle", timeout=20000)
            except PlaywrightTimeoutError:
                page.goto(url_homepage, wait_until="domcontentloaded", timeout=20000)
        except Exception as exc:
            logger.warning("Falha ao abrir %s: %s", url_homepage, exc)
            browser.close()
            return AnaliseWebsiteRaw(empresa_id=empresa_id, erro=str(exc))

        homepage_html = page.content()
        homepage_texto = page.inner_text("body")[:8000]

        contacto_html = None
        href_contacto = _encontrar_href_contacto(page)
        if href_contacto:
            try:
                page.goto(_resolver_url(url_homepage, href_contacto), wait_until="networkidle", timeout=15000)
                contacto_html = page.content()
            except Exception:
                logger.debug("Falha ao abrir pagina de contacto de %s", dominio, exc_info=True)

        widget = detect_widget(homepage_html)
        resposta_chatbot = None
        if widget:
            try:
                page.goto(url_homepage, wait_until="domcontentloaded", timeout=15000)
                if _clicar_launcher_chat(page):
                    resposta_chatbot = _enviar_pergunta_e_capturar_resposta(page, PERGUNTA_FORA_GUIAO)
            except Exception:
                logger.debug("Falha ao interagir com o widget de chat de %s", dominio, exc_info=True)

        browser.close()

        return AnaliseWebsiteRaw(
            empresa_id=empresa_id,
            homepage_html=homepage_html,
            homepage_texto=homepage_texto,
            contacto_html=contacto_html,
            widget_detectado=widget,
            resposta_chatbot=resposta_chatbot,
        )
