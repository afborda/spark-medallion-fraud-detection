"""
📦 LOAD TO POSTGRES - Gold → PostgreSQL
Carrega dados da camada Gold para PostgreSQL para BI/Metabase
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from config import POSTGRES_URL, POSTGRES_PROPERTIES, GOLD_PATH, apply_s3a_configs

print("=" * 60)
print("📦 LOAD TO POSTGRES - Gold → PostgreSQL")
print("🇧🇷 Dados brasileiros")
print("=" * 60)

# Configurações S3 são carregadas via variáveis de ambiente (seguro!)
spark = apply_s3a_configs(
    SparkSession.builder.appName("Load_to_Postgres")
).getOrCreate()

spark.sparkContext.setLogLevel("WARN")

GOLD_BASE = f"{GOLD_PATH}"

# ============================================
# 1. CARREGAR TRANSACTIONS (fraud_detection)
# ============================================
print("\n" + "=" * 40)
print("💳 Carregando TRANSACTIONS...")
print("=" * 40)

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

df_tx_pg.write \
    .mode("overwrite") \
    .jdbc(POSTGRES_URL, "transactions", properties=POSTGRES_PROPERTIES)

print(f"💾 Tabela 'transactions' criada no PostgreSQL")

# ============================================
# 2. CARREGAR FRAUD_ALERTS
# ============================================
print("\n" + "=" * 40)
print("⚠️ Carregando FRAUD_ALERTS...")
print("=" * 40)

df_alerts = spark.read.parquet(f"{GOLD_BASE}/fraud_alerts")

alert_count = df_alerts.count()
print(f"✅ {alert_count:,} alertas para carregar")

df_alerts.write \
    .mode("overwrite") \
    .jdbc(POSTGRES_URL, "fraud_alerts", properties=POSTGRES_PROPERTIES)

print(f"💾 Tabela 'fraud_alerts' criada no PostgreSQL")

# ============================================
# 3. CARREGAR CUSTOMER_SUMMARY
# ============================================
print("\n" + "=" * 40)
print("👤 Carregando CUSTOMER_SUMMARY...")
print("=" * 40)

df_customers = spark.read.parquet(f"{GOLD_BASE}/customer_summary")

customer_count = df_customers.count()
print(f"✅ {customer_count:,} clientes para carregar")

df_customers.write \
    .mode("overwrite") \
    .jdbc(POSTGRES_URL, "customer_summary", properties=POSTGRES_PROPERTIES)

print(f"💾 Tabela 'customer_summary' criada no PostgreSQL")

# ============================================
# 4. CARREGAR FRAUD_METRICS
# ============================================
print("\n" + "=" * 40)
print("📈 Carregando FRAUD_METRICS...")
print("=" * 40)

df_metrics = spark.read.parquet(f"{GOLD_BASE}/fraud_metrics")

metrics_count = df_metrics.count()
print(f"✅ {metrics_count} métricas para carregar")

df_metrics.write \
    .mode("overwrite") \
    .jdbc(POSTGRES_URL, "fraud_metrics", properties=POSTGRES_PROPERTIES)

print(f"💾 Tabela 'fraud_metrics' criada no PostgreSQL")

# ============================================
# SUMÁRIO FINAL
# ============================================
print("\n" + "=" * 60)
print("✅ LOAD TO POSTGRES CONCLUÍDO!")
print("=" * 60)
print(f"📊 Tabelas criadas no PostgreSQL:")
print(f"   💳 transactions: {tx_count:,} registros")
print(f"   ⚠️ fraud_alerts: {alert_count:,} registros")
print(f"   👤 customer_summary: {customer_count:,} registros")
print(f"   📈 fraud_metrics: {metrics_count} registros")
print("=" * 60)

spark.stop()
