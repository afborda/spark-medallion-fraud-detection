"""
🔐 CONFIGURAÇÃO CENTRALIZADA - Variáveis de Ambiente
Carrega credenciais de forma segura via variáveis de ambiente
"""

import os

# ============================================
# MinIO (S3-compatible Object Storage)
# ============================================
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "http://minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_SECRET_KEY = os.getenv("MINIO_ROOT_PASSWORD", "")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "fraud-data")

# ============================================
# PostgreSQL
# ============================================
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "postgres")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
POSTGRES_DB = os.getenv("POSTGRES_DB", "fraud_db")
POSTGRES_USER = os.getenv("POSTGRES_USER", "fraud_user")
POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "")

# URL JDBC
POSTGRES_URL = f"jdbc:postgresql://{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DB}"
POSTGRES_PROPERTIES = {
    "user": POSTGRES_USER,
    "password": POSTGRES_PASSWORD,
    "driver": "org.postgresql.Driver",
    "stringtype": "unspecified"
}

# ============================================
# Kafka
# ============================================
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "kafka:9092")
KAFKA_TOPIC = os.getenv("KAFKA_TOPIC", "transactions")

# ============================================
# Spark
# ============================================
SPARK_MASTER = os.getenv("SPARK_MASTER", "spark://spark-master:7077")

# ============================================
# Paths
# ============================================
BRONZE_PATH = f"s3a://{MINIO_BUCKET}/medallion/bronze"
SILVER_PATH = f"s3a://{MINIO_BUCKET}/medallion/silver"
GOLD_PATH = f"s3a://{MINIO_BUCKET}/medallion/gold"


def get_spark_s3a_configs():
    """Retorna configurações S3A para SparkSession"""
    return {
        "spark.hadoop.fs.s3a.endpoint": MINIO_ENDPOINT,
        "spark.hadoop.fs.s3a.access.key": MINIO_ACCESS_KEY,
        "spark.hadoop.fs.s3a.secret.key": MINIO_SECRET_KEY,
        "spark.hadoop.fs.s3a.path.style.access": "true",
        "spark.hadoop.fs.s3a.impl": "org.apache.hadoop.fs.s3a.S3AFileSystem",
        "spark.hadoop.fs.s3a.connection.ssl.enabled": "false",
    }


def apply_s3a_configs(spark_builder):
    """Aplica configurações S3A a um SparkSession.Builder"""
    for key, value in get_spark_s3a_configs().items():
        spark_builder = spark_builder.config(key, value)
    return spark_builder


# Verificar se variáveis críticas estão definidas
def validate_env():
    """Valida se as variáveis de ambiente críticas estão definidas"""
    missing = []
    if not MINIO_SECRET_KEY:
        missing.append("MINIO_ROOT_PASSWORD")
    if not POSTGRES_PASSWORD:
        missing.append("POSTGRES_PASSWORD")
    
    if missing:
        print("⚠️  AVISO: Variáveis de ambiente não definidas:")
        for var in missing:
            print(f"   - {var}")
        print("   Usando valores padrão (não recomendado em produção)")
    
    return len(missing) == 0
