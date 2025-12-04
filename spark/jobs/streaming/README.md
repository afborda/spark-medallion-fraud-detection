# 🌊 Pipeline STREAMING - Tempo Real (Kafka)

> Scripts para processamento em tempo real de dados vindos do Kafka/ShadowTraffic.

## 📋 Visão Geral

Scripts para processamento de streaming usando **Spark Structured Streaming**.
Processam dados em tempo real do Kafka, aplicam transformações e salvam resultados.

**Fonte de Dados:** Kafka topic `transactions` (alimentado pelo ShadowTraffic)

## ✅ Status: Implementado e Funcionando

Pipeline de streaming em tempo real **operacional em produção**!

## 🔄 Fluxo do Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                  PIPELINE STREAMING (Tempo Real)                    │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ShadowTraffic (10 tx/seg)                                         │
│         │                                                           │
│         ▼                                                           │
│   ┌─────────────────┐                                               │
│   │     Kafka       │  Topic: transactions                          │
│   └────────┬────────┘                                               │
│            │                                                        │
│            ▼                                                        │
│   ┌─────────────────┐                                               │
│   │streaming_bronze │  Kafka → Parquet (MinIO streaming/bronze)     │
│   └────────┬────────┘                                               │
│            │                                                        │
│            ▼                                                        │
│   ┌─────────────────┐                                               │
│   │streaming_silver │  Limpeza + Flags de Fraude                    │
│   └────────┬────────┘                                               │
│            │                                                        │
│            ▼                                                        │
│   ┌─────────────────┐                                               │
│   │streaming_gold   │  Métricas Agregadas                           │
│   └────────┬────────┘                                               │
│            │                                                        │
│            ▼                                                        │
│   ┌─────────────────────────────┐                                   │
│   │streaming_realtime_dashboard │  → PostgreSQL (Metabase RT)       │
│   └─────────────────────────────┘                                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 📁 Scripts

| Script | Descrição | Entrada | Saída |
|--------|-----------|---------|-------|
| `streaming_bronze.py` | Ingestão streaming | Kafka | `s3a://fraud-data/streaming/bronze/` |
| `streaming_silver.py` | Transformações streaming | Bronze Streaming | `s3a://fraud-data/streaming/silver/` |
| `streaming_gold.py` | Agregações streaming | Silver Streaming | `s3a://fraud-data/streaming/gold/` |
| `streaming_to_postgres.py` | Sink direto Kafka→PG | Kafka | PostgreSQL |
| `streaming_realtime_dashboard.py` | Dashboard RT completo | Kafka | PostgreSQL (métricas) |

## 🔄 Diferença: Batch vs Streaming

| Aspecto | Batch (`production/`) | Streaming (`streaming/`) |
|---------|---------------------|------------------------|
| **Fonte** | JSON local (🇧🇷) | Kafka (ShadowTraffic) |
| **Latência** | Minutos | Segundos |
| **Volume** | 51M transações | ~10 tx/segundo |
| **Uso** | Análise histórica | Dashboard tempo real |

## 🚀 Como Executar

```bash
# Iniciar ShadowTraffic (gera dados no Kafka)
docker compose --profile streaming up -d

# Rodar pipeline streaming
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    /jobs/streaming/streaming_realtime_dashboard.py
```
- readStream do MinIO (bronze)
- Transformações stateless
- Watermarking para late data
- writeStream para MinIO (silver)
```

### streaming_gold.py
```python
# Conceitos-chave:
- Agregações com estado (stateful)
- Window functions em streaming
- Output modes: append, complete, update
- writeStream para MinIO (gold)
```

### streaming_to_postgres.py
```python
# Conceitos-chave:
- foreachBatch para sink customizado
- JDBC write em micro-batches
- Upsert/Merge logic
- Error handling
```

## 🖥️ Como Executar

### No Cluster Spark

```bash
docker exec -it spark-master bash

# Streaming Bronze (roda continuamente)
spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3 \
  --jars /jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar \
  /spark/jobs/streaming/streaming_bronze.py

# Streaming Silver
spark-submit \
  --master spark://spark-master:7077 \
  --jars /jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar \
  /spark/jobs/streaming/streaming_silver.py

# Streaming Gold
spark-submit \
  --master spark://spark-master:7077 \
  --jars /jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar,/jars/postgresql-42.7.4.jar \
  /spark/jobs/streaming/streaming_gold.py
```

### Execução Local

```bash
spark-submit \
  --master local[*] \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3 \
  streaming_bronze.py
```

## ⚙️ Configurações Importantes

### Kafka
```python
kafka_bootstrap_servers = "kafka:9092"
topic = "transactions"
```

### Checkpointing
```python
# OBRIGATÓRIO para streaming
checkpoint_location = "s3a://lakehouse/checkpoints/streaming_bronze"
```

### Triggers
```python
# Micro-batch a cada 10 segundos
.trigger(processingTime='10 seconds')

# Continuous (baixa latência)
.trigger(continuous='1 second')

# Uma vez só (para testes)
.trigger(once=True)
```

## 📊 Monitoramento

- **Spark UI**: http://localhost:4040 (durante execução)
- **Streaming Tab**: Mostra throughput, latência, batches
- **Kafka Consumer Groups**: `kafka-consumer-groups.sh --describe`

## 🐛 Troubleshooting

### Streaming para de processar
```bash
# Verificar se Kafka está rodando
docker logs kafka

# Verificar checkpoints
aws s3 ls s3://lakehouse/checkpoints/ --recursive
```

### Late data não aparece
- Ajustar watermark: `.withWatermark("event_time", "1 hour")`

### Out of Memory
- Reduzir `maxOffsetsPerTrigger`
- Aumentar intervalo de trigger

## 🎓 Conceitos para Estudar

1. **Structured Streaming** - API unificada batch/streaming
2. **Checkpointing** - Fault tolerance e exactly-once
3. **Watermarking** - Lidar com dados atrasados
4. **Output Modes** - append, complete, update
5. **Stateful Operations** - Agregações com estado
6. **Triggers** - Controle de micro-batches

## ✅ Implementações Concluídas

- [x] Implementar regras de fraude em streaming
- [x] Adicionar alertas em tempo real (PostgreSQL → Metabase)
- [x] Dashboard com métricas de streaming (auto-refresh 1 min)
- [x] Pipeline completo: ShadowTraffic → Kafka → Spark → PostgreSQL → Metabase

## 📝 Próximos Passos (Futuro)

- [ ] Integração com sistema de notificações (SMS/Email)
- [ ] Alertas push para dispositivos móveis
