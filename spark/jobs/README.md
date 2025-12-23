# 🎯 Spark Jobs - Índice Principal

## 📋 Visão Geral

Esta pasta contém todos os scripts Spark para o pipeline de **Detecção de Fraude Bancária**.
Os scripts estão organizados por categoria e propósito.

## 📁 Estrutura de Pastas

```
spark/jobs/
├── README.md                 # Este arquivo
├── production/               # 🚀 Scripts de produção (USE ESTES!)
│   ├── medallion_bronze.py
│   ├── medallion_silver.py
│   ├── medallion_gold.py
│   └── README.md
├── streaming/                # 🌊 Scripts de streaming (tempo real)
│   ├── streaming_bronze.py
│   ├── streaming_silver.py
│   ├── streaming_gold.py
│   ├── streaming_to_postgres.py
│   └── README.md
├── utils/                    # 🔧 Scripts utilitários
│   ├── check_flags.py
│   ├── check_gps.py
│   └── README.md
├── experimental/             # 🧪 Scripts experimentais
│   ├── batch_silver_gold.py
│   ├── kafka_to_postgres_batch.py
│   └── README.md
└── legacy/                   # 📦 Scripts antigos (referência)
    ├── bronze_layer.py
    ├── silver_layer.py
    ├── gold_layer.py
    ├── bronze_to_minio.py
    ├── silver_to_minio.py
    ├── gold_to_minio.py
    ├── fraud_detection.py
    ├── load_to_postgres.py
    └── README.md
```

## 🚀 Quick Start

### Executar Pipeline Completo (Produção)

```bash
# 1. Entrar no container
docker exec -it spark-master bash

# 2. Variável com JARs (facilita os comandos)
JARS="/jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar,/jars/postgresql-42.7.4.jar"

# 3. Executar na ordem
spark-submit --master spark://spark-master:7077 --jars $JARS /spark/jobs/production/medallion_bronze.py
spark-submit --master spark://spark-master:7077 --jars $JARS /spark/jobs/production/medallion_silver.py
spark-submit --master spark://spark-master:7077 --jars $JARS /spark/jobs/production/medallion_gold.py
```

## 📊 Qual Pasta Usar?

| Situação | Pasta |
|----------|-------|
| Rodar em produção | `production/` |
| Processar em tempo real | `streaming/` |
| Debug/validar dados | `utils/` |
| Testar nova ideia | `experimental/` |
| Entender código antigo | `legacy/` |

## 🏗️ Arquitetura Medallion

```
                    BRONZE              SILVER              GOLD
                    ┌─────┐            ┌─────┐            ┌─────┐
    Kafka ────────▶ │ Raw │ ────────▶ │Clean│ ────────▶ │Aggr │ ────▶ PostgreSQL
                    │Data │            │+Flag│            │Score│
                    └─────┘            └─────┘            └─────┘
                        │                  │                  │
                        ▼                  ▼                  ▼
                   MinIO bronze/      MinIO silver/      MinIO gold/
```

## 📦 Dependências (JARs)

| JAR | Versão | Propósito |
|-----|--------|-----------|
| `hadoop-aws` | 3.3.4 | Conexão MinIO/S3 |
| `aws-java-sdk-bundle` | 1.12.262 | SDK AWS |
| `postgresql` | 42.7.4 | Driver PostgreSQL |
| `spark-sql-kafka` | 3.5.3 | Conexão Kafka (streaming) |

## 🎯 Scripts por Funcionalidade

### Ingestão de Dados
| Script | Tipo | Input | Output |
|--------|------|-------|--------|
| `production/medallion_bronze.py` | Batch | Kafka | MinIO |
| `streaming/streaming_bronze.py` | Streaming | Kafka | MinIO |

### Transformação + Flags
| Script | Tipo | Input | Output |
|--------|------|-------|--------|
| `production/medallion_silver.py` | Batch | MinIO bronze/ | MinIO silver/ |
| `streaming/streaming_silver.py` | Streaming | MinIO bronze/ | MinIO silver/ |

### Scoring + Analytics
| Script | Tipo | Input | Output |
|--------|------|-------|--------|
| `production/medallion_gold.py` | Batch | MinIO silver/ | MinIO gold/ + PostgreSQL |
| `streaming/streaming_gold.py` | Streaming | MinIO silver/ | MinIO gold/ |

## 📈 Monitoramento

| Serviço | URL | Propósito |
|---------|-----|-----------|
| Spark Master | http://localhost:8080 | Cluster status |
| Spark App | http://localhost:4040 | Job details |
| MinIO | http://localhost:9001 | Storage |
| Kafka UI | http://localhost:8081 | Topics |

## 🔧 Configurações

### MinIO
```python
endpoint = "minio:9000"
access_key = "minioadmin"
secret_key = "minioadmin"
bucket = "lakehouse"
```

### PostgreSQL
```python
host = "postgres"
port = "5432"
database = "fraud_detection"
user = "postgres"
password = "postgres"
```

### Kafka
```python
bootstrap_servers = "kafka:9092"
topics = ["transactions", "customers"]
```

## 📝 Convenções de Código

1. **Nomes de arquivos**: `snake_case.py`
2. **SparkSession**: Sempre configurar MinIO no início
3. **Logging**: Usar `print()` com prefixos `===`
4. **Particionamento**: Por `event_date` quando possível
5. **Formato**: Parquet com compressão snappy

## 🆘 Troubleshooting

### ClassNotFoundException
```bash
# Adicionar JARs ao comando
--jars /jars/hadoop-aws-3.3.4.jar,...
```

### Connection refused (MinIO/Kafka)
```bash
# Verificar se serviços estão rodando
docker compose ps
```

### Out of Memory
```bash
# Aumentar memória do executor
--executor-memory 2g
```

## 📚 Documentação Relacionada

- [docs/INDEX.md](../../docs/INDEX.md) - Índice de documentação
- [docs/GUIA_COMPLETO_ESTUDO.md](../../docs/GUIA_COMPLETO_ESTUDO.md) - Guia completo
- [docs/ARQUITETURA_COMPLETA.md](../../docs/ARQUITETURA_COMPLETA.md) - Arquitetura
- [docs/REFERENCIA_RAPIDA.md](../../docs/REFERENCIA_RAPIDA.md) - Referência rápida
