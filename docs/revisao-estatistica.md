# Revisão estatística 2.0

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

6 testes Python de casos matemáticos/temporais e 11 casos JavaScript de entrada monetária; verificação de sintaxe JavaScript; geração completa dos 25 indicadores com os arquivos versionados. A coleta online completa e a inspeção visual em navegador não foram executadas nesta revisão.

## Pendências antes de afirmar validação integral

- Conferir versão e harmonização de PNADS_GINI nos metadados do produtor.
- Conferir no SOFI original a revisão específica de 2,7%.
- Conciliar integralmente filtros ANP, INEP, SIM e demais séries com arquivos originais.
- Médias anuais ponderadas restantes são convenções, não resultados observados em frações do ano. Falta publicar análise de sensibilidade dos anos de transição.
- Salário mínimo permanece com ganho acumulado entre médias móveis de 12 meses; não comparar como ritmo anual.
- Não foram calculados intervalos amostrais: exigem desenho amostral, microdados ou estimativas oficiais.
- Reprocessamento offline do PIB per capita usa população já armazenada para anos posteriores às Contas Nacionais; a coleta online consulta projeção separada e pode revisar o resultado.

## Publicação

A branch não publica no GitHub Pages. O workflow de main coleta e regenera as saídas ao integrar o PR. Revisar as diferenças e as pendências antes de integrar.
