"""
🥉 BRONZE LAYER - Kafka → MinIO
Ingestão de dados brutos do Kafka para o Data Lake
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, col
from config import KAFKA_BROKER, KAFKA_TOPIC, apply_s3a_configs

print("=" * 60)
print("🥉 BRONZE LAYER - Kafka → MinIO")
print("=" * 60)

# Configurações S3 são carregadas via variáveis de ambiente (seguro!)
spark = apply_s3a_configs(
    SparkSession.builder.appName("Bronze_Kafka_to_MinIO")
).getOrCreate()

spark.sparkContext.setLogLevel("WARN")

print("📡 Lendo dados do Kafka...")

# Ler TUDO do Kafka
df_kafka = spark.read \
    .format("kafka") \
    .option("kafka.bootstrap.servers", KAFKA_BROKER) \
    .option("subscribe", KAFKA_TOPIC) \
    .option("startingOffsets", "earliest") \
    .option("endingOffsets", "latest") \
    .load()

total = df_kafka.count()
print(f"✅ {total:,} mensagens lidas do Kafka")

# Bronze: salvar dados BRUTOS com metadados de ingestão
df_bronze = df_kafka.select(
    col("key").cast("string").alias("kafka_key"),
    col("value").cast("string").alias("raw_json"),
    col("topic"),
    col("partition").alias("kafka_partition"),
    col("offset").alias("kafka_offset"),
    col("timestamp").alias("kafka_timestamp"),
    current_timestamp().alias("ingestion_timestamp")
)

# Salvar no MinIO como Parquet
output_path = "s3a://fraud-data/medallion/bronze/transactions"
print(f"💾 Salvando em: {output_path}")

df_bronze.write \
    .mode("overwrite") \
    .parquet(output_path)

# Verificar
df_check = spark.read.parquet(output_path)
print(f"✅ BRONZE CONCLUÍDO: {df_check.count():,} registros no MinIO")
print("=" * 60)

spark.stop()
