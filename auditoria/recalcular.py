"""Auditoria independente do Tira-Teima.

Não importa nada de pipeline/. Baixa de novo cada série na fonte primária (quando possível, numa fonte
diferente da usada pelo site), refaz as contas com código próprio a partir das regras escritas na
Metodologia do site e compara com o que está publicado em site/data/painel.json.

Saídas em auditoria/resultados/:
  comparacao.csv   uma linha por número conferido (publicado x recalculado)
  fontes.csv       o que foi baixado, de onde, quantas observações e a última data
  erros.csv        o que não foi possível baixar ou calcular
  dados/*.csv      as séries brutas baixadas, para reprodução
"""
from __future__ import annotations

import io
import json
import math
import re
import time
import traceback
import zipfile
from datetime import date
from pathlib import Path

import pandas as pd
import requests

RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / "auditoria" / "resultados"
DADOS = OUT / "dados"
DADOS.mkdir(parents=True, exist_ok=True)
SITE = json.loads((RAIZ / "site" / "data" / "painel.json").read_text(encoding="utf-8"))
IND = SITE["indicadores"]

S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (auditoria independente de dados publicos)"
COMP, FONTES, ERROS = [], [], []

# --------------------------------------------------------------------------- #
# Regras declaradas na Metodologia do site (reimplementadas aqui)
# --------------------------------------------------------------------------- #
GOV = [(g["id"], date.fromisoformat(g["inicio"]), date.fromisoformat(g["fim"])) for g in SITE["governos"]]
GIDS = [g[0] for g in GOV]


def gov_mes(a, m):
    d = date(a, m, 15)
    return next((g for g, i, f in GOV if i <= d <= f), None)


def pesos(ano):
    ini, fim = date(ano, 1, 1), date(ano, 12, 31)
    tot = (fim - ini).days + 1
    out = {}
    for g, i, f in GOV:
        a, b = max(ini, i), min(fim, f)
        if a <= b:
            out[g] = ((b - a).days + 1) / tot
    return out


def meses_do_gov(g, ate: pd.Timestamp):
    _, i, f = next(x for x in GOV if x[0] == g)
    ms = pd.period_range(f"{i.year}-{i.month:02d}", f"{min(f, ate.date()).year}-{min(f, ate.date()).month:02d}", freq="M")
    return [p for p in ms if gov_mes(p.year, p.month) == g]


def media_mensal_gov(s: pd.Series):
    """s: índice = Period mensal. Média simples dos meses de cada governo, cobertura >= 75%."""
    out = {}
    ate = s.index.max().to_timestamp()
    for g in GIDS:
        esperados = meses_do_gov(g, ate)
        tem = [p for p in esperados if p in s.index and pd.notna(s[p])]
        if esperados and len(tem) / len(esperados) >= 0.75:
            out[g] = (s[tem].mean(), len(tem), len(esperados))
    return out


def media_ponderada_gov(a: pd.Series):
    """a: índice = ano. Média dos anos ponderada pelos dias de governo; cobertura >= 75%."""
    a = a.dropna()
    ult = int(a.index.max())
    out = {}
    for g, i, f in GOV:
        w = sum(pesos(y).get(g, 0) for y in a.index)
        s = sum(a[y] * pesos(y).get(g, 0) for y in a.index)
        poss = sum(pesos(y).get(g, 0) for y in range(i.year, min(f.year, ult) + 1))
        if w > 0 and poss and w / poss >= 0.75:
            out[g] = s / w
    return out


def ritmo_gov(a: pd.Series, relativo=False, tol=2):
    obs = a.dropna()
    anos = range(int(obs.index.min()), int(obs.index.max()) + 1)
    ser = obs.reindex(anos).interpolate(limit_area="inside")
    perto = lambda y: min(abs(y - o) for o in obs.index) <= tol  # noqa: E731
    out = {}
    for g, i, f in GOV:
        base = i.year - 1 if i.month <= 6 else i.year
        fim = f.year if f.month >= 7 else f.year - 1
        fim = min(fim, int(obs.index.max()))
        if fim <= base or base not in ser.index or fim not in ser.index:
            continue
        if pd.isna(ser[base]) or pd.isna(ser[fim]) or not (perto(base) and perto(fim)):
            continue
        if relativo:
            v = ((ser[fim] / ser[base]) ** (1 / (fim - base)) - 1) * 100
        else:
            v = (ser[fim] - ser[base]) / (fim - base)
        out[g] = v
    return out


def ranking(valores: dict, direcao: str):
    sinal = 1 if direcao == "maior" else -1
    v = {g: round(sinal * x, 3) for g, x in valores.items()}
    n, k = len(v), math.ceil(len(v) / 4)
    out = {}
    for g, x in v.items():
        melhores = sum(1 for y in v.values() if y > x)
        piores = sum(1 for y in v.values() if y < x)
        out[g] = (melhores + 1, "bom" if melhores < k else ("ruim" if piores < k else ""))
    return out


# --------------------------------------------------------------------------- #
# Registro
# --------------------------------------------------------------------------- #
def comparar(ind, item, publicado, recalculado, fonte, tol_rel=0.005, tol_abs=0.051, nota=""):
    if publicado is None or recalculado is None or (isinstance(recalculado, float) and math.isnan(recalculado)):
        situacao = "sem par"
        dif = None
    else:
        dif = recalculado - publicado
        ok = abs(dif) <= max(tol_abs, abs(publicado) * tol_rel)
        situacao = "confere" if ok else "DIVERGE"
    COMP.append({"indicador": ind, "item": item, "publicado": publicado, "recalculado": recalculado,
                 "diferenca": dif, "situacao": situacao, "fonte_recalculo": fonte, "nota": nota})


def fonte(nome, url, df, col_data=None):
    try:
        ult = str(df.index.max() if col_data is None else df[col_data].max())
        n = len(df)
    except Exception:  # noqa: BLE001
        ult, n = "?", 0
    FONTES.append({"serie": nome, "url": url, "observacoes": n, "ultima": ult})


def erro(onde, e):
    ERROS.append({"etapa": onde, "erro": f"{type(e).__name__}: {str(e)[:400]}", "trace": traceback.format_exc()[-800:]})
    print("ERRO", onde, e)


def get(url, tent=4, **kw):
    for t in range(tent):
        try:
            r = S.get(url, timeout=120, **kw)
            r.raise_for_status()
            return r
        except Exception:  # noqa: BLE001
            if t == tent - 1:
                raise
            time.sleep(5 * (t + 1))


def publicado_resumo(ind_id):
    return {g: r["valor"] for g, r in IND[ind_id]["resumo"].items()}


def publicado_serie(ind_id):
    return {p["x"]: p["y"] for p in IND[ind_id]["serie"]}


# --------------------------------------------------------------------------- #
# Fontes primárias
# --------------------------------------------------------------------------- #
def sgs(codigo, inicio=1980, diaria=False):
    partes = []
    hoje = date.today().year
    passo = 9 if diaria else 60
    for a in range(inicio, hoje + 1, passo):
        b = min(a + passo - 1, hoje)
        url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json"
               f"&dataInicial=01/01/{a}&dataFinal=31/12/{b}")
        r = get(url)
        partes += r.json()
    df = pd.DataFrame(partes)
    df["data"] = pd.to_datetime(df["data"], dayfirst=True)
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna().drop_duplicates("data").sort_values("data")
    df.to_csv(DADOS / f"sgs_{codigo}.csv", index=False)
    fonte(f"BCB SGS {codigo}", f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo}/dados?formato=json", df, "data")
    return df


def sidra(tabela, variavel, nivel="n1/all", periodo="all", extra=""):
    url = f"https://apisidra.ibge.gov.br/values/t/{tabela}/{nivel}/v/{variavel}/p/{periodo}{extra}"
    r = get(url)
    j = r.json()
    cab, linhas = j[0], j[1:]
    kper = next(k for k, n in cab.items() if k.endswith("C") and n.startswith(("Mês", "Ano", "Trimestre")))
    kvar = next(k for k, n in cab.items() if k.endswith("N") and n.startswith("Variável"))
    df = pd.DataFrame({"periodo": [l[kper] for l in linhas], "variavel": [l[kvar] for l in linhas],
                       "valor": pd.to_numeric([l["V"] for l in linhas], errors="coerce")})
    df.to_csv(DADOS / f"sidra_{tabela}_{variavel}.csv", index=False)
    fonte(f"IBGE SIDRA {tabela} v{variavel}", url, df, "periodo")
    return df


def ipea(codigo):
    url = f"http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{codigo}')"
    v = pd.DataFrame(get(url).json()["value"])
    if "NIVNOME" in v and v["NIVNOME"].fillna("").str.strip().ne("").any():
        v = v[v["NIVNOME"].fillna("").str.strip().str.lower() == "brasil"]
    df = pd.DataFrame({"data": pd.to_datetime(v["VALDATA"].str[:10]), "valor": pd.to_numeric(v["VALVALOR"], errors="coerce")})
    df = df.dropna().sort_values("data")
    df.to_csv(DADOS / f"ipea_{codigo}.csv", index=False)
    try:
        meta = get(f"http://www.ipeadata.gov.br/api/odata4/Metadados('{codigo}')").json()["value"][0]
        unid = f"{meta.get('UNINOME')} | {meta.get('SERNOME')} | {meta.get('FNTSIGLA')} | atualizada {meta.get('SERATUALIZACAO')}"
    except Exception:  # noqa: BLE001
        unid = "?"
    FONTES.append({"serie": f"Ipeadata {codigo}", "url": url, "observacoes": len(df), "ultima": str(df.data.max()), "metadados": unid})
    return df


def banco_mundial(codigo):
    url = f"https://api.worldbank.org/v2/country/BRA/indicator/{codigo}?format=json&per_page=500"
    j = get(url).json()
    linhas = [(int(x["date"]), x["value"]) for x in j[1] if x["value"] is not None]
    s = pd.Series(dict(linhas)).sort_index().astype(float)
    s.to_csv(DADOS / f"bm_{codigo}.csv", header=["valor"])
    upd = j[0].get("lastupdated")
    FONTES.append({"serie": f"Banco Mundial {codigo}", "url": url, "observacoes": len(s), "ultima": str(s.index.max()), "metadados": f"lastupdated {upd}"})
    return s


# --------------------------------------------------------------------------- #
# Recálculos
# --------------------------------------------------------------------------- #
def ipca_mensal_sidra():
    df = sidra(1737, 63)
    s = pd.Series(df.valor.values, index=pd.PeriodIndex(pd.to_datetime(df.periodo, format="%Y%m"), freq="M")).sort_index()
    return s


def audit_ipca(ipca_m):
    # série anual: acumulado de jan a dez (ou até o último mês) a partir da variação mensal do SIDRA 1737
    pub = publicado_serie("ipca")
    anual = {}
    for a in sorted(set(p.year for p in ipca_m.index)):
        m = ipca_m[[p for p in ipca_m.index if p.year == a]]
        anual[a] = ((1 + m / 100).prod() - 1) * 100
    for a, v in anual.items():
        if str(a) in pub:
            comparar("ipca", f"série {a}", pub[str(a)], v, "SIDRA 1737 v63 (variação mensal), acumulada no ano")
    # conferência adicional com a variação acumulada em 12 meses de dezembro publicada pelo IBGE (v2265)
    try:
        d12 = sidra(1737, 2265)
        d12 = d12[d12.periodo.str.endswith("12")]
        for _, r in d12.iterrows():
            a = int(r.periodo[:4])
            if str(a) in pub:
                comparar("ipca", f"série {a} x IBGE 12 meses em dezembro", pub[str(a)], r.valor, "SIDRA 1737 v2265 (dezembro)")
    except Exception as e:  # noqa: BLE001
        erro("ipca 12 meses", e)
    # resumo por governo: média anual equivalente ao acumulado
    pubr = IND["ipca"]["resumo"]
    ate = ipca_m.index.max().to_timestamp()
    rec = {}
    for g in GIDS:
        esperados = meses_do_gov(g, ate)
        tem = [p for p in esperados if p in ipca_m.index]
        if not esperados or len(tem) / len(esperados) < 0.75:
            continue
        acum = ((1 + ipca_m[tem] / 100).prod() - 1) * 100
        eq = ((1 + acum / 100) ** (12 / len(tem)) - 1) * 100
        rec[g] = eq
        if g in pubr:
            comparar("ipca", f"{g} média anual equivalente", pubr[g]["valor"], eq, "SIDRA 1737 v63")
            comparar("ipca", f"{g} acumulado no governo", pubr[g].get("acumulado"), acum, "SIDRA 1737 v63", tol_rel=0.01)
            comparar("ipca", f"{g} número de meses", pubr[g].get("meses"), float(len(tem)), "regra do dia 15")
    audit_rank("ipca", rec)


def audit_rank(ind_id, rec):
    ind = IND[ind_id]
    if not ind.get("direcao") or len(rec) < 3:
        return
    rk = ranking(rec, ind["direcao"])
    for g, (pos, aval) in rk.items():
        r = ind["resumo"].get(g)
        if r is None:
            COMP.append({"indicador": ind_id, "item": f"{g} ranking", "publicado": None, "recalculado": pos,
                         "situacao": "DIVERGE", "nota": "governo com resultado recalculado mas sem resultado no site"})
            continue
        ok = r.get("posicao") == pos and (r.get("avaliacao") or "") == aval
        COMP.append({"indicador": ind_id, "item": f"{g} posição e ✓/✕", "publicado": f"{r.get('posicao')} {r.get('avaliacao') or ''}",
                     "recalculado": f"{pos} {aval}", "situacao": "confere" if ok else "DIVERGE", "fonte_recalculo": "ranking recalculado"})
    for g in ind["resumo"]:
        if g not in rec:
            COMP.append({"indicador": ind_id, "item": f"{g} presença", "publicado": "com resultado", "recalculado": "sem resultado",
                         "situacao": "DIVERGE", "nota": "site mostra resultado para governo que o recálculo não cobre"})


def indice_ipca(ipca_m):
    idx = (1 + ipca_m / 100).cumprod()
    return idx / idx.iloc[-1]


TROCAS = [("1986-02-28", 1000), ("1989-01-16", 1000), ("1993-08-01", 1000), ("1994-07-01", 2750)]


def para_reais_mes(p: pd.Period, v):
    d = f"{p.year}-{p.month:02d}-15"
    for data, fator in TROCAS:
        if d < data:
            v = v / fator
    return v


def audit_salario(ipca_m):
    sm = sgs(1619, 1980)
    s = sm.set_index(pd.PeriodIndex(sm.data, freq="M")).valor
    s = s[~s.index.duplicated(keep="last")]
    s = s[s.index >= pd.Period("1984-01", "M")]
    reais = pd.Series([para_reais_mes(p, v) for p, v in s.items()], index=s.index)
    idx = indice_ipca(ipca_m)
    comum = reais.index.intersection(idx.index)
    real = reais[comum] / idx[comum]
    pub = publicado_serie("salario_minimo")
    for p in comum:
        k = f"{p.year}-{p.month:02d}"
        if k in pub and (p.month in (1, 7) or p == comum.max()):
            comparar("salario_minimo", f"série {k} (R$ de hoje)", pub[k], real[p], "BCB SGS 1619 + fatores das moedas + SIDRA 1737", tol_rel=0.01)
    # resumo: média 12 meses antes da posse x últimos 12 meses do governo
    pubr = IND["salario_minimo"]["resumo"]
    rec = {}
    ate = real.index.max().to_timestamp()
    for g in GIDS:
        ms = [p for p in meses_do_gov(g, ate) if p in real.index]
        if not ms:
            continue
        esperados = meses_do_gov(g, ate)
        if len(ms) / len(esperados) < 0.75:
            continue
        ini = min(ms)
        antes = [ini - k for k in range(1, 13) if (ini - k) in real.index]
        if len(antes) < 9:
            continue
        fim = sorted(ms)[-12:]
        v = (real[fim].mean() / real[antes].mean() - 1) * 100
        rec[g] = v
        if g in pubr:
            comparar("salario_minimo", f"{g} ganho real", pubr[g]["valor"], v, "BCB SGS 1619 + SIDRA 1737", tol_abs=0.6)
    audit_rank("salario_minimo", rec)
    # conferência com a série oficial de salário mínimo real do Ipea (GAC12_SALMINRE12): variação no governo
    try:
        ir = ipea("GAC12_SALMINRE12")
        ir = ir.set_index(pd.PeriodIndex(ir.data, freq="M")).valor
        for g in GIDS:
            ms = [p for p in meses_do_gov(g, ir.index.max().to_timestamp()) if p in ir.index]
            if len(ms) < 12:
                continue
            ini = min(ms)
            antes = [ini - k for k in range(1, 13) if (ini - k) in ir.index]
            if len(antes) < 9:
                continue
            v = (ir[sorted(ms)[-12:]].mean() / ir[antes].mean() - 1) * 100
            if g in pubr:
                comparar("salario_minimo", f"{g} ganho real x série oficial do Ipea", pubr[g]["valor"], v,
                         "Ipeadata GAC12_SALMINRE12 (salário mínimo real, deflator INPC)", tol_abs=3,
                         nota="o Ipea deflaciona pelo INPC; o site pelo IPCA: diferença pequena é esperada")
    except Exception as e:  # noqa: BLE001
        erro("salário real Ipea", e)
    return reais, real


def audit_cesta(sm_reais):
    c = ipea("DIEESE12_CBSP12")
    c = c.set_index(pd.PeriodIndex(c.data, freq="M")).valor
    c = c[~c.index.duplicated(keep="last")]
    cr = pd.Series([para_reais_mes(p, v) if p < pd.Period("1994-07", "M") else v for p, v in c.items()], index=c.index)
    # a série do DIEESE no Ipeadata pode já vir convertida: confere pelo salto na troca de 1994
    salto = c.get(pd.Period("1994-07", "M"), None), c.get(pd.Period("1994-06", "M"), None)
    nota = f"jun/1994={salto[1]} jul/1994={salto[0]}"
    if salto[0] and salto[1] and salto[1] / salto[0] < 50:
        cr = c  # já em R$ equivalentes
        nota += " (série já convertida)"
    comum = cr.index.intersection(sm_reais.index)
    pct = cr[comum] / sm_reais[comum] * 100
    pub = publicado_serie("cesta_sp")
    for p in comum:
        k = f"{p.year}-{p.month:02d}"
        if k in pub and p.month == 1:
            comparar("cesta_sp", f"série {k}", pub[k], pct[p], "Ipeadata DIEESE12_CBSP12 / BCB SGS 1619", tol_rel=0.01, nota=nota)
    rec = {g: v[0] for g, v in media_mensal_gov(pct).items()}
    for g, v in rec.items():
        comparar("cesta_sp", f"{g} média no governo", IND["cesta_sp"]["resumo"].get(g, {}).get("valor"), v, "recalculado", tol_abs=0.3)
    audit_rank("cesta_sp", rec)


def audit_dolar():
    d = sgs(1, 1994, diaria=True)
    m = d.set_index("data").valor.resample("MS").mean()
    m.index = m.index.to_period("M")
    pub = publicado_serie("dolar")
    for p, v in m.items():
        k = f"{p.year}-{p.month:02d}"
        if k in pub and p.month in (1, 7):
            comparar("dolar", f"série {k}", pub[k], v, "BCB SGS 1, média dos dias úteis do mês")
    m = m[m.index >= pd.Period("1994-07", "M")]
    rec = {g: v[0] for g, v in media_mensal_gov(m).items()}
    for g, v in rec.items():
        comparar("dolar", f"{g} média no governo", IND["dolar"]["resumo"].get(g, {}).get("valor"), v, "BCB SGS 1")
    for g in IND["dolar"]["resumo"]:
        if g not in rec:
            comparar("dolar", f"{g} média no governo", IND["dolar"]["resumo"][g]["valor"], None, "BCB SGS 1", nota="sem cobertura de 75% no recálculo")


def audit_pib():
    s7326 = sgs(7326, 1980)
    a = pd.Series(s7326.valor.values, index=s7326.data.dt.year)
    pub = publicado_serie("pib_crescimento")
    for y, v in a.items():
        if str(y) in pub:
            comparar("pib_crescimento", f"série {y}", pub[str(y)], v, "BCB SGS 7326")
    try:
        t = sidra(6784, "all")
        t = t[t.variavel.str.strip() == "PIB - variação em volume"]
        for _, r in t.iterrows():
            if str(r.periodo) in pub and pd.notna(r.valor):
                comparar("pib_crescimento", f"série {r.periodo} x IBGE Contas Nacionais", pub[str(r.periodo)], r.valor, "SIDRA 6784 v9810")
    except Exception as e:  # noqa: BLE001
        erro("pib sidra", e)
    a = a[a.index >= 1985]
    rec = media_ponderada_gov(a)
    for g, v in rec.items():
        comparar("pib_crescimento", f"{g} média ponderada", IND["pib_crescimento"]["resumo"].get(g, {}).get("valor"), v, "BCB SGS 7326")
    audit_rank("pib_crescimento", rec)
    return a


def audit_pib_pc(pib_a):
    # IBGE: variação em volume do PIB per capita (SIDRA 6784). Descobre o código da variável pelo nome.
    t = sidra(6784, "all")
    vol = t[t.variavel.str.contains("per capita", case=False) & t.variavel.str.contains("volume", case=False)]
    pop = t[t.variavel.str.startswith("População")]
    vol = pd.Series(vol.valor.values, index=vol.periodo.astype(int)).dropna()
    # crescimento implícito na série de nível publicada pelo site
    pub = publicado_serie("pib_per_capita")
    niv = pd.Series({int(k): v for k, v in pub.items() if v is not None}).sort_index()
    implicito = (niv / niv.shift(1) - 1) * 100
    for y, v in vol.items():
        if y in implicito.index:
            comparar("pib_per_capita", f"crescimento {y}", implicito[y], v, "SIDRA 6784 (PIB per capita, variação em volume)")
    # anos fora da tabela do IBGE: PIB / população (IBGE) — mostra quanto pesa a base de população
    rec_ser = implicito.copy()
    for y in vol.index:
        rec_ser[y] = vol[y]
    rec = media_ponderada_gov(rec_ser[rec_ser.index >= 1985])
    for g, v in rec.items():
        comparar("pib_per_capita", f"{g} crescimento médio", IND["pib_per_capita"]["resumo"].get(g, {}).get("valor"), v,
                 "SIDRA 6784 nos anos cobertos; fora deles, o crescimento implícito do próprio site",
                 nota="governos inteiramente cobertos pela tabela do IBGE: 1997–2023")
    audit_rank("pib_per_capita", rec)


def audit_desemprego():
    t = sidra(4099, 4099, periodo="all")
    t["ano"] = t.periodo.str[:4].astype(int)
    t["tri"] = t.periodo.str[-2:].astype(int)
    meses = {}
    for _, r in t.iterrows():
        for k in range(3):
            meses[pd.Period(f"{r.ano}-{(r.tri - 1) * 3 + 1 + k:02d}", "M")] = r.valor
    m = pd.Series(meses).sort_index()
    pub = publicado_serie("desemprego")
    for p, v in m.items():
        k = f"{p.year}-{p.month:02d}"
        if p.month in (2, 5, 8, 11):
            comparar("desemprego", f"trimestre que contém {k}", pub.get(k), v, "SIDRA 4099 (taxa de desocupação trimestral)",
                     nota="se o publicado estiver um trimestre deslocado, a data do Ipeadata está sendo lida como início do trimestre seguinte")
    # médias anuais oficiais (média dos 4 trimestres) x site
    anual = t.groupby("ano").valor.agg(["mean", "count"])
    for y, r in anual.iterrows():
        if r["count"] == 4:
            ms = [v for k, v in pub.items() if k.startswith(str(y))]
            if len(ms) == 12:
                comparar("desemprego", f"média de {y}", sum(ms) / 12, r["mean"], "SIDRA 4099, média dos 4 trimestres")
    rec = {g: v[0] for g, v in media_mensal_gov(m).items()}
    for g, v in rec.items():
        comparar("desemprego", f"{g} média no governo", IND["desemprego"]["resumo"].get(g, {}).get("valor"), v, "SIDRA 4099")
    audit_rank("desemprego", rec)


def audit_bm(ind_id, codigo, metodo, inverter=False):
    s = banco_mundial(codigo)
    if inverter:
        s = 100 - s
    pub = publicado_serie(ind_id)
    for y, v in s.items():
        if str(y) in pub and pub[str(y)] is not None:
            comparar(ind_id, f"série {y}", pub[str(y)], v, f"Banco Mundial {codigo}", tol_abs=0.051)
        elif str(y) in pub and pub[str(y)] is None:
            comparar(ind_id, f"série {y}", None, v, f"Banco Mundial {codigo}", nota="site sem valor neste ano")
    s = s[s.index >= 1984]
    if metodo == "ritmo":
        rec = ritmo_gov(s)
    elif metodo == "ritmo_rel":
        rec = ritmo_gov(s, relativo=True)
    elif metodo == "media":
        rec = media_ponderada_gov(s[s.index >= 1985])
    else:
        rec = {}
    for g, v in rec.items():
        comparar(ind_id, f"{g} resumo ({metodo})", IND[ind_id]["resumo"].get(g, {}).get("valor"), v, f"Banco Mundial {codigo}", tol_abs=0.011)
    audit_rank(ind_id, rec)
    return s


def audit_ipea_anual(ind_id, codigo, metodo, rank=True):
    df = ipea(codigo)
    a = df.groupby(df.data.dt.year).valor.mean()
    if ind_id == "gini" and a.max() <= 1:
        a = a * 100
    pub = publicado_serie(ind_id)
    for y, v in a.items():
        if str(y) in pub and pub[str(y)] is not None:
            comparar(ind_id, f"série {y}", pub[str(y)], v, f"Ipeadata {codigo}")
    if metodo == "ritmo":
        rec = ritmo_gov(a)
    elif metodo == "ritmo_rel":
        rec = ritmo_gov(a, relativo=True)
    else:
        rec = media_ponderada_gov(a[a.index >= 1985])
    for g, v in rec.items():
        comparar(ind_id, f"{g} resumo ({metodo})", IND[ind_id]["resumo"].get(g, {}).get("valor"), v, f"Ipeadata {codigo}", tol_abs=0.011)
    if rank:
        audit_rank(ind_id, rec)
    return a


def audit_queimadas():
    base = "https://dataserver-coids.inpe.br/queimadas/queimadas/focos/csv/anual/"
    html = get(base).text
    pastas = re.findall(r'href="([^"?/][^"]*/)"', html)
    FONTES.append({"serie": "INPE focos anuais (listagem)", "url": base, "observacoes": len(pastas), "ultima": ";".join(pastas)[:300]})
    pasta = next((p for p in pastas if "brasil" in p.lower() and "ref" in p.lower()), None)
    if not pasta:
        raise ValueError(f"pasta Brasil satélite de referência não encontrada: {pastas}")
    arqs = re.findall(r'href="([^"]+\.(?:zip|csv))"', get(base + pasta).text)
    pub = publicado_serie("queimadas")
    contagem = {}
    for arq in arqs:
        m = re.search(r"(20\d\d)", arq)
        if not m:
            continue
        ano = int(m.group(1))
        if str(ano) not in pub:
            continue
        cont = get(base + pasta + arq).content
        if arq.endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(cont)) as z:
                nome = next(n for n in z.namelist() if n.lower().endswith(".csv"))
                cont = z.read(nome)
        df = pd.read_csv(io.BytesIO(cont), low_memory=False)
        cols = {c.lower(): c for c in df.columns}
        info = []
        n = len(df)
        if "pais" in cols:
            info.append(f"países: {df[cols['pais']].value_counts().to_dict()}")
            n = int((df[cols["pais"]].astype(str).str.lower() == "brasil").sum())
        if "satelite" in cols:
            info.append(f"satélites: {df[cols['satelite']].value_counts().to_dict()}")
        contagem[ano] = n
        comparar("queimadas", f"série {ano}", pub[str(ano)], float(n), f"INPE {pasta}{arq}, linhas lidas com pandas", tol_abs=0.5,
                 nota="; ".join(info)[:300])
    rec = media_ponderada_gov(pd.Series(contagem).sort_index())
    for g, v in rec.items():
        comparar("queimadas", f"{g} média", IND["queimadas"]["resumo"].get(g, {}).get("valor"), v, "INPE")
    audit_rank("queimadas", rec)


def audit_gasolina(ipca_m, sm_reais):
    base = ("https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/"
            "precos-revenda-e-de-distribuicao-combustiveis/shlp/mensal/")
    partes = []
    links = {base + "mensal-brasil-desde-jan2013.xlsx",
             base.replace("/shlp/mensal/", "/shlp/2001-2012/") + "mensal-brasil-2001-a-2012.xlsx"}
    raiz = "https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/"
    for pg in ("serie-historica-do-levantamento-de-precos", "serie-historica-levantamento-precos"):
        try:
            html = get(raiz + pg, tent=2).text
            links |= {u for u in re.findall(r'href="([^"]+\.xlsx)"', html) if "mensal" in u.lower() and "brasil" in u.lower()}
        except Exception as e:  # noqa: BLE001
            erro(f"ANP página {pg}", e)
    FONTES.append({"serie": "ANP planilhas mensais Brasil encontradas", "url": raiz, "observacoes": len(links), "ultima": " ; ".join(sorted(links))[:600]})
    for arq in sorted(links):
        try:
            cont = get(arq).content
        except Exception as e:  # noqa: BLE001
            erro(f"ANP {arq}", e)
            continue
        for aba, bruto in pd.read_excel(io.BytesIO(cont), sheet_name=None, header=None).items():
            for i in range(min(30, len(bruto))):
                linha = [str(x).upper() for x in bruto.iloc[i].tolist()]
                if any("PRODUTO" in x for x in linha) and any("REVENDA" in x and "MÉDIO" in x for x in linha):
                    tab = bruto.iloc[i + 1:].copy()
                    tab.columns = linha
                    cp = next(c for c in tab.columns if "PRODUTO" in c)
                    cm = next(c for c in tab.columns if c.startswith("MÊS") or c.startswith("MES") or "DATA" in c)
                    cv = next(c for c in tab.columns if "REVENDA" in c and "MÉDIO" in c and "PREÇO" in c)
                    tab = tab[tab[cp].astype(str).str.upper().str.strip() == "GASOLINA COMUM"]
                    partes.append(pd.DataFrame({"data": pd.to_datetime(tab[cm], errors="coerce"),
                                                "valor": pd.to_numeric(tab[cv], errors="coerce"), "arquivo": f"{arq.rsplit('/', 1)[-1]}/{aba}"}))
                    break
    if not partes:
        raise ValueError("planilhas da ANP sem tabela reconhecida")
    g = pd.concat(partes).dropna(subset=["data", "valor"])
    g.to_csv(DADOS / "anp_gasolina_comum.csv", index=False)
    fonte("ANP gasolina comum, preço médio de revenda (Brasil, mensal)", base, g, "data")
    m = g.groupby(g.data.dt.to_period("M")).valor.mean()
    pub = {p["x"]: p for p in IND["gasolina"]["serie"]}
    idx = indice_ipca(ipca_m)
    real = m / idx.reindex(m.index)
    for p, v in m.items():
        k = f"{p.year}-{p.month:02d}"
        if k in pub and p.month in (1, 7):
            comparar("gasolina", f"preço nominal {k}", pub[k].get("n"), v, "ANP")
            comparar("gasolina", f"preço real {k}", pub[k]["y"], real.get(p), "ANP / IPCA SIDRA", tol_rel=0.01)
    rec = {k: v[0] for k, v in media_mensal_gov(real.dropna()).items()}
    for k, v in rec.items():
        comparar("gasolina", f"{k} preço real médio", IND["gasolina"]["resumo"].get(k, {}).get("valor"), v, "ANP / IPCA", tol_rel=0.01)
    audit_rank("gasolina", rec)
    litros = (sm_reais.reindex(m.index) / m).dropna()
    publ = publicado_serie("gasolina_litros")
    for p, v in litros.items():
        k = f"{p.year}-{p.month:02d}"
        if k in publ and p.month == 1:
            comparar("gasolina_litros", f"série {k}", publ[k], v, "BCB SGS 1619 / ANP", tol_rel=0.01)
    rec = {k: v[0] for k, v in media_mensal_gov(litros).items()}
    for k, v in rec.items():
        comparar("gasolina_litros", f"{k} média", IND["gasolina_litros"]["resumo"].get(k, {}).get("valor"), v, "BCB / ANP", tol_rel=0.01)
    audit_rank("gasolina_litros", rec)


def audit_calculadora(ipca_m, sm_reais):
    C = SITE["calculadora"]
    idx = indice_ipca(ipca_m)
    for k, (ym, ind_pub, sm_pub) in enumerate(zip(C["meses"], C["indice"], C["salario"])):
        if not (ym.endswith("-01") or k == len(C["meses"]) - 1):
            continue
        p = pd.Period(ym, "M")
        comparar("calculadora", f"índice {ym}", ind_pub, idx.get(p), "SIDRA 1737, base = último mês", tol_rel=0.002, tol_abs=0)
        comparar("calculadora", f"salário mínimo em R$ {ym}", sm_pub, sm_reais.get(p), "BCB SGS 1619 + fatores", tol_rel=0.002, tol_abs=0.01)


def main():
    ipca_m = None
    try:
        ipca_m = ipca_mensal_sidra()
        audit_ipca(ipca_m)
    except Exception as e:  # noqa: BLE001
        erro("ipca", e)
    sm_reais = None
    if ipca_m is not None:
        try:
            sm_reais, _ = audit_salario(ipca_m)
        except Exception as e:  # noqa: BLE001
            erro("salario", e)
    etapas = [
        ("cesta", lambda: audit_cesta(sm_reais)),
        ("dolar", audit_dolar),
        ("pib e per capita", lambda: audit_pib_pc(audit_pib())),
        ("desemprego", audit_desemprego),
        ("gasolina", lambda: audit_gasolina(ipca_m, sm_reais)),
        ("calculadora", lambda: audit_calculadora(ipca_m, sm_reais)),
        ("queimadas", audit_queimadas),
        ("fome", lambda: audit_bm("fome", "SN.ITK.DEFC.ZS", None)),
        ("pobreza", lambda: audit_bm("pobreza", "SI.POV.DDAY", "ritmo_rel")),
        ("mortalidade", lambda: audit_bm("mortalidade_infantil", "SP.DYN.IMRT.IN", "ritmo_rel")),
        ("expectativa", lambda: audit_bm("expectativa_vida", "SP.DYN.LE00.IN", "ritmo")),
        ("saude", lambda: audit_bm("gasto_saude", "SH.XPD.GHED.GD.ZS", "media")),
        ("educacao", lambda: audit_bm("gasto_educacao", "SE.XPD.TOTL.GD.ZS", "media")),
        ("analfabetismo", lambda: audit_bm("analfabetismo", "SE.ADT.LITR.ZS", "ritmo_rel", inverter=True)),
        ("ensino superior", lambda: audit_bm("ensino_superior", "SE.TER.ENRR", "ritmo")),
        ("gini", lambda: audit_ipea_anual("gini", "PNADS_GINI", "ritmo")),
        ("homicidios", lambda: audit_ipea_anual("homicidios", "AVIOL12_THOMIC", "media")),
        ("bolsa", lambda: audit_ipea_anual("bolsa_familia", "FAM_PBF", "media")),
        ("leitos", lambda: audit_ipea_anual("leitos_sus", "SIS_NMLTINTSUS1000HUF", "media")),
        ("analfabetismo IBGE", lambda: audit_ipea_anual("analfabetismo", "PNADCA_TXA15MUF", "ritmo_rel", rank=False)),
    ]
    for nome, f in etapas:
        try:
            f()
        except Exception as e:  # noqa: BLE001
            erro(nome, e)
    pd.DataFrame(COMP).to_csv(OUT / "comparacao.csv", index=False)
    pd.DataFrame(FONTES).to_csv(OUT / "fontes.csv", index=False)
    pd.DataFrame(ERROS).to_csv(OUT / "erros.csv", index=False)
    resumo = pd.DataFrame(COMP).groupby(["indicador", "situacao"]).size().unstack(fill_value=0)
    resumo.to_csv(OUT / "resumo.csv")
    (OUT / "versao.txt").write_text(f"painel.json gerado em {SITE['gerado_em']}; auditoria rodada em {pd.Timestamp.now('UTC')}\n")
    print(resumo)


if __name__ == "__main__":
    main()
