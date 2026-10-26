"""Períodos de governo usados para recortar as séries.

Regras (documentadas em site/metodologia.html):
- Dado mensal: o mês pertence ao governo em exercício no dia 15 daquele mês.
- Dado anual: o ano é dividido entre os governos na proporção dos dias que cada
  um governou naquele ano (afeta 1985, 1990, 1992 e 2016).
- Afastamentos por impeachment (Collor em 1992, Dilma em 2016): o período do vice
  começa na data em que assumiu como interino.
"""
from datetime import date

GOVERNOS = [
    {"id": "sarney",    "nome": "Sarney",     "presidente": "José Sarney",               "inicio": "1985-03-15", "fim": "1990-03-14"},
    {"id": "collor",    "nome": "Collor",     "presidente": "Fernando Collor de Mello",  "inicio": "1990-03-15", "fim": "1992-10-01"},
    {"id": "itamar",    "nome": "Itamar",     "presidente": "Itamar Franco",             "inicio": "1992-10-02", "fim": "1994-12-31"},
    {"id": "fhc1",      "nome": "FHC 1",      "presidente": "Fernando Henrique Cardoso", "inicio": "1995-01-01", "fim": "1998-12-31"},
    {"id": "fhc2",      "nome": "FHC 2",      "presidente": "Fernando Henrique Cardoso", "inicio": "1999-01-01", "fim": "2002-12-31"},
    {"id": "lula1",     "nome": "Lula 1",     "presidente": "Luiz Inácio Lula da Silva", "inicio": "2003-01-01", "fim": "2006-12-31"},
    {"id": "lula2",     "nome": "Lula 2",     "presidente": "Luiz Inácio Lula da Silva", "inicio": "2007-01-01", "fim": "2010-12-31"},
    {"id": "dilma1",    "nome": "Dilma 1",    "presidente": "Dilma Rousseff",            "inicio": "2011-01-01", "fim": "2014-12-31"},
    {"id": "dilma2",    "nome": "Dilma 2",    "presidente": "Dilma Rousseff",            "inicio": "2015-01-01", "fim": "2016-05-11"},
    {"id": "temer",     "nome": "Temer",      "presidente": "Michel Temer",              "inicio": "2016-05-12", "fim": "2018-12-31"},
    {"id": "bolsonaro", "nome": "Bolsonaro",  "presidente": "Jair Bolsonaro",            "inicio": "2019-01-01", "fim": "2022-12-31"},
    {"id": "lula3",     "nome": "Lula 3",     "presidente": "Luiz Inácio Lula da Silva", "inicio": "2023-01-01", "fim": "2026-12-31"},
]

for g in GOVERNOS:
    g["_ini"] = date.fromisoformat(g["inicio"])
    g["_fim"] = date.fromisoformat(g["fim"])

ANO_INICIAL = 1985
INICIO_REAL = "1994-07-01"  # Plano Real: comparações nominais em moeda só fazem sentido daqui em diante


def governo_do_mes(ano: int, mes: int) -> str | None:
    d = date(ano, mes, 15)
    for g in GOVERNOS:
        if g["_ini"] <= d <= g["_fim"]:
            return g["id"]
    return None


def pesos_do_ano(ano: int) -> dict[str, float]:
    """Fração do ano governada por cada governo (soma = 1)."""
    ini, fim = date(ano, 1, 1), date(ano, 12, 31)
    total = (fim - ini).days + 1
    pesos = {}
    for g in GOVERNOS:
        a, b = max(ini, g["_ini"]), min(fim, g["_fim"])
        if a <= b:
            pesos[g["id"]] = ((b - a).days + 1) / total
    return pesos


def governos_publicos():
    return [{k: v for k, v in g.items() if not k.startswith("_")} for g in GOVERNOS]


# Contexto factual de cada período: fatos datados, sem avaliação. Serve para ler os
# números com o que estava acontecendo no país e no mundo.
CONTEXTO = {
    "sarney": ["Fim da ditadura; primeiro governo civil desde 1964", "Plano Cruzado (1986) e congelamento de preços",
               "Moratória da dívida externa (1987)", "Nova Constituição (1988)", "Hiperinflação no fim do mandato"],
    "collor": ["Plano Collor (1990) e bloqueio das cadernetas de poupança", "Abertura comercial",
               "Afastado em out/1992 no processo de impeachment"],
    "itamar": ["Assume após o afastamento de Collor", "Plano Real: URV (mar/1994) e nova moeda (jul/1994)"],
    "fhc1": ["Consolidação do Real e queda da inflação", "Privatizações", "Crises do México (1995), da Ásia (1997) e da Rússia (1998)"],
    "fhc2": ["Desvalorização do real e câmbio flutuante (jan/1999)", "Regime de metas de inflação (1999)",
             "Lei de Responsabilidade Fiscal (2000)", "Racionamento de energia (2001)"],
    "lula1": ["Alta internacional dos preços de commodities", "Unificação de programas no Bolsa Família (2003)"],
    "lula2": ["Crise financeira global (2008–2009)", "Política de valorização do salário mínimo"],
    "dilma1": ["Fim do ciclo de alta das commodities", "Protestos de junho de 2013", "Copa do Mundo (2014)"],
    "dilma2": ["Recessão de 2015–2016", "Afastada em mai/2016 no processo de impeachment"],
    "temer": ["Teto de gastos (EC 95, 2016)", "Reforma trabalhista (2017)", "Greve dos caminhoneiros (2018)"],
    "bolsonaro": ["Reforma da Previdência (2019)", "Pandemia de Covid-19 (2020–2022)", "Auxílio emergencial (2020)",
                  "Guerra na Ucrânia e alta dos combustíveis (2022)"],
    "lula3": ["Novo arcabouço fiscal (2023)", "Reforma tributária (EC 132, 2023)", "Mandato em andamento"],
}

# Marcos desenhados nos gráficos (mês do evento).
MARCOS = [
    {"data": "1986-03", "rotulo": "Plano Cruzado", "curto": "Cruzado"},
    {"data": "1990-03", "rotulo": "Plano Collor", "curto": "P. Collor"},
    {"data": "1994-07", "rotulo": "Plano Real", "curto": "Real"},
    {"data": "1999-01", "rotulo": "Câmbio flutuante", "curto": "Câmbio"},
    {"data": "2008-09", "rotulo": "Crise financeira global", "curto": "Crise 2008"},
    {"data": "2020-03", "rotulo": "Pandemia de Covid-19", "curto": "Covid"},
]
