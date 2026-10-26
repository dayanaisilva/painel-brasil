"""Coleta das fontes públicas.

Cada função devolve um DataFrame com colunas `data` (datetime) e `valor` (float).
Nenhuma função inventa dado: se a fonte falhar, levanta exceção e o build
mantém o último CSV válido em data/processed/ (ver build.py).
"""
from __future__ import annotations

import io
import logging
import re
import zipfile
from datetime import date

import pandas as pd
import requests

log = logging.getLogger("fontes")
S = requests.Session()
S.headers["User-Agent"] = "painel-brasil/1.0 (+https://github.com/dayanaisilva/painel-brasil)"
TIMEOUT = 90


def _get(url, **kw):
    r = S.get(url, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r


# --------------------------------------------------------------------------- #
# Banco Central — SGS (https://dadosabertos.bcb.gov.br)
# --------------------------------------------------------------------------- #
SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados"


def sgs(codigo: int, inicio: int = 2002) -> pd.DataFrame:
    """Série do SGS, baixada em janelas de 10 anos (limite da API)."""
    partes = []
    hoje = date.today().year
    for ini in range(inicio, hoje + 1, 10):
        fim = min(ini + 9, hoje)
        r = _get(SGS_URL.format(cod=codigo), params={
            "formato": "json", "dataInicial": f"01/01/{ini}", "dataFinal": f"31/12/{fim}"})
        dados = r.json()
        if isinstance(dados, list):
            partes.extend(dados)
    if not partes:
        raise ValueError(f"SGS {codigo}: resposta vazia")
    df = pd.DataFrame(partes)
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna().drop_duplicates("data").sort_values("data").reset_index(drop=True)
    log.info("SGS %s: %d obs (%s a %s), últimos valores %s", codigo, len(df),
             df.data.min().date(), df.data.max().date(), df.valor.tail(3).tolist())
    return df[["data", "valor"]]


# --------------------------------------------------------------------------- #
# Banco Mundial — World Development Indicators (dados do IBGE harmonizados)
# --------------------------------------------------------------------------- #
def banco_mundial(indicador: str) -> pd.DataFrame:
    r = _get(f"https://api.worldbank.org/v2/country/BRA/indicator/{indicador}",
             params={"format": "json", "per_page": 200})
    linhas = [x for x in r.json()[1] if x.get("value") is not None]
    df = pd.DataFrame({"data": pd.to_datetime([f"{x['date']}-01-01" for x in linhas]),
                       "valor": [float(x["value"]) for x in linhas]})
    df = df.sort_values("data").reset_index(drop=True)
    log.info("Banco Mundial %s: %d anos (%s a %s)", indicador, len(df),
             df.data.min().year, df.data.max().year)
    return df


# --------------------------------------------------------------------------- #
# Ipeadata — API OData v4 (http://www.ipeadata.gov.br/api/)
# --------------------------------------------------------------------------- #
IPEA = "http://www.ipeadata.gov.br/api/odata4"
_meta_cache: pd.DataFrame | None = None


def ipea_metadados() -> pd.DataFrame:
    global _meta_cache
    if _meta_cache is None:
        r = _get(f"{IPEA}/Metadados")
        _meta_cache = pd.DataFrame(r.json()["value"])
        log.info("Ipeadata: %d séries no catálogo", len(_meta_cache))
    return _meta_cache


def ipea_buscar(*termos: str, fonte: str | None = None, periodicidade: str | None = "Mensal") -> pd.DataFrame:
    m = ipea_metadados()
    nome = m["SERNOME"].fillna("").str.lower()
    mask = pd.Series(True, index=m.index)
    for t in termos:
        mask &= nome.str.contains(t.lower(), regex=False)
    if fonte:
        mask &= m["FNTSIGLA"].fillna("").str.upper().str.contains(fonte.upper(), regex=False)
    if periodicidade:
        mask &= m["PERNOME"].fillna("").str.lower().eq(periodicidade.lower())
    cols = [c for c in ["SERCODIGO", "SERNOME", "FNTSIGLA", "PERNOME", "UNINOME", "SERSTATUS", "SERMAXDATA"] if c in m]
    achados = m.loc[mask, cols]
    log.info("Ipeadata busca %s fonte=%s: %d candidatos\n%s", termos, fonte, len(achados),
             achados.head(15).to_string(index=False))
    return achados


def ipea_serie(codigo: str) -> pd.DataFrame:
    r = _get(f"{IPEA}/ValoresSerie(SERCODIGO='{codigo}')")
    v = pd.DataFrame(r.json()["value"])
    df = pd.DataFrame({"data": pd.to_datetime(v["VALDATA"].str[:10]),
                       "valor": pd.to_numeric(v["VALVALOR"], errors="coerce")}).dropna()
    df = df.sort_values("data").reset_index(drop=True)
    log.info("Ipeadata %s: %d obs (%s a %s)", codigo, len(df), df.data.min().date(), df.data.max().date())
    return df


def ipea_escolher(candidatos: pd.DataFrame, preferir: list[str]) -> str:
    """Escolhe a série ativa mais recente, priorizando nomes com os termos de `preferir`."""
    if candidatos.empty:
        raise ValueError("nenhuma série candidata no Ipeadata")
    c = candidatos.copy()
    c["_score"] = sum(c["SERNOME"].str.lower().str.contains(p.lower(), regex=False).astype(int) for p in preferir)
    if "SERMAXDATA" in c:
        c["_max"] = pd.to_datetime(c["SERMAXDATA"].str[:10], errors="coerce")
        c = c.sort_values(["_score", "_max"], ascending=False)
    else:
        c = c.sort_values("_score", ascending=False)
    escolha = c.iloc[0]
    log.info("Ipeadata escolhida: %s — %s", escolha.SERCODIGO, escolha.SERNOME)
    return escolha.SERCODIGO


# --------------------------------------------------------------------------- #
# INPE — focos de queimada (satélite de referência)
# --------------------------------------------------------------------------- #
INPE_FOCOS = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/anual/"


def _listar(url: str) -> list[str]:
    html = _get(url).text
    return sorted(set(re.findall(r'href="([^"?/][^"]*)"', html)))


def inpe_focos_ano(ano: int) -> int:
    """Conta os focos do satélite de referência no Brasil em um ano."""
    pasta = None
    for item in _listar(INPE_FOCOS):
        if "brasil" in item.lower() and "ref" in item.lower():
            pasta = INPE_FOCOS + item
            break
    if pasta is None:
        raise ValueError(f"pasta do satélite de referência não encontrada em {INPE_FOCOS}")
    arquivos = [a for a in _listar(pasta) if str(ano) in a and a.lower().endswith((".zip", ".csv"))]
    if not arquivos:
        raise ValueError(f"sem arquivo de {ano} em {pasta}")
    url = pasta + arquivos[0]
    conteudo = _get(url).content
    if url.lower().endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            conteudo = z.read(nome)
    linhas = conteudo.strip().count(b"\n") + 1  # inclui o cabeçalho
    n = linhas - 1
    log.info("INPE focos %d: %d (%s)", ano, n, url)
    return n


# --------------------------------------------------------------------------- #
# INPE — PRODES Amazônia Legal (taxa anual de desmatamento, km²)
# --------------------------------------------------------------------------- #
TERRABRASILIS = "https://terrabrasilis.dpi.inpe.br"


def prodes_descobrir() -> None:
    """Registra no log os arquivos que o TerraBrasilis publica (para achar a tabela de taxas)."""
    r = _get(f"{TERRABRASILIS}/business/api/v1/download/all")
    itens = r.json()
    for it in itens:
        txt = f"{it.get('name')} {it.get('link')} {it.get('category')}"
        if re.search(r"rate|taxa|amaz|legal", txt, re.I):
            log.info("TerraBrasilis: %s", txt)
