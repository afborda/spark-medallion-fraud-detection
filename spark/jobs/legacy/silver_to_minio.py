"""
Silver to MinIO - Upload Silver Layer para Data Lake
Copia dados processados (Silver) para storage S3-compatible
"""

from pyspark.sql import SparkSession
import os

# ============================================================
# CONFIGURAÇÕES
# ============================================================

# Detecta se está rodando em Docker ou Local
IS_DOCKER = os.path.exists("/data")
BASE_DIR = "/data" if IS_DOCKER else "data"

# Caminhos de origem (local)
SILVER_PATH = f"{BASE_DIR}/silver"

# Caminhos de destino (MinIO)
MINIO_BUCKET = "fraud-data"
MINIO_SILVER_PATH = f"s3a://{MINIO_BUCKET}/silver"

# Credenciais MinIO (em produção, usar variáveis de ambiente!)
# NOTA: Usar 'minio' (service name) ao invés de 'fraud_minio' (container_name)
# Hostnames com underscore causam erro no AWS SDK
MINIO_ENDPOINT = "http://minio:9000" if IS_DOCKER else "http://localhost:9002"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin123@@!!_2"

# JARs necessários para S3A (mesma config do bronze_to_minio.py)
JARS_PATH = "/jars" if IS_DOCKER else "jars"

print("=" * 60)
print("📤 SILVER TO MINIO - Upload para Data Lake")
print("=" * 60)
print(f"📂 Origem: {SILVER_PATH}")
print(f"☁️  Destino: {MINIO_SILVER_PATH}")
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
    .appName("Silver to MinIO") \
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

# Configurar S3A - já configurado no builder acima via spark.hadoop.*
# hadoop_conf não precisa mais ser setado manualmente

print(f"✅ Spark Session iniciada. Versão: {spark.version}")

# ============================================================
# FUNÇÕES DE UPLOAD
# ============================================================

def upload_customers():
    """Upload de customers Silver para MinIO"""
    print("\n📤 Uploading: customers")
    
    # 1. Ler do local
    local_path = f"{SILVER_PATH}/customers"
    df = spark.read.parquet(local_path)
    count = df.count()
    print(f"   📂 Lidos {count:,} registros de {local_path}")
    
    # 2. Escrever no MinIO
    minio_path = f"{MINIO_SILVER_PATH}/customers"
    df.write.mode("overwrite").parquet(minio_path)
    print(f"   ☁️  Salvos em {minio_path}")
    
    return count


def upload_transactions():
    """Upload de transactions Silver para MinIO"""
    print("\n📤 Uploading: transactions")
    
    # 1. Ler do local
    local_path = f"{SILVER_PATH}/transactions"
    df = spark.read.parquet(local_path)
    count = df.count()
    print(f"   📂 Lidos {count:,} registros de {local_path}")
    
    # 2. Escrever no MinIO
    minio_path = f"{MINIO_SILVER_PATH}/transactions"
    df.write.mode("overwrite").parquet(minio_path)
    print(f"   ☁️  Salvos em {minio_path}")
    
    return count


# ============================================================
# EXECUÇÃO PRINCIPAL
# ============================================================

if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 INICIANDO UPLOAD SILVER → MINIO")
    print("=" * 60)
    
    # Upload customers
    customers_count = upload_customers()
    
    # Upload transactions
    transactions_count = upload_transactions()
    
    # Resumo
    print("\n" + "=" * 60)
    print("✅ UPLOAD CONCLUÍDO!")
    print("=" * 60)
    print(f"📊 Customers: {customers_count:,} registros")
    print(f"📊 Transactions: {transactions_count:,} registros")
    print(f"☁️  Bucket: {MINIO_BUCKET}")
    print(f"📂 Path: {MINIO_SILVER_PATH}")
    print("=" * 60)
    
    # Encerrar Spark
    spark.stop()
    print("\n🏁 Spark Session encerrada.")
