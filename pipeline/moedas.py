"""Conversão de valores anteriores ao Plano Real para reais (R$).

Entre 1986 e 1994 o Brasil trocou de moeda quatro vezes, cortando zeros a cada
troca. Uma série em "moeda da época" despenca na mês da troca. Este módulo:

1. procura essa queda perto da data de cada troca;
2. se encontrar, divide todos os valores anteriores pelo fator oficial da troca;
3. registra o que fez em data/descoberta/moedas_<serie>.csv.

Se a série já vier convertida (sem queda), nada é alterado. Assim o código
funciona igual para fontes que entregam valores na moeda da época ou já em R$.

Fatores oficiais (Banco Central, "Padrões monetários brasileiros"):
  28/02/1986  Cruzeiro (Cr$)        → Cruzado (Cz$)           ÷ 1.000
  16/01/1989  Cruzado (Cz$)         → Cruzado Novo (NCz$)     ÷ 1.000
  16/03/1990  Cruzado Novo (NCz$)   → Cruzeiro (Cr$)          ÷ 1 (só troca de nome)
  01/08/1993  Cruzeiro (Cr$)        → Cruzeiro Real (CR$)     ÷ 1.000
  01/07/1994  Cruzeiro Real (CR$)   → Real (R$)               ÷ 2.750
"""
from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

log = logging.getLogger("moedas")
DESCOBERTA = Path(__file__).resolve().parent.parent / "data" / "descoberta"

TROCAS = [
    ("1986-02-28", 1000, "Cruzeiro → Cruzado"),
    ("1989-01-16", 1000, "Cruzado → Cruzado Novo"),
    ("1993-08-01", 1000, "Cruzeiro → Cruzeiro Real"),
    ("1994-07-01", 2750, "Cruzeiro Real → Real"),
]


def para_reais(df: pd.DataFrame, nome: str) -> pd.DataFrame:
    """Recebe série mensal (data, valor) e devolve tudo em R$ equivalentes."""
    df = df.sort_values("data").reset_index(drop=True).copy()
    registro = []
    for data_troca, fator, rotulo in TROCAS:
        d = pd.Timestamp(data_troca)
        janela = df[(df.data >= d - pd.DateOffset(months=2)) & (df.data <= d + pd.DateOffset(months=2))]
        if len(janela) < 2:
            registro.append({"troca": rotulo, "data": data_troca, "acao": "sem dados na janela"})
            continue
        razoes = (janela.valor / janela.valor.shift(1)).iloc[1:]
        menor = razoes.min()
        # Uma série na moeda da época cai ~fator vezes na troca (mesmo com inflação de 80% ao mês).
        if menor < 20 / fator:
            idx_queda = razoes.idxmin()
            corte = df.loc[idx_queda, "data"]
            df.loc[df.data < corte, "valor"] = df.loc[df.data < corte, "valor"] / fator
            registro.append({"troca": rotulo, "data": data_troca, "acao": f"convertido ÷{fator}",
                             "queda_detectada_em": str(corte.date()), "razao": round(float(menor), 6)})
        else:
            registro.append({"troca": rotulo, "data": data_troca, "acao": "já estava convertida",
                             "razao": round(float(menor), 4)})
    DESCOBERTA.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(registro).to_csv(DESCOBERTA / f"moedas_{nome}.csv", index=False)
    log.info("Conversão de moeda %s: %s", nome, registro)
    return df
