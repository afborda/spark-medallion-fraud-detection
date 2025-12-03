"""
🥉 BRONZE LAYER (DEVELOP) - JSON File → MinIO
Ingestão de dados do arquivo JSON para o Data Lake

DIFERENÇA DO PRODUCTION:
- Production: lê do Kafka (streaming)
- Develop: lê do arquivo JSON (batch) - mais rápido para testes!
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, col, lit, monotonically_increasing_id, to_json, struct
import time
from config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, BRONZE_PATH

print("=" * 60)
print("🥉 BRONZE LAYER (DEVELOP) - JSON → MinIO")
print("=" * 60)

# Configuração
INPUT_PATH = "/data/raw/transactions.json"  # Arquivo com 30M de transações
OUTPUT_PATH = f"{BRONZE_PATH}/transactions"

# JARs necessários (sem Kafka!)
JARS_PATH = "/jars"
HADOOP_AWS = f"{JARS_PATH}/hadoop-aws-3.3.4.jar"
AWS_SDK = f"{JARS_PATH}/aws-java-sdk-bundle-1.12.262.jar"

spark = SparkSession.builder \
    .appName("Bronze_JSON_to_MinIO_DEV") \
    .config("spark.jars", f"{HADOOP_AWS},{AWS_SDK}") \
    .config("spark.driver.extraClassPath", f"{HADOOP_AWS}:{AWS_SDK}") \
    .config("spark.executor.extraClassPath", f"{HADOOP_AWS}:{AWS_SDK}") \
    .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
    .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
    .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
    .config("spark.sql.shuffle.partitions", "200") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

start_time = time.time()

print(f"📂 Lendo dados de: {INPUT_PATH}")

# Ler arquivo JSON Lines (cada linha é um JSON)
df_raw = spark.read.json(INPUT_PATH)

total = df_raw.count()
elapsed_read = time.time() - start_time
print(f"✅ {total:,} transações lidas em {elapsed_read:.1f}s")

# Bronze: converter para formato compatível com production (raw_json)
# Isso garante que Silver funcione igual para ambos!
print("🔄 Convertendo para formato Bronze...")

df_bronze = df_raw.select(
    lit(None).cast("string").alias("kafka_key"),
    to_json(struct("*")).alias("raw_json"),  # Serializa de volta para JSON string
    lit("transactions").alias("topic"),
    lit(0).alias("kafka_partition"),
    monotonically_increasing_id().alias("kafka_offset"),
    current_timestamp().alias("kafka_timestamp"),
    current_timestamp().alias("ingestion_timestamp")
)

# Salvar no MinIO como Parquet
print(f"💾 Salvando em: {OUTPUT_PATH}")

df_bronze.write \
    .mode("overwrite") \
    .parquet(OUTPUT_PATH)

elapsed_total = time.time() - start_time

# Verificar
df_check = spark.read.parquet(OUTPUT_PATH)
final_count = df_check.count()

print(f"\n✅ BRONZE CONCLUÍDO!")
print(f"   📊 Registros: {final_count:,}")
print(f"   ⏱️  Tempo: {elapsed_total/60:.1f} minutos")
print(f"   🚀 Velocidade: {final_count/elapsed_total:,.0f} registros/seg")
print("=" * 60)

spark.stop()
