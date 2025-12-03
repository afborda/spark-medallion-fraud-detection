"""
🥉 BRONZE LAYER - Kafka → MinIO
Ingestão de dados brutos do Kafka para o Data Lake
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, col
from config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, KAFKA_BROKER, KAFKA_TOPIC

print("=" * 60)
print("🥉 BRONZE LAYER - Kafka → MinIO")
print("=" * 60)

# JARs
JARS_PATH = "/jars"
HADOOP_AWS = f"{JARS_PATH}/hadoop-aws-3.3.4.jar"
AWS_SDK = f"{JARS_PATH}/aws-java-sdk-bundle-1.12.262.jar"
KAFKA_SQL = f"{JARS_PATH}/spark-sql-kafka-0-10_2.12-3.5.3.jar"
KAFKA_CLIENT = f"{JARS_PATH}/kafka-clients-3.5.1.jar"
COMMONS_POOL = f"{JARS_PATH}/commons-pool2-2.11.1.jar"
TOKEN_PROVIDER = f"{JARS_PATH}/spark-token-provider-kafka-0-10_2.12-3.5.3.jar"

JARS = f"{HADOOP_AWS},{AWS_SDK},{KAFKA_SQL},{KAFKA_CLIENT},{COMMONS_POOL},{TOKEN_PROVIDER}"
CLASSPATH = f"{HADOOP_AWS}:{AWS_SDK}"

spark = SparkSession.builder \
    .appName("Bronze_Kafka_to_MinIO") \
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
