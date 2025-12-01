# 🚀 Production - Scripts de Produção

## 📋 Visão Geral

Esta pasta contém os **scripts principais** da arquitetura Medallion usados em produção.
São os scripts otimizados e testados que processam dados do Kafka até o PostgreSQL.

## 📁 Arquivos

| Arquivo | Descrição | Input | Output |
|---------|-----------|-------|--------|
| `medallion_bronze.py` | Camada Bronze - Ingestão | Kafka | MinIO (bronze/) |
| `medallion_silver.py` | Camada Silver - Limpeza + Flags de Fraude | MinIO (bronze/) | MinIO (silver/) |
| `medallion_gold.py` | Camada Gold - Scoring + Analytics | MinIO (silver/) | MinIO (gold/) + PostgreSQL |

## 🏗️ Arquitetura Medallion

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    Kafka     │ ──▶ │    Bronze    │ ──▶ │    Silver    │ ──▶ │     Gold     │
│ (raw events) │     │  (raw JSON)  │     │ (cleaned +   │     │ (aggregated +│
│              │     │              │     │   flags)     │     │   scores)    │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                            │                    │                    │
                            ▼                    ▼                    ▼
                      MinIO bronze/        MinIO silver/       MinIO gold/
                                                               PostgreSQL
```

## 🎯 Detalhes dos Scripts

### medallion_bronze.py
- **Função**: Lê dados brutos do Kafka e salva no MinIO
- **Formato**: Parquet particionado por data
- **Sem transformações**: Dados puros (single source of truth)

### medallion_silver.py
- **Função**: Limpeza, validação e criação de flags de fraude
- **Regras Implementadas**:
  - Regra 1: Clonagem de Cartão (Window Functions + lag)
  - Regra 7: Categoria Suspeita (electronics, airline_ticket)
  - Regra 9: Compra Online Alto Valor (> R$1.000)
  - Regra 10: Muitas Parcelas (≥10 parcelas + > R$500)
- **Técnicas**: Window Functions, lag(), partitionBy

### medallion_gold.py
- **Função**: Cálculo de score de fraude e carregamento no PostgreSQL
- **Output**: Tabela `fraud_alerts` no PostgreSQL
- **Score**: Soma ponderada das flags (0-100)

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
