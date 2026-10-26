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

import math

from . import fontes, moedas
from .governos import (ANO_INICIAL, CONTEXTO, GOVERNOS, INICIO_REAL, MARCOS, governo_do_mes,
                       governos_publicos, pesos_do_ano)

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
SGS_INICIO = 1980
QUEIMADAS_INICIO = 2003  # série comparável do satélite de referência (AQUA) começa em meados de 2002
# Série confirmada na primeira coleta (26/10/2026): "Cesta básica - município de São Paulo".
IPEA = {"cesta_sp": "DIEESE12_CBSP12"}

STATUS: list[dict] = []


# --------------------------------------------------------------------------- #
# Coleta com fallback para o último CSV válido
# --------------------------------------------------------------------------- #
def coletar(id_: str, func, fonte: str, max_atraso_dias: int = 120) -> pd.DataFrame | None:
    """Baixa a série e só substitui a cópia salva se a nova for recente e não encolher."""
    arq = RAW / f"{id_}.csv"
    try:
        df = func()
        fonte = FONTE_USADA.get(id_, fonte)
        if df is not None:
            df = df[df.data <= pd.Timestamp.today()]  # algumas séries trazem meses futuros já decretados
        if df is None or df.empty:
            raise ValueError("série vazia")
        if df.data.max() < pd.Timestamp.today() - pd.Timedelta(days=max_atraso_dias):
            raise ValueError(f"série desatualizada: último dado em {df.data.max().date()}")
        if arq.exists():
            antigo = pd.read_csv(arq, parse_dates=["data"])
            if df.data.max() < antigo.data.max() or len(df[df.data >= "2002-01-01"]) < 0.98 * len(antigo[antigo.data >= "2002-01-01"]):
                raise ValueError(f"nova coleta menor que a anterior ({len(df)} vs {len(antigo)} obs)")
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
        return fontes.sgs(SGS["pib_crescimento"], SGS_INICIO)
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


def sgs_ou_ipea(chave, codigo, rotulo_sgs, valido, ipea_args, inicio=SGS_INICIO):
    def f():
        try:
            df = fontes.sgs(codigo, inicio)
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
    for ano in range(QUEIMADAS_INICIO - 1, ano_atual + 1):
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
COBERTURA_MINIMA = 0.75  # governo só entra no resumo se a série cobrir 75% do seu período


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


def deflacionar(dm, idx):
    d = dm.copy()
    d["valor"] = d["valor"] / idx.reindex(d.data).values
    return d.dropna(subset=["valor"])


def meses_esperados(gid, ate):
    g = next(x for x in GOVERNOS if x["id"] == gid)
    meses = pd.date_range(pd.Timestamp(g["inicio"]).to_period("M").to_timestamp(),
                          min(pd.Timestamp(g["fim"]), ate), freq="MS")
    return sum(governo_do_mes(m.year, m.month) == gid for m in meses)


def cobertura_mensal(dm, gid):
    n = (dm.governo == gid).sum()
    esperado = meses_esperados(gid, dm.data.max())
    return n / esperado if esperado else 0


def resumo_media_ponderada(df_anual):
    """Média dos valores anuais de cada governo, ponderada pelos dias governados no ano."""
    ultimo = int(df_anual.ano.max())
    acc = {g["id"]: [0.0, 0.0, []] for g in GOVERNOS}
    for _, r in df_anual.iterrows():
        for gid, p in pesos_do_ano(int(r.ano)).items():
            acc[gid][0] += r.valor * p
            acc[gid][1] += p
            acc[gid][2].append(int(r.ano))
    out = {}
    for g in GOVERNOS:
        s, w, anos = acc[g["id"]]
        possivel = sum(pesos_do_ano(a).get(g["id"], 0) for a in range(int(g["inicio"][:4]), min(int(g["fim"][:4]), ultimo) + 1))
        if w > 0 and possivel and w / possivel >= COBERTURA_MINIMA:
            out[g["id"]] = {"valor": s / w, "periodo": f"{min(anos)}–{max(anos)}", "parcial": g["id"] == "lula3"}
    return out


def resumo_variacao(dm):
    """Variação % do último mês antes do governo até o último mês do governo."""
    s = dm.set_index("data")["valor"]
    out = {}
    for g in GOVERNOS:
        meses = dm[dm.governo == g["id"]]
        if meses.empty or cobertura_mensal(dm, g["id"]) < COBERTURA_MINIMA:
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
        if not m.empty and cobertura_mensal(dm, g["id"]) >= COBERTURA_MINIMA:
            out[g["id"]] = {"valor": m.valor.mean(), "periodo": f"{m.data.min():%m/%Y} → {m.data.max():%m/%Y}",
                            "parcial": g["id"] == "lula3"}
    return out


def ipca_acumulado(ipca_m):
    out = {}
    for g in GOVERNOS:
        m = ipca_m[ipca_m.governo == g["id"]]
        if m.empty or cobertura_mensal(ipca_m, g["id"]) < COBERTURA_MINIMA:
            continue
        acum = ((1 + m.valor / 100).prod() - 1) * 100
        anos = len(m) / 12
        out[g["id"]] = {"valor": ((1 + acum / 100) ** (1 / anos) - 1) * 100,
                        "acumulado": acum, "meses": len(m),
                        "periodo": f"{m.data.min():%m/%Y} → {m.data.max():%m/%Y}", "parcial": g["id"] == "lula3"}
    return out


def ranquear(ind):
    """Marca, com a mesma regra para todos, os melhores e piores períodos de cada indicador.

    `direcao` = "maior" (maior é melhor), "menor" (menor é melhor) ou None (sem juízo).
    Entre os n governos com dado, o quarto superior (arredondado para cima) é ponto forte
    e o quarto inferior é ponto fraco. Empates (mesmo valor arredondado) recebem a mesma
    classificação.
    """
    direcao = ind.get("direcao")
    res = ind["resumo"]
    if not direcao or len(res) < 3:
        return
    sinal = 1 if direcao == "maior" else -1
    v = {g: round(sinal * r["valor"], 3) for g, r in res.items()}
    n, k = len(v), math.ceil(len(v) / 4)
    for gid, x in v.items():
        melhores = sum(1 for y in v.values() if y > x)
        piores = sum(1 for y in v.values() if y < x)
        r = res[gid]
        r["posicao"], r["total"] = melhores + 1, n
        r["avaliacao"] = "bom" if melhores < k else ("ruim" if piores < k else None)
    ind["melhor"] = max(v, key=v.get)
    ind["pior"] = min(v, key=v.get)


def ano_base_fim(g, ultimo_ano):
    """Ano-base (antes do governo) e ano final de um governo para medir a variação de um nível."""
    ini, fim = pd.Timestamp(g["inicio"]), pd.Timestamp(g["fim"])
    base = ini.year - 1 if ini.month <= 6 else ini.year
    final = fim.year if fim.month >= 7 else fim.year - 1
    return base, min(final, ultimo_ano)


def resumo_ritmo(df_anual, tolerancia=2):
    """Variação média por ano de um indicador de nível durante cada governo.

    Compara o valor do ano anterior à posse com o do último ano do governo, com
    interpolação linear entre anos observados. Só usa anos a no máximo `tolerancia`
    anos de uma observação real, para não inventar tendência em lacunas longas.
    Medir o ritmo (e não o nível) evita premiar governos só por virem depois:
    mortalidade e analfabetismo caem há décadas.
    """
    obs = df_anual.groupby("ano").valor.mean()
    anos = range(int(obs.index.min()), int(obs.index.max()) + 1)
    serie = obs.reindex(anos).interpolate(limit_area="inside")
    perto = lambda a: min(abs(a - o) for o in obs.index) <= tolerancia  # noqa: E731
    out = {}
    for g in GOVERNOS:
        base, final = ano_base_fim(g, int(obs.index.max()))
        if final <= base or base not in serie.index or final not in serie.index:
            continue
        if pd.isna(serie[base]) or pd.isna(serie[final]) or not (perto(base) and perto(final)):
            continue
        out[g["id"]] = {"valor": (serie[final] - serie[base]) / (final - base),
                        "de": float(serie[base]), "para": float(serie[final]),
                        "periodo": f"{base} → {final}", "parcial": g["id"] == "lula3"}
    return out


def serie_anual_completa(a):
    """Série anual com todos os anos do intervalo; anos sem dado ficam null (o gráfico mostra a lacuna)."""
    obs = a.groupby("ano").valor.mean()
    anos = range(int(obs.index.min()), int(obs.index.max()) + 1)
    return [{"x": str(y), "y": (round(float(obs[y]), 4) if y in obs.index else None)} for y in anos]


def serie_json(df, fmt):
    return [{"x": d.strftime(fmt), "y": round(float(v), 4)} for d, v in zip(df.data, df.valor)]


# --------------------------------------------------------------------------- #
def main():
    ind = {}
    corte = pd.Timestamp(ANO_INICIAL - 1, 1, 1)
    hoje = pd.Timestamp.today()

    ipca = coletar("ipca", lambda: fontes.sgs(SGS["ipca"], SGS_INICIO), "BCB/SGS 433 (IBGE)")
    sm = coletar("salario_minimo", sgs_ou_ipea(
        "salario_minimo", SGS["salario_minimo"], "BCB/SGS 1619", nao_decrescente(1000, 3000),
        (["salário mínimo"], None, ["vigente", "nominal"], nao_decrescente(1000, 3000), ("real", "regional", "estadual"))),
        "BCB/SGS 1619")
    dolar = coletar("dolar", sgs_ou_ipea(
        "dolar", SGS["dolar"], "BCB/SGS 1 (PTAX venda)", faixa(3, 10),
        (["câmbio", "comercial", "venda"], None, ["média", "r$ / us$"], faixa(3, 10), ("real", "efetiva", "fim")),
        inicio=1994), "BCB/SGS 1 (PTAX venda)")
    pib = coletar("pib_crescimento", pib_crescimento, "BCB/SGS 7326 (IBGE)", max_atraso_dias=800)
    pibpc = coletar("pib_per_capita", lambda: fontes.banco_mundial("NY.GDP.PCAP.KD"), "Banco Mundial (IBGE)",
                    max_atraso_dias=800)
    cesta = coletar("cesta_sp", ipea_auto("cesta_sp", ["cesta", "são paulo"], "DIEESE", ["valor", "custo"],
                                          faixa(300, 3000), ("variação", "horas", "%")),
                    "DIEESE via Ipeadata")
    gas = coletar("gasolina", gasolina, "ANP — Levantamento de Preços")
    focos = coletar("queimadas", queimadas, "INPE/BDQueimadas", max_atraso_dias=800)
    # Descoberta (não afeta o site): candidatas oficiais do IBGE para PIB per capita e população.
    for termos in (["per capita"], ["população"]):
        try:
            fontes.ipea_buscar(*termos, periodicidade="Anual")
        except Exception as e:  # noqa: BLE001
            log.warning("descoberta %s: %s", termos, e)

    idx = indice_precos(ipca) if ipca is not None else None
    ref_mes = idx.index[-1].strftime("%m/%Y") if idx is not None else ""
    ano_atual = date.today().year

    def recorte(df):
        return df[df.data >= corte]

    # Moeda: salário mínimo e cesta básica antes do Real são convertidos para R$ equivalentes.
    sm_r = moedas.para_reais(mensal(recorte(sm))[["data", "valor"]], "salario_minimo") if sm is not None else None
    if sm_r is not None:
        sm_r["governo"] = [governo_do_mes(d.year, d.month) for d in sm_r.data]
    cesta_r = moedas.para_reais(mensal(recorte(cesta))[["data", "valor"]], "cesta_sp") if cesta is not None else None

    if pib is not None:
        a = anual(recorte(pib))
        a = a[a.ano >= ANO_INICIAL]
        ind["pib_crescimento"] = dict(
            tema="economia",
            titulo="Crescimento do PIB", unidade="% ao ano", formato="pct", grafico="barra", freq="anual",
            direcao="maior", pergunta="A economia cresceu?",
            descricao="Variação real do Produto Interno Bruto em relação ao ano anterior. Barras abaixo de zero são anos de recessão.",
            resumo_rotulo="crescimento médio por ano", resumo=resumo_media_ponderada(a),
            serie=serie_json(a, "%Y"), fonte=FONTE_PIB["txt"], fonte_url="https://www3.bcb.gov.br/sgspub/")

    if pibpc is not None:
        a = anual(pibpc)
        a["cresc"] = a.valor.pct_change() * 100
        g = a.dropna()[["ano", "cresc"]].rename(columns={"cresc": "valor"})
        g = g[g.ano >= ANO_INICIAL]
        a = a[a.ano >= ANO_INICIAL]
        ind["pib_per_capita"] = dict(
            tema="economia",
            titulo="PIB per capita", unidade="US$ de 2015 por pessoa", formato="moeda_usd", grafico="barra", freq="anual",
            direcao="maior", pergunta="A riqueza por pessoa aumentou?",
            descricao="PIB dividido pela população, em dólares constantes de 2015, sem efeito de inflação ou câmbio.",
            resumo_rotulo="crescimento médio por ano", resumo_formato="pct",
            resumo=resumo_media_ponderada(g), serie=serie_json(a, "%Y"),
            fonte="Banco Mundial, World Development Indicators (NY.GDP.PCAP.KD), a partir de dados do IBGE",
            fonte_url="https://data.worldbank.org/indicator/NY.GDP.PCAP.KD?locations=BR")

    if ipca is not None:
        m = mensal(recorte(ipca))
        m = m[m.data.dt.year >= ANO_INICIAL]
        por_ano = m.groupby(m.data.dt.year).valor.apply(lambda v: ((1 + v / 100).prod() - 1) * 100)
        a = pd.DataFrame({"data": pd.to_datetime([f"{y}-01-01" for y in por_ano.index]), "valor": por_ano.values})
        ind["ipca"] = dict(
            tema="custo",
            titulo="Inflação (IPCA)", unidade="% no ano, escala logarítmica", formato="pct", grafico="barra",
            freq="anual", escala="log", direcao="menor", pergunta="Os preços subiram muito?",
            descricao=(f"IPCA acumulado em cada ano. Até 1994 a inflação passou de 1.000% ao ano, por isso o eixo é "
                       f"logarítmico: cada linha do eixo vale 10 vezes a anterior. {ano_atual} vai só até o último mês divulgado."),
            resumo_rotulo="inflação média por ano", resumo=ipca_acumulado(m),
            serie=serie_json(a, "%Y"), fonte="IBGE — IPCA, via Banco Central (SGS 433)",
            fonte_url="https://www.ibge.gov.br/estatisticas/economicas/precos-e-custos/9256-indice-nacional-de-precos-ao-consumidor-amplo.html")
        m.to_csv(PROC / "ipca_mensal.csv", index=False, date_format="%Y-%m-%d")

    if sm_r is not None and idx is not None:
        r = deflacionar(sm_r, idx)
        ind["salario_minimo"] = dict(
            tema="custo",
            titulo="Salário mínimo real", unidade=f"R$ de {ref_mes}", formato="moeda", grafico="linha", freq="mensal",
            direcao="maior", pergunta="O salário mínimo compra mais?",
            descricao=(f"Salário mínimo convertido para reais e corrigido pelo IPCA até {ref_mes}. "
                       "Mostra o poder de compra: quanto o mínimo de cada época valeria hoje."),
            resumo_rotulo="ganho real no período", resumo_formato="pct", resumo=resumo_variacao(r),
            serie=serie_json(r[r.data.dt.year >= ANO_INICIAL], "%Y-%m"),
            fonte=FONTE_USADA.get("salario_minimo", "Banco Central (SGS 1619)") + ", deflacionado pelo IPCA/IBGE",
            fonte_url="https://www3.bcb.gov.br/sgspub/")
        r.to_csv(PROC / "salario_minimo_real.csv", index=False, date_format="%Y-%m-%d")
        validar_salario(r, ref_mes)

    if cesta_r is not None and sm_r is not None:
        j = cesta_r.merge(sm_r[["data", "valor"]], on="data", suffixes=("_cesta", "_sm"))
        j["valor"] = j.valor_cesta / j.valor_sm * 100
        j = j[j.data.dt.year >= ANO_INICIAL]
        j["governo"] = [governo_do_mes(d.year, d.month) for d in j.data]
        ind["cesta_sp"] = dict(
            tema="custo",
            titulo="Cesta básica (São Paulo)", unidade="% do salário mínimo", formato="pct_simples",
            grafico="linha", freq="mensal", direcao="menor", pergunta="A comida pesa no bolso?",
            descricao="Quanto do salário mínimo bruto a cesta básica de São Paulo consome. Acima de 100%, o mínimo não pagava a cesta.",
            resumo_rotulo="peso médio da cesta", resumo=resumo_media_mensal(j),
            serie=serie_json(j, "%Y-%m"),
            fonte="DIEESE — Pesquisa Nacional da Cesta Básica, via Ipeadata; salário mínimo do BCB",
            fonte_url="https://www.dieese.org.br/cesta/")

    if gas is not None and idx is not None:
        r = deflacionar(mensal(recorte(gas)), idx)
        ind["gasolina"] = dict(
            tema="custo",
            titulo="Gasolina", unidade=f"R$/litro de {ref_mes}", formato="moeda", grafico="linha", freq="mensal",
            direcao="menor", pergunta="Abastecer ficou mais caro?",
            descricao=f"Preço médio da gasolina comum nos postos, corrigido pelo IPCA para reais de {ref_mes}. A pesquisa da ANP começa em 2001.",
            resumo_rotulo="preço real médio", resumo=resumo_media_mensal(r),
            serie=serie_json(r, "%Y-%m"), fonte="ANP — Levantamento de Preços de Combustíveis (série histórica mensal)",
            fonte_url="https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos")

    if dolar is not None:
        d = mensal(recorte(dolar))
        d = d[d.data >= INICIO_REAL]
        ind["dolar"] = dict(
            tema="economia",
            titulo="Dólar", unidade="R$ por US$", formato="moeda", grafico="linha", freq="mensal",
            direcao=None, pergunta="Quanto custava o dólar?",
            descricao=("Média mensal da PTAX de venda, desde o Plano Real. Valor nominal. Não há ranking: dólar alto "
                       "favorece exportadores e encarece importados e viagens, então não é bom nem ruim por si só."),
            resumo_rotulo="cotação média", resumo=resumo_media_mensal(d),
            serie=serie_json(d, "%Y-%m"), fonte=FONTE_USADA.get("dolar", "Banco Central — PTAX venda (SGS 1)"),
            fonte_url="https://www3.bcb.gov.br/sgspub/")

    if focos is not None:
        a = anual(focos)
        a = a[a.ano >= QUEIMADAS_INICIO]
        fechados = a[a.ano < ano_atual]
        ind["queimadas"] = dict(
            tema="ambiente",
            titulo="Focos de queimada", unidade="focos no ano", formato="inteiro", grafico="barra", freq="anual",
            direcao="menor", pergunta="O país queimou mais?",
            descricao=(f"Focos de calor detectados pelo satélite de referência do INPE em todo o Brasil. "
                       f"A série comparável começa em 2003. {ano_atual} está incompleto e fica fora das médias."),
            resumo_rotulo="focos por ano, em média", resumo=resumo_media_ponderada(fechados),
            serie=serie_json(a, "%Y"), fonte="INPE — Programa Queimadas (satélite de referência)",
            fonte_url="https://terrabrasilis.dpi.inpe.br/queimadas/portal/")

    # ---------------- Fome, pobreza, saúde, educação (Banco Mundial / FAO / OMS / UNESCO, base IBGE) -------------
    WB = "https://data.worldbank.org/indicator/{}?locations=BR"
    sociais = [
        # id, código, título, pergunta, unidade, tema, direção, método, descrição, fonte
        ("fome", "SN.ITK.DEFC.ZS", "Mapa da Fome", "O Brasil estava no Mapa da Fome?", "% da população subalimentada",
         "fome", "menor", "nivel",
         "Prevalência de subalimentação calculada pela FAO (média de três anos). O país entra no Mapa da Fome quando "
         "passa de 2,5% da população. A FAO não divulga valores abaixo de 2,5%: nesses anos o gráfico mostra 2,5% e o país está fora do mapa.",
         "FAO (ONU), via Banco Mundial (SN.ITK.DEFC.ZS)"),
        ("pobreza", "SI.POV.DDAY", "Extrema pobreza", "Quantos viviam na extrema pobreza?", "% da população",
         "fome", "menor", "ritmo",
         "Parcela da população abaixo da linha internacional de extrema pobreza do Banco Mundial (paridade de poder de compra), calculada com a PNAD/IBGE.",
         "Banco Mundial (SI.POV.DDAY), a partir da PNAD/IBGE"),
        ("gini", "SI.POV.GINI", "Desigualdade (Gini)", "A desigualdade de renda caiu?", "índice de Gini (0 a 100)",
         "fome", "menor", "ritmo",
         "Índice de Gini da renda: 0 seria todos com a mesma renda, 100 seria uma pessoa com toda a renda. Calculado com a PNAD/IBGE.",
         "Banco Mundial (SI.POV.GINI), a partir da PNAD/IBGE"),
        ("mortalidade_infantil", "SP.DYN.IMRT.IN", "Mortalidade infantil", "Morriam menos bebês?", "mortes por mil nascidos vivos",
         "saude", "menor", "ritmo",
         "Mortes antes de 1 ano de idade a cada mil nascidos vivos. Cai há décadas no Brasil, por isso o ranking mede a velocidade da queda em cada governo.",
         "ONU (IGME), via Banco Mundial (SP.DYN.IMRT.IN), com dados do Ministério da Saúde e IBGE"),
        ("expectativa_vida", "SP.DYN.LE00.IN", "Expectativa de vida", "Os brasileiros passaram a viver mais?", "anos ao nascer",
         "saude", "maior", "ritmo",
         "Anos que um recém-nascido deve viver nas condições do período. O ranking mede quanto ela subiu por ano em cada governo.",
         "ONU (World Population Prospects), via Banco Mundial (SP.DYN.LE00.IN)"),
        ("gasto_saude", "SH.XPD.GHED.GD.ZS", "Gasto público em saúde", "Quanto o governo investiu em saúde?", "% do PIB",
         "saude", None, "nivel",
         "Despesa pública com saúde (União, estados e municípios, incluindo o SUS) como parcela do PIB. Sem ranking: gasto é insumo, não resultado.",
         "OMS (Global Health Expenditure Database), via Banco Mundial (SH.XPD.GHED.GD.ZS)"),
        ("gasto_educacao", "SE.XPD.TOTL.GD.ZS", "Gasto público em educação", "Quanto o governo investiu em educação?", "% do PIB",
         "educacao", None, "nivel",
         "Despesa pública com educação (todas as esferas) como parcela do PIB. Há anos sem dado. Sem ranking: gasto é insumo, não resultado.",
         "UNESCO, via Banco Mundial (SE.XPD.TOTL.GD.ZS), a partir de dados do INEP"),
        ("analfabetismo", "SE.ADT.LITR.ZS", "Analfabetismo", "O analfabetismo caiu?", "% das pessoas com 15 anos ou mais",
         "educacao", "menor", "ritmo",
         "Parcela das pessoas de 15 anos ou mais que não sabem ler e escrever (PNAD e Censo/IBGE). O ranking mede a velocidade da queda.",
         "UNESCO, via Banco Mundial (SE.ADT.LITR.ZS), a partir da PNAD/IBGE"),
        ("ensino_superior", "SE.TER.ENRR", "Acesso ao ensino superior", "Mais gente chegou à faculdade?", "taxa bruta de matrícula, %",
         "educacao", "maior", "ritmo",
         "Matrículas no ensino superior em relação à população na idade típica (taxa bruta, Censo da Educação Superior/INEP). O ranking mede quanto ela subiu por ano.",
         "UNESCO, via Banco Mundial (SE.TER.ENRR), a partir do Censo da Educação Superior/INEP"),
    ]
    for id_, cod, titulo, pergunta, unidade, tema, direcao, metodo, descricao, fonte in sociais:
        bruto = coletar(id_, (lambda c=cod: fontes.banco_mundial(c)), fonte, max_atraso_dias=365 * 6)
        if bruto is None:
            continue
        a = anual(bruto)
        if id_ == "analfabetismo":
            a["valor"] = 100 - a["valor"]
        a = a[a.ano >= ANO_INICIAL - 1]
        d = dict(titulo=titulo, pergunta=pergunta, unidade=unidade, tema=tema, direcao=direcao,
                 formato="pct_simples" if "%" in unidade or id_ == "gini" else "decimal",
                 grafico="linha_anual", freq="anual", descricao=descricao, fonte=fonte, fonte_url=WB.format(cod),
                 serie=serie_anual_completa(a[a.ano >= ANO_INICIAL]))
        if id_ == "gini":
            d["formato"] = "decimal"
        if metodo == "ritmo":
            d.update(resumo=resumo_ritmo(a), resumo_rotulo="variação por ano no governo", resumo_formato="delta")
        else:
            d.update(resumo=resumo_media_ponderada(a[a.ano >= ANO_INICIAL]), resumo_rotulo="média no governo")
        if id_ == "fome":
            d["limite"] = {"valor": 2.5, "rotulo": "Linha do Mapa da Fome (2,5%)"}
            d["mapa_fome"] = {str(int(r.ano)): bool(r.valor > 2.5) for r in a.itertuples()}
        ind[id_] = d

    try:
        fontes.mec_descobrir()
    except Exception as e:  # noqa: BLE001
        log.warning("descoberta MEC falhou: %s", e)

    for v in ind.values():
        ranquear(v)

    # ---------------- saídas ----------------
    linhas = []
    for id_, d in ind.items():
        for p in d["serie"]:
            x = p["x"]
            ano = int(x[:4])
            if len(x) > 4:
                gid = governo_do_mes(ano, int(x[5:7]))
            else:
                pesos = pesos_do_ano(ano)
                gid = max(pesos.items(), key=lambda kv: kv[1])[0] if pesos else None
            linhas.append({"indicador": id_, "periodo": x, "valor": p["y"], "governo": gid})
        pd.DataFrame([l for l in linhas if l["indicador"] == id_]).to_csv(PROC / f"{id_}.csv", index=False)

    with sqlite3.connect(RAIZ / "data" / "painel.sqlite") as db:
        for t in ("serie", "governo", "indicador", "resumo"):
            db.execute(f"DROP TABLE IF EXISTS {t}")
        pd.DataFrame(linhas).to_sql("serie", db, index=False)
        pd.DataFrame(governos_publicos()).to_sql("governo", db, index=False)
        pd.DataFrame([{"id": k, "titulo": v["titulo"], "unidade": v["unidade"], "frequencia": v["freq"],
                       "direcao": v.get("direcao"), "fonte": v["fonte"]} for k, v in ind.items()]).to_sql("indicador", db, index=False)
        pd.DataFrame([{"indicador": k, "governo": g, "metrica": v["resumo_rotulo"], "valor": r["valor"],
                       "posicao": r.get("posicao"), "total": r.get("total"), "avaliacao": r.get("avaliacao"),
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
             "governos": governos_publicos(), "contexto": CONTEXTO, "marcos": MARCOS,
             "indicadores": limpa(ind), "fontes": STATUS}
    (SITE_DATA / "painel.json").write_text(json.dumps(saida, ensure_ascii=False), encoding="utf-8")
    pd.DataFrame(STATUS).to_csv(RAIZ / "data" / "status_fontes.csv", index=False)
    log.info("Status das fontes:\n%s", pd.DataFrame(STATUS).to_string(index=False))
    log.info("Indicadores gerados: %s", list(ind))


def validar_salario(r, ref_mes):
    """Compara o salário mínimo real calculado aqui com a série oficial do Ipea (deflator INPC).

    Não altera nada: só grava data/descoberta/validacao_salario.csv para conferência.
    """
    try:
        ipea = mensal(fontes.ipea_serie("GAC12_SALMINRE12"))[["data", "valor"]]
        j = r[["data", "valor"]].merge(ipea, on="data", suffixes=("_painel", "_ipea"))
        j = j[j.data.dt.month == 1]
        j["razao"] = j.valor_painel / j.valor_ipea
        j.to_csv(RAIZ / "data" / "descoberta" / "validacao_salario.csv", index=False, date_format="%Y-%m-%d")
        log.info("Validação salário mínimo (janeiros, painel ÷ Ipea):\n%s", j.to_string(index=False))
    except Exception as e:  # noqa: BLE001
        log.warning("validação do salário mínimo não rodou: %s", e)


if __name__ == "__main__":
    main()
