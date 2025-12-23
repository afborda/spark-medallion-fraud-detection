"""
Script para verificar schema dos dados no pipeline
"""
import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from config import apply_s3a_configs

def main():
    spark = apply_s3a_configs(
        SparkSession.builder
        .appName("Schema_Check")
        .config("spark.sql.parquet.enableVectorizedReader", "false")
    ).getOrCreate()
    
    spark.sparkContext.setLogLevel("ERROR")
    
    print("\n" + "=" * 70)
    print("VERIFICAÇÃO DE SCHEMA DO PIPELINE")
    print("=" * 70)
    
    # 1. Raw
    print("\n📂 1. RAW DATA (fraud-generator output)")
    print("-" * 50)
    try:
        df_raw = spark.read.parquet("s3a://fraud-data/raw/batch/transactions_*.parquet")
        df_raw.printSchema()
        print(f"   Registros: {df_raw.count():,}")
        print("\n   Amostra timestamp:")
        df_raw.select("timestamp").show(3, truncate=False)
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    # 2. Bronze
    print("\n📂 2. BRONZE DATA")
    print("-" * 50)
    try:
        df_bronze = spark.read.option("recursiveFileLookup", "true").parquet("s3a://fraud-data/bronze/batch/transactions")
        df_bronze.printSchema()
        print(f"   Registros: {df_bronze.count():,}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    # 3. Silver
    print("\n📂 3. SILVER DATA")
    print("-" * 50)
    try:
        df_silver = spark.read.parquet("s3a://fraud-data/silver/batch/transactions")
        df_silver.printSchema()
        print(f"   Registros: {df_silver.count():,}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    # 4. Gold
    print("\n📂 4. GOLD DATA")
    print("-" * 50)
    try:
        df_gold = spark.read.parquet("s3a://fraud-data/gold/batch/fraud_detection")
        df_gold.printSchema()
        print(f"   Registros: {df_gold.count():,}")
    except Exception as e:
        print(f"   ❌ Erro: {e}")
    
    print("\n" + "=" * 70)
    spark.stop()

if __name__ == "__main__":
    main()
