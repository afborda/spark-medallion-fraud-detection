"""
🥉 BRONZE LAYER - Kafka → MinIO (STREAMING)
Spark Streaming - Kafka para Bronze Layer

Este job lê transações do Kafka em tempo real e salva no MinIO.

TIPO: STREAMING (tempo real via Kafka/fraud-generator v4-beta)
FONTE: Kafka topic 'transactions' (dados em inglês do fraud-generator)
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, current_timestamp
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    BooleanType, IntegerType
)
from config import KAFKA_BROKER, KAFKA_TOPIC, apply_s3a_configs

# Schema das transações do Brazilian Fraud Data Generator (v4-beta - English field names)
transaction_schema = StructType([
    StructField("transaction_id", StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("session_id", StringType(), True),
    StructField("device_id", StringType(), True),
    StructField("timestamp", StringType(), True),  # ISO format string
    StructField("type", StringType(), True),  # PIX, CREDIT_CARD, DEBIT_CARD, TED, BOLETO
    StructField("amount", DoubleType(), True),
    StructField("currency", StringType(), True),
    StructField("channel", StringType(), True),  # MOBILE_APP, WEB_BANKING, ATM, BRANCH
    StructField("ip_address", StringType(), True),
    StructField("geolocation_lat", DoubleType(), True),
    StructField("geolocation_lon", DoubleType(), True),
    StructField("merchant_id", StringType(), True),
    StructField("merchant_name", StringType(), True),
    StructField("merchant_category", StringType(), True),
    StructField("mcc_code", StringType(), True),
    StructField("mcc_risk_level", StringType(), True),
    StructField("card_number_hash", StringType(), True),
    StructField("card_brand", StringType(), True),  # VISA, MASTERCARD, ELO, etc
    StructField("card_type", StringType(), True),  # CREDIT, DEBIT
    StructField("installments", IntegerType(), True),
    StructField("card_entry", StringType(), True),  # CHIP, CONTACTLESS, MANUAL, ONLINE
    StructField("cvv_validated", BooleanType(), True),
    StructField("auth_3ds", BooleanType(), True),
    StructField("pix_key_type", StringType(), True),  # CPF, CNPJ, EMAIL, PHONE, RANDOM
    StructField("pix_key_destination", StringType(), True),
    StructField("destination_bank", StringType(), True),
    StructField("distance_from_last_txn_km", DoubleType(), True),
    StructField("time_since_last_txn_min", IntegerType(), True),
    StructField("transactions_last_24h", IntegerType(), True),
    StructField("accumulated_amount_24h", DoubleType(), True),
    StructField("unusual_time", BooleanType(), True),
    StructField("new_beneficiary", BooleanType(), True),
    StructField("status", StringType(), True),  # APPROVED, DECLINED, PENDING, BLOCKED
    StructField("refusal_reason", StringType(), True),
    StructField("fraud_score", DoubleType(), True),
    StructField("is_fraud", BooleanType(), True),
    StructField("fraud_type", StringType(), True)
])

def main():
    # Configurações S3 são carregadas via variáveis de ambiente (seguro!)
    spark = apply_s3a_configs(
        SparkSession.builder
        .appName("Streaming_Kafka_to_Bronze")
        .config("spark.hadoop.fs.s3a.multipart.size", "104857600")
        .config("spark.hadoop.fs.s3a.fast.upload", "true")
        .config("spark.hadoop.fs.s3a.committer.name", "directory")
        .config("spark.sql.streaming.metricsEnabled", "true")
    ).getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    print("=" * 60)
    print("🚀 INICIANDO SPARK STREAMING - KAFKA → BRONZE")
    print("   Fonte: fraud-generator v4-beta (campos em inglês)")
    print("=" * 60)
    
    # Ler do Kafka
    df_kafka = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "latest") \
        .option("failOnDataLoss", "false") \
        .load()
    
    print(f"✅ Conectado ao Kafka - Tópico: {KAFKA_TOPIC}")
    
    # Converter o valor (bytes) para JSON e extrair campos
    df_transactions = df_kafka \
        .selectExpr("CAST(value AS STRING) as json_value") \
        .select(from_json(col("json_value"), transaction_schema).alias("data")) \
        .select("data.*") \
        .filter(col("transaction_id").isNotNull()) \
        .withColumn("processed_at", current_timestamp())
    
    print("✅ Schema aplicado às transações")
    
    # Escrever no MinIO (Bronze Layer) em formato Parquet
    query = df_transactions.writeStream \
        .format("parquet") \
        .option("path", "s3a://fraud-data/streaming/bronze/transactions") \
        .option("checkpointLocation", "s3a://fraud-data/streaming/checkpoints/bronze") \
        .outputMode("append") \
        .trigger(processingTime="10 seconds") \
        .start()
    
    print("✅ Escrevendo no MinIO: s3a://fraud-data/streaming/bronze/transactions")
    print("")
    print("📊 Streaming ativo! Aguardando dados...")
    print("   Pressione Ctrl+C para parar")
    print("=" * 60)
    
    # Aguardar o streaming
    query.awaitTermination()

if __name__ == "__main__":
    main()
