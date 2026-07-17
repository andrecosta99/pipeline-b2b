"""Fase 4 - Recolha de emails de contacto a partir do website de uma empresa.

Visita um pequeno conjunto de paginas tipicas (homepage, contacto, sobre) e
extrai todos os enderecos de email encontrados (texto solto + links
`mailto:`), com uma lista de exclusao para falsos positivos comuns
(imagens @2x, dominios de exemplo/terceiros que aparecem em templates, etc.).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

from pipeline.config import settings
from pipeline.utils.logging_config import get_logger

logger = get_logger(__name__)

CAMINHOS_A_TENTAR = [
    "/",
    "/contacto",
    "/contactos",
    "/contact",
    "/contact-us",
    "/sobre",
    "/sobre-nos",
    "/about",
    "/about-us",
    "/quem-somos",
]

_EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9.-]*[a-zA-Z]")

# Dominios que aparecem tipicamente em templates/trackers e nao sao emails de contacto reais.
_DOMINIOS_EXCLUIDOS = {
    "example.com",
    "sentry.io",
    "wixpress.com",
    "godaddy.com",
    "schema.org",
    "w3.org",
    "domain.com",
    "yourdomain.com",
    "email.com",
}

# Extensoes de imagem que geram falsos positivos tipo "nome@2x.png".
_SUFIXO_IMAGEM = re.compile(r"\.(png|jpe?g|gif|svg|webp)$", re.IGNORECASE)


@dataclass
class EmailCandidato:
    email: str
    origem_pagina: str


def _valido(email: str) -> bool:
    email = email.strip().strip(".,;:")
    if _SUFIXO_IMAGEM.search(email):
        return False
    dominio = email.rsplit("@", 1)[-1].lower()
    if dominio in _DOMINIOS_EXCLUIDOS:
        return False
    if len(email) > 254:
        return False
    return True


def _extrair_emails_de_html(html: str) -> set[str]:
    soup = BeautifulSoup(html, "lxml")
    encontrados: set[str] = set()

    for link in soup.select("a[href^='mailto:']"):
        email = link["href"].removeprefix("mailto:").split("?")[0].strip()
        if email:
            encontrados.add(email)

    for match in _EMAIL_REGEX.finditer(soup.get_text(" ")):
        encontrados.add(match.group(0))

    return {e for e in encontrados if _valido(e)}


def procurar_emails(dominio: str, timeout: int = 15) -> list[EmailCandidato]:
    """Visita um conjunto de paginas do dominio e devolve os emails encontrados."""
    base_url = f"https://{dominio}"
    headers = {"User-Agent": settings.http_user_agent}
    candidatos: dict[str, str] = {}  # email -> primeira pagina onde apareceu

    for caminho in CAMINHOS_A_TENTAR:
        url = base_url.rstrip("/") + caminho
        try:
            resposta = requests.get(url, headers=headers, timeout=timeout)
            if resposta.status_code >= 400:
                continue
        except requests.RequestException as exc:
            logger.debug("Falha ao aceder a %s: %s", url, exc)
            continue

        for email in _extrair_emails_de_html(resposta.text):
            if email not in candidatos:
                candidatos[email] = caminho

    return [EmailCandidato(email=email, origem_pagina=origem) for email, origem in candidatos.items()]
