"""
📤 STREAMING TO POSTGRES - Kafka → PostgreSQL (STREAMING)
Spark Streaming - Kafka para PostgreSQL (Tempo Real)

Este job:
1. Lê transações do Kafka em tempo real
2. Aplica regras de detecção de fraude
3. Salva no PostgreSQL para o Dashboard

TIPO: STREAMING (tempo real via Kafka)
DESTINO: PostgreSQL para Metabase Dashboard
FONTE: fraud-generator v4-beta (campos em inglês)
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, when, abs as spark_abs, 
    current_timestamp, round as spark_round, to_timestamp, hour
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    BooleanType, IntegerType
)
from config import POSTGRES_URL, POSTGRES_PROPERTIES, KAFKA_BROKER, KAFKA_TOPIC, apply_s3a_configs

# Schema das transações do Brazilian Fraud Data Generator (v4-beta)
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

def process_batch(df, batch_id):
    """Processa cada micro-batch e salva no PostgreSQL"""
    
    if df.count() == 0:
        print(f"[Batch {batch_id}] Nenhum dado para processar")
        return
    
    count = df.count()
    print(f"\n[Batch {batch_id}] Processando {count} transações...")
    
    # Aplicar transformações e regras de risco
    df_processed = df \
        .withColumn("event_time", to_timestamp(col("timestamp"))) \
        .withColumn("transaction_hour", hour(to_timestamp(col("timestamp")))) \
        .withColumn("amount_clean", 
            when(col("amount") < 0, spark_abs(col("amount"))).otherwise(col("amount"))) \
        .withColumn("is_pix_new_beneficiary",
            when((col("type") == "PIX") & (col("new_beneficiary") == True), True).otherwise(False)) \
        .withColumn("is_high_value",
            when(col("amount") > 5000, True).otherwise(False)) \
        .withColumn("is_high_velocity",
            when(col("transactions_last_24h") > 10, True).otherwise(False)) \
        .withColumn("is_location_jump",
            when(col("distance_from_last_txn_km") > 100, True).otherwise(False)) \
        .withColumn("is_manual_card_entry",
            when(col("card_entry") == "MANUAL", True).otherwise(False))
    
    # Calcular Fraud Score Adicional
    df_scored = df_processed.withColumn("fraud_score_additional",
        (when(col("is_pix_new_beneficiary"), 25).otherwise(0) +
         when(col("is_high_value"), 15).otherwise(0) +
         when(col("is_high_velocity"), 20).otherwise(0) +
         when(col("is_location_jump"), 25).otherwise(0) +
         when(col("is_manual_card_entry"), 10).otherwise(0) +
         when(col("unusual_time") == True, 10).otherwise(0) +
         when(col("mcc_risk_level") == "high", 20).otherwise(
             when(col("mcc_risk_level") == "medium", 10).otherwise(0)))
    )
    
    # Combinar scores
    df_scored = df_scored.withColumn("fraud_score_combined",
        spark_round(col("fraud_score") + (col("fraud_score_additional") * 0.5), 2)
    )
    
    # Determinar Risk Level
    df_final = df_scored.withColumn("risk_level",
        when(col("fraud_score_combined") >= 80, "CRITICAL")
        .when(col("fraud_score_combined") >= 60, "HIGH")
        .when(col("fraud_score_combined") >= 40, "MEDIUM")
        .when(col("fraud_score_combined") >= 20, "LOW")
        .otherwise("NORMAL")
    )
    
    # Selecionar colunas para transactions
    df_transactions = df_final.select(
        col("transaction_id"),
        col("customer_id"),
        col("device_id"),
        col("event_time"),
        col("type").alias("transaction_type"),
        col("amount_clean").alias("amount"),
        col("channel"),
        col("merchant_name").alias("merchant"),
        col("merchant_category").alias("category"),
        col("mcc_risk_level"),
        col("card_brand"),
        col("pix_key_type"),
        col("transactions_last_24h"),
        col("accumulated_amount_24h"),
        col("fraud_score").cast("integer"),
        col("fraud_score_combined").cast("integer").alias("fraud_score_total"),
        col("risk_level"),
        col("is_fraud"),
        col("fraud_type"),
        col("status")
    )
    
    # Salvar todas transações
    df_transactions.write \
        .jdbc(POSTGRES_URL, "transactions", mode="append", properties=POSTGRES_PROPERTIES)
    
    # Filtrar e salvar alertas (HIGH e CRITICAL)
    df_alerts = df_final.filter(col("risk_level").isin("HIGH", "CRITICAL")) \
        .select(
            col("transaction_id"),
            col("customer_id"),
            col("device_id"),
            col("event_time"),
            col("type").alias("transaction_type"),
            col("amount_clean").alias("amount"),
            col("channel"),
            col("merchant_name").alias("merchant"),
            col("merchant_category").alias("category"),
            col("pix_key_type"),
            col("destination_bank"),
            col("is_pix_new_beneficiary"),
            col("is_location_jump"),
            col("distance_from_last_txn_km"),
            col("fraud_score").cast("integer"),
            col("fraud_score_combined").cast("integer").alias("fraud_score_total"),
            col("risk_level"),
            col("is_fraud"),
            col("fraud_type")
        )
    
    alerts_count = df_alerts.count()
    if alerts_count > 0:
        df_alerts.write \
            .jdbc(POSTGRES_URL, "fraud_alerts", mode="append", properties=POSTGRES_PROPERTIES)
        print(f"[Batch {batch_id}] 🚨 {alerts_count} ALERTAS de fraude salvos!")
    
    # Mostrar estatísticas
    fraud_count = df_final.filter(col("is_fraud") == True).count()
    print(f"[Batch {batch_id}] ✅ {count} transações salvas | {fraud_count} fraudes | {alerts_count} alertas")
    df_final.groupBy("risk_level").count().show()


def main():
    spark = apply_s3a_configs(
        SparkSession.builder.appName("Streaming_Kafka_to_PostgreSQL")
    ).getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    print("=" * 60)
    print("🚀 SPARK STREAMING - KAFKA → POSTGRESQL")
    print("   Fonte: fraud-generator v4-beta (campos em inglês)")
    print("=" * 60)
    print("📡 Conectando ao Kafka...")
    
    # Ler do Kafka (PROCESSAR APENAS NOVOS desde agora)
    df_kafka = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "latest") \
        .option("maxOffsetsPerTrigger", "10000") \
        .option("failOnDataLoss", "false") \
        .load()
    
    # Parsear JSON
    df_transactions = df_kafka \
        .selectExpr("CAST(value AS STRING) as json_value") \
        .select(from_json(col("json_value"), transaction_schema).alias("data")) \
        .select("data.*") \
        .filter(col("transaction_id").isNotNull())
    
    print(f"✅ Conectado ao Kafka - Tópico: {KAFKA_TOPIC}")
    print("✅ Aguardando dados em tempo real...")
    print("=" * 60)
    
    # Processar em micro-batches e salvar no PostgreSQL
    # Checkpoint LOCAL (temporário para debug)
    checkpoint_location = "/tmp/streaming_checkpoints/postgres"
    
    query = df_transactions.writeStream \
        .foreachBatch(process_batch) \
        .outputMode("append") \
        .trigger(processingTime="10 seconds") \
        .option("checkpointLocation", checkpoint_location) \
        .start()
    
    print(f"📍 Checkpoint persistente: {checkpoint_location}")
    
    query.awaitTermination()


if __name__ == "__main__":
    main()
