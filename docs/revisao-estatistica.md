# Revisão estatística 2.1

Esta revisão corrige regras de transformação e apresentação. Não certifica todas as observações das fontes.

## Alterações

- Extremos dos ritmos exigem observações presentes na fonte; nenhuma interpolação é usada. Cobertura mínima de 75% dos anos entre extremos, antes de preenchimento. Uma estimativa publicada pela fonte continua sendo observação da série, não medição sem incerteza.
- Bolsa Família: retratos de dezembro atribuídos pela data, sem ratear dezembro de 2016 para Dilma 2.
- PRODES: apenas ciclos agosto–julho inteiros dentro de um governo e consolidados entram no resumo. Cobertura: ciclos consolidados disponíveis / ciclos completos elegíveis até a data da execução. Ciclos compartilhados e estimativas permanecem no gráfico. Essa escolha reduz a comparabilidade de amostras; não é estimativa causal.
- CSV e SQLite não atribuem ciclos PRODES compartilhados ou triênios FAO a um único governo.
- Calculadora valida toda a entrada pt-BR: 1.000 significa mil; letras, negativos e formatos inválidos são rejeitados.
- Retirada de placares agregados; rankings restantes são descritivos, não inferência estatística.
- FAO: tooltip e CSV mostram triênios e `<2,5`; desmatamento mostra ciclos no tooltip.
- Rótulos de gastos públicos e médias de três meses nas trajetórias esclarecidos.
- Hashes dos arquivos de entrada e versão da metodologia no JSON.
- Reprocessamento offline preserva CSVs brutos e marca a origem como cópia anterior. Não representa atualização das fontes.

## Validação executada

11 testes Python de casos matemáticos/temporais e 11 casos JavaScript de entrada monetária; verificação de sintaxe JavaScript; geração completa dos 25 indicadores com os arquivos versionados. A coleta online completa e a inspeção visual em navegador não foram executadas nesta revisão.

## Pendências antes de afirmar validação integral

- A harmonização de PNADS_GINI foi conferida nos metadados do Ipeadata; ainda não foi refeita a estimação com microdados.
- Conferir no SOFI original a revisão específica de 2,7%.
- Conciliar integralmente filtros ANP, INEP, SIM e demais séries com arquivos originais.
- Médias anuais ponderadas são convenções, não resultados observados em frações do ano. A análise de sensibilidade agora compara com anos civis completos, excluindo transições e ano corrente; não é intervalo de confiança. Ainda falta sensibilidade dos anos-base nas métricas de ritmo.
- Salário mínimo permanece com ganho acumulado entre médias móveis de 12 meses; não comparar como ritmo anual.
- Não foram calculados intervalos amostrais: exigem desenho amostral, microdados ou estimativas oficiais.
- A coleta online completa e a conciliação de todas as séries permanecem pendentes. Novas versões das fontes podem revisar resultados; isso deve ser distinguido de mudança de método.

## Continuação: metodologia 2.1

- Gini: metadados oficiais consultados em 03/11/2026, registrados em `data/metadata/gini.json`. O produtor confirma PNAD até 2011, PNAD Contínua desde 2012 e ajuste multiplicativo do trecho antigo para igualar as pesquisas em 2012. Referência indicada pelo Ipea: Souza e Hecksher (2025). A ressalva agora explica essa harmonização, sem confundir a série com valores originais do IBGE. Endpoint: https://www.ipeadata.gov.br/api/odata4/Metadados('PNADS_GINI').
- PIB per capita: projeção DEPIS_POPP coletada e versionada separadamente em `data/raw/populacao_projecao.csv`. Os dois modos usam o mesmo cálculo e o mesmo insumo identificado. Sem projeção, não se estende o resultado pós-Contas Nacionais com outra população silenciosamente. Lacunas não viram crescimento anual.
- Fome: removida a contagem de triênios por governo. O gráfico e o CSV continuam mostrando os triênios. Retirada a atribuição não conciliada da revisão de 2,7% a uma edição específica do SOFI; o valor da série armazenada foi preservado e sua conciliação continua pendente.
- Sensibilidade: médias anuais ponderadas agora incluem a alternativa com somente anos civis inteiros do governo e já encerrados, exigindo a mesma cobertura mínima de 75%. A alternativa aparece no site e no CSV. Exemplo nos dados reprocessados: PIB de Temer, 0,38% na média ponderada de 2016–2018 versus 1,55% usando 2017–2018. A diferença de 1,17 ponto percentual mostra por que o recorte deve ser explícito, não qual estimativa é causalmente correta.
- Validação adicional: 5 testes de população e sensibilidade; geração dos 25 indicadores; checagem de resumos finitos e ausência de resumo governamental da fome. O CI do primeiro commit do PR passou; este registro não presume aprovação do CI de commits posteriores.

## Publicação

A branch não publica no GitHub Pages. O workflow de main coleta e regenera as saídas ao integrar o PR. Revisar as diferenças e as pendências antes de integrar.
