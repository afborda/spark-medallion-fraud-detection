"""
🥇 GOLD LAYER - Agregações e Detecção de Fraude
Cria tabelas analíticas prontas para consumo

Tabelas geradas:
1. fraud_detection: Transações com análise de risco
2. customer_summary: Perfil consolidado de clientes
3. fraud_alerts: Alertas de fraude para investigação
4. fraud_metrics: Métricas agregadas de fraude
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, lit, count, sum as spark_sum, avg, max as spark_max, min as spark_min,
    current_timestamp, round as spark_round, percent_rank, countDistinct,
    first, last, collect_set, array_contains, size, concat_ws
)
from pyspark.sql.window import Window
from pyspark.sql.types import *

print("=" * 60)
print("🥇 GOLD LAYER - Agregações e Detecção de Fraude")
print("🇧🇷 Dados brasileiros")
print("=" * 60)

spark = SparkSession.builder \
    .appName("Gold_Analytics") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123@@!!_2") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
    .config("spark.sql.adaptive.enabled", "true") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# Diretórios
SILVER_BASE = "s3a://fraud-data/medallion/silver"
GOLD_BASE = "s3a://fraud-data/medallion/gold"

# ============================================
# CARREGAR DADOS SILVER
# ============================================
print("\n📥 Carregando dados Silver...")

df_customers = spark.read.parquet(f"{SILVER_BASE}/customers")
df_devices = spark.read.parquet(f"{SILVER_BASE}/devices")
df_transactions = spark.read.parquet(f"{SILVER_BASE}/transactions")

print(f"   Clientes: {df_customers.count():,}")
print(f"   Dispositivos: {df_devices.count():,}")
print(f"   Transações: {df_transactions.count():,}")

# ============================================
# 1. FRAUD DETECTION TABLE
# ============================================
print("\n" + "=" * 40)
print("🚨 Criando FRAUD_DETECTION...")
print("=" * 40)

# Calcular risco baseado em múltiplos fatores
df_fraud_detection = df_transactions \
    .withColumn("risk_points", lit(0)) \
    .withColumn("risk_points", 
        col("risk_points") +
        when(col("horario_incomum"), 15).otherwise(0) +
        when(col("novo_beneficiario"), 10).otherwise(0) +
        when(col("is_high_risk_mcc"), 20).otherwise(0) +
        when(col("valor") > 5000, 15).otherwise(0) +
        when(col("valor") > 10000, 15).otherwise(0) +  # +15 adicional para valores muito altos
        when(col("tipo") == "PIX", 5).otherwise(0) +
        when(col("autenticacao_3ds") == False, 10).otherwise(0) +
        when(col("cvv_validado") == False, 10).otherwise(0) +
        when(col("periodo_dia") == "MADRUGADA", 10).otherwise(0) +
        when(col("fraud_score") > 70, 20).otherwise(
            when(col("fraud_score") > 50, 10).otherwise(0)
        )
    ) \
    .withColumn("risk_level",
        when(col("risk_points") >= 50, "CRÍTICO")
        .when(col("risk_points") >= 30, "ALTO")
        .when(col("risk_points") >= 15, "MÉDIO")
        .otherwise("BAIXO")
    ) \
    .withColumn("requires_review",
        (col("risk_level").isin(["CRÍTICO", "ALTO"])) | 
        (col("is_fraud") == True)
    )

# Selecionar campos para tabela Gold
df_fraud_gold = df_fraud_detection.select(
    "transaction_id",
    "customer_id",
    "timestamp_dt",
    "tx_date",
    "tx_year",
    "tx_month",
    "tx_hour",
    "tipo",
    "valor",
    "moeda",
    "canal",
    "merchant_name",
    "merchant_category",
    "mcc_code",
    "mcc_risk_level",
    "bandeira",
    "entrada_cartao",
    "chave_pix_tipo",
    "banco_destino",
    "status",
    "motivo_recusa",
    "fraud_score",
    "fraud_score_category",
    "is_fraud",
    "fraud_type",
    "horario_incomum",
    "novo_beneficiario",
    "is_high_risk_mcc",
    "periodo_dia",
    "faixa_valor",
    "is_weekend",
    "risk_points",
    "risk_level",
    "requires_review",
    current_timestamp().alias("_gold_timestamp")
)

fraud_count = df_fraud_gold.count()
print(f"✅ {fraud_count:,} transações analisadas")

# Estatísticas de risco
print("\n📊 Distribuição por nível de risco:")
df_fraud_gold.groupBy("risk_level").count().show()

df_fraud_gold.write \
    .mode("overwrite") \
    .partitionBy("risk_level") \
    .parquet(f"{GOLD_BASE}/fraud_detection")

print(f"💾 Salvo em: {GOLD_BASE}/fraud_detection")

# ============================================
# 2. FRAUD ALERTS TABLE
# ============================================
print("\n" + "=" * 40)
print("⚠️ Criando FRAUD_ALERTS...")
print("=" * 40)

# Apenas transações que requerem investigação
df_alerts = df_fraud_detection \
    .filter(col("requires_review") == True) \
    .select(
        "transaction_id",
        "customer_id",
        "timestamp_dt",
        "tipo",
        "valor",
        "merchant_name",
        "merchant_category",
        "risk_points",
        "risk_level",
        "fraud_score",
        "is_fraud",
        "fraud_type",
        "status",
        when(col("horario_incomum"), "HORARIO_INCOMUM").alias("flag_horario"),
        when(col("novo_beneficiario"), "NOVO_BENEFICIARIO").alias("flag_beneficiario"),
        when(col("is_high_risk_mcc"), "MCC_RISCO").alias("flag_mcc"),
        lit("PENDENTE").alias("investigation_status"),
        lit("").cast("string").alias("analyst_id"),
        lit("").cast("string").alias("investigation_notes"),
        current_timestamp().alias("created_at")
    )

alert_count = df_alerts.count()
print(f"✅ {alert_count:,} alertas gerados")

df_alerts.write \
    .mode("overwrite") \
    .parquet(f"{GOLD_BASE}/fraud_alerts")

print(f"💾 Salvo em: {GOLD_BASE}/fraud_alerts")

# ============================================
# 3. CUSTOMER SUMMARY TABLE
# ============================================
print("\n" + "=" * 40)
print("👤 Criando CUSTOMER_SUMMARY...")
print("=" * 40)

# Agregações por cliente
window_customer = Window.partitionBy("customer_id")

df_customer_summary = df_fraud_detection \
    .groupBy("customer_id") \
    .agg(
        count("*").alias("total_transactions"),
        spark_round(spark_sum("valor"), 2).alias("total_valor"),
        spark_round(avg("valor"), 2).alias("avg_valor"),
        spark_max("valor").alias("max_valor"),
        spark_min("valor").alias("min_valor"),
        countDistinct("merchant_category").alias("unique_categories"),
        countDistinct("banco_destino").alias("unique_banks_pix"),
        spark_sum(when(col("is_fraud"), 1).otherwise(0)).alias("fraud_transactions"),
        spark_sum(when(col("risk_level") == "CRÍTICO", 1).otherwise(0)).alias("critical_risk_count"),
        spark_sum(when(col("risk_level") == "ALTO", 1).otherwise(0)).alias("high_risk_count"),
        spark_sum(when(col("status") == "APROVADA", 1).otherwise(0)).alias("approved_count"),
        spark_sum(when(col("status") == "RECUSADA", 1).otherwise(0)).alias("declined_count"),
        spark_sum(when(col("horario_incomum"), 1).otherwise(0)).alias("unusual_time_count"),
        spark_sum(when(col("novo_beneficiario"), 1).otherwise(0)).alias("new_beneficiary_count"),
        spark_round(avg("fraud_score"), 2).alias("avg_fraud_score"),
        spark_max("fraud_score").alias("max_fraud_score"),
        spark_min("timestamp_dt").alias("first_transaction"),
        spark_max("timestamp_dt").alias("last_transaction"),
    )

# Join com dados do cliente
df_customer_gold = df_customer_summary \
    .join(
        df_customers.select(
            "customer_id", "nome_completo", "cpf_limpo", "estado_upper",
            "cidade_clean", "banco_nome", "renda_mensal", "faixa_renda",
            "score_credito", "faixa_score", "status", "is_premium", "pep"
        ),
        on="customer_id",
        how="left"
    ) \
    .withColumn("fraud_rate", 
        spark_round(col("fraud_transactions") / col("total_transactions") * 100, 2)
    ) \
    .withColumn("customer_risk_level",
        when(col("fraud_rate") > 5, "VERY_HIGH")
        .when(col("fraud_rate") > 2, "HIGH")
        .when((col("critical_risk_count") + col("high_risk_count")) > 5, "MEDIUM")
        .otherwise("LOW")
    ) \
    .withColumn("_gold_timestamp", current_timestamp())

customer_summary_count = df_customer_gold.count()
print(f"✅ {customer_summary_count:,} clientes sumarizados")

df_customer_gold.write \
    .mode("overwrite") \
    .parquet(f"{GOLD_BASE}/customer_summary")

print(f"💾 Salvo em: {GOLD_BASE}/customer_summary")

# ============================================
# 4. FRAUD METRICS TABLE
# ============================================
print("\n" + "=" * 40)
print("📈 Criando FRAUD_METRICS...")
print("=" * 40)

# Métricas agregadas por período
df_metrics = df_fraud_detection \
    .groupBy("tx_year", "tx_month") \
    .agg(
        count("*").alias("total_transactions"),
        spark_round(spark_sum("valor"), 2).alias("total_volume"),
        spark_round(avg("valor"), 2).alias("avg_transaction_value"),
        spark_sum(when(col("is_fraud"), 1).otherwise(0)).alias("fraud_count"),
        spark_sum(when(col("is_fraud"), col("valor")).otherwise(0)).alias("fraud_volume"),
        spark_sum(when(col("risk_level") == "CRÍTICO", 1).otherwise(0)).alias("critical_count"),
        spark_sum(when(col("risk_level") == "ALTO", 1).otherwise(0)).alias("high_count"),
        spark_sum(when(col("risk_level") == "MÉDIO", 1).otherwise(0)).alias("medium_count"),
        spark_sum(when(col("risk_level") == "BAIXO", 1).otherwise(0)).alias("low_count"),
        spark_sum(when(col("status") == "APROVADA", 1).otherwise(0)).alias("approved_count"),
        spark_sum(when(col("status") == "RECUSADA", 1).otherwise(0)).alias("declined_count"),
        spark_sum(when(col("status") == "BLOQUEADA", 1).otherwise(0)).alias("blocked_count"),
        countDistinct("customer_id").alias("unique_customers"),
        spark_round(avg("fraud_score"), 2).alias("avg_fraud_score"),
    ) \
    .withColumn("fraud_rate", 
        spark_round(col("fraud_count") / col("total_transactions") * 100, 4)
    ) \
    .withColumn("approval_rate",
        spark_round(col("approved_count") / col("total_transactions") * 100, 2)
    ) \
    .withColumn("_gold_timestamp", current_timestamp()) \
    .orderBy("tx_year", "tx_month")

metrics_count = df_metrics.count()
print(f"✅ {metrics_count} períodos analisados")

df_metrics.show()

df_metrics.write \
    .mode("overwrite") \
    .parquet(f"{GOLD_BASE}/fraud_metrics")

print(f"💾 Salvo em: {GOLD_BASE}/fraud_metrics")

# ============================================
# SUMÁRIO FINAL
# ============================================
print("\n" + "=" * 60)
print("✅ GOLD LAYER CONCLUÍDA!")
print("=" * 60)
print(f"📊 Tabelas criadas:")
print(f"   🚨 fraud_detection: {fraud_count:,} registros")
print(f"   ⚠️ fraud_alerts: {alert_count:,} registros")
print(f"   👤 customer_summary: {customer_summary_count:,} registros")
print(f"   📈 fraud_metrics: {metrics_count} registros")
print(f"\n💾 Dados salvos em: {GOLD_BASE}/")
print("=" * 60)

spark.stop()
