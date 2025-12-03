"""
Bronze Layer to MinIO - Ingestão para Data Lake S3
Lê dados RAW (JSON) e salva como Parquet no MinIO
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, lit
from datetime import date
import os
from config import (
    MINIO_ENDPOINT as CONFIG_MINIO_ENDPOINT, 
    MINIO_ACCESS_KEY as CONFIG_MINIO_ACCESS_KEY, 
    MINIO_SECRET_KEY as CONFIG_MINIO_SECRET_KEY
)

# Detecta ambiente (Docker vs Local)
IS_DOCKER = os.path.exists("/data")
BASE_DIR = "/data" if IS_DOCKER else "data"

# Configurações do MinIO via config.py
MINIO_ENDPOINT = CONFIG_MINIO_ENDPOINT if IS_DOCKER else "http://localhost:9002"
MINIO_ACCESS_KEY = CONFIG_MINIO_ACCESS_KEY
MINIO_SECRET_KEY = CONFIG_MINIO_SECRET_KEY

# Caminhos
RAW_PATH = f"{BASE_DIR}/raw"
BRONZE_BUCKET = "s3a://fraud-data/bronze"

# JARs path
JARS_PATH = "/jars" if IS_DOCKER else "jars"

print("=" * 50)
print("🪣 BRONZE LAYER → MINIO")
print("=" * 50)
print(f"📂 Origem: {RAW_PATH}")
print(f"🪣 Destino: {BRONZE_BUCKET}")
print(f"🔗 MinIO: {MINIO_ENDPOINT}")
print(f"📅 Data: {date.today().isoformat()}")
print("=" * 50)


# ============================================================
# INICIALIZAR SPARK COM SUPORTE S3A
# ============================================================
#
# IMPORTANTE: Por que essas configurações?
#
# 1. spark.jars - Carrega os JARs necessários no driver
# 2. spark.driver.extraClassPath - Adiciona JARs ao classpath do driver
# 3. spark.executor.extraClassPath - Adiciona JARs ao classpath dos workers
#    (SEM ISSO, os workers não conseguem escrever no S3A!)
#
# 4. hadoop-aws-3.3.4 usa AWS SDK v1 que funciona com MinIO HTTP
#    Spark 3.5.x + Hadoop 3.3.x = AWS SDK v1 (compatível)
#    Spark 4.0.x + Hadoop 3.4.x = AWS SDK v2 (BUG com MinIO HTTP!)
#
# 5. fs.s3a.path.style.access=true - MinIO usa path-style (bucket no path)
#    AWS S3 usa virtual-hosted-style (bucket no subdomínio)
#
# Veja docs/ERROS_CONHECIDOS.md para mais detalhes sobre os erros.
# ============================================================

print("🚀 Iniciando Spark Session...")

# JARs necessários para S3A
HADOOP_AWS_JAR = f"{JARS_PATH}/hadoop-aws-3.3.4.jar"
AWS_SDK_JAR = f"{JARS_PATH}/aws-java-sdk-bundle-1.12.262.jar"
JARS = f"{HADOOP_AWS_JAR},{AWS_SDK_JAR}"
CLASSPATH = f"{HADOOP_AWS_JAR}:{AWS_SDK_JAR}"

spark = SparkSession.builder \
    .appName("Bronze Layer to MinIO") \
    .config("spark.jars", JARS) \
    .config("spark.driver.extraClassPath", CLASSPATH) \
    .config("spark.executor.extraClassPath", CLASSPATH) \
    .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
    .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
    .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
    .config("spark.sql.files.maxPartitionBytes", "128m") \
    .getOrCreate()

print(f"✅ Spark inicializado: {spark.version}")
print(f"✅ S3A configurado para: {MINIO_ENDPOINT}")


def process_to_bronze (spark, source_path,  dest_path, table_name):
	"""Processa dados RAW para Bronze Layer no MinIO
	
	Args:
		spark: SparkSession
		source_path: Caminho dos dados RAW (JSON)
		dest_path: Caminho destino no MinIO (Parquet)
		table_name: Nome da tabela (clientes ou transações)
	"""
	print(f"🔄 Processando dados de {table_name}...")
	# Ler dados RAW (JSON)
	df  = spark.read.json(source_path)
	print(f"   📥 Registros lidos: {df.count()}")
	# Adicionar colunas de metadata
	df_bronze = df \
		.withColumn("_ingestion_time", current_timestamp()) \
		.withColumn("_source", lit(source_path)) \
		.withColumn("_process_date", lit(date.today().isoformat()))

	# Salvar como Parquet no MinIO
	df_bronze.write \
		.mode("overwrite") \
		.parquet(dest_path)
	print(f"✅ Dados salvos em {dest_path} ({df_bronze.count()} registros)")

# ============================================
# CÓDIGO PRINCIPAL	
# ============================================

# Processar customers
customer_count = process_to_bronze(
	spark,
	f"{RAW_PATH}/customers.json",
	f"{BRONZE_BUCKET}/customers",
	"customers"
)

# Processar transactions
transactions_count = process_to_bronze(
	spark,
	f"{RAW_PATH}/transactions.json",
	f"{BRONZE_BUCKET}/transactions",
	"transactions"
)


# 3. Resumo
print("\n" + "=" * 50)
print("✅ BRONZE LAYER NO MINIO CONCLUÍDO!")
print("=" * 50)
print(f"   👤 customers: {customer_count} registros")
print(f"   💳 transactions: {transactions_count} registros")
print(f"   🪣 Bucket: {BRONZE_BUCKET}")

# Encerrar Spark
spark.stop()
print("\n🏁 Spark encerrado.")
