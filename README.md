# Painel Brasil 2003–2026

Indicadores econômicos e ambientais do Brasil comparados governo a governo, de Lula 1 a Lula 3, com dados públicos oficiais e atualização automática.

**Site:** https://dayanaisilva.github.io/painel-brasil/

## O que tem

| Indicador | Fonte | Frequência | Métrica por governo |
|---|---|---|---|
| Crescimento do PIB | IBGE via Banco Central (SGS 7326) | anual | média anual |
| PIB per capita | Banco Mundial (NY.GDP.PCAP.KD), base IBGE | anual | crescimento médio anual |
| Inflação (IPCA) | IBGE via Banco Central (SGS 433) | mensal | média anual equivalente |
| Salário mínimo real | Banco Central (SGS 1619) deflacionado pelo IPCA | mensal | ganho real no mandato |
| Cesta básica SP | DIEESE via Ipeadata | mensal | % do salário mínimo |
| Gasolina | ANP via Ipeadata, deflacionada pelo IPCA | mensal | preço real médio |
| Dólar | Banco Central (SGS 3698) | mensal | cotação média |
| Focos de queimada | INPE, satélite de referência | anual | média anual |

Regras de atribuição (mês pelo dia 15, ano pela proporção de dias governados) e limites de leitura estão na seção Metodologia do site.

## Arquitetura

```
GitHub Actions (dias 12 e 28 + a cada push)
  └─ python -m pipeline.build
       ├─ pipeline/fontes.py     coleta: APIs do BCB, Banco Mundial, Ipeadata, INPE
       ├─ pipeline/governos.py   períodos e regras de atribuição
       └─ pipeline/build.py      tratamento, deflação, resumos por governo
            ├─ data/raw/*.csv          séries originais (versionadas)
            ├─ data/processed/*.csv    séries tratadas + governo
            ├─ data/painel.sqlite      base para SQL
            └─ site/data/painel.json   o que o site lê
  └─ GitHub Pages publica a pasta site/
```

Se uma fonte falhar, o pipeline reaproveita o último CSV válido e marca a série como "cópia anterior" na tabela de situação das fontes. Nenhum dado é inventado ou preenchido.

## Rodar localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pipeline.build
cd site && python -m http.server 8000   # abra http://localhost:8000
```

## Consultas SQL

`queries/exemplos.sql` tem consultas prontas sobre `data/painel.sqlite`: pivot do comparativo, `ROW_NUMBER`, `LAG` e média móvel.

```bash
sqlite3 data/painel.sqlite < queries/exemplos.sql
```

## Aviso

Os números mostram o que aconteceu durante cada governo, não o que cada governo causou. Contexto externo e decisões de mandatos anteriores afetam os resultados.
