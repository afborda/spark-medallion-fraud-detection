"""
🥇 GOLD LAYER - Agregações e Detecção de Fraude
Cria tabelas analíticas prontas para consumo

Tabelas geradas:
1. fraud_detection: Transações com análise de risco
2. customer_summary: Perfil consolidado de clientes
3. fraud_alerts: Alertas de fraude para investigação
4. fraud_metrics: Métricas agregadas de fraude
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, lit, count, sum as spark_sum, avg, max as spark_max, min as spark_min,
    current_timestamp, round as spark_round, percent_rank, countDistinct,
    first, last, collect_set, array_contains, size, concat_ws,
    datediff, months_between, floor, current_date, year
)
from pyspark.sql.window import Window
from pyspark.sql.types import *
from config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, SILVER_PATH, GOLD_PATH

print("=" * 60)
print("🥇 GOLD LAYER - Agregações e Detecção de Fraude")
print("🇧🇷 Dados brasileiros")
print("=" * 60)

spark = SparkSession.builder \
    .appName("Gold_Analytics") \
    .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
    .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
    .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
    .config("spark.sql.adaptive.enabled", "true") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# Diretórios
SILVER_BASE = SILVER_PATH
GOLD_BASE = GOLD_PATH

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

# ============================================
# 🎓 LIÇÃO: ENRIQUECER TRANSAÇÕES COM JOINs
# ============================================
# Para detectar fraudes avançadas, precisamos combinar dados de:
# - transactions: dados da compra
# - devices: informações do dispositivo usado
# - customers: perfil do cliente (idade, renda, etc.)

print("📊 Enriquecendo transações com dados de devices e customers...")

# JOIN 1: Transações + Devices (para Account Takeover)
# Selecionamos apenas os campos necessários do devices para evitar conflito de nomes
df_devices_join = df_devices.select(
    col("device_id"),
    col("is_trusted").alias("device_is_trusted"),
    col("is_rooted").alias("device_is_rooted"),
    col("is_emulator").alias("device_is_emulator"),
    col("risk_score").alias("device_risk_score"),
    col("device_risk_category")
)

df_enriched = df_transactions.join(
    df_devices_join,
    on="device_id",
    how="left"  # LEFT JOIN: mantém transações mesmo sem device
)

# JOIN 2: + Customers (para Idade Incompatível)
df_customers_join = df_customers.select(
    col("customer_id"),
    col("data_nascimento_dt"),
    col("renda_mensal").alias("customer_renda_mensal"),
    col("faixa_renda").alias("customer_faixa_renda"),
    col("is_premium").alias("customer_is_premium")
)

df_enriched = df_enriched.join(
    df_customers_join,
    on="customer_id",
    how="left"
)

# ============================================
# 🎓 LIÇÃO: CALCULAR IDADE DO CLIENTE
# ============================================
# Idade = (data_atual - data_nascimento) / 365.25
# Usamos floor() para arredondar para baixo

df_enriched = df_enriched.withColumn(
    "customer_age",
    floor(datediff(current_date(), col("data_nascimento_dt")) / 365.25)
)

print(f"✅ Transações enriquecidas com {df_enriched.count():,} registros")

# ============================================
# 🎓 LIÇÃO: NOVAS REGRAS DE FRAUDE (12/12 IMPLEMENTADAS!)
# ============================================
# 
# REGRA 11 - ACCOUNT TAKEOVER:
#   Se device_is_trusted = false E valor > R$500 → +25 pontos
#   Se device_is_rooted ou device_is_emulator → +30 pontos
#   Se device_risk_score > 80 → +15 pontos
#   Motivo: Dispositivo suspeito fazendo compra
#
# REGRA 12 - IDADE INCOMPATÍVEL:
#   Se idade <18 E categoria "Joias" E valor >R$10.000 → +20 pontos
#   Se idade >75 E categoria "Games/Crypto" E valor >R$2.000 → +15 pontos
#   Se idade <18 E valor >R$5.000 → +15 pontos
#   Motivo: Perfil de compra incompatível com faixa etária

# Calcular risco baseado em múltiplos fatores (INCLUINDO AS NOVAS REGRAS!)
df_fraud_detection = df_enriched \
    .withColumn("risk_points", lit(0)) \
    .withColumn("risk_points", 
        col("risk_points") +
        # === REGRAS EXISTENTES ===
        when(col("horario_incomum"), 15).otherwise(0) +
        when(col("novo_beneficiario"), 10).otherwise(0) +
        when(col("is_high_risk_mcc"), 20).otherwise(0) +
        when(col("valor") > 5000, 15).otherwise(0) +
        when(col("valor") > 10000, 15).otherwise(0) +
        when(col("tipo") == "PIX", 5).otherwise(0) +
        when(col("autenticacao_3ds") == False, 10).otherwise(0) +
        when(col("cvv_validado") == False, 10).otherwise(0) +
        when(col("periodo_dia") == "MADRUGADA", 10).otherwise(0) +
        when(col("fraud_score") > 70, 20).otherwise(
            when(col("fraud_score") > 50, 10).otherwise(0)
        ) +
        # === REGRA 11: ACCOUNT TAKEOVER (NOVA!) ===
        # Device não confiável + valor alto = suspeito
        when(
            (col("device_is_trusted") == False) & (col("valor") > 500),
            25
        ).otherwise(0) +
        # Device com root/emulador = muito suspeito
        when(
            (col("device_is_rooted") == True) | (col("device_is_emulator") == True),
            30
        ).otherwise(0) +
        # Device com risk_score alto
        when(col("device_risk_score") > 80, 15).otherwise(
            when(col("device_risk_score") > 60, 8).otherwise(0)
        ) +
        # === REGRA 12: IDADE INCOMPATÍVEL (NOVA!) ===
        # 🎓 LIÇÃO: Regras realistas baseadas em comportamento de mercado
        # 
        # Menor de idade (<18) comprando joias muito caras - suspeito!
        when(
            (col("customer_age") < 18) & 
            (col("merchant_category").isin("Joias", "Joalheria", "Luxury", "Joias e Relógios")) & 
            (col("valor") > 10000),
            20
        ).otherwise(0) +
        # Idoso (>75) comprando games/crypto - perfil muito incomum
        when(
            (col("customer_age") > 75) & 
            (col("merchant_category").isin("Games", "Jogos", "Gaming", "Criptomoedas", "Crypto")) & 
            (col("valor") > 2000),
            15
        ).otherwise(0) +
        # Menor de idade (<18) com compra alta (mais de R$ 5.000) - suspeito
        when(
            (col("customer_age") < 18) & (col("valor") > 5000),
            15
        ).otherwise(0)
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
    ) \
    .withColumn("is_account_takeover",
        # Flag para REGRA 11: Account Takeover
        ((col("device_is_trusted") == False) & (col("valor") > 500)) |
        (col("device_is_rooted") == True) |
        (col("device_is_emulator") == True)
    ) \
    .withColumn("is_age_mismatch",
        # Flag para REGRA 12: Idade Incompatível (valores realistas)
        # Menor de idade + joias muito caras
        ((col("customer_age") < 18) & 
         (col("merchant_category").isin("Joias", "Joalheria", "Luxury", "Joias e Relógios")) & 
         (col("valor") > 10000)) |
        # Idoso + games/crypto caro
        ((col("customer_age") > 75) & 
         (col("merchant_category").isin("Games", "Jogos", "Gaming", "Criptomoedas", "Crypto")) & 
         (col("valor") > 2000)) |
        # Menor de idade + compra alta
        ((col("customer_age") < 18) & (col("valor") > 5000))
    )

# Selecionar campos para tabela Gold (incluindo novas colunas de regras)
df_fraud_gold = df_fraud_detection.select(
    "transaction_id",
    "customer_id",
    "device_id",
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
    # === NOVAS COLUNAS DAS REGRAS 11 e 12 ===
    "device_is_trusted",
    "device_is_rooted",
    "device_is_emulator",
    "device_risk_score",
    "device_risk_category",
    "customer_age",
    "customer_renda_mensal",
    # === FLAGS DAS NOVAS REGRAS ===
    "is_account_takeover",
    "is_age_mismatch",
    # === FIM NOVAS COLUNAS ===
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
