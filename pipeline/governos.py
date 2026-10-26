"""Períodos de governo usados para recortar as séries.

Regras (documentadas em site/metodologia.html):
- Dado mensal: o mês pertence ao governo em exercício no dia 15 daquele mês.
- Dado anual: o ano é dividido entre os governos na proporção dos dias que cada
  um governou naquele ano (só afeta 2016, ano do afastamento de Dilma Rousseff).
"""
from datetime import date

GOVERNOS = [
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

ANO_INICIAL = 2003


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
