#!/usr/bin/env python3
"""Ajuda a calibrar o parser da Fase 1 depois de uma execucao real.

Le um ficheiro HTML guardado em data/raw_html/ e imprime, para cada <table>
encontrada, o id/class e o conteudo da primeira linha (cabecalho) e da
segunda linha (primeira publicacao), para confirmar/ajustar COLUNAS em
pipeline/scrapers/mj_portal_parser.py.

Uso:
    python scripts/inspect_raw_html.py data/raw_html/mj_aveiro_pagina001_*.html
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from bs4 import BeautifulSoup  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 1

    caminho = Path(sys.argv[1])
    html = caminho.read_text(encoding="utf-8")
    soup = BeautifulSoup(html, "lxml")

    tabelas = soup.find_all("table")
    print(f"Encontradas {len(tabelas)} tabelas em {caminho.name}\n")

    for i, tabela in enumerate(tabelas):
        linhas = tabela.find_all("tr")
        print(f"--- Tabela #{i} | id={tabela.get('id')!r} class={tabela.get('class')!r} | {len(linhas)} linhas ---")
        for linha in linhas[:2]:
            celulas = linha.find_all(["td", "th"])
            textos = [c.get_text(strip=True) for c in celulas]
            print("  ", textos)
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
