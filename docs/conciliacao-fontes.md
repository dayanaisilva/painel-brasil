# Matriz de conciliação das fontes — metodologia 2.2

A concordância com uma série publicada verifica a transcrição, não elimina erros, revisões ou incertezas do produtor. As capturas desta revisão estão em `data/auditoria/originais`; hashes, endereços e filtros identificam a origem. Os arquivos brutos existentes do painel não foram substituídos nesta etapa.

| Indicador | Conferência executada | Resultado | Limite / próximo passo |
|---|---|---|---|
| Gasolina | Duas planilhas mensais nacionais ANP, produto exatamente GASOLINA COMUM, preço médio de revenda, R$/l | 302/302 meses coincidem, jul/2001–set/2026 | Conciliado com ressalvas: mudança de média simples para ponderada em 2004, alterações de amostra e interrupção em 2020 |
| Gasolina real | Recalcular cada valor nominal pelo produto das taxas IPCA posteriores ao mês até a referência | 302/302 valores coincidem dentro do arredondamento de 4 casas | Confere a transformação com a série IPCA armazenada; não reestima a inflação |
| Homicídios | Série AVIOL12_THOMIC, apenas NIVNOME=Brasil, 1980–2024 | 45/45 taxas coincidem; 20,1 em 2024 confirmado também pela divulgação oficial do Atlas 2026 | Parcial: metadado traz título de homicídios e descrição de suicídios; não recontados óbitos nem conciliado denominador histórico |
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

## SIM/Ipeadata: inconsistência não resolvida

- [Metadado consultado](https://www.ipeadata.gov.br/api/odata4/Metadados('AVIOL12_THOMIC')).
- [Valores consultados](https://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='AVIOL12_THOMIC')). O snapshot arquivado contém somente as 45 linhas Brasil extraídas da resposta integral; seu hash integral está em `originais/downloads.json`.
- [Divulgação oficial do Atlas 2026](https://www.gov.br/planejamento/pt-br/assuntos/noticias/2026/maio/atlas-da-violencia-brasil-registrou-42-590-homicidios-em-2024-menor-resultado-da-serie-historica-mas-subnotificacao-preocupa).
- [Definição no Atlas 2020](https://repositorio.ipea.gov.br/bitstream/11058/10353/1/AtlasdaViolencia2020_Cap1.pdf): óbitos por residência, agressões e intervenção legal (X85–Y09 e Y35–Y36).

O metadado AVIOL12_THOMIC menciona E950–E959 e X60–X84, que são códigos de suicídio, apesar do título de homicídios. Não usamos essa descrição para reconstruir um numerador. Os valores coincidem com a série publicada e a taxa de 2024 tem confirmação independente, mas isso não resolve a definição histórica. Para fechar a auditoria, é preciso identificar a versão correta do dicionário e reproduzir numeradores e denominadores ano a ano. A série não deve ser confundida com registros policiais ou estimativas de homicídios ocultos.

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
