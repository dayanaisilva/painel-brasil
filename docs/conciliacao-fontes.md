# Matriz de conciliação das fontes — metodologia 2.3

A concordância com uma série publicada verifica a transcrição, não elimina erros, revisões ou incertezas do produtor. As capturas desta revisão estão em `data/auditoria/originais`; hashes, endereços e filtros identificam a origem. Homicídios agora usa a série direta do Atlas; a edição anterior do Ipeadata foi preservada como evidência separada. As demais séries brutas não foram substituídas.

| Indicador | Conferência executada | Resultado | Limite / próximo passo |
|---|---|---|---|
| Gasolina | Duas planilhas mensais nacionais ANP, produto exatamente GASOLINA COMUM, preço médio de revenda, R$/l | 302/302 meses coincidem, jul/2001–set/2026 | Conciliado com ressalvas: mudança de média simples para ponderada em 2004, alterações de amostra e interrupção em 2020 |
| Gasolina real | Recalcular cada valor nominal pelo produto das taxas IPCA posteriores ao mês até a referência | 302/302 valores coincidem dentro do arredondamento de 4 casas | Confere a transformação com a série IPCA armazenada; não reestima a inflação |
| Homicídios | API Atlas, série 20, Brasil 1076, 1990–2024 | 35/35 taxas transcritas; todas diferem da edição Ipeadata anterior | Parcial: definição do Atlas identificada; diferenças entre versões ainda não conciliadas. Ranking suspenso |
| Subalimentação | API Banco Mundial SN.ITK.DEFC.ZS e FAOSTAT item 210041, Brazil, médias trienais | 24/24 triênios coincidem nas duas fontes; 2022–2024=2,7; 2023–2025=<2,5 | Conciliado com ressalvas: estimativas revisáveis, censura e sobreposição temporal; não reconstrói edições históricas |
| Universidades federais | Confronto do total 2024 com apresentação oficial INEP localizada por busca | 69 coincide com o arquivo armazenado | Parcial: documento indexado confirma o total; download do PDF e microdados retornou 503. Série histórica não recontada |
| Municípios com ensino federal | Revisão dos filtros e testes sintéticos | Código agora exige evidência de modalidade presencial | Pendente: 616 municípios em 2024 ainda não recontados nos microdados. Município não é campus |

## ANP: método e reprodução

Arquivos nacionais arquivados nesta revisão:
- [2001–2012](https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/precos-revenda-e-de-distribuicao-combustiveis/shlp/2001-2012/mensal-brasil-2001-a-2012.xlsx): aba BRASIL, cabeçalho na linha 13, coluna PRECO MÉDIO REVENDA.
- [Desde janeiro/2013](https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/precos-revenda-e-de-distribuicao-combustiveis/shlp/mensal/mensal-brasil-desde-jan2013.xlsx): cabeçalho na linha 17, coluna PREÇO MÉDIO REVENDA.
- [Metodologia e histórico da ANP](https://www.gov.br/anp/pt-br/assuntos/precos-e-defesa-da-concorrencia/precos/precos-revenda-e-de-distribuicao-combustiveis/informacoes-levantamento-de-precos-de-combustiveis).

A média nacional já vem calculada pela ANP. O painel não faz média simples de postos ou estados. A partir de novembro/2004, os valores nacionais publicados são ponderados pelas vendas informadas por distribuidoras; antes, a média era simples. Na média por governo, o painel dá peso igual aos meses observados. Setembro/2020 permanece ausente. A planilha e a página divergem no dia exato de início da interrupção de agosto/2020; ambas confirmam a interrupção, sem motivo para inventar setembro.

Correção monetária: preço real do mês t = preço nominal de t × produto de (1 + IPCA_m/100), para os meses m posteriores a t até o mês de referência. O script de auditoria refaz esse produto sem chamar a função de deflação do pipeline. Tolerância: 0,000051 R$/l, compatível com o arredondamento de saída em quatro casas.

O coletor foi corrigido para rejeitar unidade diferente de R$/l, planilha sem identificação Brasil e preços diferentes para um mesmo mês; sobreposição idêntica é deduplicada. Corrigido também o endereço fixo do arquivo 2001–2012.

## Atlas da Violência: coleta direta e divergência preservada

- [Série 20 — Taxa de homicídios registrados](https://www.ipea.gov.br/atlasviolencia/dados-series/20).
- [API de valores, abrangência países](https://www.ipea.gov.br/dados-api/series-values/20/1): selecionado `serie_id=20`, `tipo_regiao=1`, `regiao_id=1076`. O código Brasil foi confirmado em `/dados-api/geo/countries`.
- Metadados obtidos em `https://www.ipea.gov.br/cms/api/series/20?filters[projetos][id][$eq]=3`.
- Definição publicada: óbitos por residência, CID-10 X85–Y09 e Y35; taxa multiplicada por 100 mil. Para 1979–1995, o texto do produtor lista CID-9 E960–E978 e E990–E999. O painel não reinterpreta esses códigos nem reconta microdados.
- Captura: 35 anos (1990–2024), com datas anuais representadas na API em 15 de janeiro. O painel normaliza para 1 de janeiro sem interpretar isso como dia do óbito. Não extrapola anos ausentes.
- O Atlas fornece 20,03 em 2024, enquanto a edição Ipeadata arquivada fornece 20,10. Os 35 anos comuns diferem; `homicidios_entre_fontes.csv` preserva cada diferença e os anos exclusivos do Ipeadata. Não se calcula média entre fontes, não se emenda 1980–1989 à série nova e não se presume que a diferença seja apenas arredondamento.
- A API e o metadado correto do Atlas resolvem o acesso direto e a identificação da variável, mas ainda faltam a conciliação das versões de população/numeradores e a recontagem SIM. O ranking continua suspenso. Não confundir homicídios registrados com registros policiais ou estimativas de homicídios ocultos.

Os snapshots nacionais, o metadado, a identificação geográfica e o hash da resposta integral estão em `data/auditoria/originais/atlas_*`. O coletor rejeita identidade geográfica alterada, série errada, duplicação anual e taxas inválidas. A auditoria independente verifica a transcrição da edição Atlas armazenada; a edição Ipeadata anterior continua arquivada, inclusive seu metadado contraditório.

## FAO: censura confirmada na fonte primária

- [Arquivo FAOSTAT consultado](https://bulks-faostat.fao.org/production/Food_Security_Data_E_All_Data_(Normalized).zip), cabeçalho HTTP Last-Modified: 21/07/2026. Hash do ZIP e filtros em `originais/fao_origem.json`.
- Seleção: Area=Brazil, Item Code=210041, Element Code=6121, unidade %. A variável é prevalência de subalimentação, média de três anos. Flag E identifica estimativa.
- O CSV extraído preserva Year, Value e Flag. Os triênios 2011–2013 a 2018–2020 e 2023–2025 trazem literalmente <2.5. O ponto 2022–2024 traz 2.7.
- [API Banco Mundial](https://api.worldbank.org/v2/country/BRA/indicator/SN.ITK.DEFC.ZS?format=json&per_page=200), atualização informada 08/10/2026. Nela, 2,5 pode representar censura: por isso o metadado sozinho não basta para classificar todos esses pontos.

O site agora liga a marcação de censura à evidência FAOSTAT da mesma entrada. Se o arquivo bruto mudar, a validação é suspensa até nova conciliação. Não substituímos a observação censurada por zero nem a tratamos como 2,5 exato. Não contamos triênios sobrepostos como anos de governo. Confirmar o arquivo de julho/2026 não equivale a reconstituir o que cada relatório anterior divulgou na época.

## INEP: proteção implementada, recontagem bloqueada

- [Microdados 2024](https://download.inep.gov.br/microdados/microdados_censo_da_educacao_superior_2024.zip): tentativa de acesso parcial devolveu HTTP 503; não desativamos verificação TLS.
- [Apresentação oficial 2024](https://download.inep.gov.br/educacao_superior/censo_superior/documentos/2024/apresentacao_censo_da_educacao_superior_2024.pdf): resultado indexado informa 69 universidades e 41 institutos/CEFETs; download também retornou 503.

Instituições individualizadas precisam de CO_IES e são deduplicadas por identidade; classificações conflitantes geram erro. Arquivos históricos agregados continuam usando a coluna NUMERODEIES, inclusive para institutos. Municípios só contam com categoria federal e modalidade presencial explícita, ou arquivo histórico explicitamente denominado GRADUACAO_PRESENCIAL. Cursos a distância e municípios de código vazio/zero são excluídos. Não inferimos campus pela contagem de cursos ou municípios.

Essas proteções foram testadas com exemplos controlados, mas só o processamento dos microdados de cada ano permitirá concluir a conciliação histórica. O próximo passo depende de o INEP disponibilizar novamente os downloads ou de uma cópia oficial identificada por versão.

## Executar novamente

1. `TIRA_TEIMA_OFFLINE=1 python -m pipeline.build`
2. `python -m pipeline.auditar_fontes`
3. `python -m unittest discover -s tests -v`
4. `node tests/numeros.test.js`

O script gera CSVs por observação e `resultado.json`. Divergência não é corrigida automaticamente: uma revisão legítima da fonte precisa de novos snapshots e explicação. O registro de auditoria apresentado no site tem vínculo com o hash da entrada e, para gasolina real, também com o IPCA. Ainda não houve inspeção visual em navegador nem auditoria integral dos 25 indicadores.

## Tratamento de publicação

Após nova tentativa de consulta, persistiu o HTTP 503 no INEP. O acesso direto ao Atlas resolveu a identificação da variável, mas revelou diferenças em todos os 35 anos comuns com o Ipeadata. Na versão 2.3, esses três indicadores conservam suas séries, mas não geram resumo nem ranking por governo enquanto sua situação for parcial ou pendente. A restrição também se aplica automaticamente quando uma entrada auditada muda. Não se apresenta a suspensão como validação concluída.

A publicação em main usa o reprocessamento offline, seguido dos testes numéricos, de fontes, de DOM simulado e da conciliação com os snapshots. Coletas agendadas precisam passar pelas mesmas verificações antes de substituir o site.
