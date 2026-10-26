"""Coleta das fontes públicas.

Cada função devolve um DataFrame com colunas `data` (datetime) e `valor` (float).
Nenhuma função inventa dado: se a fonte falhar, levanta exceção e o build
mantém o último CSV válido em data/processed/ (ver build.py).
"""
from __future__ import annotations

import io
import logging
import re
import time
import zipfile
from pathlib import Path
from datetime import date

import pandas as pd
import requests

log = logging.getLogger("fontes")
S = requests.Session()
S.headers["User-Agent"] = "painel-brasil/1.0 (+https://github.com/dayanaisilva/painel-brasil)"
TIMEOUT = 90


DESCOBERTA = Path(__file__).resolve().parent.parent / "data" / "descoberta"


def _get(url, tentativas=3, **kw):
    for i in range(tentativas):
        try:
            r = S.get(url, timeout=TIMEOUT, **kw)
            r.raise_for_status()
            return r
        except requests.RequestException:
            if i == tentativas - 1:
                raise
            time.sleep(4 * (i + 1))


def _json(r):
    try:
        return r.json()
    except ValueError as e:
        raise ValueError(f"resposta não-JSON (HTTP {r.status_code}, {r.headers.get('content-type')}): "
                         f"{r.text[:120]!r}") from e


# --------------------------------------------------------------------------- #
# Banco Central — SGS (https://dadosabertos.bcb.gov.br)
# --------------------------------------------------------------------------- #
SGS_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{cod}/dados"


def sgs(codigo: int, inicio: int = 2002) -> pd.DataFrame:
    """Série do SGS, baixada em janelas de 10 anos (limite da API)."""
    partes, erros = [], []
    hoje = date.today().year
    for ini in range(inicio, hoje + 1, 10):
        fim = min(ini + 9, hoje)
        try:
            r = _get(SGS_URL.format(cod=codigo), params={
                "formato": "json", "dataInicial": f"01/01/{ini}", "dataFinal": f"31/12/{fim}"})
            dados = _json(r)
            if isinstance(dados, list):
                partes.extend(dados)
        except Exception as e:  # noqa: BLE001
            erros.append(f"{ini}-{fim}: {e}")
            log.warning("SGS %s janela %s-%s: %s", codigo, ini, fim, e)
        time.sleep(1)
    if not partes:
        raise ValueError(f"SGS {codigo}: sem dados. " + " | ".join(erros)[:300])
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
        _meta_cache = pd.DataFrame(_json(r)["value"])
        log.info("Ipeadata: %d séries no catálogo", len(_meta_cache))
    return _meta_cache


def ipea_buscar(*termos: str, fonte: str | None = None, periodicidade: str | None = "Mensal",
                excluir: tuple[str, ...] = ()) -> pd.DataFrame:
    m = ipea_metadados()
    nome = m["SERNOME"].fillna("").str.lower()
    mask = pd.Series(True, index=m.index)
    for t in termos:
        mask &= nome.str.contains(t.lower(), regex=False)
    for t in excluir:
        mask &= ~nome.str.contains(t.lower(), regex=False)
    if fonte:
        mask &= m["FNTSIGLA"].fillna("").str.upper().str.contains(fonte.upper(), regex=False)
    if periodicidade:
        mask &= m["PERNOME"].fillna("").str.lower().eq(periodicidade.lower())
    cols = [c for c in ["SERCODIGO", "SERNOME", "FNTSIGLA", "PERNOME", "UNINOME", "SERSTATUS", "SERMAXDATA"] if c in m]
    achados = m.loc[mask, cols]
    DESCOBERTA.mkdir(parents=True, exist_ok=True)
    achados.to_csv(DESCOBERTA / ("ipea_" + "_".join(re.sub(r"\W+", "", t) for t in termos) + ".csv"), index=False)
    log.info("Ipeadata busca %s fonte=%s: %d candidatos\n%s", termos, fonte, len(achados),
             achados.head(15).to_string(index=False))
    return achados


def ipea_serie(codigo: str) -> pd.DataFrame:
    r = _get(f"{IPEA}/ValoresSerie(SERCODIGO='{codigo}')")
    v = pd.DataFrame(_json(r)["value"])
    df = pd.DataFrame({"data": pd.to_datetime(v["VALDATA"].str[:10]),
                       "valor": pd.to_numeric(v["VALVALOR"], errors="coerce")}).dropna()
    df = df.sort_values("data").reset_index(drop=True)
    log.info("Ipeadata %s: %d obs (%s a %s)", codigo, len(df), df.data.min().date(), df.data.max().date())
    return df


def ipea_validada(candidatos: pd.DataFrame, preferir: list[str], valido, chave: str, max_testes: int = 10):
    """Testa os candidatos em ordem de preferência e devolve a primeira série
    cujo valor mais recente passa em `valido` (faixa plausível de valores)."""
    if candidatos.empty:
        raise ValueError("nenhuma série candidata no Ipeadata")
    ordem = ipea_ordenar(candidatos, preferir)
    testes = []
    for _, c in ordem.head(max_testes).iterrows():
        try:
            df = ipea_serie(c.SERCODIGO)
            ok = (not df.empty) and df.data.max().year >= date.today().year - 1 and bool(valido(df))
            testes.append({"codigo": c.SERCODIGO, "nome": c.SERNOME, "ultimo": df.valor.iloc[-1] if len(df) else None,
                           "ultima_data": df.data.max() if len(df) else None, "aprovada": ok})
            if ok:
                pd.DataFrame(testes).to_csv(DESCOBERTA / f"escolha_{chave}.csv", index=False)
                return df
        except Exception as e:  # noqa: BLE001
            testes.append({"codigo": c.SERCODIGO, "nome": c.SERNOME, "erro": str(e)[:150]})
    pd.DataFrame(testes).to_csv(DESCOBERTA / f"escolha_{chave}.csv", index=False)
    raise ValueError(f"nenhuma série do Ipeadata passou na validação para {chave}")


def ipea_ordenar(candidatos: pd.DataFrame, preferir: list[str]) -> pd.DataFrame:
    c = candidatos.copy()
    c["_score"] = sum(c["SERNOME"].str.lower().str.contains(p.lower(), regex=False).astype(int) for p in preferir)
    if "SERMAXDATA" in c:
        c["_max"] = pd.to_datetime(c["SERMAXDATA"].astype(str).str[:10], errors="coerce")
        return c.sort_values(["_score", "_max"], ascending=False)
    return c.sort_values("_score", ascending=False)


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
    itens = _json(r)
    DESCOBERTA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(itens).to_csv(DESCOBERTA / "terrabrasilis_downloads.csv", index=False)
    for it in itens:
        txt = f"{it.get('name')} {it.get('link')} {it.get('category')}"
        if re.search(r"rate|taxa|amaz|legal", txt, re.I):
            log.info("TerraBrasilis: %s", txt)


# --------------------------------------------------------------------------- #
# ANP — Levantamento de Preços de Combustíveis (série histórica mensal, Brasil)
# --------------------------------------------------------------------------- #
ANP_BASE = ("https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/"
            "precos-revenda-e-de-distribuicao-combustiveis")
ANP_ARQUIVOS = [f"{ANP_BASE}/shlp/mensal/mensal-brasil-2001-a-2012.xlsx",
                f"{ANP_BASE}/shlp/mensal/mensal-brasil-desde-jan2013.xlsx"]
ANP_PAGINAS = [f"{ANP_BASE}/serie-historica-do-levantamento-de-precos",
               f"{ANP_BASE}/serie-historica-levantamento-precos"]


def _anp_links() -> list[str]:
    links = set(ANP_ARQUIVOS)
    achados = []
    for pg in ANP_PAGINAS:
        try:
            html = _get(pg, tentativas=1).text
            for h in re.findall(r'href="([^"]+\.xlsx?)"', html, re.I):
                achados.append(h)
                if "mensal" in h.lower() and "brasil" in h.lower():
                    links.add(h if h.startswith("http") else "https://www.gov.br" + h)
        except Exception as e:  # noqa: BLE001
            log.warning("ANP página %s: %s", pg, e)
    DESCOBERTA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"link": achados}).to_csv(DESCOBERTA / "anp_links.csv", index=False)
    return sorted(links)


def _anp_planilha(conteudo: bytes) -> pd.DataFrame:
    bruto = pd.read_excel(io.BytesIO(conteudo), header=None)
    cab = next(i for i in range(min(30, len(bruto)))
               if bruto.iloc[i].astype(str).str.upper().str.contains("PRODUTO").any())
    df = pd.read_excel(io.BytesIO(conteudo), header=cab)
    cols = {c: str(c).upper() for c in df.columns}
    c_mes = next(c for c, u in cols.items() if u.startswith("M") and ("ÊS" in u or "ES" in u))
    c_prod = next(c for c, u in cols.items() if "PRODUTO" in u)
    c_preco = next(c for c, u in cols.items() if "REVENDA" in u and ("MÉDIO" in u or "MEDIO" in u)
                   and "DESVIO" not in u and "MARGEM" not in u)
    g = df[df[c_prod].astype(str).str.upper().str.contains("GASOLINA COMUM")]
    return pd.DataFrame({"data": pd.to_datetime(g[c_mes], errors="coerce"),
                         "valor": pd.to_numeric(g[c_preco], errors="coerce")}).dropna()


def anp_gasolina() -> pd.DataFrame:
    partes, erros = [], []
    for url in _anp_links():
        try:
            partes.append(_anp_planilha(_get(url).content))
            log.info("ANP %s: %d meses", url, len(partes[-1]))
        except Exception as e:  # noqa: BLE001
            erros.append(f"{url.rsplit('/', 1)[-1]}: {e}")
    if not partes:
        raise ValueError("ANP sem planilha válida. " + " | ".join(erros)[:300])
    df = pd.concat(partes).drop_duplicates("data").sort_values("data").reset_index(drop=True)
    return df
