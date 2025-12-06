"""
🥉 BRONZE LAYER - MinIO Raw → MinIO Bronze (BATCH)
Ingestão de dados brutos do MinIO raw/batch para o Bronze Layer

Este job processa os dados gerados pelo fraud-generator no MinIO:
- Lê de: s3a://fraud-data/raw/batch/
- Escreve em: s3a://fraud-data/bronze/batch/

TIPO: BATCH (processamento em lote)
FONTE: fraud-generator v4-beta (campos em inglês)
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    current_timestamp, col, lit, input_file_name, 
    to_timestamp, year, month, dayofmonth
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    BooleanType, IntegerType
)
from config import apply_s3a_configs

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================
RAW_PATH = "s3a://fraud-data/raw/batch"
BRONZE_PATH = "s3a://fraud-data/bronze/batch"
REPARTITION_COUNT = 16  # Otimização de particionamento

# Schema das transações do Brazilian Fraud Data Generator (v4-beta - English)
transaction_schema = StructType([
    StructField("transaction_id", StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("session_id", StringType(), True),
    StructField("device_id", StringType(), True),
    StructField("timestamp", StringType(), True),
    StructField("type", StringType(), True),
    StructField("amount", DoubleType(), True),
    StructField("currency", StringType(), True),
    StructField("channel", StringType(), True),
    StructField("ip_address", StringType(), True),
    StructField("geolocation_lat", DoubleType(), True),
    StructField("geolocation_lon", DoubleType(), True),
    StructField("merchant_id", StringType(), True),
    StructField("merchant_name", StringType(), True),
    StructField("merchant_category", StringType(), True),
    StructField("mcc_code", StringType(), True),
    StructField("mcc_risk_level", StringType(), True),
    StructField("card_number_hash", StringType(), True),
    StructField("card_brand", StringType(), True),
    StructField("card_type", StringType(), True),
    StructField("installments", IntegerType(), True),
    StructField("card_entry", StringType(), True),
    StructField("cvv_validated", BooleanType(), True),
    StructField("auth_3ds", BooleanType(), True),
    StructField("pix_key_type", StringType(), True),
    StructField("pix_key_destination", StringType(), True),
    StructField("destination_bank", StringType(), True),
    StructField("distance_from_last_txn_km", DoubleType(), True),
    StructField("time_since_last_txn_min", IntegerType(), True),
    StructField("transactions_last_24h", IntegerType(), True),
    StructField("accumulated_amount_24h", DoubleType(), True),
    StructField("unusual_time", BooleanType(), True),
    StructField("new_beneficiary", BooleanType(), True),
    StructField("status", StringType(), True),
    StructField("refusal_reason", StringType(), True),
    StructField("fraud_score", DoubleType(), True),
    StructField("is_fraud", BooleanType(), True),
    StructField("fraud_type", StringType(), True)
])

def main():
    print("=" * 70)
    print("🥉 BRONZE LAYER - BATCH PROCESSING")
    print("   Fonte: s3a://fraud-data/raw/batch")
    print("   Destino: s3a://fraud-data/bronze/batch")
    print("   Repartition: 16 partições")
    print("=" * 70)
    
    # Configurações S3 via variáveis de ambiente
    spark = apply_s3a_configs(
        SparkSession.builder
        .appName("Batch_Raw_to_Bronze")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.hadoop.fs.s3a.multipart.size", "104857600")
        .config("spark.hadoop.fs.s3a.fast.upload", "true")
        # Suporte para timestamps INT96/NANOS do PyArrow
        .config("spark.sql.parquet.int96RebaseModeInRead", "CORRECTED")
        .config("spark.sql.parquet.datetimeRebaseModeInRead", "CORRECTED")
        .config("spark.sql.parquet.outputTimestampType", "TIMESTAMP_MICROS")
        .config("spark.sql.legacy.parquet.nanosAsLong", "true")
    ).getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    # =========================================================================
    # LER DADOS DO RAW (PARQUET ou JSONL - fraud-generator)
    # =========================================================================
    print("\n📂 Verificando arquivos no RAW...")
    
    # Tentar ler Parquet primeiro (formato mais eficiente)
    try:
        # Ler todos os parquets de transações
        df_raw = spark.read \
            .option("recursiveFileLookup", "true") \
            .option("pathGlobFilter", "transactions_*.parquet") \
            .parquet(f"{RAW_PATH}")
        
        # Verificar se leu algo
        if df_raw.head(1):
            file_format = "parquet"
            print(f"✅ Encontrados arquivos Parquet")
        else:
            raise Exception("Nenhum dado encontrado em Parquet")
        
    except Exception as parquet_error:
        print(f"⚠️ Parquet não encontrado ({parquet_error}), tentando JSONL...")
        try:
            df_raw = spark.read \
                .schema(transaction_schema) \
                .option("recursiveFileLookup", "true") \
                .json(f"{RAW_PATH}")
            file_format = "jsonl"
            print(f"✅ Encontrados arquivos JSONL")
            
        except Exception as json_error:
            print(f"❌ Erro ao ler dados: {json_error}")
            raise
    
    # Filtrar apenas transações (ignorar customers e devices se existirem)
    if "transaction_id" in df_raw.columns:
        df_raw = df_raw.filter(col("transaction_id").isNotNull())
    
    total_records = df_raw.count()
    print(f"✅ Lidos {total_records:,} registros do RAW ({file_format})")
    
    # =========================================================================
    # ADICIONAR METADADOS BRONZE
    # =========================================================================
    print("\n🔄 Adicionando metadados Bronze...")
    
    df_bronze = df_raw \
        .withColumn("ingestion_timestamp", current_timestamp()) \
        .withColumn("source_layer", lit("raw")) \
        .withColumn("source_format", lit(file_format)) \
        .withColumn("processing_date", current_timestamp().cast("date"))
    
    # Adicionar partições de data se o timestamp existir
    if "timestamp" in df_bronze.columns:
        df_bronze = df_bronze \
            .withColumn("ts_parsed", to_timestamp(col("timestamp"))) \
            .withColumn("year", year(col("ts_parsed"))) \
            .withColumn("month", month(col("ts_parsed"))) \
            .withColumn("day", dayofmonth(col("ts_parsed"))) \
            .drop("ts_parsed")
    
    # =========================================================================
    # REPARTITION E ESCRITA
    # =========================================================================
    print(f"\n📊 Reparticionando para {REPARTITION_COUNT} partições...")
    
    df_bronze = df_bronze.repartition(REPARTITION_COUNT)
    
    print(f"\n💾 Escrevendo no Bronze: {BRONZE_PATH}/transactions")
    
    # Escrever particionado por ano/mês/dia
    df_bronze.write \
        .mode("overwrite") \
        .partitionBy("year", "month", "day") \
        .parquet(f"{BRONZE_PATH}/transactions")
    
    print("=" * 70)
    print("✅ BRONZE LAYER CONCLUÍDO!")
    print(f"   📊 Registros processados: {total_records:,}")
    print(f"   📁 Partições: {REPARTITION_COUNT}")
    print(f"   📂 Destino: {BRONZE_PATH}/transactions")
    print("=" * 70)
    
    # Mostrar estatísticas
    print("\n📈 Estatísticas:")
    df_bronze.groupBy("type").count().orderBy("count", ascending=False).show(10)
    
    spark.stop()

if __name__ == "__main__":
    main()
