# 📊 Guia Rápido - Dashboard Metabase

## 🚀 Acesso Rápido
- **URL:** https://metabase.abnerfonseca.com.br
- **Banco:** fraud_db (PostgreSQL)

---

## 📋 Como Criar um Dashboard

### 1. Criar Nova Pergunta (Query)
1. Clique em **"New"** → **"Question"**
2. Selecione **"Native query"**
3. Escolha o banco **"fraud_db"**
4. Cole a query SQL
5. Clique em **"Get Answer"**
6. Salve com nome descritivo

### 2. Adicionar ao Dashboard
1. Clique em **"New"** → **"Dashboard"**
2. Dê um nome (ex: "🔍 Fraud Detection - Overview")
3. Clique em **"+"** para adicionar cards
4. Selecione as perguntas salvas

---

## 🎯 Queries Recomendadas por Tipo de Visualização

### 📈 KPIs (Cards Grandes)

**Total de Transações:**
```sql
SELECT TO_CHAR(COUNT(*), 'FM999,999,999') AS "Total"
FROM batch_transactions;
```

**Taxa de Fraude:**
```sql
SELECT ROUND((COUNT(CASE WHEN is_fraud THEN 1 END)::numeric / COUNT(*)::numeric) * 100, 2) || '%' AS "Taxa de Fraude"
FROM batch_transactions;
```

**Volume Total:**
```sql
SELECT 'R$ ' || TO_CHAR(SUM(amount), 'FM999,999,999.00') AS "Volume"
FROM batch_transactions;
```

---

### 🍩 Gráfico de Pizza

**Distribuição por Risco:**
```sql
SELECT risk_level AS "Risco", COUNT(*) AS "Quantidade"
FROM batch_transactions
WHERE risk_level IS NOT NULL
GROUP BY risk_level;
```

**Por Canal:**
```sql
SELECT channel AS "Canal", COUNT(*) AS "Transações"
FROM batch_transactions
GROUP BY channel
ORDER BY COUNT(*) DESC;
```

---

### 📊 Gráfico de Barras

**Top 10 Categorias com Fraudes:**
```sql
SELECT merchant_category AS "Categoria", COUNT(*) AS "Fraudes"
FROM batch_transactions
WHERE is_fraud = true
GROUP BY merchant_category
ORDER BY COUNT(*) DESC
LIMIT 10;
```

---

### 📈 Gráfico de Linha

**Tendência Mensal:**
```sql
SELECT 
    tx_year || '-' || LPAD(tx_month::text, 2, '0') AS "Período",
    COUNT(*) AS "Transações",
    SUM(CASE WHEN is_fraud THEN 1 ELSE 0 END) AS "Fraudes"
FROM batch_transactions
GROUP BY tx_year, tx_month
ORDER BY tx_year, tx_month;
```

---

### 📋 Tabela

**Últimos Alertas:**
```sql
SELECT 
    timestamp_dt AS "Data",
    customer_id AS "Cliente",
    type AS "Tipo",
    amount AS "Valor",
    risk_level AS "Risco"
FROM batch_fraud_alerts
ORDER BY timestamp_dt DESC
LIMIT 50;
```

---

## 📁 Arquivo Completo de Queries

Todas as queries estão em: `docs/METABASE_QUERIES.sql`

---

## 📊 Dados Disponíveis

| Tabela | Registros | Descrição |
|--------|-----------|-----------|
| `batch_transactions` | 805,305 | Transações processadas |
| `batch_fraud_alerts` | ~40,000+ | Alertas de fraude |
| `batch_fraud_metrics` | ~12 | Métricas mensais |

### Níveis de Risco
| Risco | Quantidade | Valor Total |
|-------|------------|-------------|
| CRITICAL | 27,691 | R$ 168M |
| HIGH | 54,872 | R$ 74M |
| MEDIUM | 158,627 | R$ 66M |
| LOW | 564,115 | R$ 150M |

### Canais
| Canal | Transações | Taxa Fraude |
|-------|------------|-------------|
| MOBILE_APP | 557,857 | 5.05% |
| WEB_BANKING | 160,999 | 5.05% |
| ATM | 41,313 | 4.92% |
| BRANCH | 24,337 | 5.20% |
| WHATSAPP_PAY | 20,799 | 4.90% |

---

## 🎨 Layout Sugerido para Dashboard

```
┌─────────────────────────────────────────────────────────────┐
│                    🔍 FRAUD DETECTION                        │
├──────────┬──────────┬──────────┬──────────┬────────────────┤
│  TOTAL   │  FRAUDES │   TAXA   │  VALOR   │   CRÍTICOS     │
│  805K    │   40.5K  │  5.04%   │  R$460M  │    27.6K       │
├──────────┴──────────┼──────────┴──────────┼────────────────┤
│                     │                     │                │
│   📈 TENDÊNCIA      │   🍩 POR RISCO      │  📊 POR CANAL  │
│   (Linha)           │   (Pizza)           │  (Barras)      │
│                     │                     │                │
├─────────────────────┴─────────────────────┴────────────────┤
│                                                             │
│              📋 ÚLTIMOS ALERTAS DE FRAUDE                   │
│              (Tabela com scroll)                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## ⚡ Dicas

1. **Auto-refresh:** Configure para 1 min em dashboards de streaming
2. **Filtros:** Use variáveis `{{campo}}` para filtros interativos
3. **Cores:** CRITICAL = 🔴, HIGH = 🟠, MEDIUM = 🟡, LOW = 🟢
4. **Cache:** Desabilite para dados em tempo real
