"""
🥇 GOLD LAYER - Silver → Gold → PostgreSQL
Aplicação de regras de negócio e carga para banco analítico
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, current_timestamp, count, avg, sum as spark_sum,
    round as spark_round
)
from config import (
    MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY,
    SILVER_PATH, GOLD_PATH, POSTGRES_URL, POSTGRES_PROPERTIES
)

print("=" * 60)
print("🥇 GOLD LAYER - Silver → Gold → PostgreSQL")
print("=" * 60)

# JARs
JARS_PATH = "/jars"
HADOOP_AWS = f"{JARS_PATH}/hadoop-aws-3.3.4.jar"
AWS_SDK = f"{JARS_PATH}/aws-java-sdk-bundle-1.12.262.jar"
POSTGRES = f"{JARS_PATH}/postgresql-42.7.4.jar"
JARS = f"{HADOOP_AWS},{AWS_SDK},{POSTGRES}"
CLASSPATH = f"{HADOOP_AWS}:{AWS_SDK}:{POSTGRES}"

spark = SparkSession.builder \
    .appName("Gold_Silver_to_PostgreSQL") \
    .config("spark.jars", JARS) \
    .config("spark.driver.extraClassPath", CLASSPATH) \
    .config("spark.executor.extraClassPath", CLASSPATH) \
    .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
    .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
    .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# Ler Silver
silver_path = f"{SILVER_PATH}/transactions"
print(f"📂 Lendo Silver: {silver_path}")

df_silver = spark.read.parquet(silver_path)
total_silver = df_silver.count()
print(f"✅ {total_silver:,} registros no Silver")

# ============================================================
# REGRAS DE NEGÓCIO - Cálculo do Fraud Score (CALIBRADO 2.5-5%)
# ============================================================
print("🔍 Aplicando regras de detecção de fraude (calibrado para 2.5-5% fraude)...")

# Scoring ULTRA CONSERVADOR
# Fraude real requer MÚLTIPLAS COMBINAÇÕES RARAS de fatores
# Fatores individuais têm peso MUITO baixo - só combinações específicas marcam fraude

df_scored = df_silver.withColumn("fraud_score",
    # === FATORES INDIVIDUAIS (peso muito baixo) ===
    (when(col("is_cross_state"), 2).otherwise(0) +
     when(col("is_night_transaction"), 3).otherwise(0) +
     when(col("is_high_value"), 3).otherwise(0) +
     when(col("is_high_velocity"), 5).otherwise(0) +
     when(col("is_gps_mismatch"), 5).otherwise(0) +
     when(col("is_first_purchase_in_state"), 2).otherwise(0) +
     when(col("is_international"), 4).otherwise(0) +
     # REGRA 7: Categoria de alto risco (eletrônicos, passagens)
     when(col("is_risky_category"), 4).otherwise(0) +
     # REGRA 9: Online de alto valor
     when(col("is_online_high_value"), 5).otherwise(0) +
     # REGRA 10: Muitas parcelas (diluição de fraude)
     when(col("is_many_installments"), 4).otherwise(0) +
     # REGRA 1: Suspeita de clonagem (PESO ALTO - é muito grave!)
     # Se detectamos que o mesmo cartão foi usado em 2 lugares distantes
     # em menos de 1 hora, isso é QUASE CERTEZA de fraude!
     when(col("is_cloning_suspect"), 25).otherwise(0) +
     # REGRA 2: Velocidade Impossível (PESO MÁXIMO!)
     # Se a velocidade necessária entre duas compras é > 900 km/h (avião),
     # é FISICAMENTE IMPOSSÍVEL - indica cartão clonado ou fraude!
     when(col("is_impossible_velocity"), 40).otherwise(0) +
     
     # === COMBINAÇÕES DE 2 FATORES (peso moderado) ===
     when((col("is_gps_mismatch")) & (col("is_high_value")), 10).otherwise(0) +
     when((col("is_gps_mismatch")) & (col("is_night_transaction")), 8).otherwise(0) +
     when((col("is_high_velocity")) & (col("is_high_value")), 8).otherwise(0) +
     when((col("is_cross_state")) & (col("had_travel_purchase_last_12m") == False), 12).otherwise(0) +
     # REGRA 7 combo: Categoria de risco + Valor alto
     when((col("is_risky_category")) & (col("is_high_value")), 12).otherwise(0) +
     # REGRA 7 combo: Categoria de risco + Noite
     when((col("is_risky_category")) & (col("is_night_transaction")), 8).otherwise(0) +
     # REGRA 9 combo: Online + Noite = muito suspeito
     when((col("is_online_high_value")) & (col("is_night_transaction")), 10).otherwise(0) +
     # REGRA 9 combo: Online alto valor + Categoria risco = altíssimo
     when((col("is_online_high_value")) & (col("is_risky_category")), 15).otherwise(0) +
     # REGRA 10 combo: Muitas parcelas + Categoria risco = fraude parcelada
     when((col("is_many_installments")) & (col("is_risky_category")), 12).otherwise(0) +
     
     # === COMBINAÇÕES DE 3+ FATORES (peso alto - FRAUDE REAL) ===
     # GPS errado + Valor alto + Noite = muito suspeito
     when((col("is_gps_mismatch")) & (col("is_high_value")) & (col("is_night_transaction")), 25).otherwise(0) +
     
     # GPS errado + Cross-state + Sem histórico = altíssimo risco
     when((col("is_gps_mismatch")) & (col("is_cross_state")) & (col("had_travel_purchase_last_12m") == False), 30).otherwise(0) +
     
     # Alta velocidade + GPS errado + Valor alto = fraude provável
     when((col("is_high_velocity")) & (col("is_gps_mismatch")) & (col("is_high_value")), 35).otherwise(0) +
     
     # Noite + Alta velocidade + Cross-state sem histórico = fraude
     when((col("is_night_transaction")) & (col("is_high_velocity")) & (col("is_cross_state")) & (col("had_travel_purchase_last_12m") == False), 40).otherwise(0) +
     
     # REGRA 7 combo triplo: Categoria risco + Valor alto + Noite = muito suspeito
     when((col("is_risky_category")) & (col("is_high_value")) & (col("is_night_transaction")), 20).otherwise(0) +
     
     # REGRA 9 combo triplo: Online + Eletrônicos + Noite = padrão clássico de fraude
     when((col("is_online_high_value")) & (col("is_risky_category")) & (col("is_night_transaction")), 25).otherwise(0) +
     
     # REGRA 10 combo triplo: Muitas parcelas + Eletrônicos + Online = fraude parcelada
     when((col("is_many_installments")) & (col("is_risky_category")) & (col("is_online_high_value")), 30).otherwise(0))
)

# Classificação de Risco - AJUSTADO para 2.5-5% em CRÍTICO+ALTO
# Com as novas flags do Silver (GPS threshold 20 graus), precisamos thresholds menores
df_gold = df_scored.withColumn("risk_level",
    when(col("fraud_score") >= 50, "CRÍTICO")      # Top ~0.5% - combinações extremas
    .when(col("fraud_score") >= 30, "ALTO")        # ~2-3% - combinações de risco
    .when(col("fraud_score") >= 18, "MÉDIO")       # ~5-10% - suspeito
    .when(col("fraud_score") >= 10, "BAIXO")       # Monitorar
    .otherwise("NORMAL")                            # Transação típica (~85%)
).withColumn("gold_timestamp", current_timestamp())

# Salvar Gold no MinIO
gold_path = f"{GOLD_PATH}/transactions"
print(f"💾 Salvando Gold em: {gold_path}")

df_gold.write \
    .mode("overwrite") \
    .partitionBy("risk_level") \
    .parquet(gold_path)

# Mostrar distribuição
print("\n📊 DISTRIBUIÇÃO DE RISCO:")
df_gold.groupBy("risk_level").count().orderBy("count", ascending=False).show()

# ============================================================
# CARREGAR PARA POSTGRESQL
# ============================================================
print("🐘 Carregando para PostgreSQL...")

postgres_url = POSTGRES_URL
postgres_props = POSTGRES_PROPERTIES

# Tabela transactions
df_transactions = df_gold.select(
    col("transaction_id"),
    col("customer_id"),
    col("amount_clean").alias("amount"),
    col("merchant"),
    col("category"),
    col("fraud_score").cast("integer"),
    col("risk_level"),
    col("is_fraud")
)

df_transactions.write \
    .jdbc(postgres_url, "transactions", mode="overwrite", properties=postgres_props)

print(f"✅ {df_transactions.count():,} transações salvas em 'transactions'")

# Tabela fraud_alerts (só ALTO e CRÍTICO)
df_alerts = df_gold.filter(col("risk_level").isin("ALTO", "CRÍTICO")) \
    .select(
        col("transaction_id"),
        col("customer_id"),
        col("amount_clean").alias("amount"),
        col("merchant"),
        col("fraud_score").cast("integer"),
        col("risk_level"),
        col("is_fraud"),
        col("customer_home_state"),
        col("purchase_state")
    )

df_alerts.write \
    .jdbc(postgres_url, "fraud_alerts", mode="overwrite", properties=postgres_props)

alerts_count = df_alerts.count()
print(f"🚨 {alerts_count:,} alertas salvos em 'fraud_alerts'")

# ============================================================
# MÉTRICAS AGREGADAS
# ============================================================
print("\n📈 MÉTRICAS FINAIS:")

# Por risco
df_gold.groupBy("risk_level") \
    .agg(
        count("*").alias("total"),
        spark_round(avg("amount_clean"), 2).alias("avg_amount"),
        spark_round(avg("fraud_score"), 1).alias("avg_score")
    ) \
    .orderBy("total", ascending=False) \
    .show()

# Por categoria
print("📊 Top 5 Categorias com mais fraudes:")
df_gold.filter(col("risk_level").isin("ALTO", "CRÍTICO")) \
    .groupBy("category") \
    .count() \
    .orderBy("count", ascending=False) \
    .limit(5) \
    .show()

print("=" * 60)
print("✅ GOLD LAYER CONCLUÍDO!")
print(f"📊 Total processado: {total_silver:,} transações")
print(f"🚨 Alertas gerados: {alerts_count:,}")
print("=" * 60)

spark.stop()
