-- ============================================
-- 📊 QUERIES SQL PARA DASHBOARD METABASE
-- Fraud Detection Pipeline
-- ============================================
-- 
-- Como usar no Metabase:
-- 1. Acesse https://metabase.abnerfonseca.com.br
-- 2. Clique em "New" → "Question" → "Native query"
-- 3. Selecione o banco "fraud_db"
-- 4. Cole a query desejada
-- 5. Salve e adicione ao dashboard
--
-- ============================================

-- ============================================
-- 🎯 KPIs PRINCIPAIS (Cards Grandes)
-- ============================================

-- KPI 1: Total de Transações
SELECT 
    TO_CHAR(COUNT(*), 'FM999,999,999') AS "Total Transações"
FROM batch_transactions;

-- KPI 2: Volume Total (R$)
SELECT 
    'R$ ' || TO_CHAR(SUM(amount), 'FM999,999,999,999.00') AS "Volume Total"
FROM batch_transactions;

-- KPI 3: Total de Fraudes Detectadas
SELECT 
    TO_CHAR(COUNT(*), 'FM999,999') AS "Fraudes Detectadas"
FROM batch_transactions 
WHERE is_fraud = true;

-- KPI 4: Taxa de Fraude (%)
SELECT 
    ROUND(
        (COUNT(CASE WHEN is_fraud THEN 1 END)::numeric / COUNT(*)::numeric) * 100, 
        2
    ) || '%' AS "Taxa de Fraude"
FROM batch_transactions;

-- KPI 5: Valor Protegido (Fraudes Bloqueadas)
SELECT 
    'R$ ' || TO_CHAR(SUM(amount), 'FM999,999,999,999.00') AS "Valor Protegido"
FROM batch_transactions 
WHERE is_fraud = true AND status = 'DECLINED';

-- KPI 6: Alertas Críticos
SELECT 
    TO_CHAR(COUNT(*), 'FM999,999') AS "Alertas Críticos"
FROM batch_fraud_alerts 
WHERE risk_level = 'CRITICAL';


-- ============================================
-- 📈 GRÁFICOS DE LINHA (Tendências)
-- ============================================

-- Gráfico 1: Transações por Mês
SELECT 
    tx_year || '-' || LPAD(tx_month::text, 2, '0') AS "Período",
    COUNT(*) AS "Transações",
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS "Fraudes"
FROM batch_transactions
GROUP BY tx_year, tx_month
ORDER BY tx_year, tx_month;

-- Gráfico 2: Volume Financeiro por Mês
SELECT 
    tx_year || '-' || LPAD(tx_month::text, 2, '0') AS "Período",
    ROUND(SUM(amount)::numeric, 2) AS "Volume Total (R$)",
    ROUND(SUM(CASE WHEN is_fraud THEN amount ELSE 0 END)::numeric, 2) AS "Volume Fraudes (R$)"
FROM batch_transactions
GROUP BY tx_year, tx_month
ORDER BY tx_year, tx_month;

-- Gráfico 3: Taxa de Fraude por Mês (%)
SELECT 
    tx_year || '-' || LPAD(tx_month::text, 2, '0') AS "Período",
    ROUND(
        (SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)::numeric / COUNT(*)::numeric) * 100, 
        2
    ) AS "Taxa de Fraude (%)"
FROM batch_transactions
GROUP BY tx_year, tx_month
ORDER BY tx_year, tx_month;

-- Gráfico 4: Transações por Hora do Dia
SELECT 
    tx_hour AS "Hora",
    COUNT(*) AS "Total Transações",
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS "Fraudes"
FROM batch_transactions
GROUP BY tx_hour
ORDER BY tx_hour;


-- ============================================
-- 🍩 GRÁFICOS DE PIZZA/DONUT
-- ============================================

-- Pizza 1: Distribuição por Nível de Risco
SELECT 
    risk_level AS "Nível de Risco",
    COUNT(*) AS "Quantidade"
FROM batch_transactions
WHERE risk_level IS NOT NULL
GROUP BY risk_level
ORDER BY 
    CASE risk_level 
        WHEN 'CRITICAL' THEN 1 
        WHEN 'HIGH' THEN 2 
        WHEN 'MEDIUM' THEN 3 
        WHEN 'LOW' THEN 4 
    END;

-- Pizza 2: Distribuição por Canal
SELECT 
    channel AS "Canal",
    COUNT(*) AS "Transações"
FROM batch_transactions
GROUP BY channel
ORDER BY COUNT(*) DESC;

-- Pizza 3: Distribuição por Tipo de Transação
SELECT 
    type AS "Tipo",
    COUNT(*) AS "Quantidade"
FROM batch_transactions
GROUP BY type
ORDER BY COUNT(*) DESC;

-- Pizza 4: Status das Transações
SELECT 
    status AS "Status",
    COUNT(*) AS "Quantidade"
FROM batch_transactions
GROUP BY status
ORDER BY COUNT(*) DESC;


-- ============================================
-- 📊 GRÁFICOS DE BARRAS
-- ============================================

-- Barras 1: Top 10 Categorias com Mais Fraudes
SELECT 
    merchant_category AS "Categoria",
    COUNT(*) AS "Total Fraudes",
    ROUND(SUM(amount)::numeric, 2) AS "Valor Total (R$)"
FROM batch_transactions
WHERE is_fraud = true
GROUP BY merchant_category
ORDER BY COUNT(*) DESC
LIMIT 10;

-- Barras 2: Fraudes por Período do Dia
SELECT 
    period_of_day AS "Período",
    COUNT(*) AS "Fraudes",
    ROUND(
        (COUNT(*)::numeric / (SELECT COUNT(*) FROM batch_transactions WHERE is_fraud)::numeric) * 100, 
        1
    ) AS "% do Total"
FROM batch_transactions
WHERE is_fraud = true
GROUP BY period_of_day
ORDER BY 
    CASE period_of_day 
        WHEN 'MADRUGADA' THEN 1 
        WHEN 'MANHÃ' THEN 2 
        WHEN 'TARDE' THEN 3 
        WHEN 'NOITE' THEN 4 
    END;

-- Barras 3: Fraudes por Faixa de Valor
SELECT 
    amount_range AS "Faixa de Valor",
    COUNT(*) AS "Fraudes"
FROM batch_transactions
WHERE is_fraud = true
GROUP BY amount_range
ORDER BY 
    CASE amount_range 
        WHEN 'MICRO' THEN 1 
        WHEN 'PEQUENO' THEN 2 
        WHEN 'MEDIO' THEN 3 
        WHEN 'GRANDE' THEN 4 
        WHEN 'MUITO_GRANDE' THEN 5 
    END;

-- Barras 4: Top 10 Merchants com Fraudes
SELECT 
    merchant_name AS "Merchant",
    COUNT(*) AS "Fraudes",
    ROUND(SUM(amount)::numeric, 2) AS "Valor (R$)"
FROM batch_transactions
WHERE is_fraud = true
GROUP BY merchant_name
ORDER BY COUNT(*) DESC
LIMIT 10;


-- ============================================
-- 📋 TABELAS DETALHADAS
-- ============================================

-- Tabela 1: Últimos Alertas de Fraude
SELECT 
    transaction_id AS "ID Transação",
    timestamp_dt AS "Data/Hora",
    customer_id AS "Cliente",
    type AS "Tipo",
    'R$ ' || TO_CHAR(amount, 'FM999,999.00') AS "Valor",
    merchant_name AS "Merchant",
    risk_level AS "Risco",
    fraud_score AS "Score",
    investigation_status AS "Status Investigação"
FROM batch_fraud_alerts
ORDER BY timestamp_dt DESC
LIMIT 50;

-- Tabela 2: Clientes com Mais Alertas
SELECT 
    customer_id AS "Cliente",
    COUNT(*) AS "Total Alertas",
    SUM(CASE WHEN risk_level = 'CRITICAL' THEN 1 ELSE 0 END) AS "Críticos",
    SUM(CASE WHEN risk_level = 'HIGH' THEN 1 ELSE 0 END) AS "Altos",
    'R$ ' || TO_CHAR(SUM(amount), 'FM999,999.00') AS "Valor Total"
FROM batch_fraud_alerts
GROUP BY customer_id
ORDER BY COUNT(*) DESC
LIMIT 20;

-- Tabela 3: Métricas Mensais Detalhadas
SELECT 
    tx_year || '-' || LPAD(tx_month::text, 2, '0') AS "Período",
    TO_CHAR(total_transactions, 'FM999,999,999') AS "Transações",
    'R$ ' || TO_CHAR(total_volume, 'FM999,999,999.00') AS "Volume",
    TO_CHAR(fraud_count, 'FM999,999') AS "Fraudes",
    ROUND(fraud_rate::numeric, 2) || '%' AS "Taxa Fraude",
    critical_count AS "Críticos",
    high_count AS "Altos"
FROM batch_fraud_metrics
ORDER BY tx_year DESC, tx_month DESC;


-- ============================================
-- 🔥 ANÁLISES AVANÇADAS
-- ============================================

-- Análise 1: Matriz de Risco (Canal x Tipo)
SELECT 
    channel AS "Canal",
    type AS "Tipo",
    COUNT(*) AS "Total",
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS "Fraudes",
    ROUND(
        (SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0)::numeric) * 100, 
        2
    ) AS "Taxa Fraude %"
FROM batch_transactions
GROUP BY channel, type
ORDER BY "Taxa Fraude %" DESC NULLS LAST;

-- Análise 2: Padrão de Fraude por Hora e Dia da Semana
SELECT 
    CASE 
        WHEN is_weekend THEN 'Fim de Semana'
        ELSE 'Dia Útil'
    END AS "Tipo Dia",
    tx_hour AS "Hora",
    COUNT(*) AS "Total",
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS "Fraudes",
    ROUND(
        (SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)::numeric / COUNT(*)::numeric) * 100, 
        2
    ) AS "Taxa Fraude %"
FROM batch_transactions
GROUP BY is_weekend, tx_hour
ORDER BY is_weekend, tx_hour;

-- Análise 3: Efetividade do Score de Fraude
SELECT 
    fraud_score_category AS "Categoria Score",
    COUNT(*) AS "Total",
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS "Fraudes Reais",
    ROUND(
        (SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)::numeric / COUNT(*)::numeric) * 100, 
        2
    ) AS "Precision %"
FROM batch_transactions
WHERE fraud_score_category IS NOT NULL
GROUP BY fraud_score_category
ORDER BY 
    CASE fraud_score_category 
        WHEN 'CRITICAL' THEN 1 
        WHEN 'HIGH' THEN 2 
        WHEN 'MEDIUM' THEN 3 
        WHEN 'LOW' THEN 4 
        WHEN 'NORMAL' THEN 5
    END;

-- Análise 4: Velocidade de Transações Suspeitas
SELECT 
    customer_id AS "Cliente",
    COUNT(*) AS "Transações 24h",
    SUM(amount) AS "Valor Acumulado",
    MAX(distance_from_last_txn_km) AS "Maior Distância (km)",
    MAX(risk_level) AS "Maior Risco"
FROM batch_fraud_alerts
WHERE timestamp_dt >= NOW() - INTERVAL '24 hours'
GROUP BY customer_id
HAVING COUNT(*) > 3
ORDER BY COUNT(*) DESC
LIMIT 20;


-- ============================================
-- 📍 ANÁLISES GEOGRÁFICAS (se houver dados)
-- ============================================

-- Análise por Flag de Localização
SELECT 
    flag_location AS "Flag Localização",
    COUNT(*) AS "Alertas",
    ROUND(AVG(distance_from_last_txn_km)::numeric, 2) AS "Distância Média (km)"
FROM batch_fraud_alerts
WHERE flag_location IS NOT NULL
GROUP BY flag_location
ORDER BY COUNT(*) DESC;


-- ============================================
-- 🎛️ FILTROS ÚTEIS (para dashboards interativos)
-- ============================================

-- Lista de Meses Disponíveis (para filtro)
SELECT DISTINCT 
    tx_year || '-' || LPAD(tx_month::text, 2, '0') AS "Período"
FROM batch_transactions
ORDER BY 1;

-- Lista de Canais (para filtro)
SELECT DISTINCT channel AS "Canal"
FROM batch_transactions
WHERE channel IS NOT NULL
ORDER BY channel;

-- Lista de Tipos (para filtro)
SELECT DISTINCT type AS "Tipo"
FROM batch_transactions
WHERE type IS NOT NULL
ORDER BY type;

-- Lista de Níveis de Risco (para filtro)
SELECT DISTINCT risk_level AS "Nível de Risco"
FROM batch_transactions
WHERE risk_level IS NOT NULL;


-- ============================================
-- 📊 QUERIES COM VARIÁVEIS (Template Metabase)
-- ============================================

-- Query com filtro de data (use {{data_inicio}} e {{data_fim}} no Metabase)
/*
SELECT 
    DATE(timestamp_dt) AS "Data",
    COUNT(*) AS "Transações",
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS "Fraudes"
FROM batch_transactions
WHERE timestamp_dt BETWEEN {{data_inicio}} AND {{data_fim}}
GROUP BY DATE(timestamp_dt)
ORDER BY DATE(timestamp_dt);
*/

-- Query com filtro de canal (use {{canal}} no Metabase)
/*
SELECT 
    type AS "Tipo",
    COUNT(*) AS "Total",
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS "Fraudes"
FROM batch_transactions
WHERE channel = {{canal}}
GROUP BY type
ORDER BY COUNT(*) DESC;
*/


-- ============================================
-- 🚨 ALERTAS EM TEMPO REAL (para streaming)
-- ============================================

-- Se existir tabela de streaming, use queries similares:
/*
-- Últimas transações (tempo real)
SELECT *
FROM streaming_transactions
WHERE timestamp_dt >= NOW() - INTERVAL '5 minutes'
ORDER BY timestamp_dt DESC
LIMIT 100;

-- Fraudes detectadas nos últimos 5 minutos
SELECT 
    COUNT(*) AS "Fraudes 5min",
    SUM(amount) AS "Valor 5min"
FROM streaming_transactions
WHERE is_fraud = true
AND timestamp_dt >= NOW() - INTERVAL '5 minutes';
*/


-- ============================================
-- 📈 MÉTRICAS DE PERFORMANCE DO MODELO
-- ============================================

-- Recall e Precision por Categoria
SELECT 
    risk_level AS "Nível Detectado",
    COUNT(*) AS "Total Alertas",
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS "Fraudes Confirmadas (TP)",
    SUM(CASE WHEN NOT is_fraud THEN 1 ELSE 0 END) AS "Falsos Positivos (FP)",
    ROUND(
        (SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END)::numeric / NULLIF(COUNT(*), 0)::numeric) * 100, 
        2
    ) AS "Precision %"
FROM batch_transactions
WHERE risk_level IN ('CRITICAL', 'HIGH', 'MEDIUM')
GROUP BY risk_level
ORDER BY 
    CASE risk_level 
        WHEN 'CRITICAL' THEN 1 
        WHEN 'HIGH' THEN 2 
        WHEN 'MEDIUM' THEN 3 
    END;

-- Sumário de Performance
SELECT 
    'Total' AS "Métrica",
    (SELECT COUNT(*) FROM batch_transactions WHERE is_fraud) AS "Fraudes Reais",
    (SELECT COUNT(*) FROM batch_transactions WHERE risk_level IN ('CRITICAL', 'HIGH', 'MEDIUM')) AS "Alertas Gerados",
    (SELECT COUNT(*) FROM batch_transactions WHERE is_fraud AND risk_level IN ('CRITICAL', 'HIGH', 'MEDIUM')) AS "True Positives",
    (SELECT COUNT(*) FROM batch_transactions WHERE is_fraud AND risk_level NOT IN ('CRITICAL', 'HIGH', 'MEDIUM')) AS "False Negatives";
