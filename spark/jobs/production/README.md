# 📦 Pipeline BATCH - Dados Brasileiros

> Scripts para processamento em lote de dados brasileiros gerados localmente.

## 📋 Visão Geral

Este diretório contém os jobs Spark para processamento **BATCH** (em lote) dos dados brasileiros.

**Fonte de Dados:** Arquivos JSON gerados pelo script `scripts/generate_brazilian_data.py`

## 🔄 Fluxo do Pipeline

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PIPELINE BATCH (Dados 🇧🇷)                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   /data/raw/*.json                                                  │
│         │                                                           │
│         ▼                                                           │
│   ┌─────────────────┐                                               │
│   │ bronze_brazilian│  Ingestão: JSON → Parquet (MinIO)            │
│   └────────┬────────┘                                               │
│            │                                                        │
│            ▼                                                        │
│   ┌─────────────────┐                                               │
│   │ silver_brazilian│  Limpeza: Tipos, Duplicatas, Derivados       │
│   └────────┬────────┘                                               │
│            │                                                        │
│            ▼                                                        │
│   ┌─────────────────┐                                               │
│   │ gold_brazilian  │  Agregações: Fraud Score, Métricas           │
│   └────────┬────────┘                                               │
│            │                                                        │
│            ▼                                                        │
│   ┌─────────────────┐                                               │
│   │ load_to_postgres│  Exportação: Parquet → PostgreSQL            │
│   └─────────────────┘                                               │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 📁 Scripts Principais (USAR ESTES)

| Script | Descrição | Entrada | Saída |
|--------|-----------|---------|-------|
| `bronze_brazilian.py` | Ingestão de JSON bruto | `/data/raw/*.json` | `s3a://fraud-data/medallion/bronze/` |
| `silver_brazilian.py` | Limpeza e transformação | Bronze (Parquet) | `s3a://fraud-data/medallion/silver/` |
| `gold_brazilian.py` | Agregações e Fraud Score | Silver (Parquet) | `s3a://fraud-data/medallion/gold/` |
| `load_to_postgres.py` | Carga para PostgreSQL | Gold (Parquet) | PostgreSQL (Metabase) |

## 🚀 Como Executar

```bash
# 1. Bronze Layer
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    /jobs/production/bronze_brazilian.py

# 2. Silver Layer
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    /jobs/production/silver_brazilian.py

# 3. Gold Layer
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    /jobs/production/gold_brazilian.py

# 4. Load to PostgreSQL
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    /jobs/production/load_to_postgres.py
```

## ⚠️ Scripts Legados (DEPRECADOS)

Os scripts `medallion_*.py` são versões antigas que foram usadas para testes com dados do Kafka.
**Use os scripts `*_brazilian.py`** para o pipeline batch de produção.

## 🖥️ Como Executar

### No Cluster Spark (Produção)

```bash
# Entrar no container spark-master
docker exec -it spark-master bash

# Bronze Layer
spark-submit \
  --master spark://spark-master:7077 \
  --jars /jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar,/jars/postgresql-42.7.4.jar \
  /spark/jobs/production/medallion_bronze.py

# Silver Layer
spark-submit \
  --master spark://spark-master:7077 \
  --jars /jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar,/jars/postgresql-42.7.4.jar \
  /spark/jobs/production/medallion_silver.py

# Gold Layer
spark-submit \
  --master spark://spark-master:7077 \
  --jars /jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar,/jars/postgresql-42.7.4.jar \
  /spark/jobs/production/medallion_gold.py
```

### Execução Local (Desenvolvimento)

```bash
# Com Spark instalado localmente
spark-submit \
  --master local[*] \
  --jars /path/to/hadoop-aws-3.3.4.jar,/path/to/aws-java-sdk-bundle-1.12.262.jar,/path/to/postgresql-42.7.4.jar \
  medallion_silver.py
```

## ⚙️ Configurações Necessárias

### JARs Obrigatórios
- `hadoop-aws-3.3.4.jar` - Conexão com MinIO/S3
- `aws-java-sdk-bundle-1.12.262.jar` - SDK AWS para S3
- `postgresql-42.7.4.jar` - Driver PostgreSQL

### Variáveis de Ambiente
Os scripts usam valores hardcoded, mas podem ser externalizados:
- MinIO: `minio:9000`, `minioadmin:minioadmin`
- PostgreSQL: `postgres:5432`, `postgres:postgres`

## 📊 Ordem de Execução

**IMPORTANTE**: Sempre execute na ordem correta!

```
1. medallion_bronze.py  (Kafka → MinIO bronze/)
2. medallion_silver.py  (MinIO bronze/ → MinIO silver/)
3. medallion_gold.py    (MinIO silver/ → MinIO gold/ + PostgreSQL)
```

## 🔍 Monitoramento

- **Spark UI**: http://localhost:8080
- **MinIO Console**: http://localhost:9001
- **PostgreSQL**: porta 5432

## 📝 Notas de Desenvolvimento

- Cada script é idempotente (pode ser re-executado)
- Dados são particionados por `event_date` para otimização
- Silver usa Parquet com compressão snappy
- Gold cria 3 níveis de risco: Alto, Médio, Baixo
