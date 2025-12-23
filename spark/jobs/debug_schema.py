#!/usr/bin/env python3
"""Script para verificar schema do Parquet no MinIO"""
import os
import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from config import apply_s3a_configs

spark = apply_s3a_configs(
    SparkSession.builder
    .appName("Schema_Check")
    .master("local[1]")
).getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

print("=" * 60)
print("VERIFICANDO SCHEMA DE CADA ARQUIVO")
print("=" * 60)

RAW_PATH = "s3a://fraud-data/raw/batch"

for i in range(3):
    print(f"\n📄 Arquivo transactions_0000{i}.parquet:")
    try:
        df = spark.read.parquet(f"{RAW_PATH}/transactions_0000{i}.parquet")
        # Mostrar tipo do timestamp
        for field in df.schema.fields:
            if field.name == 'timestamp':
                print(f"   timestamp: {field.dataType}")
            if field.name == 'transactions_last_24h':
                print(f"   transactions_last_24h: {field.dataType}")
        print(f"   Total colunas: {len(df.columns)}")
    except Exception as e:
        print(f"   ERRO: {e}")

spark.stop()
