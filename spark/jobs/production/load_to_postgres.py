"""
📦 LOAD TO POSTGRES - Gold → PostgreSQL
Carrega dados da camada Gold para PostgreSQL para BI/Metabase

🚀 OTIMIZADO: Escrita paralela com repartition + batchsize
   Benchmark: 2.73x mais rápido (22k → 61k reg/s)
"""

import sys
sys.path.insert(0, '/jobs')

import time
from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from config import POSTGRES_URL, POSTGRES_PROPERTIES, GOLD_PATH, apply_s3a_configs

# ============================================
# CONFIGURAÇÕES DE ESCRITA OTIMIZADA
# ============================================
NUM_PARTITIONS_LARGE = 16   # Para tabelas grandes (transactions, alerts)
NUM_PARTITIONS_SMALL = 4    # Para tabelas pequenas (customer_summary, metrics)
BATCH_SIZE = 10000          # Linhas por INSERT batch

# Properties otimizadas para PostgreSQL
WRITE_PROPERTIES = POSTGRES_PROPERTIES.copy()
WRITE_PROPERTIES["batchsize"] = str(BATCH_SIZE)
WRITE_PROPERTIES["rewriteBatchedInserts"] = "true"

print("=" * 60)
print("📦 LOAD TO POSTGRES - Gold → PostgreSQL")
print("🇧🇷 Dados brasileiros")
print("🚀 Modo: ESCRITA PARALELA OTIMIZADA")
print(f"   Partições: {NUM_PARTITIONS_LARGE} (grandes) / {NUM_PARTITIONS_SMALL} (pequenas)")
print(f"   Batch size: {BATCH_SIZE}")
print("=" * 60)

# Configurações S3 são carregadas via variáveis de ambiente (seguro!)
spark = apply_s3a_configs(
    SparkSession.builder.appName("Load_to_Postgres")
).getOrCreate()

spark.sparkContext.setLogLevel("WARN")

GOLD_BASE = f"{GOLD_PATH}"
start_total = time.time()

# ============================================
# 1. CARREGAR TRANSACTIONS (fraud_detection)
# ============================================
print("\n" + "=" * 40)
print("💳 Carregando TRANSACTIONS...")
print(f"   🔀 Partições: {NUM_PARTITIONS_LARGE}")
print("=" * 40)

start_tx = time.time()
df_transactions = spark.read.parquet(f"{GOLD_BASE}/fraud_detection")

# Selecionar campos para PostgreSQL (evitar campos muito grandes)
df_tx_pg = df_transactions.select(
    "transaction_id",
    "customer_id",
    "timestamp_dt",
    "tx_date",
    "tx_year",
    "tx_month",
    "tx_hour",
    "tipo",
    col("valor").alias("amount"),
    "canal",
    "merchant_name",
    "merchant_category",
    "mcc_code",
    "mcc_risk_level",
    "bandeira",
    "entrada_cartao",
    "status",
    "motivo_recusa",
    "fraud_score",
    "fraud_score_category",
    "is_fraud",
    "fraud_type",
    "risk_points",
    "risk_level",
    "requires_review",
    "periodo_dia",
    "faixa_valor",
    "is_weekend",
    "_gold_timestamp"
)

tx_count = df_tx_pg.count()
print(f"✅ {tx_count:,} transações para carregar")

# 🚀 ESCRITA PARALELA OTIMIZADA
df_tx_pg.repartition(NUM_PARTITIONS_LARGE).write \
    .mode("overwrite") \
    .option("truncate", "true") \
    .jdbc(POSTGRES_URL, "transactions", properties=WRITE_PROPERTIES)

elapsed_tx = time.time() - start_tx
throughput_tx = tx_count / elapsed_tx if elapsed_tx > 0 else 0
print(f"💾 Tabela 'transactions' criada em {elapsed_tx:.1f}s ({throughput_tx:,.0f} reg/s)")

# ============================================
# 2. CARREGAR FRAUD_ALERTS
# ============================================
print("\n" + "=" * 40)
print("⚠️ Carregando FRAUD_ALERTS...")
print(f"   🔀 Partições: {NUM_PARTITIONS_LARGE}")
print("=" * 40)

start_alerts = time.time()
df_alerts = spark.read.parquet(f"{GOLD_BASE}/fraud_alerts")

alert_count = df_alerts.count()
print(f"✅ {alert_count:,} alertas para carregar")

# 🚀 ESCRITA PARALELA OTIMIZADA
df_alerts.repartition(NUM_PARTITIONS_LARGE).write \
    .mode("overwrite") \
    .option("truncate", "true") \
    .jdbc(POSTGRES_URL, "fraud_alerts", properties=WRITE_PROPERTIES)

elapsed_alerts = time.time() - start_alerts
throughput_alerts = alert_count / elapsed_alerts if elapsed_alerts > 0 else 0
print(f"💾 Tabela 'fraud_alerts' criada em {elapsed_alerts:.1f}s ({throughput_alerts:,.0f} reg/s)")

# ============================================
# 3. CARREGAR CUSTOMER_SUMMARY
# ============================================
print("\n" + "=" * 40)
print("👤 Carregando CUSTOMER_SUMMARY...")
print(f"   🔀 Partições: {NUM_PARTITIONS_SMALL}")
print("=" * 40)

start_customers = time.time()
df_customers = spark.read.parquet(f"{GOLD_BASE}/customer_summary")

customer_count = df_customers.count()
print(f"✅ {customer_count:,} clientes para carregar")

# 🚀 ESCRITA PARALELA (menos partições para tabela menor)
df_customers.repartition(NUM_PARTITIONS_SMALL).write \
    .mode("overwrite") \
    .option("truncate", "true") \
    .jdbc(POSTGRES_URL, "customer_summary", properties=WRITE_PROPERTIES)

elapsed_customers = time.time() - start_customers
throughput_customers = customer_count / elapsed_customers if elapsed_customers > 0 else 0
print(f"💾 Tabela 'customer_summary' criada em {elapsed_customers:.1f}s ({throughput_customers:,.0f} reg/s)")

# ============================================
# 4. CARREGAR FRAUD_METRICS
# ============================================
print("\n" + "=" * 40)
print("📈 Carregando FRAUD_METRICS...")
print("=" * 40)

start_metrics = time.time()
df_metrics = spark.read.parquet(f"{GOLD_BASE}/fraud_metrics")

metrics_count = df_metrics.count()
print(f"✅ {metrics_count} métricas para carregar")

# Tabela pequena - escrita simples (sem repartition)
df_metrics.write \
    .mode("overwrite") \
    .option("truncate", "true") \
    .jdbc(POSTGRES_URL, "fraud_metrics", properties=WRITE_PROPERTIES)

elapsed_metrics = time.time() - start_metrics
print(f"💾 Tabela 'fraud_metrics' criada em {elapsed_metrics:.1f}s")

# ============================================
# SUMÁRIO FINAL
# ============================================
elapsed_total = time.time() - start_total
total_records = tx_count + alert_count + customer_count + metrics_count
throughput_total = total_records / elapsed_total if elapsed_total > 0 else 0

print("\n" + "=" * 60)
print("✅ LOAD TO POSTGRES CONCLUÍDO!")
print("=" * 60)
print(f"📊 Tabelas criadas no PostgreSQL:")
print(f"   💳 transactions:     {tx_count:>12,} registros ({elapsed_tx:.1f}s)")
print(f"   ⚠️ fraud_alerts:     {alert_count:>12,} registros ({elapsed_alerts:.1f}s)")
print(f"   👤 customer_summary: {customer_count:>12,} registros ({elapsed_customers:.1f}s)")
print(f"   📈 fraud_metrics:    {metrics_count:>12} registros ({elapsed_metrics:.1f}s)")
print("-" * 60)
print(f"📦 TOTAL: {total_records:,} registros em {elapsed_total:.1f}s")
print(f"🚀 Throughput médio: {throughput_total:,.0f} registros/segundo")
print("=" * 60)

spark.stop()
