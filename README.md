# Tira-Teima · os números do Brasil, governo a governo (1985–2026)

Indicadores econômicos e ambientais do Brasil desde a redemocratização, comparados governo a governo (de Sarney a Lula 3), com dados públicos oficiais e atualização automática.

Cada indicador tem uma direção declarada (maior é melhor, menor é melhor ou sem ranking). Em cada um, o quarto melhor dos governos recebe ▲ ponto forte e o quarto pior ▼ ponto fraco, com a mesma régua para todos.

**Site:** https://tirateimabr.com.br

## O que tem

| Indicador | Fonte | Frequência | Métrica por governo |
|---|---|---|---|
| Crescimento do PIB | IBGE via Banco Central (SGS 7326) | anual | média anual |
| PIB per capita | Banco Mundial (NY.GDP.PCAP.KD), base IBGE | anual | crescimento médio anual |
| Inflação (IPCA) | IBGE via Banco Central (SGS 433) | mensal | média anual equivalente |
| Salário mínimo real | Banco Central (SGS 1619) deflacionado pelo IPCA | mensal | ganho real no mandato |
| Cesta básica SP | DIEESE via Ipeadata | mensal | % do salário mínimo |
| Gasolina | ANP, deflacionada pelo IPCA, desde 2001 | mensal | preço real médio |
| Dólar | Banco Central, PTAX venda (SGS 1), desde jul/1994 | mensal | cotação média (sem ranking) |
| Focos de queimada | INPE, satélite de referência, desde 2003 | anual | média anual |

Regras de atribuição (mês pelo dia 15, ano pela proporção de dias governados), conversão das moedas anteriores ao Real (`pipeline/moedas.py`) e limites de leitura estão na seção Metodologia do site.

## Arquitetura

```
GitHub Actions (dias 12 e 28 + a cada push)
  └─ python -m pipeline.build
       ├─ pipeline/fontes.py     coleta: APIs do BCB, Banco Mundial, Ipeadata, INPE
       ├─ pipeline/governos.py   períodos, contexto e regras de atribuição
       ├─ pipeline/moedas.py     conversão Cruzeiro → Cruzado → … → Real
       └─ pipeline/build.py      tratamento, deflação, resumos por governo
            ├─ data/raw/*.csv          séries originais (versionadas)
            ├─ data/processed/*.csv    séries tratadas + governo
            ├─ data/painel.sqlite      base para SQL
            └─ site/data/painel.json   o que o site lê
  └─ GitHub Pages publica a pasta site/
```

Se uma fonte falhar, o pipeline reaproveita o último CSV válido e marca a série como "cópia anterior" na tabela de situação das fontes. Extremos ausentes não são interpolados nos rankings. A metodologia 2.3 distingue retratos de dezembro, ciclos PRODES e médias anuais convencionais.

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

## Revisão estatística 2.3

- Sem placar agregado entre indicadores; posições são descritivas, não testes de significância.
- Ritmos exigem extremos presentes na fonte e cobertura original mínima de 75% dos anos.
- Bolsa Família: média dos retratos de dezembro atribuídos ao governo nessa data.
- PRODES: resumo apenas dos ciclos completos dentro do governo e consolidados; cobertura mínima de 75% dos ciclos elegíveis. Estimativas e ciclos compartilhados continuam no gráfico.
- Gráficos FAO mostram o triênio e exportam o limite como `<2,5`, não como observação exata.
- A base registra hashes SHA-256 dos CSVs usados. Isso rastreia entradas, mas não certifica a fonte nem substitui revisão de seus metadados.

Validação: `python -m unittest discover -s tests -v` e `node tests/numeros.test.js`.
Reprocessamento sem coleta: `TIRA_TEIMA_OFFLINE=1 python -m pipeline.build`.
Nesse modo os CSVs existentes são preservados e as fontes são identificadas como cópia anterior; a projeção populacional usa a população já armazenada. Não é uma atualização de dados.

Limitações ainda abertas: conciliação integral com os produtores, harmonização histórica do Gini, revisão FAO de 2,7%, intervalos amostrais e sensibilidade das médias anuais ponderadas. Não interpretar posições como efeito causal ou superioridade estatisticamente comprovada.

## Conciliação de fontes

Execute `python -m pipeline.auditar_fontes` após o build para comparar os dados com os snapshots oficiais arquivados em `data/auditoria/originais`. O comando falha diante de divergências e produz comparações por observação. Não substitui os dados automaticamente. Instale as dependências de `requirements.txt`.

Escopo, pendências, definições e links: [matriz de conciliação](docs/conciliacao-fontes.md). O status apresentado no site exige nova conferência quando muda o arquivo de entrada.

Homicídios: coleta direta do [Atlas da Violência, série 20](https://www.ipea.gov.br/atlasviolencia/dados-series/20), Brasil 1076, 1990–2024. A edição Ipeadata anterior foi arquivada e as diferenças estão em `data/auditoria/homicidios_entre_fontes.csv`. Rankings permanecem suspensos até conciliar as versões; dados de homicídios ocultos não são somados à série registrada.
