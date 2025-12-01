"""
Silver Layer - Limpeza e Validação de Dados
Transforma dados brutos (Bronze) em dados confiáveis (Silver)
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, trim, lower, current_timestamp, to_date, regexp_replace
from datetime import date
import os

# Detecta se está rodando em Docker (caminho absoluto) ou local (caminho relativo)
BASE_DIR = os.environ.get("DATA_DIR", "/data" if os.path.exists("/data") else "data")
BRONZE_PATH = f"{BASE_DIR}/bronze"
SILVER_PATH = f"{BASE_DIR}/silver"
PROCESS_DATE = date.today().isoformat()


print("=" * 50)
print("⚪ SILVER LAYER - Limpeza e Validação")
print("=" * 50)
print(f"📂 Origem: {BRONZE_PATH}")
print(f"📂 Destino: {SILVER_PATH}")
print(f"📅 Data: {PROCESS_DATE}")
print("=" * 50)

print ("🚀 Iniciando Spark Session...")

spark = SparkSession.builder \
	.appName("Silver Layer - Data Cleaning and Validation") \
	.config("spark.sql.files.maxPartitionBytes", "128m") \
	.getOrCreate()
print(f"✅ Spark Session iniciada. Versão: {spark.version}")

def clean_customers():
	"""Limpa e valida dados de clientes"""
	print("🔄 Processando dados de clientes...")
	# Ler do bronze
	customers_df = spark.read.parquet(f"{BRONZE_PATH}/customers")
	print(f"✅ Dados de clientes carregados. Registros: {customers_df.count()}")
	# Remove duplicados ( customer_id )
	customers_df = customers_df.dropDuplicates(["customer_id"])
	#Remover registro sem campos obrigatorios
	customers_df = customers_df.dropna(subset=["customer_id", "email"])
	# 4. Padronizar: email em minúsculas, nome sem espaços extras
	customers_df = customers_df.withColumn("email", lower(trim(col("email"))))
	customers_df = customers_df.withColumn("name", trim(col("name")))
	customers_df = customers_df.withColumn("city",trim(col("city")))
	# 5. Adicionar metadado de quando foi processado
	customers_df = customers_df.withColumn("processed_date", to_date(current_timestamp()))
	# 6. Salvar no Silver
	output_path = f"{SILVER_PATH}/customers"
	customers_df.write.mode("overwrite").parquet(output_path)
	count = customers_df.count()
	print(f"✅ Dados de clientes limpos e salvos. Registros finais: {count}")
	return count


def clean_transactions():
	"""Limpa e valida dados de transações"""
	print("\n 🔄 Processando dados de transações...")
	#1. Ler do bronze
	transactions_df = spark.read.parquet(f"{BRONZE_PATH}/transactions")
	print(f"✅ Dados de transações carregados. Registros: {transactions_df.count()}")
	#2. Remove duplicados ( transaction_id )
	transactions_df = transactions_df.dropDuplicates(["transaction_id"])
	#3. Remover registros sem campos obrigatórios
	transactions_df = transactions_df.dropna(subset=["transaction_id", "customer_id", "amount"])
	#4. Corrigir formatos: remover caracteres não numéricos de amount e converter para float
	transactions_df = transactions_df.filter(col("amount") > 0)
	#5. Padronizar nome do merchant
	transactions_df = transactions_df.withColumn("merchant", trim(col("merchant")))
	#6. Adicionar metadado de quando foi processado
	transactions_df = transactions_df.withColumn("_silver_timestamp", current_timestamp())
	#7. Salvar no Silver
	output_path = f"{SILVER_PATH}/transactions"
	transactions_df.write.mode("overwrite").parquet(output_path)
	count = transactions_df.count()
	print(f"✅ Dados de transações limpos e salvos. Registros finais: {count}")
	return count
	

# Executa processos de limpeza
if __name__ == "__main__":
	total = 0
	total += clean_customers()
	total += clean_transactions()
	print("\n" + "=" * 50)
	print(f"✅ SILVER LAYER COMPLETO! Total de registros processados: {total	}")
	print("=" * 50)
	spark.stop()