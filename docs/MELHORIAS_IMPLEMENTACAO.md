# 🚀 Melhorias do Pipeline de Detecção de Fraudes

> **Data:** 06 de Dezembro de 2025  
> **Score Atual do Pipeline:** 8.1/10  
> **Status:** Produção com melhorias pendentes

---

## 📊 Resumo Executivo

O pipeline de detecção de fraudes está operacional com arquitetura Medallion (Bronze → Silver → Gold) e streaming em tempo real via Kafka. Esta documentação apresenta as melhorias identificadas, priorizadas por impacto e urgência.

### Métricas Atuais
| Métrica | Valor |
|---------|-------|
| Taxa de Streaming | 572 tx/min (~9.5 tx/s) |
| Transações Processadas | 27.917+ |
| Alertas de Fraude | 531 |
| Workers Spark | 5 × 2 cores × 3GB |
| Dados Batch Gerados | ~660MB (40 arquivos Parquet) |

---

## 🔴 CRÍTICO - Implementar Imediatamente

### 1. Checkpoint do Streaming em Local Persistente

**Problema:** O checkpoint está em `/tmp/streaming_postgres_checkpoint`, que é perdido ao reiniciar o container, causando reprocessamento ou perda de dados.

**Arquivo:** `spark/jobs/streaming_to_postgres.py`

**Solução:**
```python
# ANTES (instável)
checkpoint_location = "/tmp/streaming_postgres_checkpoint"

# DEPOIS (persistente)
checkpoint_location = "s3a://fraud-data/streaming/checkpoints/postgres"
```

**Impacto:** 
- ✅ Streaming sobrevive a reinicializações
- ✅ Garantia exactly-once semântica
- ✅ Recuperação automática após falhas

**Comando para aplicar:**
```bash
# Editar o arquivo
sed -i 's|/tmp/streaming_postgres_checkpoint|s3a://fraud-data/streaming/checkpoints/postgres|g' spark/jobs/streaming_to_postgres.py
```

---

### 2. Corrigir Nomes dos Scripts no Airflow DAG

**Problema:** O DAG `medallion_pipeline.py` referencia scripts com nomes incorretos.

**Arquivo:** `airflow/dags/medallion_pipeline.py`

**Mapeamento de Correções:**
| Referência Atual | Nome Correto |
|------------------|--------------|
| `bronze_brazilian.py` | `batch_bronze_from_raw.py` |
| `silver_brazilian.py` | `batch_silver_from_bronze.py` |
| `gold_brazilian.py` | `batch_gold_from_silver.py` |

**Impacto:**
- ✅ DAG executa corretamente
- ✅ Automação do pipeline batch funcional

---

## 🟡 IMPORTANTE - Implementar Esta Semana

### 3. Adicionar Monitoramento de Lag do Kafka

**Problema:** Não há visibilidade do lag entre produção e consumo de mensagens.

**Solução:** Adicionar endpoint de métricas ou integração com Prometheus.

**Implementação sugerida em `spark/jobs/streaming_to_postgres.py`:**
```python
def log_batch_metrics(batch_df, batch_id):
    """Log métricas de cada micro-batch"""
    count = batch_df.count()
    print(f"[METRICS] Batch {batch_id}: {count} registros processados")
    print(f"[METRICS] Timestamp: {datetime.now().isoformat()}")
    
    # Adicionar ao PostgreSQL para histórico
    metrics_df = spark.createDataFrame([{
        "batch_id": batch_id,
        "record_count": count,
        "processed_at": datetime.now()
    }])
    metrics_df.write.jdbc(url, "streaming_metrics", mode="append", properties=props)
```

---

### 4. Health Check para Containers Spark

**Problema:** Workers Spark sem health check podem ficar em estado "unhealthy" sem reiniciar.

**Arquivo:** `docker-compose.yml`

**Adicionar aos workers:**
```yaml
spark-worker-1:
  healthcheck:
    test: ["CMD", "curl", "-f", "http://localhost:8081"]
    interval: 30s
    timeout: 10s
    retries: 3
    start_period: 60s
  restart: unless-stopped
```

---

### 5. Otimizar Particionamento do Batch Pipeline

**Problema:** Escrita no PostgreSQL pode ser lenta sem particionamento adequado.

**Arquivo:** `spark/jobs/batch_postgres_from_gold.py`

**Otimização:**
```python
# Adicionar repartição antes de escrever
df_optimized = df.repartition(10)  # Baseado em 10 cores disponíveis

df_optimized.write \
    .format("jdbc") \
    .option("url", jdbc_url) \
    .option("dbtable", "gold_transactions") \
    .option("batchsize", "10000") \
    .option("numPartitions", "10") \
    .mode("append") \
    .save()
```

---

## 🟢 RECOMENDADO - Melhorias de Longo Prazo

### 6. Implementar Dead Letter Queue (DLQ)

**Objetivo:** Capturar mensagens que falham no processamento para reprocessamento posterior.

**Arquitetura:**
```
Kafka (transactions) 
    ↓
Spark Streaming
    ↓ (erro)
    → Kafka (transactions-dlq)
    → PostgreSQL (dlq_errors table)
```

**Código sugerido:**
```python
def process_with_dlq(batch_df, batch_id):
    try:
        # Processamento normal
        process_batch(batch_df, batch_id)
    except Exception as e:
        # Enviar para DLQ
        error_df = batch_df.withColumn("error_message", lit(str(e)))
        error_df.write.jdbc(url, "dlq_errors", mode="append", properties=props)
```

---

### 7. Adicionar Testes Automatizados

**Estrutura sugerida:**
```
tests/
├── unit/
│   ├── test_fraud_rules.py
│   ├── test_transformations.py
│   └── test_schema_validation.py
├── integration/
│   ├── test_bronze_pipeline.py
│   ├── test_silver_pipeline.py
│   └── test_gold_pipeline.py
└── e2e/
    └── test_full_pipeline.py
```

**Framework:** pytest + pyspark.testing

---

### 8. Implementar Data Quality Checks

**Biblioteca:** Great Expectations ou Deequ

**Checks sugeridos:**
```python
from great_expectations.dataset import SparkDFDataset

def validate_bronze_data(df):
    ge_df = SparkDFDataset(df)
    
    # Validações
    assert ge_df.expect_column_to_exist("transaction_id").success
    assert ge_df.expect_column_values_to_not_be_null("amount").success
    assert ge_df.expect_column_values_to_be_between("amount", 0, 1000000).success
    assert ge_df.expect_column_values_to_match_regex(
        "transaction_id", 
        r"^[a-f0-9-]{36}$"
    ).success
```

---

### 9. Dashboard de Métricas em Tempo Real

**Stack sugerido:** Grafana + Prometheus

**Métricas a monitorar:**
- Taxa de ingestão (tx/segundo)
- Latência end-to-end
- Taxa de fraudes detectadas
- Uso de recursos (CPU, memória)
- Lag do Kafka
- Erros por tipo

**Docker Compose adicional:**
```yaml
prometheus:
  image: prom/prometheus:latest
  volumes:
    - ./prometheus.yml:/etc/prometheus/prometheus.yml
  ports:
    - "9090:9090"

grafana:
  image: grafana/grafana:latest
  ports:
    - "3001:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
```

---

### 10. Backup Automatizado

**Objetivo:** Backup diário do PostgreSQL e checkpoints.

**Script sugerido (`scripts/backup.sh`):**
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="s3a://fraud-data/backups/${DATE}"

# Backup PostgreSQL
docker exec fraud_postgres pg_dump -U fraud_user fraud_db | \
  gzip > /tmp/postgres_backup_${DATE}.sql.gz

# Upload para MinIO
mc cp /tmp/postgres_backup_${DATE}.sql.gz minio/${BACKUP_DIR}/

# Limpar backups antigos (manter últimos 7 dias)
mc rm --recursive --older-than 7d minio/fraud-data/backups/
```

---

## 📋 Plano de Implementação

### Semana 1 (Urgente)
| Tarefa | Esforço | Impacto |
|--------|---------|---------|
| Fix checkpoint streaming | 30 min | Alto |
| Fix nomes scripts Airflow | 15 min | Alto |
| Adicionar health checks | 1 hora | Médio |

### Semana 2 (Importante)
| Tarefa | Esforço | Impacto |
|--------|---------|---------|
| Monitoramento Kafka lag | 2 horas | Alto |
| Otimizar particionamento | 1 hora | Médio |
| Implementar DLQ básico | 3 horas | Alto |

### Semana 3-4 (Melhorias)
| Tarefa | Esforço | Impacto |
|--------|---------|---------|
| Testes automatizados | 8 horas | Alto |
| Data quality checks | 4 horas | Médio |
| Dashboard Grafana | 6 horas | Alto |

---

## 🔧 Comandos Úteis

### Verificar Status do Pipeline
```bash
# Status do streaming
docker exec fraud_postgres psql -U fraud_user -d fraud_db -c \
  "SELECT COUNT(*) as total, MAX(timestamp) as ultimo FROM transactions;"

# Taxa de ingestão (executar 2x com 1 min intervalo)
docker exec fraud_postgres psql -U fraud_user -d fraud_db -c \
  "SELECT COUNT(*) FROM transactions;"

# Alertas de fraude
docker exec fraud_postgres psql -U fraud_user -d fraud_db -c \
  "SELECT risk_level, COUNT(*) FROM fraud_alerts GROUP BY risk_level;"

# Logs do streaming
docker logs -f --tail 100 spark-master 2>&1 | grep -i "streaming\|batch\|error"
```

### Reiniciar Streaming com Novo Checkpoint
```bash
# Parar streaming atual
docker exec spark-master pkill -f streaming_to_postgres

# Limpar checkpoint antigo
docker exec minio-client mc rm --recursive minio/fraud-data/streaming/checkpoints/

# Reiniciar
docker exec -d spark-master spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3 \
  /opt/spark-apps/streaming_to_postgres.py
```

---

## 📈 Métricas de Sucesso

Após implementar as melhorias, esperamos:

| Métrica | Atual | Meta |
|---------|-------|------|
| Uptime Streaming | ~95% | 99.9% |
| Tempo de Recuperação | Manual | < 1 min (auto) |
| Cobertura de Testes | 0% | 80% |
| Visibilidade de Métricas | Básica | Completa |
| Alertas Proativos | Não | Sim |

---

## 📚 Referências

- [Spark Structured Streaming](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html)
- [Kafka Best Practices](https://kafka.apache.org/documentation/#design)
- [Great Expectations](https://greatexpectations.io/expectations)
- [Prometheus + Grafana](https://prometheus.io/docs/visualization/grafana/)

---

> **Autor:** Pipeline Analysis Agent  
> **Última Atualização:** 06/12/2025  
> **Próxima Revisão:** 13/12/2025
