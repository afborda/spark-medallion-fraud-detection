# 🌊 Pipeline STREAMING - Tempo Real (Kafka)

> Scripts para processamento em tempo real de dados vindos do Kafka (fraud-generator v4-beta).

## 📋 Visão Geral

Scripts para processamento de streaming usando **Spark Structured Streaming**.
Processam dados em tempo real do Kafka, aplicam transformações e salvam resultados.

**Fonte de Dados:** Kafka topic `transactions` (alimentado pelo **Brazilian Fraud Data Generator v4-beta**)

## ✅ Status: Atualizado para fraud-generator v4-beta

Pipeline de streaming em tempo real **com campos em inglês** (novo schema).

## 🔄 Fluxo do Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                  PIPELINE STREAMING (Tempo Real)                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   fraud-generator v4-beta (10 tx/seg)                               │
│         │                                                           │
│         ▼                                                           │
│   ┌─────────────────┐                                               │
│   │     Kafka       │  Topic: transactions                          │
│   └────────┬────────┘                                               │
│            │                                                        │
│            ├───────────────────────────────┐                        │
│            │                               │                        │
│            ▼                               ▼                        │
│   ┌─────────────────┐             ┌───────────────────────┐         │
│   │streaming_bronze │             │streaming_realtime_    │         │
│   │ Kafka → MinIO   │             │dashboard (PostgreSQL) │         │
│   └────────┬────────┘             └───────────────────────┘         │
│            │                                                        │
│            ▼                                                        │
│   ┌─────────────────┐                                               │
│   │streaming_silver │  Limpeza + Flags de Risco                     │
│   └────────┬────────┘                                               │
│            │                                                        │
│            ▼                                                        │
│   ┌─────────────────┐                                               │
│   │streaming_gold   │  Métricas por tipo, canal, categoria          │
│   └─────────────────┘                                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 📁 Scripts

| Script | Descrição | Entrada | Saída |
|--------|-----------|---------|-------|
| `streaming_bronze.py` | Ingestão streaming | Kafka | `s3a://fraud-data/streaming/bronze/` |
| `streaming_silver.py` | Transformações + flags de risco | Bronze Streaming | `s3a://fraud-data/streaming/silver/` |
| `streaming_gold.py` | Agregações por tipo, canal, categoria | Silver Streaming | `s3a://fraud-data/streaming/gold/` |
| `streaming_to_postgres.py` | Sink direto Kafka→PostgreSQL | Kafka | PostgreSQL (transactions, fraud_alerts) |
| `streaming_realtime_dashboard.py` | Dashboard RT completo | Kafka | PostgreSQL (streaming_metrics) |

## 📊 Schema das Transações (fraud-generator v4-beta)

```python
# Campos principais (English)
- transaction_id: String        # ID único da transação
- customer_id: String           # ID do cliente
- timestamp: String             # ISO format timestamp
- type: String                  # PIX, CREDIT_CARD, DEBIT_CARD, TED, BOLETO
- amount: Double                # Valor em R$
- channel: String               # MOBILE_APP, WEB_BANKING, ATM, BRANCH

# Localização
- geolocation_lat/lon: Double   # Coordenadas GPS
- merchant_name: String         # Nome do estabelecimento
- merchant_category: String     # Categoria (Restaurantes, Varejo, etc)
- mcc_code: String              # Código MCC
- mcc_risk_level: String        # low, medium, high

# Cartão
- card_brand: String            # VISA, MASTERCARD, ELO, HIPERCARD
- card_type: String             # CREDIT, DEBIT
- installments: Integer         # Número de parcelas
- card_entry: String            # CHIP, CONTACTLESS, MANUAL, ONLINE
- cvv_validated: Boolean        # CVV validado
- auth_3ds: Boolean             # Autenticação 3D Secure

# PIX
- pix_key_type: String          # CPF, CNPJ, EMAIL, PHONE, RANDOM
- destination_bank: String      # Código do banco destino

# Indicadores de Risco
- distance_from_last_txn_km: Double    # Distância da última transação
- time_since_last_txn_min: Integer     # Tempo desde última transação
- transactions_last_24h: Integer       # Transações nas últimas 24h
- accumulated_amount_24h: Double       # Valor acumulado 24h
- unusual_time: Boolean                # Horário incomum
- new_beneficiary: Boolean             # Novo beneficiário

# Fraude
- fraud_score: Double           # Score de fraude (0-100)
- is_fraud: Boolean             # Transação fraudulenta
- fraud_type: String            # Tipo de fraude (se aplicável)
- status: String                # APPROVED, DECLINED, PENDING, BLOCKED
```

## 🎯 Regras de Risco (Silver Layer)

| Flag | Condição | Score |
|------|----------|-------|
| `is_pix_new_beneficiary` | PIX + novo beneficiário | +25 |
| `is_high_value` | Valor > R$ 5.000 | +15 |
| `is_high_velocity` | > 10 transações em 24h | +20 |
| `is_high_accumulated` | > R$ 10.000 acumulados em 24h | +15 |
| `is_location_jump` | Distância > 100km da última | +25 |
| `is_manual_card_entry` | Cartão digitado manualmente | +10 |
| `is_no_3ds_online` | Web banking sem 3DS | +15 |
| `unusual_time` | Horário incomum | +10 |
| `mcc_risk_level = high` | MCC de alto risco | +20 |

## 🚦 Níveis de Risco

| Nível | Score Combinado | Ação |
|-------|-----------------|------|
| CRITICAL | ≥ 80 | Bloquear imediatamente |
| HIGH | ≥ 60 | Revisar manualmente |
| MEDIUM | ≥ 40 | Monitorar |
| LOW | ≥ 20 | Aceitar com log |
| NORMAL | < 20 | Aceitar |

## 🚀 Como Executar

```bash
# 1. Iniciar fraud-generator (gera dados no Kafka)
docker compose --profile streaming up -d fraud-generator

# 2. Dashboard em tempo real (recomendado)
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    /jobs/streaming/streaming_realtime_dashboard.py

# 3. Pipeline completo Medallion (Bronze → Silver → Gold)
# Terminal 1: Bronze
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    /jobs/streaming/streaming_bronze.py

# Terminal 2: Silver (após Bronze estar rodando)
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    /jobs/streaming/streaming_silver.py

# Terminal 3: Gold (após Silver estar rodando)
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    /jobs/streaming/streaming_gold.py
```

## 📈 Métricas Geradas (Gold Layer)

1. **fraud_alerts**: Transações HIGH/CRITICAL para revisão
2. **metrics_by_type**: Agregados por PIX, CREDIT_CARD, etc
3. **metrics_by_channel**: Agregados por MOBILE_APP, WEB_BANKING, etc
4. **metrics_by_category**: Agregados por categoria de merchant
5. **metrics_by_card_brand**: Agregados por VISA, MASTERCARD, etc

## 🔧 Configurações de Trigger

| Script | Trigger | Checkpoint |
|--------|---------|------------|
| Bronze | 10 segundos | streaming/checkpoints/bronze |
| Silver | 15 segundos | streaming/checkpoints/silver |
| Gold | 30 segundos | streaming/checkpoints/gold_* |
| Dashboard | 30 segundos | /tmp/streaming_dashboard_checkpoint |

## 📝 Notas

- Os scripts usam `startingOffsets: latest` para não reprocessar dados antigos
- `failOnDataLoss: false` permite continuar mesmo se mensagens forem perdidas
- Checkpoints garantem exatamente uma vez (exactly-once) semântica
- O fraud-generator v4-beta gera dados com campos em **inglês** (atualizado em Dez/2025)
