"""
Bronze Layer to MinIO - Ingestão para Data Lake S3
Lê dados RAW (JSON) e salva como Parquet no MinIO
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, lit
from datetime import date

# Configurações do MinIO
MINIO_ENDPOINT = "http://localhost:9002"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin123@@!!_2"


# Caminho Bronze Layer no MinIO
RAW_PATH = "data/raw"
BRONZE_BUCKET = "s3a://bronze"

print("=" * 50)
print("🪣 BRONZE LAYER → MINIO")
print("=" * 50)
print(f"📂 Origem: {RAW_PATH}")
print(f"🪣 Destino: {BRONZE_BUCKET}")
print(f"📅 Data: {date.today().isoformat()}")
print("=" * 50)


# Inicializar Spark com configurações do S3/MinIO
print("🚀 Iniciando Spark Session...")
spark = SparkSession.builder \
	.appName("Bronze Layer to MinIO") \
	.config("spark.jars", "jars/hadoop-aws-3.4.1.jar,jars/bundle-2.29.51.jar,jars/wildfly-openssl-1.0.7.Final.jar") \
	.config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
	.config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
	.config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
	.config("spark.hadoop.fs.s3a.path.style.access", "true") \
	.config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
	.getOrCreate()
print(f"✅ Spark inicializado: {spark.version}")


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
