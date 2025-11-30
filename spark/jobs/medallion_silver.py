"""
🥈 SILVER LAYER - Bronze → Silver (MinIO)
Limpeza e enriquecimento dos dados
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, when, abs as spark_abs, sqrt, pow as spark_pow,
    current_timestamp, round as spark_round
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    BooleanType, LongType, IntegerType
)

print("=" * 60)
print("🥈 SILVER LAYER - Bronze → Silver")
print("=" * 60)

# Schema das transações
transaction_schema = StructType([
    StructField("transaction_id", StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("amount", DoubleType(), True),
    StructField("merchant", StringType(), True),
    StructField("category", StringType(), True),
    StructField("transaction_hour", DoubleType(), True),
    StructField("day_of_week", StringType(), True),
    StructField("customer_home_state", StringType(), True),
    StructField("purchase_state", StringType(), True),
    StructField("purchase_city", StringType(), True),
    StructField("purchase_latitude", DoubleType(), True),
    StructField("purchase_longitude", DoubleType(), True),
    StructField("device_latitude", DoubleType(), True),
    StructField("device_longitude", DoubleType(), True),
    StructField("device_id", StringType(), True),
    StructField("ip_address", StringType(), True),
    StructField("payment_method", StringType(), True),
    StructField("card_brand", StringType(), True),
    StructField("installments", IntegerType(), True),
    StructField("had_travel_purchase_last_12m", BooleanType(), True),
    StructField("is_first_purchase_in_state", BooleanType(), True),
    StructField("transactions_last_24h", DoubleType(), True),
    StructField("avg_transaction_amount_30d", DoubleType(), True),
    StructField("is_international", BooleanType(), True),
    StructField("is_online", BooleanType(), True),
    StructField("is_fraud", BooleanType(), True),
    StructField("timestamp", LongType(), True)
])

# JARs
JARS_PATH = "/jars"
HADOOP_AWS = f"{JARS_PATH}/hadoop-aws-3.3.4.jar"
AWS_SDK = f"{JARS_PATH}/aws-java-sdk-bundle-1.12.262.jar"
JARS = f"{HADOOP_AWS},{AWS_SDK}"
CLASSPATH = f"{HADOOP_AWS}:{AWS_SDK}"

spark = SparkSession.builder \
    .appName("Silver_Bronze_to_Silver") \
    .config("spark.jars", JARS) \
    .config("spark.driver.extraClassPath", CLASSPATH) \
    .config("spark.executor.extraClassPath", CLASSPATH) \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123@@!!_2") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# Ler Bronze
bronze_path = "s3a://fraud-data/medallion/bronze/transactions"
print(f"📂 Lendo Bronze: {bronze_path}")

df_bronze = spark.read.parquet(bronze_path)
total_bronze = df_bronze.count()
print(f"✅ {total_bronze:,} registros no Bronze")

# Parsear JSON
print("🔄 Parseando JSON e limpando dados...")

df_parsed = df_bronze \
    .select(from_json(col("raw_json"), transaction_schema).alias("data")) \
    .select("data.*") \
    .filter(col("transaction_id").isNotNull())

# Transformações Silver - Limpeza e Enriquecimento
# THRESHOLDS REALISTAS para evitar excesso de flags
df_silver = df_parsed \
    .withColumn("amount_clean", 
        when(col("amount") < 0, spark_abs(col("amount")))
        .otherwise(col("amount"))) \
    .withColumn("distance_gps",
        spark_round(sqrt(
            spark_pow(col("device_latitude") - col("purchase_latitude"), 2) +
            spark_pow(col("device_longitude") - col("purchase_longitude"), 2)
        ), 4)) \
    .withColumn("is_cross_state",
        # Cross-state só é relevante SE não houver histórico de viagem
        when((col("customer_home_state") != col("purchase_state")) & 
             (col("had_travel_purchase_last_12m") == False), True)
        .otherwise(False)) \
    .withColumn("is_night_transaction",
        # Horário suspeito: 2-5am (não 0-6)
        when((col("transaction_hour") >= 2) & (col("transaction_hour") < 5), True)
        .otherwise(False)) \
    .withColumn("is_high_value",
        # Valor alto: 5x a média (não 3x) - mais conservador
        when(col("amount") > col("avg_transaction_amount_30d") * 5, True)
        .otherwise(False)) \
    .withColumn("is_high_velocity",
        # Alta velocidade: mais de 15 transações em 24h (não 5)
        when(col("transactions_last_24h") > 15, True)
        .otherwise(False)) \
    .withColumn("is_gps_mismatch",
        # GPS mismatch: distância > 20 graus (~2222km) é suspeito
        # Dados ShadowTraffic têm mediana de 10 graus, p95=21 graus
        # Threshold alto para pegar apenas ~5% dos casos extremos
        when(col("distance_gps") > 20.0, True)
        .otherwise(False)) \
    .withColumn("silver_timestamp", current_timestamp())

# Salvar Silver
silver_path = "s3a://fraud-data/medallion/silver/transactions"
print(f"💾 Salvando em: {silver_path}")

df_silver.write \
    .mode("overwrite") \
    .parquet(silver_path)

# Verificar
df_check = spark.read.parquet(silver_path)
print(f"✅ SILVER CONCLUÍDO: {df_check.count():,} registros limpos")

# Mostrar estatísticas
print("\n📊 Estatísticas Silver:")
print(f"   - Transações cross-state: {df_check.filter(col('is_cross_state')).count():,}")
print(f"   - Transações noturnas: {df_check.filter(col('is_night_transaction')).count():,}")
print(f"   - Alto valor: {df_check.filter(col('is_high_value')).count():,}")
print(f"   - GPS suspeito: {df_check.filter(col('is_gps_mismatch')).count():,}")
print("=" * 60)

spark.stop()
