"""
🥉 BRONZE LAYER - Kafka → MinIO (STREAMING)
Spark Streaming - Kafka para Bronze Layer

Este job lê transações do Kafka em tempo real e salva no MinIO.

TIPO: STREAMING (tempo real via Kafka/ShadowTraffic)
FONTE: Kafka topic 'transactions' (dados em inglês do ShadowTraffic)
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, col, current_timestamp
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    BooleanType, LongType, IntegerType
)
from config import KAFKA_BROKER, KAFKA_TOPIC, apply_s3a_configs

# Schema das transações (mesmo que definimos no ShadowTraffic)
transaction_schema = StructType([
    StructField("transaction_id", StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("amount", DoubleType(), True),
    StructField("merchant", StringType(), True),
    StructField("category", StringType(), True),
    StructField("transaction_hour", DoubleType(), True),
    StructField("day_of_week", StringType(), True),
    StructField("customer_home_state", StringType(), True),
    StructField("purchase_state", StringType(), True),
    StructField("purchase_city", StringType(), True),
    StructField("purchase_latitude", DoubleType(), True),
    StructField("purchase_longitude", DoubleType(), True),
    StructField("device_latitude", DoubleType(), True),
    StructField("device_longitude", DoubleType(), True),
    StructField("device_id", StringType(), True),
    StructField("ip_address", StringType(), True),
    StructField("payment_method", StringType(), True),
    StructField("card_brand", StringType(), True),
    StructField("installments", IntegerType(), True),
    StructField("had_travel_purchase_last_12m", BooleanType(), True),
    StructField("is_first_purchase_in_state", BooleanType(), True),
    StructField("transactions_last_24h", DoubleType(), True),
    StructField("avg_transaction_amount_30d", DoubleType(), True),
    StructField("is_international", BooleanType(), True),
    StructField("is_online", BooleanType(), True),
    StructField("is_fraud", BooleanType(), True),
    StructField("timestamp", LongType(), True)
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
    print("=" * 60)
    
    # Ler do Kafka
    df_kafka = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "earliest") \
        .load()
    
    print(f"✅ Conectado ao Kafka - Tópico: {KAFKA_TOPIC}")
    
    # Converter o valor (bytes) para JSON e extrair campos
    df_transactions = df_kafka \
        .selectExpr("CAST(value AS STRING) as json_value") \
        .select(from_json(col("json_value"), transaction_schema).alias("data")) \
        .select("data.*") \
        .withColumn("processed_at", current_timestamp())
    
    print("✅ Schema aplicado às transações")
    
    # Escrever no MinIO (Bronze Layer) em formato Parquet
    query = df_transactions.writeStream \
        .format("parquet") \
        .option("path", "s3a://fraud-data/streaming/bronze/transactions") \
        .option("checkpointLocation", "s3a://fraud-data/streaming/checkpoints/transactions") \
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
