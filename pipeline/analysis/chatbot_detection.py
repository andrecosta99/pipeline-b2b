"""Deteta a presenca de widgets de chatbot conhecidos a partir do HTML de uma pagina.

Reconhece assinaturas (scripts/globais JS) dos widgets mais comuns. Quando
nenhuma assinatura conhecida e encontrada mas ha sinais genericos de um
widget de chat (iframe/div com "chat" no id/class/src), classifica como
"generico" em vez de assumir ausencia de chatbot.
"""
from __future__ import annotations

import re
from typing import Optional

# Ordem importa: assinaturas mais especificas primeiro.
ASSINATURAS_WIDGETS: dict[str, list[str]] = {
    "intercom": ["widget.intercom.io", "intercomcdn.com", "Intercom('boot'"],
    "drift": ["js.driftt.com", "drift.load(", "driftt.com"],
    "tidio": ["code.tidio.co"],
    "zendesk": ["static.zdassets.com", "zendesk.com/embeddable"],
    "crisp": ["client.crisp.chat", "window.$crisp"],
    "tawk.to": ["embed.tawk.to"],
}

_PADRAO_GENERICO = re.compile(
    r'(id|class|src)=["\'][^"\']*chat(bot|-widget)?[^"\']*["\']', re.IGNORECASE
)


def detect_widget(html: str) -> Optional[str]:
    """Devolve o nome do widget detetado ('intercom', 'drift', ...),
    'generico' se houver sinais genericos de chat sem assinatura conhecida,
    ou None se nao houver nenhum indicio de chatbot."""
    if not html:
        return None

    for widget, marcadores in ASSINATURAS_WIDGETS.items():
        if any(marcador in html for marcador in marcadores):
            return widget

    if _PADRAO_GENERICO.search(html):
        return "generico"

    return None
