"""Teste de leitura do RAW"""
import sys
sys.path.insert(0, '/jobs')
from pyspark.sql import SparkSession
from config import apply_s3a_configs

spark = apply_s3a_configs(SparkSession.builder.appName("TestReadRAW")).getOrCreate()
spark.sparkContext.setLogLevel("ERROR")

print("\n" + "="*60)
print("TESTE DE LEITURA RAW")
print("="*60)

# Tentar ler sem schema
try:
    print("\n1. Lendo transactions_*.parquet SEM schema...")
    df = spark.read.parquet("s3a://fraud-data/raw/batch/transactions_*.parquet")
    count = df.count()
    print(f"   Registros: {count}")
    if count > 0:
        print(f"   Colunas: {df.columns[:5]}")
        df.select("transaction_id", "timestamp", "amount").show(2, truncate=False)
except Exception as e:
    print(f"   ERRO: {e}")

# Tentar ler transactions_00000.parquet especificamente
try:
    print("\n2. Lendo transactions_00000.parquet especificamente...")
    df = spark.read.parquet("s3a://fraud-data/raw/batch/transactions_00000.parquet")
    count = df.count()
    print(f"   Registros: {count}")
    if count > 0:
        df.select("transaction_id", "timestamp", "amount").show(2, truncate=False)
except Exception as e:
    print(f"   ERRO: {e}")

spark.stop()
print("\n✅ Teste concluído")
