"""
Bronze Layer - Converte JSON para Parquet
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, lit
from datetime import datetime
import os

# Detecta se está rodando em Docker (caminho absoluto) ou local (caminho relativo)
BASE_DIR = os.environ.get("DATA_DIR", "/data" if os.path.exists("/data") else "data")
RAW_DIR = f"{BASE_DIR}/raw"
BRONZE_DIR = f"{BASE_DIR}/bronze"
PROCESS_DATE = datetime.now().strftime("%Y-%m-%d")

print("=" * 50)
print("🔶 BRONZE LAYER - Ingestão de dados brutos")
print("=" * 50)
print(f"📂 Origem: {RAW_DIR}")
print(f"📂 Destino: {BRONZE_DIR}")
print(f"📅 Data: {PROCESS_DATE}")
print("=" * 50)

# Inicializa Spark
print("\n🚀 Inicializando Spark...")
spark = SparkSession.builder \
	.appName("Bronze Layer Ingestion") \
	.config("spark.sql.files.maxPartitionBytes", "128m") \
	.getOrCreate()

print(f"✅ Spark inicializado. {spark.version} \n")

def process_entity(spark, entity_name):
	"""
	Processa uma entidade: JSON -> Parquet
	"""

	json_path = f"{RAW_DIR}/{entity_name}.json"
	parquet_path = f"{BRONZE_DIR}/{entity_name}"

	print(f"\n📥 Processando: {entity_name}")

	# Lê JSON
	df = spark.read.json(json_path)
	print(f" Registros lidos: {df.count()}")

	# Adiciona colunas de metadata
	df = df.withColumn("_ingestion_time", current_timestamp())
	df = df.withColumn("_process_date", lit(PROCESS_DATE))

	# Salva como Parquet
	count = df.count() 
	df.write.mode("overwrite").parquet(parquet_path)

	print(f" 📦 Dados salvos em Parquet: {parquet_path}")

	return count


if __name__ == "__main__":
	total = 0
	total += process_entity(spark, "customers")

	total += process_entity(spark, "transactions")
	# Resumo final
	print("\n" + "=" * 50)
	print(f"🎉 Bronze Layer completo!")
	print(f"   Total de registros processados: {total}")
	print("=" * 50)
	# Encerrar Spark
	spark.stop()