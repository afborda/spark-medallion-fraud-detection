# 📊 Dashboard Real-Time de Detecção de Fraudes

Este documento descreve como configurar o dashboard de streaming no Metabase para visualizar fraudes em tempo real.

## 🚀 Arquitetura do Fluxo Real-Time

```
ShadowTraffic → Kafka → Spark Streaming → PostgreSQL → Metabase Dashboard
     ↓           ↓          ↓               ↓               ↓
 Gera TX     Buffer    Processa +      Métricas      Auto-refresh
 ~10/seg    Real-time   Agrega        Agregadas       cada 30s
```

## 📋 Pré-requisitos

1. **Containers rodando:**
   ```bash
   docker ps | grep -E "(kafka|spark|postgres|metabase|shadow)"
   ```

2. **Streaming job ativo:**
   ```bash
   docker exec -d fraud_spark_master /opt/spark/bin/spark-submit \
     --master 'local[2]' \
     --jars /jars/spark-sql-kafka-0-10_2.12-3.5.3.jar,/jars/kafka-clients-3.5.1.jar,/jars/spark-token-provider-kafka-0-10_2.12-3.5.3.jar,/jars/commons-pool2-2.11.1.jar,/jars/postgresql-42.7.4.jar \
     --conf spark.driver.memory=2g \
     /jobs/streaming/streaming_realtime_dashboard.py
   ```

## 📊 Configurar Dashboard no Metabase

### 1. Acessar Metabase
- URL: http://localhost:3000
- Já deve estar conectado ao PostgreSQL (fraud_db)

### 2. Criar Novo Dashboard
- Clique em **"+ New"** → **"Dashboard"**
- Nome: **"Real-Time Fraud Detection"**

### 3. Adicionar Cards (Queries)

---

#### 📈 Card 1: Métricas Principais (Big Numbers)

**Query SQL:**
```sql
SELECT 
  total_tx as "Transações (5min)",
  total_frauds as "Fraudes Detectadas",
  fraud_rate_pct || '%' as "Taxa de Fraude",
  'R$ ' || total_amount::text as "Volume Total"
FROM v_realtime_summary;
```

**Tipo:** Number ou Trend  
**Auto-refresh:** 30 segundos

---

#### 📊 Card 2: Transações vs Fraudes (Linha do Tempo)

**Query SQL:**
```sql
SELECT 
  window_start as "Horário",
  total_transactions as "Transações",
  fraud_count as "Fraudes"
FROM streaming_metrics
WHERE processed_at > NOW() - INTERVAL '30 minutes'
ORDER BY window_start;
```

**Tipo:** Line Chart  
**X-axis:** Horário  
**Y-axis:** Transações, Fraudes

---

#### 🥧 Card 3: Fraudes por Categoria (Pizza/Donut)

**Query SQL:**
```sql
SELECT 
  category as "Categoria",
  total_frauds as "Fraudes"
FROM v_fraud_by_category
WHERE total_frauds > 0
ORDER BY total_frauds DESC
LIMIT 10;
```

**Tipo:** Pie Chart ou Donut

---

#### 🗺️ Card 4: Fraudes por Estado (Mapa/Barras)

**Query SQL:**
```sql
SELECT 
  state as "Estado",
  total_frauds as "Fraudes",
  total_transactions as "Total TX"
FROM v_fraud_by_state
ORDER BY total_frauds DESC
LIMIT 10;
```

**Tipo:** Bar Chart (horizontal)

---

#### 🚨 Card 5: Últimas Fraudes Detectadas (Tabela)

**Query SQL:**
```sql
SELECT 
  TO_CHAR(detected_at, 'HH24:MI:SS') as "Hora",
  transaction_id as "ID",
  'R$ ' || amount::text as "Valor",
  category as "Categoria",
  purchase_state as "Estado",
  purchase_city as "Cidade",
  payment_method as "Pagamento"
FROM v_latest_frauds
LIMIT 20;
```

**Tipo:** Table  
**Auto-refresh:** 30 segundos

---

#### 📉 Card 6: Taxa de Fraude por Hora

**Query SQL:**
```sql
SELECT 
  EXTRACT(HOUR FROM window_start) || ':00' as "Hora",
  ROUND(AVG(fraud_rate * 100)::numeric, 2) as "Taxa Fraude %"
FROM streaming_metrics
WHERE processed_at > NOW() - INTERVAL '2 hours'
GROUP BY EXTRACT(HOUR FROM window_start)
ORDER BY 1;
```

**Tipo:** Area Chart ou Line

---

#### 💳 Card 7: Fraudes por Método de Pagamento

**Query SQL:**
```sql
SELECT 
  payment_method as "Método",
  COUNT(*) as "Quantidade",
  ROUND(AVG(amount)::numeric, 2) as "Valor Médio"
FROM streaming_recent_frauds
WHERE detected_at > NOW() - INTERVAL '1 hour'
GROUP BY payment_method
ORDER BY 2 DESC;
```

**Tipo:** Bar Chart

---

### 4. Configurar Auto-Refresh

1. No dashboard, clique no ícone **⚙️ (configurações)**
2. Selecione **"Auto-refresh"**
3. Escolha **"30 seconds"** ou **"1 minute"**

### 5. Layout Sugerido

```
┌─────────────────────────────────────────────────────────┐
│  📊 REAL-TIME FRAUD DETECTION DASHBOARD                 │
├─────────────┬─────────────┬─────────────┬──────────────┤
│  TX (5min)  │   Fraudes   │ Taxa Fraude │ Volume Total │
│    1,234    │     28      │    2.3%     │ R$ 650,000   │
├─────────────┴─────────────┴─────────────┴──────────────┤
│         📈 Transações vs Fraudes (30 min)               │
│  [=========== LINE CHART ===========]                   │
├────────────────────────┬────────────────────────────────┤
│   🥧 Fraudes/Categoria │   🗺️ Fraudes por Estado        │
│   [PIE CHART]          │   [BAR CHART]                  │
├────────────────────────┴────────────────────────────────┤
│            🚨 ÚLTIMAS FRAUDES DETECTADAS                │
│  [==================== TABLE ====================]      │
└─────────────────────────────────────────────────────────┘
```

## 🔄 Verificar Dados Chegando

```bash
# Verificar métricas no PostgreSQL
docker exec fraud_postgres psql -U fraud_user -d fraud_db \
  -c "SELECT * FROM v_realtime_summary;"

# Verificar fraudes recentes
docker exec fraud_postgres psql -U fraud_user -d fraud_db \
  -c "SELECT * FROM v_latest_frauds LIMIT 5;"

# Contar registros por tabela
docker exec fraud_postgres psql -U fraud_user -d fraud_db \
  -c "SELECT 'metrics' as tabela, COUNT(*) FROM streaming_metrics
      UNION ALL
      SELECT 'frauds', COUNT(*) FROM streaming_recent_frauds;"
```

## 🛠️ Troubleshooting

### Dados não aparecem no dashboard
1. Verificar se streaming job está rodando:
   ```bash
   docker exec fraud_spark_master ps aux | grep spark-submit
   ```

2. Verificar logs do streaming:
   ```bash
   docker logs fraud_spark_master 2>&1 | tail -50
   ```

3. Verificar se Kafka tem mensagens:
   ```bash
   docker exec fraud_kafka kafka-run-class kafka.tools.GetOffsetShell \
     --broker-list localhost:9092 --topic transactions --time -1
   ```

### Dashboard não atualiza
- Verifique se auto-refresh está habilitado
- Verifique conexão com PostgreSQL no Metabase

## 📝 Tabelas Disponíveis

| Tabela | Descrição |
|--------|-----------|
| `streaming_metrics` | Métricas agregadas por janela de 1 minuto |
| `streaming_metrics_by_category` | Métricas por categoria de transação |
| `streaming_metrics_by_state` | Métricas por estado |
| `streaming_recent_frauds` | Últimas fraudes detectadas |

## 📊 Views Disponíveis

| View | Descrição |
|------|-----------|
| `v_realtime_summary` | Resumo consolidado (últimos 5 min) |
| `v_realtime_dashboard` | Métricas detalhadas (últimos 5 min) |
| `v_fraud_by_category` | Fraudes por categoria (últimos 10 min) |
| `v_fraud_by_state` | Fraudes por estado (últimos 10 min) |
| `v_latest_frauds` | 50 últimas fraudes (últimos 30 min) |
