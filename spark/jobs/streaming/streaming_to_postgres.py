"""
📤 STREAMING TO POSTGRES - Kafka → PostgreSQL (STREAMING)
Spark Streaming - Kafka para PostgreSQL (Tempo Real)

Este job:
1. Lê transações do Kafka em tempo real
2. Aplica regras de detecção de fraude
3. Salva no PostgreSQL para o Dashboard

TIPO: STREAMING (tempo real via Kafka)
DESTINO: PostgreSQL para Metabase Dashboard
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, when, abs as spark_abs, sqrt, pow as spark_pow,
    current_timestamp, round as spark_round
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    BooleanType, LongType, IntegerType
)
from config import POSTGRES_URL, POSTGRES_PROPERTIES, KAFKA_BROKER, KAFKA_TOPIC, apply_s3a_configs

# Schema das transações do Kafka
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

def process_batch(df, batch_id):
    """Processa cada micro-batch e salva no PostgreSQL"""
    
    if df.count() == 0:
        print(f"[Batch {batch_id}] Nenhum dado para processar")
        return
    
    print(f"\n[Batch {batch_id}] Processando {df.count()} transações...")
    
    # Aplicar regras de detecção de fraude
    df_processed = df \
        .withColumn("amount_clean", 
            when(col("amount") < 0, spark_abs(col("amount"))).otherwise(col("amount"))) \
        .withColumn("distance_device_purchase",
            spark_round(sqrt(
                spark_pow(col("device_latitude") - col("purchase_latitude"), 2) +
                spark_pow(col("device_longitude") - col("purchase_longitude"), 2)
            ), 4)) \
        .withColumn("is_cross_state",
            when(col("customer_home_state") != col("purchase_state"), True).otherwise(False)) \
        .withColumn("is_night_transaction",
            when(col("transaction_hour") < 6, True).otherwise(False)) \
        .withColumn("is_high_value",
            when(col("amount") > col("avg_transaction_amount_30d") * 3, True).otherwise(False)) \
        .withColumn("is_high_velocity",
            when(col("transactions_last_24h") > 5, True).otherwise(False)) \
        .withColumn("is_gps_mismatch",
            when(col("distance_device_purchase") > 5, True).otherwise(False)) \
        .withColumn("is_cross_state_no_travel",
            when((col("is_cross_state") == True) & (col("had_travel_purchase_last_12m") == False), True).otherwise(False))
    
    # Calcular Fraud Score
    df_scored = df_processed.withColumn("fraud_score",
        (when(col("is_cross_state"), 15).otherwise(0) +
         when(col("is_night_transaction"), 10).otherwise(0) +
         when(col("is_high_value"), 20).otherwise(0) +
         when(col("is_high_velocity"), 15).otherwise(0) +
         when(col("is_gps_mismatch"), 25).otherwise(0) +
         when(col("is_cross_state_no_travel"), 30).otherwise(0) +
         when(col("is_first_purchase_in_state"), 10).otherwise(0) +
         when(col("is_international"), 15).otherwise(0))
    )
    
    # Determinar Risk Level
    df_final = df_scored.withColumn("risk_level",
        when(col("fraud_score") >= 70, "CRÍTICO")
        .when(col("fraud_score") >= 50, "ALTO")
        .when(col("fraud_score") >= 30, "MÉDIO")
        .when(col("fraud_score") >= 15, "BAIXO")
        .otherwise("NORMAL")
    )
    
    # Selecionar colunas para transactions
    df_transactions = df_final.select(
        col("transaction_id"),
        col("customer_id"),
        col("amount_clean").alias("amount"),
        col("merchant"),
        col("category"),
        col("fraud_score").cast("integer"),
        col("risk_level"),
        col("is_fraud")
    )
    
    # Salvar todas transações
    df_transactions.write \
        .jdbc(POSTGRES_URL, "transactions", mode="append", properties=POSTGRES_PROPERTIES)
    
    # Filtrar e salvar alertas (ALTO e CRÍTICO)
    df_alerts = df_final.filter(col("risk_level").isin("ALTO", "CRÍTICO")) \
        .select(
            col("transaction_id"),
            col("customer_id"),
            col("amount_clean").alias("amount"),
            col("merchant"),
            col("fraud_score").cast("integer"),
            col("risk_level"),
            col("is_fraud"),
            col("customer_home_state"),
            col("purchase_state")
        )
    
    alerts_count = df_alerts.count()
    if alerts_count > 0:
        df_alerts.write \
            .jdbc(POSTGRES_URL, "fraud_alerts", mode="append", properties=POSTGRES_PROPERTIES)
        print(f"[Batch {batch_id}] 🚨 {alerts_count} ALERTAS de fraude salvos!")
    
    # Mostrar estatísticas
    print(f"[Batch {batch_id}] ✅ Transações salvas no PostgreSQL")
    df_final.groupBy("risk_level").count().show()


def main():
    # Configurações S3 são carregadas via variáveis de ambiente (seguro!)
    spark = apply_s3a_configs(
        SparkSession.builder.appName("Streaming_Kafka_to_PostgreSQL")
    ).getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    print("=" * 60)
    print("🚀 SPARK STREAMING - KAFKA → POSTGRESQL")
    print("=" * 60)
    print("📡 Conectando ao Kafka...")
    
    # Ler do Kafka
    df_kafka = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "earliest") \
        .option("failOnDataLoss", "false") \
        .load()
    
    # Parsear JSON
    df_transactions = df_kafka \
        .selectExpr("CAST(value AS STRING) as json_value") \
        .select(from_json(col("json_value"), transaction_schema).alias("data")) \
        .select("data.*")
    
    print("✅ Conectado ao Kafka - Tópico: transactions")
    print("✅ Aguardando dados em tempo real...")
    print("=" * 60)
    
    # Processar em micro-batches e salvar no PostgreSQL
    query = df_transactions.writeStream \
        .foreachBatch(process_batch) \
        .outputMode("append") \
        .trigger(processingTime="5 seconds") \
        .start()
    
    query.awaitTermination()


if __name__ == "__main__":
    main()
