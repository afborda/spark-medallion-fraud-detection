"""
Gold to MinIO - Upload Gold Layer para Data Lake
Copia dados agregados (Gold) para storage S3-compatible
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
import os
from config import (
    MINIO_ENDPOINT as CONFIG_MINIO_ENDPOINT, 
    MINIO_ACCESS_KEY as CONFIG_MINIO_ACCESS_KEY, 
    MINIO_SECRET_KEY as CONFIG_MINIO_SECRET_KEY
)

# ============================================================
# CONFIGURAÇÕES
# ============================================================

# Detecta se está rodando em Docker ou Local
IS_DOCKER = os.path.exists("/data")
BASE_DIR = "/data" if IS_DOCKER else "data"

# Caminhos de origem (local)
GOLD_PATH = f"{BASE_DIR}/gold"

# Caminhos de destino (MinIO)
MINIO_BUCKET = "fraud-data"
MINIO_GOLD_PATH = f"s3a://{MINIO_BUCKET}/gold"

# Credenciais MinIO via config.py
MINIO_ENDPOINT = CONFIG_MINIO_ENDPOINT if IS_DOCKER else "http://localhost:9002"
MINIO_ACCESS_KEY = CONFIG_MINIO_ACCESS_KEY
MINIO_SECRET_KEY = CONFIG_MINIO_SECRET_KEY

# JARs necessários para S3A (mesma config do bronze_to_minio.py)
JARS_PATH = "/jars" if IS_DOCKER else "jars"

print("=" * 60)
print("📤 GOLD TO MINIO - Upload para Data Lake")
print("=" * 60)
print(f"📂 Origem: {GOLD_PATH}")
print(f"☁️  Destino: {MINIO_GOLD_PATH}")
print(f"🔗 MinIO Endpoint: {MINIO_ENDPOINT}")
print(f"🐳 Rodando em Docker: {IS_DOCKER}")
print("=" * 60)

# ============================================================
# INICIALIZAR SPARK COM SUPORTE S3A
# ============================================================

print("\n🚀 Iniciando Spark Session com suporte S3A...")

# JARs necessários para S3A (veja docs/ERROS_CONHECIDOS.md para detalhes)
HADOOP_AWS_JAR = f"{JARS_PATH}/hadoop-aws-3.3.4.jar"
AWS_SDK_JAR = f"{JARS_PATH}/aws-java-sdk-bundle-1.12.262.jar"
JARS = f"{HADOOP_AWS_JAR},{AWS_SDK_JAR}"
CLASSPATH = f"{HADOOP_AWS_JAR}:{AWS_SDK_JAR}"

spark = SparkSession.builder \
    .appName("Gold to MinIO") \
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

print(f"✅ Spark Session iniciada. Versão: {spark.version}")

# ============================================================
# FUNÇÕES DE UPLOAD
# ============================================================

def upload_customer_summary():
    """Upload de customer_summary Gold para MinIO"""
    print("\n📤 Uploading: customer_summary")
    
    # 1. Ler do local
    local_path = f"{GOLD_PATH}/customer_summary"
    df = spark.read.parquet(local_path)
    count = df.count()
    print(f"   📂 Lidos {count:,} registros de {local_path}")
    
    # 2. Escrever no MinIO
    minio_path = f"{MINIO_GOLD_PATH}/customer_summary"
    df.write.mode("overwrite").parquet(minio_path)
    print(f"   ☁️  Salvos em {minio_path}")
    
    return count


def upload_fraud_summary():
    """Upload de fraud_summary Gold para MinIO"""
    print("\n📤 Uploading: fraud_summary")
    
    # 1. Ler do local
    local_path = f"{GOLD_PATH}/fraud_summary"
    df = spark.read.parquet(local_path)
    count = df.count()
    print(f"   📂 Lidos {count:,} registros de {local_path}")
    
    # 2. Escrever no MinIO
    minio_path = f"{MINIO_GOLD_PATH}/fraud_summary"
    df.write.mode("overwrite").parquet(minio_path)
    print(f"   ☁️  Salvos em {minio_path}")
    
    return count


def upload_fraud_detection():
    """Upload de fraud_detection Gold para MinIO (particionado)"""
    print("\n📤 Uploading: fraud_detection")
    
    # 1. Ler do local (dados particionados por risk_level)
    local_path = f"{GOLD_PATH}/fraud_detection"
    df = spark.read.parquet(local_path)
    count = df.count()
    print(f"   📂 Lidos {count:,} registros de {local_path}")
    
    # 2. Escrever no MinIO (mantendo particionamento)
    minio_path = f"{MINIO_GOLD_PATH}/fraud_detection"
    df.write.mode("overwrite").partitionBy("risk_level").parquet(minio_path)
    print(f"   ☁️  Salvos em {minio_path} (particionado por risk_level)")
    
    return count


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 INICIANDO UPLOAD GOLD → MINIO")
    print("=" * 60)
    
    # Upload customer_summary
    customer_count = upload_customer_summary()
    
    # Upload fraud_summary
    fraud_summary_count = upload_fraud_summary()
    
    # Upload fraud_detection
    fraud_detection_count = upload_fraud_detection()
    
    # Resumo
    print("\n" + "=" * 60)
    print("✅ UPLOAD CONCLUÍDO!")
    print("=" * 60)
    print(f"📊 Customer Summary: {customer_count:,} registros")
    print(f"📊 Fraud Summary: {fraud_summary_count:,} registros")
    print(f"📊 Fraud Detection: {fraud_detection_count:,} registros")
    print(f"☁️  Bucket: {MINIO_BUCKET}")
    print(f"📂 Path: {MINIO_GOLD_PATH}")
    print("=" * 60)
    
    # Encerrar Spark
    spark.stop()
    print("\n🏁 Spark Session encerrada.")
