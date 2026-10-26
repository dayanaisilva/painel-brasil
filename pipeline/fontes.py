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
        # A API do BCB às vezes devolve uma página HTML de erro com HTTP 200; tenta de novo com espera.
        for tentativa in range(5):
            try:
                r = _get(SGS_URL.format(cod=codigo), params={
                    "formato": "json", "dataInicial": f"01/01/{ini}", "dataFinal": f"31/12/{fim}"})
                dados = _json(r)
                if isinstance(dados, list):
                    partes.extend(dados)
                break
            except Exception as e:  # noqa: BLE001
                log.warning("SGS %s janela %s-%s, tentativa %d: %s", codigo, ini, fim, tentativa + 1, str(e)[:120])
                if tentativa == 4:
                    erros.append(f"{ini}-{fim}: {e}")
                else:
                    time.sleep(4 * (tentativa + 1))
        time.sleep(2)
    if erros or not partes:
        # Uma janela que falha deixa a série com buracos: melhor falhar e reaproveitar a cópia anterior.
        raise ValueError(f"SGS {codigo}: falha em {len(erros)} janela(s). " + " | ".join(erros)[:300])
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
    # Séries regionais trazem todas as UFs e municípios: fica só o total Brasil.
    if "NIVNOME" in v and v["NIVNOME"].fillna("").str.strip().ne("").any():
        br = v[v["NIVNOME"].fillna("").str.strip().str.lower() == "brasil"]
        if br.empty:
            raise ValueError(f"Ipeadata {codigo}: série sem total Brasil (níveis: {v['NIVNOME'].unique()[:6]})")
        v = br
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


def _anp_planilha(conteudo: bytes, diag: list | None = None, nome: str = "") -> pd.DataFrame:
    abas = pd.read_excel(io.BytesIO(conteudo), header=None, sheet_name=None)
    partes = []
    for aba, bruto in abas.items():
        if diag is not None:
            for i in range(min(16, len(bruto))):
                diag.append({"arquivo": nome, "aba": aba, "linha": i,
                             "conteudo": " | ".join(map(str, bruto.iloc[i].tolist()))[:400]})
        try:
            partes.append(_anp_aba(bruto))
        except Exception as e:  # noqa: BLE001
            if diag is not None:
                diag.append({"arquivo": nome, "aba": aba, "linha": -1, "conteudo": f"ERRO: {e!r}"[:400]})
    partes = [p for p in partes if not p.empty]
    if not partes:
        raise ValueError("nenhuma aba com gasolina comum")
    return pd.concat(partes)


def _anp_aba(bruto: pd.DataFrame) -> pd.DataFrame:
    cab = next(i for i in range(min(30, len(bruto)))
               if bruto.iloc[i].astype(str).str.upper().str.strip().eq("PRODUTO").any())
    df = bruto.iloc[cab + 1:].copy()
    df.columns = [str(c).strip() for c in bruto.iloc[cab].tolist()]
    cols = {c: str(c).upper() for c in df.columns}
    c_mes = next(c for c, u in cols.items() if u.startswith("M") and ("ÊS" in u or "ES" in u))
    c_prod = next(c for c, u in cols.items() if "PRODUTO" in u)
    c_preco = next(c for c, u in cols.items() if "REVENDA" in u and ("MÉDIO" in u or "MEDIO" in u)
                   and "DESVIO" not in u and "MARGEM" not in u)
    g = df[df[c_prod].astype(str).str.upper().str.contains("GASOLINA COMUM")]
    return pd.DataFrame({"data": pd.to_datetime(g[c_mes], errors="coerce"),
                         "valor": pd.to_numeric(g[c_preco], errors="coerce")}).dropna()


def anp_gasolina() -> pd.DataFrame:
    partes, erros, diag = [], [], []
    for url in _anp_links():
        try:
            partes.append(_anp_planilha(_get(url).content, diag, url.rsplit("/", 1)[-1]))
            log.info("ANP %s: %d meses", url, len(partes[-1]))
        except Exception as e:  # noqa: BLE001
            erros.append(f"{url.rsplit('/', 1)[-1]}: {e}")
    pd.DataFrame(diag).to_csv(DESCOBERTA / "anp_diagnostico.csv", index=False)
    pd.DataFrame({"erro": erros}).to_csv(DESCOBERTA / "anp_erros.csv", index=False)
    if not partes:
        raise ValueError("ANP sem planilha válida. " + " | ".join(erros)[:300])
    df = pd.concat(partes).drop_duplicates("data").sort_values("data").reset_index(drop=True)
    return df


# --------------------------------------------------------------------------- #
# MEC / INEP — portal de dados abertos (CKAN) — descoberta de conjuntos
# --------------------------------------------------------------------------- #
CKAN_MEC = "https://dadosabertos.mec.gov.br/api/3/action/package_search"


def mec_descobrir(consultas=("e-mec instituições", "rede federal", "plataforma nilo peçanha",
                             "censo da educação superior", "universidades federais")) -> None:
    linhas = []
    for q in consultas:
        try:
            r = _get(CKAN_MEC, params={"q": q, "rows": 20}, tentativas=2)
            for pkg in _json(r)["result"]["results"]:
                for res in pkg.get("resources", []):
                    linhas.append({"consulta": q, "pacote": pkg.get("name"), "titulo": pkg.get("title"),
                                   "recurso": res.get("name"), "formato": res.get("format"), "url": res.get("url"),
                                   "atualizado": res.get("last_modified") or res.get("created")})
        except Exception as e:  # noqa: BLE001
            linhas.append({"consulta": q, "erro": str(e)[:200]})
    DESCOBERTA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(linhas).to_csv(DESCOBERTA / "mec_ckan.csv", index=False)


# --------------------------------------------------------------------------- #
# INEP — Censo da Educação Superior (microdados): universidades e campi federais
# --------------------------------------------------------------------------- #
INEP_URLS = [
    "https://download.inep.gov.br/microdados/microdados_censo_da_educacao_superior_{ano}.zip",
    "https://download.inep.gov.br/microdados/microdados_educacao_superior_{ano}.zip",
    "https://download.inep.gov.br/microdados/micro_censo_edu_superior{ano}.zip",
]


def _norm(c: str) -> str:
    return re.sub(r"[^A-Z_]", "", str(c).upper().strip())


def _ler_csv_zip(z, nome: str, usecols_pred) -> pd.DataFrame:
    with z.open(nome) as f:
        cab = f.readline().decode("latin-1")
    sep = ";" if cab.count(";") >= cab.count("|") else "|"
    colunas = [c.strip().strip('"') for c in cab.strip().split(sep)]
    usar = [c for c in colunas if usecols_pred(_norm(c))]
    with z.open(nome) as f:
        return pd.read_csv(f, sep=sep, encoding="latin-1", usecols=usar, dtype=str, low_memory=False)


_INEP_SESSAO = None


def _sessao_inep():
    """O servidor do INEP não envia o certificado intermediário. Em vez de desligar a verificação
    TLS, buscamos o intermediário pela própria URL indicada no certificado (AIA) e somamos ao
    pacote de autoridades confiáveis."""
    global _INEP_SESSAO
    if _INEP_SESSAO is None:
        import tempfile

        import certifi
        from aia import AIASession

        cadata = AIASession().cadata_from_url("https://download.inep.gov.br/")
        arq = tempfile.NamedTemporaryFile("w", suffix=".pem", delete=False)
        arq.write(open(certifi.where()).read() + "\n" + cadata)
        arq.close()
        _INEP_SESSAO = requests.Session()
        _INEP_SESSAO.verify = arq.name
        _INEP_SESSAO.headers["User-Agent"] = S.headers["User-Agent"]
    return _INEP_SESSAO


def inep_ano(ano: int, diag: list) -> dict:
    """Conta, no Censo da Educação Superior de `ano`:
    - universidades federais (categoria pública federal, organização acadêmica universidade);
    - institutos federais e CEFETs (IES federais com essa organização acadêmica);
    - municípios com oferta de curso presencial por instituição federal (proxy de campi).
    Só lê do zip os arquivos necessários (download parcial)."""
    from remotezip import RemoteZip

    ultimo_erro = None
    for modelo in INEP_URLS:
        url = modelo.format(ano=ano)
        try:
            with RemoteZip(url, session=_sessao_inep(), timeout=120) as z:
                nomes = z.namelist()
                diag.append({"ano": ano, "url": url, "arquivos": " | ".join(n for n in nomes if n.lower().endswith((".csv", ".txt")))[:900]})
                base = lambda n: n.rsplit("/", 1)[-1].upper()  # noqa: E731
                ies = next((n for n in nomes if base(n).endswith((".CSV", ".TXT")) and
                            (re.search(r"(^|_)IES(_|\.)", base(n)) or base(n).startswith("INSTITUICAO"))), None)
                cursos = next((n for n in nomes if base(n).endswith((".CSV", ".TXT")) and
                               ("CURSO" in base(n) or base(n).startswith("GRADUACAO_PRESENCIAL")) and "ALUNO" not in base(n)), None)
                out = {"ano": ano, "url": url}
                if ies:
                    with z.open(ies) as fh:
                        diag.append({"ano": ano, "url": url, "arquivos": "IES cabeçalho: " + fh.readline().decode("latin-1")[:700]})
                    d = _ler_csv_zip(z, ies, lambda c: any(k in c for k in ("CATEGORIA", "CATEGADM", "DEP_ADM", "DEPENDENCIA",
                                                                             "ORGANIZACAO", "NOMEORGACAD", "NATUREZA", "NUMERODEIES"))
                                     or c in ("CO_IES",))
                    d.columns = [_norm(c) for c in d.columns]
                    pref = lambda chaves: next((c for k in chaves for c in d.columns if k in c), None)  # noqa: E731
                    cat = pref(["CATEGORIA", "CATEGADM", "DEPENDENCIA", "DEP_ADM"])
                    org = pref(["ORGANIZACAO", "NOMEORGACAD", "NO_NATUREZA", "NATUREZA"])
                    if cat is None or org is None:
                        raise ValueError(f"IES sem colunas de categoria/organização: {list(d.columns)[:20]}")
                    diag.append({"ano": ano, "url": url, "arquivos": f"IES colunas: {list(d.columns)} | cat={d[cat].value_counts().head(6).to_dict()} | org={d[org].value_counts().head(6).to_dict()}"[:900]})
                    cv = d[cat].fillna("").str.strip().str.upper()
                    fed = d[(cv == "1") | cv.str.contains("FEDERAL")]
                    o = fed[org].fillna("").str.strip().str.upper()
                    eh_univ = (o == "1") | (o.str.contains("UNIVERSIDADE") & ~o.str.contains("CENTRO"))
                    if "NUMERODEIES" in fed.columns:  # 2000–2008: arquivo agregado, uma linha por grupo com a contagem
                        n_univ = int(pd.to_numeric(fed.loc[eh_univ, "NUMERODEIES"], errors="coerce").fillna(0).sum())
                    else:
                        n_univ = int(eh_univ.sum())
                    # validação: o país teve entre 30 e 90 universidades federais em todo o período
                    out["universidades_federais"] = n_univ if 30 <= n_univ <= 90 else None
                    if out["universidades_federais"] is None:
                        diag.append({"ano": ano, "url": url, "arquivos": f"contagem de universidades fora da faixa ({n_univ}); revisar códigos"})
                    out["institutos_federais"] = int((o.isin(["4", "5"]) | o.str.contains("INSTITUTO FEDERAL") | o.str.contains("CENTRO FEDERAL")).sum())
                if cursos:
                    c = _ler_csv_zip(z, cursos, lambda c: "CATEGORIA" in c or c.startswith("CO_MUNICIPIO") or "MODALIDADE" in c)
                    diag.append({"ano": ano, "url": url, "arquivos": f"CURSOS colunas: {list(c.columns)[:12]}"})
                    c.columns = [_norm(x) for x in c.columns]
                    cat = next((x for x in c.columns if "CATEGORIA" in x), None)
                    if cat is None:
                        raise ValueError(f"cursos sem coluna de categoria: {list(c.columns)[:20]}")
                    mun = next((x for x in c.columns if x.startswith("CO_MUNICIPIO")), None)
                    mod = next((x for x in c.columns if "MODALIDADE" in x), None)
                    cv = c[cat].fillna("").str.strip().str.upper()
                    f = c[(cv == "1") | cv.str.contains("FEDERAL")]
                    if mod:
                        f = f[f[mod].str.strip().isin(["1", "Presencial"])]
                    if mun:
                        out["municipios_federais"] = int(f[mun].dropna().str.strip().replace("", pd.NA).dropna().nunique())
                return out
        except Exception as e:  # noqa: BLE001
            ultimo_erro = e
            diag.append({"ano": ano, "url": url, "arquivos": f"ERRO: {type(e).__name__}: {str(e)[:300]}"})
    raise ValueError(f"INEP {ano}: {ultimo_erro}")


def prodes_taxas_descobrir() -> None:
    """Procura a tabela oficial de taxas anuais do PRODES (Amazônia Legal) e registra o que achar."""
    linhas = []
    paginas = ["https://terrabrasilis.dpi.inpe.br/app/dashboard/deforestation/biomes/legal_amazon/rates"]
    for pg in paginas:
        try:
            r = _get(pg, tentativas=1)
            html = r.text
            linhas.append({"url": pg, "tipo": "pagina", "info": f"HTTP {r.status_code}, {len(html)} bytes"})
            try:
                for i, t in enumerate(pd.read_html(io.StringIO(html))):
                    linhas.append({"url": pg, "tipo": f"tabela {i}", "info": t.head(8).to_string()[:1500]})
            except Exception as e:  # noqa: BLE001
                linhas.append({"url": pg, "tipo": "tabelas", "info": str(e)[:200]})
            from urllib.parse import urljoin
            base = re.search(r'<base href="([^"]+)"', html)
            raiz = urljoin(pg, base.group(1)) if base else pg
            for js in re.findall(r'src="([^"]+\.js)"', html)[:8]:
                u = urljoin(raiz, js)
                try:
                    codigo = _get(u, tentativas=1).text
                    for m in sorted(set(re.findall(r'["\'`]([^"\'`\s]*(?:/api/|rates|redis|dashboard|geoserver|wfs)[^"\'`\s]{0,120})["\'`]', codigo)))[:80]:
                        linhas.append({"url": u, "tipo": "js", "info": m[:200]})
                except Exception as e:  # noqa: BLE001
                    linhas.append({"url": u, "tipo": "js erro", "info": str(e)[:200]})
        except Exception as e:  # noqa: BLE001
            linhas.append({"url": pg, "tipo": "erro", "info": str(e)[:200]})
    DESCOBERTA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(linhas).to_csv(DESCOBERTA / "prodes_taxas.csv", index=False)


# Notas técnicas oficiais do INPE com a taxa PRODES da Amazônia Legal. Cada nota traz a taxa do ano
# e a do ano anterior (tabela por estado, linha "ALB"/"Amazônia Legal"). Os valores são lidos do PDF;
# nada é digitado à mão. (ano da nota, tipo, url)
PRODES_NOTAS = [
    (2021, "estimativa", ["https://www.gov.br/inpe/pt-br/assuntos/divulgacao-de-dados-prodes.pdf"]),
    (2021, "consolidada", ["https://www.gov.br/inpe/pt-br/assuntos/ultimas-noticias/nota-tecnica-prodes/NotaTecnica_consolidado_PRODES_2021_rev.pdf",
                           "http://mtc-m21d.sid.inpe.br/col/sid.inpe.br/mtc-m21d/2023/12.29.14.19/doc/NotaTecnica_consolidado_PRODES_2021_rev.pdf"]),
    (2022, "consolidada", ["https://www.gov.br/inpe/pt-br/assuntos/ultimas-noticias/a-taxa-consolidada-de-desmatamento-para-os-nove-estados-da-amazonia-legal-em-2022-foi-de-11-594-km2-1/NotaTecnica_consolidado_PRODES_2022.pdf"]),
    (2023, "estimativa", ["https://www.gov.br/inpe/pt-br/assuntos/ultimas-noticias/estimativa-de-desmatamento-na-amazonia-legal-para-2023-e-de-9-001-km2/2023_1020_Nota_tecnica_Estimativa_Taxa_2023_SEI.pdf"]),
    (2024, "estimativa", ["https://data.inpe.br/wp-content/uploads/2024/11/NT_Amz_tx_Prodes2024_T.pdf"]),
    (2024, "consolidada", ["https://data.inpe.br/biomasbr/wp-content/uploads/sites/3/2025/07/Nota_tecnica_PRODES_2024_consolidada.pdf"]),
    (2025, "estimativa", ["https://data.inpe.br/biomasbr/wp-content/uploads/sites/3/2025/10/20251015Nota_tecnica_EstimativaPRODES_2025_F.pdf"]),
    (2025, "consolidada", ["https://data.inpe.br/wp-content/uploads/sites/3/2026/03/A-taxa-consolidada-de-desmatamento-para-os-nove-estados-da-Amazonia-Legal-para-2025-e-de-5.731-km2.pdf"]),
]
_NUM = r"\d{1,2}\.\d{3}"


def _km(t: str) -> float:
    return float(t.replace(".", "").replace(",", "."))


def _baixar_pdf(urls: list[str]) -> tuple[bytes, str]:
    """Tenta cada endereço oficial; no gov.br (Plone), também o link direto de download do arquivo."""
    erros = []
    for u in urls:
        for v in ([u, u + "/@@download/file"] if "gov.br" in u else [u]):
            try:
                r = _get(v, tentativas=2)
                if r.content[:5].startswith(b"%PDF"):
                    return r.content, u
                erros.append(f"{v}: não é PDF ({r.headers.get('content-type')})")
            except Exception as e:  # noqa: BLE001
                erros.append(f"{v}: {str(e)[:120]}")
    raise ValueError(" | ".join(erros)[:400])


def _ler_nota(ano: int, urls: list[str]) -> tuple[dict, str, str]:
    """Lê do texto da nota a taxa do ano e a do ano anterior, nas frases em que o INPE as anuncia:
    título ("... para 2025 é de 5.731 km2") e comparação ("... Prodes 2024, que foi de 6.518 km2")."""
    import pdfplumber
    conteudo, url = _baixar_pdf(urls)
    with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
        texto = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    corrido = re.sub(r"\s+", " ", texto)
    achados = {}
    atual = re.search(rf"para {ano} (?:é|foi) de ({_NUM}) ?km", corrido)
    if atual:
        achados[ano] = _km(atual.group(1))
    ant = re.search(rf"pro?des(?: em)? {ano - 1},? que foi de ({_NUM}) ?km", corrido, re.I)
    if ant:
        achados[ano - 1] = _km(ant.group(1))
    # Conferência: a tabela por estado (linha ALB) tem de conter os mesmos números
    # (o valor precisa aparecer de novo no texto, além da frase; se não aparecer, fica de fora)
    achados = {a: v for a, v in achados.items() if corrido.count(f"{int(v):,}".replace(",", ".")) >= 2}
    if not achados:
        raise ValueError("nenhuma taxa confirmada no texto da nota")
    return achados, texto, url


# Apresentação oficial do INPE na coletiva do PRODES 2026 (16/10/2026, publicada pelo MMA). O gráfico da série
# histórica traz o valor de cada ano como rótulo: 1988 até a estimativa mais recente, em ordem.
PRODES_SERIE = ["https://www.gov.br/mma/pt-br/noticias-defeso-eleitoral/apresentacao-coletiva-prodes-2026_inpe.pdf"]
PRODES_SERIE_ULTIMO = 2026  # ano da estimativa mais recente nessa apresentação


def prodes_serie_apresentacao() -> tuple[dict, str]:
    conteudo, url = _baixar_pdf(PRODES_SERIE)
    import pdfplumber
    with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
        texto = "\n".join((pg.extract_text() or "") for pg in pdf.pages)
    (DESCOBERTA / "inpe_notas").mkdir(parents=True, exist_ok=True)
    (DESCOBERTA / "inpe_notas" / "apresentacao_prodes_2026.txt").write_text(texto, encoding="utf-8")
    nums = [_km(n) for n in re.findall(r"(?<![\d.,])(\d{1,2}\.\d{3})(?![\d.,])", texto)]
    n_anos = PRODES_SERIE_ULTIMO - 1988 + 1
    # procura a sequência que começa nas taxas de 1988–1990 (21.050, 17.770, 13.730) e tem um valor por ano
    for i in range(len(nums) - n_anos + 1):
        if nums[i:i + 3] == [21050.0, 17770.0, 13730.0]:
            serie = dict(zip(range(1988, PRODES_SERIE_ULTIMO + 1), nums[i:i + n_anos]))
            # conferências com valores que o INPE publica em texto em outras notas
            for ano, v in {1995: 29059, 2004: 27772, 2012: 4571, 2019: 10129, 2021: 13038, 2025: 5731}.items():
                if serie.get(ano) != v:
                    raise ValueError(f"apresentação: {ano} = {serie.get(ano)}, esperado {v}")
            return serie, url
    raise ValueError(f"série 1988–{PRODES_SERIE_ULTIMO} não encontrada no texto ({len(nums)} números)")


def prodes_taxas() -> pd.DataFrame:
    """Taxa anual PRODES da Amazônia Legal (km²), só com o que o INPE publica nas notas técnicas.
    Para cada ano vale a nota consolidada mais recente; a estimativa só entra se não houver consolidada."""
    pasta = DESCOBERTA / "inpe_notas"
    pasta.mkdir(parents=True, exist_ok=True)
    diag, melhor = [], {}
    for ano, tipo, urls in PRODES_NOTAS:
        url = urls[0]
        try:
            achados, texto, url = _ler_nota(ano, urls)
            (pasta / f"{ano}_{tipo}.txt").write_text(texto, encoding="utf-8")
            diag.append({"nota": f"{ano} {tipo}", "url": url, "achados": str(achados)})
        except Exception as e:  # noqa: BLE001
            diag.append({"nota": f"{ano} {tipo}", "url": url, "achados": f"ERRO: {type(e).__name__}: {str(e)[:200]}"})
            continue
        for a, v in achados.items():
            # ano anterior numa nota é sempre o valor consolidado; o ano da nota segue o tipo da nota
            t = "consolidada" if (a < ano or tipo == "consolidada") else "estimativa"
            prioridade = (t == "consolidada", ano)  # consolidada vence; entre iguais, a nota mais nova
            if a not in melhor or prioridade > melhor[a]["_p"]:
                melhor[a] = {"ano": a, "valor": v, "tipo": t, "nota_ano": ano, "url": url, "_p": prioridade}
    try:
        serie, url_s = prodes_serie_apresentacao()
        divergentes = {a: (melhor[a]["valor"], v) for a, v in serie.items() if a in melhor and melhor[a]["valor"] != v}
        if divergentes:
            raise ValueError(f"apresentação diverge das notas técnicas: {divergentes}")
        for a, v in serie.items():
            if a not in melhor:
                melhor[a] = {"ano": a, "valor": v, "tipo": "estimativa" if a == PRODES_SERIE_ULTIMO else "consolidada",
                             "nota_ano": PRODES_SERIE_ULTIMO, "url": url_s, "_p": (False, 0)}
        diag.append({"nota": "apresentação PRODES 2026", "url": url_s, "achados": f"{len(serie)} anos, 1988–{PRODES_SERIE_ULTIMO}"})
    except Exception as e:  # noqa: BLE001
        diag.append({"nota": "apresentação PRODES 2026", "url": PRODES_SERIE[0], "achados": f"ERRO: {type(e).__name__}: {str(e)[:250]}"})
    pd.DataFrame(diag).to_csv(DESCOBERTA / "prodes_notas.csv", index=False)
    if not melhor:
        raise ValueError("nenhuma nota técnica do INPE pôde ser lida: " + " | ".join(d["achados"] for d in diag)[:300])
    df = pd.DataFrame(sorted(melhor.values(), key=lambda d: d["ano"])).drop(columns="_p")
    df.insert(0, "data", pd.to_datetime(df.ano.astype(str) + "-01-01"))
    return df.drop(columns="ano")


# --------------------------------------------------------------------------- #
# IBGE — SIDRA (API de tabelas)
# --------------------------------------------------------------------------- #
def sidra(tabela: int, nivel: str = "n1/all", var: str = "all", per: str = "all") -> pd.DataFrame:
    """Tabela do SIDRA com colunas: variavel, unidade, ano, valor. Grava a tabela inteira em descoberta."""
    r = _get(f"https://apisidra.ibge.gov.br/values/t/{tabela}/{nivel}/v/{var}/p/{per}", tentativas=3)
    linhas = _json(r)
    cab, dados = linhas[0], linhas[1:]
    chave = {nome: k for k, nome in cab.items()}
    k_var = next(k for k, n in cab.items() if n.startswith("Variável") and k.endswith("N"))
    k_per = next(k for k, n in cab.items() if n.startswith(("Ano", "Trimestre", "Mês")) and k.endswith("N"))
    df = pd.DataFrame({"variavel": [d[k_var] for d in dados], "unidade": [d.get(chave.get("Unidade de Medida", "MN"), "") for d in dados],
                       "ano": [d[k_per] for d in dados],
                       "valor": pd.to_numeric([d["V"] for d in dados], errors="coerce")})
    DESCOBERTA.mkdir(parents=True, exist_ok=True)
    df.to_csv(DESCOBERTA / f"sidra_{tabela}.csv", index=False)
    return df


def ibge_populacao_contas() -> pd.DataFrame:
    """População residente que o IBGE usa nas Contas Nacionais para o PIB per capita (SIDRA 6784).
    Confere: PIB corrente / população tem de bater com o PIB per capita publicado na mesma tabela."""
    t = sidra(6784)
    t = t[t.ano.str.fullmatch(r"\d{4}")]
    def var(padrao):
        nomes = [v for v in t.variavel.unique() if re.search(padrao, v, re.I)]
        if not nomes:
            raise ValueError(f"SIDRA 6784 sem variável '{padrao}': {list(t.variavel.unique())[:8]}")
        return t[t.variavel == nomes[0]].set_index("ano").valor, t[t.variavel == nomes[0]].unidade.iloc[0]
    pop, _ = var(r"^Popula")
    pib, u_pib = var(r"^PIB - valores correntes")
    pc, _ = var(r"^PIB per capita - valores correntes")
    vol, _ = var(r"^PIB per capita - varia[çc][ãa]o em volume")
    mult = 1e6 if "milh" in u_pib.lower() else (1e3 if "mil" in u_pib.lower() else 1)
    unid_pop = t[t.variavel.str.match(r"^Popula", case=False)].unidade.iloc[0].lower()
    pop = pop * (1e3 if "mil" in unid_pop else 1)
    comum = pop.index.intersection(pib.index).intersection(pc.index)
    desvio = ((pib[comum] * mult / pop[comum]) / pc[comum] - 1).abs().max()
    if not desvio < 0.01:
        raise ValueError(f"SIDRA 6784: PIB/população não bate com o per capita (desvio {desvio:.3f})")
    return pd.DataFrame({"data": pd.to_datetime([f"{a}-07-01" for a in comum]), "valor": pop[comum].values,
                         "pc_nominal": pc[comum].values,
                         "pc_volume": vol.reindex(comum).values})
