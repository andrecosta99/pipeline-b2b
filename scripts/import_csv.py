#!/usr/bin/env python3
"""Importa um CSV curado manualmente com o universo de empresas (Fase 1).

Substitui o scraping automatico do Portal da Justica como fonte principal
(ver README para o motivo: reCAPTCHA + rejeicao do browser automatizado).

Colunas reconhecidas no cabecalho (case-insensitive, varias variantes aceites):
    nome:      nome, empresa, entidade, designacao
    distrito:  distrito
    concelho:  concelho
    freguesia: freguesia, localidade
    site:      site, website, dominio, url
    nif:       nif, nipc
    cae:       cae

Se o ficheiro nao tiver cabecalho reconhecivel, assume a ordem posicional:
    nome, distrito, concelho, site, nif (nif opcional)

Uso:
    python scripts/import_csv.py caminho/para/empresas.csv
    python scripts/import_csv.py caminho/para/empresas.csv --delimiter ";"
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline.config import settings  # noqa: E402
from pipeline.db.database import db_session, init_db, upsert_dominio, upsert_empresa  # noqa: E402
from pipeline.utils.domains import normalize_domain  # noqa: E402
from pipeline.utils.logging_config import get_logger  # noqa: E402

logger = get_logger(__name__)

CAMPOS = {
    "nome": {"nome", "empresa", "entidade", "designacao"},
    "distrito": {"distrito"},
    "concelho": {"concelho"},
    "freguesia": {"freguesia", "localidade"},
    "site": {"site", "website", "dominio", "url"},
    "nif": {"nif", "nipc"},
    "cae": {"cae"},
}

ORDEM_POSICIONAL = ["nome", "distrito", "concelho", "site", "nif"]


def _detetar_delimitador(amostra: str, forcar: str | None) -> str:
    if forcar:
        return forcar
    try:
        return csv.Sniffer().sniff(amostra, delimiters=",;\t").delimiter
    except csv.Error:
        return ","


def _mapear_cabecalho(cabecalho: list[str]) -> dict[str, int] | None:
    """Tenta mapear as colunas do cabecalho para os campos conhecidos.
    Devolve None se nao reconhecer pelo menos 'nome'."""
    mapa: dict[str, int] = {}
    for indice, coluna in enumerate(cabecalho):
        chave = coluna.strip().lower()
        for campo, variantes in CAMPOS.items():
            if chave in variantes and campo not in mapa:
                mapa[campo] = indice
    return mapa if "nome" in mapa else None


def _linha_para_dict(linha: list[str], mapa: dict[str, int]) -> dict[str, str | None]:
    def valor(campo: str) -> str | None:
        indice = mapa.get(campo)
        if indice is None or indice >= len(linha):
            return None
        texto = linha[indice].strip()
        return texto or None

    return {campo: valor(campo) for campo in CAMPOS}


def importar(caminho: Path, delimiter: str | None = None) -> tuple[int, int, int]:
    """Importa o CSV. Devolve (linhas_lidas, empresas_importadas, dominios_importados)."""
    init_db()

    texto = caminho.read_text(encoding="utf-8-sig")
    linhas_csv = list(csv.reader(texto.splitlines(), delimiter=_detetar_delimitador(texto[:2048], delimiter)))
    if not linhas_csv:
        logger.warning("CSV vazio: %s", caminho)
        return (0, 0, 0)

    mapa = _mapear_cabecalho(linhas_csv[0])
    if mapa:
        logger.info("Cabecalho reconhecido: %s", mapa)
        linhas_dados = linhas_csv[1:]
    else:
        logger.warning("Cabecalho nao reconhecido, a assumir ordem posicional: %s", ORDEM_POSICIONAL)
        mapa = {campo: i for i, campo in enumerate(ORDEM_POSICIONAL)}
        linhas_dados = linhas_csv

    total_linhas = 0
    total_empresas = 0
    total_dominios = 0

    with db_session() as conn:
        for numero, linha in enumerate(linhas_dados, start=1):
            if not any(c.strip() for c in linha):
                continue  # linha em branco
            total_linhas += 1

            dados = _linha_para_dict(linha, mapa)
            nome = dados.get("nome")
            if not nome:
                logger.warning("Linha %d ignorada: sem nome", numero)
                continue

            empresa_id = upsert_empresa(
                conn,
                nome=nome,
                nif=dados.get("nif"),
                cae=dados.get("cae"),
                concelho=dados.get("concelho"),
                freguesia=dados.get("freguesia"),
                distrito=dados.get("distrito") or settings.mj_distrito,
                fonte="csv_manual",
            )
            total_empresas += 1

            dominio = normalize_domain(dados.get("site"))
            if dominio:
                upsert_dominio(
                    conn,
                    empresa_id=empresa_id,
                    dominio=dominio,
                    metodo_busca="csv_manual",
                    validado=True,
                )
                total_dominios += 1
            elif dados.get("site"):
                logger.warning("Linha %d: site '%s' nao parece um dominio valido, ignorado", numero, dados.get("site"))

    return (total_linhas, total_empresas, total_dominios)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("csv_path", type=Path, help="Caminho para o ficheiro CSV")
    parser.add_argument("--delimiter", help="Forcar delimitador (default: deteta automaticamente)")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.csv_path.exists():
        logger.error("Ficheiro nao encontrado: %s", args.csv_path)
        return 1

    linhas, empresas, dominios = importar(args.csv_path, delimiter=args.delimiter)
    print(f"\nLinhas processadas: {linhas}")
    print(f"Empresas importadas/atualizadas: {empresas}")
    print(f"Dominios validos importados: {dominios}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
