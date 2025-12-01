# 🧪 Develop - Pipeline para Desenvolvimento

Scripts otimizados para **testes rápidos** com dados locais (JSON).

## 📂 Estrutura

| Arquivo | Descrição |
|---------|-----------|
| `medallion_bronze.py` | Lê de **arquivo JSON** (`/data/raw/transactions.json`) |
| `medallion_silver.py` | Idêntico ao production |
| `medallion_gold.py` | Idêntico ao production |

## 🔄 Diferença do Production

| Aspecto | Production | Develop |
|---------|------------|---------|
| **Fonte Bronze** | Kafka (streaming) | Arquivo JSON (batch) |
| **Velocidade** | ~10k/s (depende do Kafka) | ~100k/s (leitura direta) |
| **Uso** | Pipeline real | Testes e desenvolvimento |

## 🏗️ Arquitetura

```
┌──────────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  JSON File       │ ──▶ │    Bronze    │ ──▶ │    Silver    │ ──▶ │     Gold     │
│ /data/raw/*.json │     │  (MinIO)     │     │ (+ flags)    │     │ (PostgreSQL) │
└──────────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

## 🚀 Como Executar (30M de transações)

```bash
# 1. Bronze (JSON → MinIO) ~5 min
docker exec fraud_spark_master spark-submit \
  --master spark://spark-master:7077 \
  --driver-memory 4g \
  --executor-memory 2g \
  --jars /jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar \
  /jobs/develop/medallion_bronze.py

# 2. Silver (Bronze → Silver com regras de fraude) ~10 min
docker exec fraud_spark_master spark-submit \
  --master spark://spark-master:7077 \
  --driver-memory 4g \
  --executor-memory 2g \
  --jars /jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar \
  /jobs/develop/medallion_silver.py

# 3. Gold (Silver → PostgreSQL) ~5 min
docker exec fraud_spark_master spark-submit \
  --master spark://spark-master:7077 \
  --driver-memory 4g \
  --executor-memory 2g \
  --jars /jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar,/jars/postgresql-42.7.4.jar \
  /jobs/develop/medallion_gold.py
```

## 📊 Dados de Teste

Os dados são gerados pelo script `scripts/generate_fraud_data_fast.py`:

```bash
# Gerar 30M de transações com 5% de fraudes
python3 scripts/generate_fraud_data_fast.py \
  --transactions 30000000 \
  --customers 50000

# Arquivos gerados:
# - data/raw/customers.json (13 MB)
# - data/raw/transactions.json (19 GB)
```

## 🎯 Tipos de Fraude Gerados

| Tipo | % | Descrição |
|------|---|-----------|
| `card_cloning` | 50% | Duas transações em estados distantes em minutos |
| `online_high_value` | 25% | Compras online de madrugada > R$1.500 |
| `installments` | 25% | Compras com 10-12 parcelas em categorias de risco |
