"""Normalizacao de dominios/URLs (usado no import de CSV e na Fase 2)."""
from __future__ import annotations

import re
from typing import Optional
from urllib.parse import urlparse

_DOMINIO_VALIDO = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")


def normalize_domain(valor: Optional[str]) -> Optional[str]:
    """Normaliza uma URL ou dominio solto para 'exemplo.com' (sem protocolo/www/path)."""
    if not valor:
        return None

    valor = valor.strip()
    if not valor:
        return None

    if "://" not in valor:
        valor = f"//{valor}"
    parsed = urlparse(valor)
    host = (parsed.netloc or parsed.path).split("/")[0].lower()
    host = host.split(":")[0]  # remove porta, se houver

    if host.startswith("www."):
        host = host[4:]

    if not host or not _DOMINIO_VALIDO.match(host):
        return None

    return host
