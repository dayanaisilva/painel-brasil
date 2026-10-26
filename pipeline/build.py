"""Pipeline do Painel Brasil.

Baixa as séries públicas, recorta por governo e gera:
  data/raw/<id>.csv          série original de cada fonte (versionada no Git)
  data/processed/<id>.csv    série tratada + governo de cada observação
  data/painel.sqlite         base para consultas SQL (ver queries/)
  site/data/painel.json      o que o site lê

Uso:  python -m pipeline.build
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

from . import fontes
from .governos import ANO_INICIAL, GOVERNOS, governo_do_mes, governos_publicos, pesos_do_ano

RAIZ = Path(__file__).resolve().parent.parent
RAW, PROC = RAIZ / "data" / "raw", RAIZ / "data" / "processed"
SITE_DATA = RAIZ / "site" / "data"
for p in (RAW, PROC, SITE_DATA):
    p.mkdir(parents=True, exist_ok=True)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("build")

# Códigos fixos das fontes. Os do Ipeadata ficam None até a primeira execução
# confirmar a série certa no log (a busca automática escolhe e registra).
SGS = {"ipca": 433, "salario_minimo": 1619, "dolar": 1, "pib_crescimento": 7326}
IPEA = {"cesta_sp": None, "gasolina": None}

STATUS: list[dict] = []


# --------------------------------------------------------------------------- #
# Coleta com fallback para o último CSV válido
# --------------------------------------------------------------------------- #
def coletar(id_: str, func, fonte: str) -> pd.DataFrame | None:
    arq = RAW / f"{id_}.csv"
    try:
        df = func()
        fonte = FONTE_USADA.get(id_, fonte)
        if df is not None:
            df = df[df.data <= pd.Timestamp.today()]  # algumas séries trazem meses futuros já decretados
        if df is None or df.empty:
            raise ValueError("série vazia")
        df.to_csv(arq, index=False, date_format="%Y-%m-%d")
        STATUS.append({"indicador": id_, "fonte": fonte, "status": "atualizado",
                       "ultima_obs": str(df.data.max().date())})
        return df
    except Exception as e:  # noqa: BLE001
        log.warning("%s falhou: %s", id_, e)
        if arq.exists():
            df = pd.read_csv(arq, parse_dates=["data"])
            STATUS.append({"indicador": id_, "fonte": fonte, "status": "cópia anterior",
                           "ultima_obs": str(df.data.max().date()), "erro": str(e)[:200]})
            return df
        STATUS.append({"indicador": id_, "fonte": fonte, "status": "indisponível", "erro": str(e)[:200]})
        return None


FONTE_PIB = {"txt": "IBGE — Contas Nacionais, via Banco Central (SGS 7326)"}


def pib_crescimento():
    try:
        return fontes.sgs(SGS["pib_crescimento"], 2000)
    except Exception as e:  # noqa: BLE001
        log.warning("SGS 7326 falhou (%s); usando Banco Mundial", e)
        FONTE_PIB["txt"] = "Banco Mundial (NY.GDP.MKTP.KD.ZG), a partir de dados do IBGE"
        return fontes.banco_mundial("NY.GDP.MKTP.KD.ZG")


def ipea_auto(chave, termos, fonte, preferir, valido, excluir=()):
    def f():
        if IPEA.get(chave):
            return fontes.ipea_serie(IPEA[chave])
        cands = fontes.ipea_buscar(*termos, fonte=fonte, excluir=excluir)
        return fontes.ipea_validada(cands, preferir, valido, chave)
    return f


def faixa(lo, hi):
    return lambda df: lo <= df.valor.iloc[-1] <= hi


def nao_decrescente(lo, hi):
    """Salário mínimo nominal nunca cai: série desde 2002 é não decrescente e termina na faixa."""
    def v(df):
        d = df[df.data.dt.year >= 2002].valor
        return len(d) > 100 and d.is_monotonic_increasing and lo <= d.iloc[-1] <= hi
    return v


FONTE_USADA: dict[str, str] = {}


def sgs_ou_ipea(chave, codigo, rotulo_sgs, valido, ipea_args):
    def f():
        try:
            df = fontes.sgs(codigo, 2000)
            df = df[df.data <= pd.Timestamp.today()]
            if df.data.max() < pd.Timestamp.today() - pd.Timedelta(days=120):
                raise ValueError(f"SGS {codigo} parou em {df.data.max().date()}")
            if not valido(df):
                raise ValueError(f"SGS {codigo} fora da faixa esperada (último valor {df.valor.iloc[-1]})")
            FONTE_USADA[chave] = rotulo_sgs
            return df
        except Exception as e:  # noqa: BLE001
            log.warning("%s: SGS falhou (%s); tentando Ipeadata", chave, e)
            df = ipea_auto(chave, *ipea_args)()
            FONTE_USADA[chave] = "Ipeadata (fallback do SGS)"
            return df
    return f


def gasolina():
    df = fontes.anp_gasolina()
    if df.data.max() < pd.Timestamp.today() - pd.Timedelta(days=150):
        raise ValueError(f"série da ANP parou em {df.data.max().date()}")
    if not (2 <= df.valor.iloc[-1] <= 15):
        raise ValueError(f"preço fora da faixa esperada: {df.valor.iloc[-1]}")
    return df


def queimadas():
    cache = RAW / "queimadas.csv"
    antigos = {}
    if cache.exists():
        c = pd.read_csv(cache, parse_dates=["data"])
        antigos = {d.year: v for d, v in zip(c.data, c.valor)}
    ano_atual = date.today().year
    linhas = []
    for ano in range(ANO_INICIAL - 1, ano_atual + 1):
        # Anos fechados não mudam: reaproveita do cache; o ano corrente é sempre rebaixado.
        if ano in antigos and ano < ano_atual - 1:
            n = antigos[ano]
        else:
            try:
                n = fontes.inpe_focos_ano(ano)
            except Exception as e:  # noqa: BLE001
                log.warning("focos %d: %s", ano, e)
                n = antigos.get(ano)
        if n is not None:
            linhas.append((pd.Timestamp(ano, 1, 1), float(n)))
    if not linhas:
        raise ValueError("nenhum ano de focos obtido")
    return pd.DataFrame(linhas, columns=["data", "valor"])


# --------------------------------------------------------------------------- #
# Transformações
# --------------------------------------------------------------------------- #
def mensal(df):
    df = df.copy()
    df["data"] = df["data"].dt.to_period("M").dt.to_timestamp()
    df = df.groupby("data", as_index=False)["valor"].mean()
    df["governo"] = [governo_do_mes(d.year, d.month) for d in df.data]
    return df


def anual(df):
    df = df.copy()
    df["ano"] = df["data"].dt.year
    return df


def indice_precos(ipca):
    """Número-índice do IPCA (base = último mês disponível = 1)."""
    m = mensal(ipca)[["data", "valor"]].set_index("data")["valor"]
    idx = (1 + m / 100).cumprod()
    return idx / idx.iloc[-1]


def deflacionar(df, idx):
    d = mensal(df)
    fator = idx.reindex(d.data).values
    d["valor"] = d["valor"] / fator
    return d.dropna(subset=["valor"])


def resumo_media_ponderada(df_anual, ano_parcial=None):
    """Média dos valores anuais de cada governo, ponderada pelos dias governados no ano."""
    acc = {g["id"]: [0.0, 0.0, []] for g in GOVERNOS}
    for _, r in df_anual.iterrows():
        for gid, p in pesos_do_ano(int(r.ano)).items():
            acc[gid][0] += r.valor * p
            acc[gid][1] += p
            acc[gid][2].append(int(r.ano))
    out = {}
    for gid, (s, w, anos) in acc.items():
        if w > 0:
            out[gid] = {"valor": s / w, "anos": f"{min(anos)}–{max(anos)}",
                        "parcial": bool(ano_parcial and ano_parcial in anos) or gid == "lula3"}
    return out


def resumo_variacao(dm):
    """Variação % do último mês antes do governo até o último mês do governo."""
    s = dm.set_index("data")["valor"]
    out = {}
    for g in GOVERNOS:
        meses = dm[dm.governo == g["id"]]
        if meses.empty:
            continue
        ini = meses.data.min() - pd.offsets.MonthBegin(1)
        if ini not in s.index:
            continue
        fim = meses.data.max()
        out[g["id"]] = {"valor": (s[fim] / s[ini] - 1) * 100,
                        "periodo": f"{ini:%m/%Y} → {fim:%m/%Y}", "parcial": g["id"] == "lula3"}
    return out


def resumo_media_mensal(dm):
    out = {}
    for g in GOVERNOS:
        m = dm[dm.governo == g["id"]]
        if not m.empty:
            out[g["id"]] = {"valor": m.valor.mean(), "periodo": f"{m.data.min():%m/%Y} → {m.data.max():%m/%Y}",
                            "parcial": g["id"] == "lula3"}
    return out


def ipca_acumulado(ipca_m):
    out = {}
    for g in GOVERNOS:
        m = ipca_m[ipca_m.governo == g["id"]]
        if m.empty:
            continue
        acum = ((1 + m.valor / 100).prod() - 1) * 100
        anos = len(m) / 12
        out[g["id"]] = {"valor": ((1 + acum / 100) ** (1 / anos) - 1) * 100,
                        "acumulado": acum, "meses": len(m),
                        "periodo": f"{m.data.min():%m/%Y} → {m.data.max():%m/%Y}", "parcial": g["id"] == "lula3"}
    return out


def serie_json(df, fmt):
    return [{"x": d.strftime(fmt), "y": round(float(v), 4)} for d, v in zip(df.data, df.valor)]


# --------------------------------------------------------------------------- #
def main():
    ind = {}
    corte = pd.Timestamp(ANO_INICIAL - 1, 1, 1)

    ipca = coletar("ipca", lambda: fontes.sgs(SGS["ipca"], 2000), "BCB/SGS 433 (IBGE)")
    sm = coletar("salario_minimo", sgs_ou_ipea(
        "salario_minimo", SGS["salario_minimo"], "BCB/SGS 1619", nao_decrescente(1000, 3000),
        (["salário mínimo"], None, ["vigente", "nominal"], nao_decrescente(1000, 3000), ("real", "regional", "estadual"))),
        "BCB/SGS 1619")
    dolar = coletar("dolar", sgs_ou_ipea(
        "dolar", SGS["dolar"], "BCB/SGS 1 (PTAX venda)", faixa(3, 10),
        (["câmbio", "comercial", "venda"], None, ["média", "r$ / us$"], faixa(3, 10), ("real", "efetiva", "fim"))),
        "BCB/SGS 1 (PTAX venda)")
    pib = coletar("pib_crescimento", pib_crescimento, "BCB/SGS 7326 (IBGE)")
    pibpc = coletar("pib_per_capita", lambda: fontes.banco_mundial("NY.GDP.PCAP.KD"), "Banco Mundial (IBGE)")
    cesta = coletar("cesta_sp", ipea_auto("cesta_sp", ["cesta", "são paulo"], "DIEESE", ["valor", "custo"],
                                          faixa(300, 3000), ("variação", "horas", "%")),
                    "DIEESE via Ipeadata")
    gas = coletar("gasolina", gasolina, "ANP — Levantamento de Preços")
    focos = coletar("queimadas", queimadas, "INPE/BDQueimadas")
    try:
        fontes.prodes_descobrir()
    except Exception as e:  # noqa: BLE001
        log.warning("descoberta PRODES falhou: %s", e)

    idx = indice_precos(ipca) if ipca is not None else None
    ref_mes = idx.index[-1].strftime("%m/%Y") if idx is not None else ""
    ano_atual = date.today().year

    def recorte(df):
        return df[df.data >= corte]

    # PIB — crescimento real anual
    if pib is not None:
        a = anual(recorte(pib))
        a = a[a.ano >= ANO_INICIAL]
        ind["pib_crescimento"] = dict(
            titulo="Crescimento do PIB", unidade="% ao ano", formato="pct", grafico="barra", freq="anual",
            descricao="Variação real do Produto Interno Bruto em relação ao ano anterior.",
            resumo_rotulo="média anual no governo", resumo=resumo_media_ponderada(a),
            serie=serie_json(a, "%Y"), fonte=FONTE_PIB["txt"],
            fonte_url="https://www3.bcb.gov.br/sgspub/")

    # PIB per capita — nível e crescimento
    if pibpc is not None:
        a = anual(pibpc)
        a["cresc"] = a.valor.pct_change() * 100
        g = a.dropna()[["ano", "cresc"]].rename(columns={"cresc": "valor"})
        g = g[g.ano >= ANO_INICIAL]
        a = a[a.ano >= ANO_INICIAL]
        ind["pib_per_capita"] = dict(
            titulo="PIB per capita", unidade="US$ de 2015", formato="moeda_usd", grafico="barra", freq="anual",
            descricao="PIB dividido pela população, em dólares constantes de 2015 (sem efeito de inflação ou câmbio).",
            resumo_rotulo="crescimento médio anual no governo", resumo_formato="pct",
            resumo=resumo_media_ponderada(g), serie=serie_json(a, "%Y"),
            fonte="Banco Mundial, World Development Indicators (NY.GDP.PCAP.KD), a partir de dados do IBGE",
            fonte_url="https://data.worldbank.org/indicator/NY.GDP.PCAP.KD?locations=BR")

    # IPCA
    if ipca is not None:
        m = mensal(recorte(ipca))
        m = m[m.data.dt.year >= ANO_INICIAL]
        por_ano = m.groupby(m.data.dt.year).valor.apply(lambda v: ((1 + v / 100).prod() - 1) * 100)
        a = pd.DataFrame({"data": pd.to_datetime([f"{y}-01-01" for y in por_ano.index]), "valor": por_ano.values})
        ind["ipca"] = dict(
            titulo="Inflação (IPCA)", unidade="% no ano", formato="pct", grafico="barra", freq="anual",
            descricao=f"IPCA acumulado em cada ano civil. {ano_atual} acumula só até o último mês divulgado.",
            resumo_rotulo="média anual no governo", resumo=ipca_acumulado(m),
            serie=serie_json(a, "%Y"), fonte="IBGE — IPCA, via Banco Central (SGS 433)",
            fonte_url="https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9256-indice-nacional-de-precos-ao-consumidor-amplo.html")
        m.to_csv(PROC / "ipca_mensal.csv", index=False, date_format="%Y-%m-%d")

    # Salário mínimo real
    if sm is not None and idx is not None:
        r = deflacionar(recorte(sm), idx)
        r = r[r.data.dt.year >= ANO_INICIAL - 1]
        n = mensal(recorte(sm))
        ind["salario_minimo"] = dict(
            titulo="Salário mínimo real", unidade=f"R$ de {ref_mes}", formato="moeda", grafico="linha", freq="mensal",
            descricao=f"Salário mínimo corrigido pelo IPCA para reais de {ref_mes}: mostra o poder de compra, não o valor nominal.",
            resumo_rotulo="ganho real no governo", resumo_formato="pct", resumo=resumo_variacao(r),
            serie=serie_json(r[r.data.dt.year >= ANO_INICIAL], "%Y-%m"),
            extra={"nominal_atual": float(n.valor.iloc[-1]), "mes_atual": n.data.iloc[-1].strftime("%m/%Y")},
            fonte=FONTE_USADA.get("salario_minimo", "Banco Central (SGS 1619)") + ", deflacionado pelo IPCA/IBGE", fonte_url="https://www3.bcb.gov.br/sgspub/")
        r.to_csv(PROC / "salario_minimo_real.csv", index=False, date_format="%Y-%m-%d")

    # Dólar
    if dolar is not None:
        d = mensal(recorte(dolar))
        d = d[d.data.dt.year >= ANO_INICIAL]
        ind["dolar"] = dict(
            titulo="Dólar", unidade="R$ por US$", formato="moeda", grafico="linha", freq="mensal",
            descricao="Média mensal da PTAX de venda (dólar comercial) calculada pelo Banco Central. Valor nominal.",
            resumo_rotulo="cotação média no governo", resumo=resumo_media_mensal(d),
            serie=serie_json(d, "%Y-%m"), fonte=FONTE_USADA.get("dolar", "Banco Central — PTAX venda (SGS 1)"), fonte_url="https://www3.bcb.gov.br/sgspub/")

    # Cesta básica como % do salário mínimo
    if cesta is not None and sm is not None:
        c, s = mensal(recorte(cesta)), mensal(recorte(sm))
        j = c.merge(s[["data", "valor"]], on="data", suffixes=("_cesta", "_sm"))
        j["valor"] = j.valor_cesta / j.valor_sm * 100
        j = j[j.data.dt.year >= ANO_INICIAL]
        ind["cesta_sp"] = dict(
            titulo="Cesta básica (São Paulo)", unidade="% do salário mínimo", formato="pct_simples",
            grafico="linha", freq="mensal",
            descricao="Quanto do salário mínimo bruto a cesta básica de São Paulo consome. Quanto menor, maior o poder de compra.",
            resumo_rotulo="média no governo", resumo=resumo_media_mensal(j),
            serie=serie_json(j, "%Y-%m"), extra={"cesta_atual": float(j.valor_cesta.iloc[-1]),
                                                   "mes_atual": j.data.iloc[-1].strftime("%m/%Y")},
            fonte="DIEESE — Pesquisa Nacional da Cesta Básica, via Ipeadata; salário mínimo do BCB",
            fonte_url="https://www.dieese.org.br/cesta/")

    # Gasolina real
    if gas is not None and idx is not None:
        r = deflacionar(recorte(gas), idx)
        r = r[r.data.dt.year >= ANO_INICIAL]
        ind["gasolina"] = dict(
            titulo="Gasolina", unidade=f"R$/litro de {ref_mes}", formato="moeda", grafico="linha", freq="mensal",
            descricao=f"Preço médio de revenda da gasolina comum no Brasil, corrigido pelo IPCA para reais de {ref_mes}.",
            resumo_rotulo="preço real médio no governo", resumo=resumo_media_mensal(r),
            serie=serie_json(r, "%Y-%m"), fonte="ANP — Levantamento de Preços de Combustíveis (série histórica mensal)",
            fonte_url="https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos")

    # Queimadas
    if focos is not None:
        a = anual(focos)
        a = a[a.ano >= ANO_INICIAL]
        fechados = a[a.ano < ano_atual]
        ind["queimadas"] = dict(
            titulo="Focos de queimada", unidade="focos no ano", formato="inteiro", grafico="barra", freq="anual",
            descricao=f"Focos de calor detectados pelo satélite de referência do INPE em todo o Brasil. {ano_atual} está incompleto.",
            resumo_rotulo="média anual no governo", resumo=resumo_media_ponderada(fechados),
            serie=serie_json(a, "%Y"), parcial_ultimo=bool((a.ano == ano_atual).any()),
            fonte="INPE — Programa Queimadas (satélite de referência)",
            fonte_url="https://terrabrasilis.dpi.inpe.br/queimadas/portal/")

    # ---------------- saídas ----------------
    linhas = []
    for id_, d in ind.items():
        for p in d["serie"]:
            x = p["x"]
            ano, mes = int(x[:4]), int(x[5:7]) if len(x) > 4 else 7
            gid = governo_do_mes(ano, mes) if len(x) > 4 else max(pesos_do_ano(ano).items(), key=lambda kv: kv[1])[0]
            linhas.append({"indicador": id_, "periodo": x, "valor": p["y"], "governo": gid})
        pd.DataFrame([l for l in linhas if l["indicador"] == id_]).to_csv(PROC / f"{id_}.csv", index=False)

    with sqlite3.connect(RAIZ / "data" / "painel.sqlite") as db:
        db.execute("DROP TABLE IF EXISTS serie"); db.execute("DROP TABLE IF EXISTS governo")
        db.execute("DROP TABLE IF EXISTS indicador"); db.execute("DROP TABLE IF EXISTS resumo")
        pd.DataFrame(linhas).to_sql("serie", db, index=False)
        pd.DataFrame(governos_publicos()).to_sql("governo", db, index=False)
        pd.DataFrame([{"id": k, "titulo": v["titulo"], "unidade": v["unidade"], "frequencia": v["freq"],
                       "fonte": v["fonte"]} for k, v in ind.items()]).to_sql("indicador", db, index=False)
        pd.DataFrame([{"indicador": k, "governo": g, "metrica": v["resumo_rotulo"], "valor": r["valor"],
                       "parcial": r.get("parcial", False)}
                      for k, v in ind.items() for g, r in v["resumo"].items()]).to_sql("resumo", db, index=False)

    def limpa(o):
        if isinstance(o, float):
            return round(o, 4)
        if isinstance(o, dict):
            return {k: limpa(v) for k, v in o.items()}
        if isinstance(o, list):
            return [limpa(v) for v in o]
        return o

    saida = {"gerado_em": datetime.now(timezone.utc).isoformat(timespec="minutes"),
             "governos": governos_publicos(), "indicadores": limpa(ind), "fontes": STATUS}
    (SITE_DATA / "painel.json").write_text(json.dumps(saida, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame(STATUS).to_csv(RAIZ / "data" / "status_fontes.csv", index=False)
    log.info("Status das fontes:\n%s", pd.DataFrame(STATUS).to_string(index=False))
    log.info("Indicadores gerados: %s", list(ind))


if __name__ == "__main__":
    main()
