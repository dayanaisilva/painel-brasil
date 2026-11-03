# Terras Indígenas: desmatamento e limites da comparação

## Dados incluídos — metodologia 2.4

O indicador usa os incrementos do PRODES nos recortes indígenas da Amazônia Legal, edição TerraBrasilis de 16/10/2026. São 386 nomes no cadastro dessa edição e 18 ciclos de agosto a julho, 2008–2025. O usuário pode comparar dois territórios por ano e baixar todos os registros no CSV do indicador.

Origem: https://terrabrasilis.dpi.inpe.br/app/dashboard/deforestation/biomes/legal_amazon/increments . O aplicativo público consulta os arquivos `data/prodes_legal_amazon.json` e `config/loinames/prodes_legal_amazon.json` em `/app/prodes/dashboard/deforestation/files/`. Recorte `loi=4`, nome `indi`, classe `deforestation`, área `type=1`, unidade km². Os registros territoriais e o cadastro selecionados são preservados em `data/auditoria/originais/prodes_ti*`, com hashes das respostas integrais e endereço de origem.

O gráfico mostra **soma dos incrementos nos recortes**, não área nacional única: não dissolvemos possíveis sobreposições entre territórios. A máscara acumulada até 2007 é excluída do fluxo anual. O ciclo 2026 está no arquivo de origem, mas permanece fora até conferência específica da edição. Não inferimos a data ou situação jurídica histórica dos limites. Esta edição fica fixada, sem atualização automática: atualizar exige novo snapshot, exame dos recortes e conciliação.

O [INPE](https://terrabrasilis.dpi.inpe.br/faq/) distingue incremento mapeado e taxa estimada. A taxa oficial PRODES não deve ser extrapolada para TIs: nesses recortes, usam-se incrementos. Não dividir o total indígena pela taxa regional para obter participação; numerador e denominador têm métodos distintos. Nuvens, resolução e área mínima de mapeamento limitam a observação. Ausência de linha no arquivo permanece “Sem registro”, sem imputar zero. A comparação não faz ranking de governos ou de integridade dos territórios.

## Integridade não é o complemento do desmatamento

- **Vegetação nativa remanescente:** exige mapa de cobertura, limites fixados e área efetivamente classificada; incluir formações não florestais. Não usar 100% menos a soma de incrementos de 2008 em diante.
- **Fogo, degradação e garimpo:** medir áreas por classe e período, dissolvendo sobreposições. Alertas DETER servem ao monitoramento; não substituir a série anual PRODES.
- **Proteção territorial:** registrar situação fundiária com data, invasões e ações de proteção. Uma terra homologada não é automaticamente ambientalmente íntegra; mais ações registradas não provam mais ou menos invasões.
- **Comparação entre governos:** antes de calcular, fixar o universo territorial, conferir alterações de limites e aplicar somente ciclos completos comparáveis. Uma associação temporal não estima efeito causal da demarcação ou do governo.

Fontes primárias para ampliar: [dados geoespaciais Funai](https://www.gov.br/funai/pt-br/atuacao/terras-indigenas/geoprocessamento-e-mapas), [CMR/Funai](https://cmr.funai.gov.br/) e [Sala de Situação INPE](https://terrabrasilis.dpi.inpe.br/ams/). Essas outras dimensões ainda não foram integradas ao painel; são identificadas como não calculadas, sem números substitutos.
