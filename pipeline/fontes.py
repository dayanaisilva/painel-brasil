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


def prodes_taxas() -> pd.DataFrame:
    """Taxa anual oficial de desmatamento PRODES na Amazônia Legal (km²), como publicada no painel
    TerraBrasilis do INPE. Tenta a API do painel e, se falhar, a camada WFS do GeoServer do INPE."""
    linhas, erros = [], []
    for host in ("https://terrabrasilis.dpi.inpe.br", "http://terrabrasilis2.dpi.inpe.br"):
        for app in ("prodes_legal_amazon", "prodes_amazon", "prodes_amazon_", "legal_amazon"):
            try:
                r = S.get(f"{host}/dashboard/api/v1/redis-cli/data/rates", timeout=60,
                          headers={"App-Identifier": app, "Content-Type": "application/json"})
                r.raise_for_status()
                dados = _json(r)
                if isinstance(dados, dict):
                    dados = dados.get("data") or dados.get("value") or next(iter(dados.values()), [])
                if isinstance(dados, str):
                    import json as _j
                    dados = _j.loads(dados)
                linhas = [d for d in dados if isinstance(d, dict) and "rate" in d and "year" in d]
                if linhas:
                    log.info("PRODES via %s App-Identifier=%s: %d linhas", host, app, len(linhas))
                    break
            except Exception as e:  # noqa: BLE001
                erros.append(f"{host} {app}: {str(e)[:120]}")
        if linhas:
            break
    if not linhas:
        # GeoServer: procura uma camada de taxas e baixa em JSON
        try:
            cap = _get("https://terrabrasilis.dpi.inpe.br/geoserver/ows",
                       params={"service": "WFS", "version": "2.0.0", "request": "GetCapabilities"}).text
            camadas = [c for c in re.findall(r"<Name>([^<]+)</Name>", cap) if "rate" in c.lower() and "prodes" in c.lower()]
            erros.append(f"camadas WFS com 'rate': {camadas[:10]}")
            for c in camadas:
                r = _get("https://terrabrasilis.dpi.inpe.br/geoserver/ows",
                         params={"service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": c,
                                 "outputFormat": "application/json"})
                feats = [f.get("properties", {}) for f in _json(r).get("features", [])]
                linhas = [p for p in feats if "rate" in p and "year" in p]
                if linhas:
                    break
        except Exception as e:  # noqa: BLE001
            erros.append(f"WFS: {str(e)[:150]}")
    DESCOBERTA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"erro": erros}).to_csv(DESCOBERTA / "prodes_erros.csv", index=False)
    if not linhas:
        raise ValueError("PRODES indisponível: " + " | ".join(erros)[:300])
    df = pd.DataFrame(linhas)
    if "state" in df:
        tot = df[df["state"].astype(str).str.upper().isin(["AMZ", "AMAZÔNIA LEGAL", "AMAZONIA LEGAL", "LEGAL AMAZON"])]
        df = tot if not tot.empty else df.groupby("year", as_index=False)["rate"].sum()
    df = df.groupby("year", as_index=False)["rate"].max()
    return pd.DataFrame({"data": pd.to_datetime(df["year"].astype(int).astype(str) + "-01-01"),
                         "valor": pd.to_numeric(df["rate"], errors="coerce")}).dropna().sort_values("data")
