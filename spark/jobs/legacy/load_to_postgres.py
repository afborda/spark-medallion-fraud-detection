"""
Load to PostgreSQL - Carregar Gold Layer para Data Warehouse
Salva os dados processados no PostgreSQL para consumo do Metabase
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from datetime import date
import os
from config import POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD

# Detecta se está rodando em Docker (caminho absoluto) ou local (caminho relativo)
BASE_DIR = os.environ.get("DATA_DIR", "/data" if os.path.exists("/data") else "data")

# Configurações do PostgreSQL via config.py
PG_HOST = POSTGRES_HOST
PG_PORT = POSTGRES_PORT
PG_DB = POSTGRES_DB
PG_USER = POSTGRES_USER
PG_PASSWORD = POSTGRES_PASSWORD


#URL JDBC
PG_JDBC_URL = f"jdbc:postgresql://{PG_HOST}:{PG_PORT}/{PG_DB}"

#Caminho gold layer
GOLD_PATH = f"{BASE_DIR}/gold"

print("=" * 50)
print("🐘 LOAD TO POSTGRESQL")
print("=" * 50)
print(f"📂 Origem: {GOLD_PATH}")
print(f"🎯 Destino: {PG_USER}@{PG_HOST}:{PG_PORT}")
print(f"📅 Data: {date.today().isoformat()}")
print("=" * 50)


# Inicializar Spark Session
print("🚀 Iniciando Spark Session...")

spark = SparkSession.builder \
	.appName("LoadToPostgres") \
	.config("spark.jars", "/jars/postgresql-42.7.4.jar" if os.path.exists("/data") else "jars/postgresql-42.7.4.jar") \
	.config("spark.sql.files.maxPartitionBytes", "128m") \
	.getOrCreate()
print(f"✅ Spark inicializado: {spark.version}")

def write_to_postgres(df, table_name):
	"""Escreve um DataFrame no PostgreSQL
	
	Args:
		df: DataFrame do Spark a ser salvo
		table_name: Nome da tabela no PostgreSQL
	
	"""
	print(f"🔄 Carregando dados para a tabela {table_name}...")

	properties = {
		"user": PG_USER,
		"password": PG_PASSWORD,
		"driver": "org.postgresql.Driver"
	}

	# Escrever no PostgreSQL
	df.write.jdbc(
		url=PG_JDBC_URL,	
		table=table_name,
		mode="overwrite",  # Substitui a tabela se já existir
		properties=properties
	)

	print(f"✅ Tabela {table_name} salva com sucesso!")

	return df.count()
	

# ============================================
# CÓDIGO PRINCIPAL
# ============================================

# 1 Carregar dados do Gold Layer
print("🔄 Carregando dados do Gold Layer...")
df_fraud = spark.read.parquet(f"{GOLD_PATH}/fraud_detection")
print(f"✅ Dados carregados: {df_fraud.count()} registros")

# 2 Carregar customer summary da gold layer
print("\n📖 Lendo customer_summary da Gold Layer...")
df_customers = spark.read.parquet(f"{GOLD_PATH}/customer_summary")
print(f"✅ Dados carregados: {df_customers.count()} registros")

# 3 Escrever tabelas no PostgreSQL
print("\n💾 Escrevendo tabelas no PostgreSQL...")
fraud_count = write_to_postgres(df_fraud, "fraud_detections")
customer_count = write_to_postgres(df_customers, "customer_summary")

# 4 Resumo
print("\n" + "=" * 50)
print("✅ CARGA CONCLUÍDA!")
print("=" * 50)
print(f"   🔴 fraud_detection: {fraud_count} registros")
print(f"   👤 customer_summary: {customer_count} registros")
print(f"   🎯 Banco: {PG_DB}")

# Encerrar Spark
spark.stop()
print("\n🏁 Spark encerrado.")