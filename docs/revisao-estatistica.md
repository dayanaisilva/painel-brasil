# Revisão estatística 2.3

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

22 testes Python de casos matemáticos/temporais e 11 casos JavaScript de entrada monetária; verificação de sintaxe JavaScript; geração completa dos 25 indicadores com os arquivos versionados. A coleta online completa e a inspeção visual em navegador não foram executadas nesta revisão.

## Pendências antes de afirmar validação integral

- A harmonização de PNADS_GINI foi conferida nos metadados do Ipeadata; ainda não foi refeita a estimação com microdados.
- A revisão de 2,7% e os limites <2,5 foram conciliados com o arquivo FAOSTAT de 21/07/2026; ainda não se reconstituíram todas as edições anteriores do SOFI.
- ANP conciliada com as duas planilhas nacionais; INEP depende de acesso aos microdados; SIM ainda exige resolução da inconsistência do metadado e conciliação histórica do denominador. Ver docs/conciliacao-fontes.md.
- Médias anuais ponderadas são convenções, não resultados observados em frações do ano. A análise de sensibilidade agora compara com anos civis completos, excluindo transições e ano corrente; não é intervalo de confiança. A versão 2.3 também compara ritmos entre o primeiro e o último ano civil completo.
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

A branch não publica no GitHub Pages. Em push ou execução manual, main reprocessa offline os insumos revisados, executa testes e conciliação e só então publica. Coletas online permanecem no agendamento; divergências com snapshots bloqueiam a publicação até revisão. Removido o rebase automático com escolha de conflitos e a publicação após falha de push.

## Continuação: metodologia 2.2

Conciliação numérica sem divergências: 302 preços ANP, 302 valores reais recalculados pelo IPCA, 45 taxas nacionais Ipeadata e 24 triênios tanto no Banco Mundial quanto na FAOSTAT. O arquivo original da FAOSTAT confirma o 2,7% de 2022–2024 e os sinais <2,5, resolvendo essa pendência da etapa 2.1. A censura só é exibida quando vinculada à evidência do mesmo arquivo de entrada.

Adicionados 8 testes de fontes: produto e unidade da ANP, abrangência Brasil, conflito de preço duplicado, identidade de instituição, modalidade presencial e correspondência da censura FAO. Não foram alterados valores brutos existentes nesta etapa. A documentação do Ipeadata para homicídios contém uma inconsistência de códigos CID; não deve ser tomada como definição validada. Downloads INEP falharam com HTTP 503: a revisão dos filtros é uma proteção de código, não uma recontagem concluída.

## Tratamento das pendências para publicação — 2.3

Nova tentativa confirmou HTTP 503 no INEP. A integração direta do Atlas identificou a definição de homicídios, mas encontrou diferenças nos 35 anos comuns com o Ipeadata. Essas limitações externas não foram declaradas resolvidas. A correção de produto é suspender resumos e rankings governamentais de homicídios, universidades federais e municípios com ensino federal, mantendo séries e ressalvas consultáveis. O CSV/SQLite também deixa de atribuir essas observações a governos. Uma auditoria cujo insumo mudou recebe a mesma restrição até nova conciliação.

Sensibilidade dos ritmos: compara o resultado principal com a variação entre o primeiro e último ano civil completo, com extremos presentes, pelo menos dois anos completos e cobertura mínima de 75%. A tabela mostra resultado alternativo, sem interpretá-lo como efeito causal. Expressão “ficou estável” substituída por “variação inferior a 0,5%”, evitando sugerir teste estatístico inexistente.

Verificação funcional anterior à publicação: 43 rotas em DOM simulado, ausência das tabelas suspensas, censura FAO e entradas válidas/inválidas da calculadora. Isso não substitui a revisão visual dos gráficos; a checagem visual é feita no endereço público após o deploy. O rodapé distingue data de processamento de atualização das fontes.

### Integração direta do Atlas

O coletor de homicídios passou à API do Atlas da Violência (série 20, Brasil 1076). A edição anterior foi arquivada; 35 taxas de 1990–2024 substituem a série anterior sem emenda. O CSV entre fontes documenta as divergências, inclusive 20,03 versus 20,10 em 2024. A transcrição é validada por snapshot; a conciliação das versões não foi concluída, portanto a suspensão de resumos e rankings permanece. Foram adicionados testes de geografia, seleção nacional, datas, duplicação e valores inválidos.
