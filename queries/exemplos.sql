-- Consultas de exemplo para data/painel.sqlite
-- Abra com:  sqlite3 data/painel.sqlite   (ou DBeaver, DB Browser for SQLite, DuckDB)

-- 1. Tabelas disponíveis
SELECT name FROM sqlite_master WHERE type = 'table';

-- 2. O comparativo do site, em formato longo
SELECT r.indicador, g.nome AS governo, r.metrica, ROUND(r.valor, 2) AS valor, r.parcial
FROM resumo r
JOIN governo g ON g.id = r.governo
ORDER BY r.indicador, g.inicio;

-- 3. O mesmo comparativo pivotado: uma linha por governo
SELECT g.nome AS governo,
       ROUND(MAX(CASE WHEN r.indicador = 'pib_crescimento' THEN r.valor END), 1) AS pib_medio,
       ROUND(MAX(CASE WHEN r.indicador = 'ipca'            THEN r.valor END), 1) AS inflacao_media,
       ROUND(MAX(CASE WHEN r.indicador = 'salario_minimo'  THEN r.valor END), 1) AS ganho_real_sm,
       ROUND(MAX(CASE WHEN r.indicador = 'queimadas'       THEN r.valor END), 0) AS focos_ano
FROM governo g
LEFT JOIN resumo r ON r.governo = g.id
GROUP BY g.id
ORDER BY g.inicio;

-- 4. Ano com maior inflação dentro de cada governo (window function)
WITH ranqueado AS (
  SELECT governo, periodo AS ano, valor,
         ROW_NUMBER() OVER (PARTITION BY governo ORDER BY valor DESC) AS pos
  FROM serie
  WHERE indicador = 'ipca'
)
SELECT g.nome, r.ano, ROUND(r.valor, 2) AS ipca_no_ano
FROM ranqueado r JOIN governo g ON g.id = r.governo
WHERE r.pos = 1
ORDER BY g.inicio;

-- 5. Variação do salário mínimo real mês a mês (LAG)
SELECT periodo, governo, ROUND(valor, 2) AS sm_real,
       ROUND(100.0 * (valor / LAG(valor) OVER (ORDER BY periodo) - 1), 2) AS var_pct
FROM serie
WHERE indicador = 'salario_minimo'
ORDER BY periodo DESC
LIMIT 24;

-- 6. Média móvel de 12 meses do dólar
SELECT periodo,
       ROUND(AVG(valor) OVER (ORDER BY periodo ROWS BETWEEN 11 PRECEDING AND CURRENT ROW), 3) AS dolar_mm12
FROM serie
WHERE indicador = 'dolar'
ORDER BY periodo;
