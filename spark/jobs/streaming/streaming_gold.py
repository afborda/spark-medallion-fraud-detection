"""
🥇 GOLD LAYER - Silver → Gold (STREAMING)
Spark Streaming - Silver para Gold Layer

Gera métricas agregadas e identifica fraudes em tempo real.

TIPO: STREAMING (tempo real)
FONTE: MinIO silver/transactions (fraud-generator v4-beta)
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, count, sum as spark_sum, avg, max as spark_max,
    current_timestamp, window, when, round as spark_round
)
from config import apply_s3a_configs

def main():
    spark = apply_s3a_configs(
        SparkSession.builder.appName("Streaming_Silver_to_Gold")
    ).getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    print("=" * 60)
    print("🏆 INICIANDO STREAMING - SILVER → GOLD")
    print("   Fonte: fraud-generator v4-beta")
    print("=" * 60)
    
    # Ler dados Silver como streaming
    df_silver = spark.readStream \
        .format("parquet") \
        .option("path", "s3a://fraud-data/streaming/silver/transactions") \
        .load()
    
    print("✅ Lendo Silver Layer")
    
    # === GOLD 1: Alertas de Fraude (Alto Risco) ===
    df_high_risk = df_silver.filter(
        col("risk_level").isin("HIGH", "CRITICAL")
    ).select(
        "transaction_id",
        "customer_id",
        "device_id",
        "event_time",
        "type",
        "amount_clean",
        "channel",
        "merchant_name",
        "merchant_category",
        "mcc_risk_level",
        "card_brand",
        "pix_key_type",
        "destination_bank",
        "distance_from_last_txn_km",
        "transactions_last_24h",
        "accumulated_amount_24h",
        "is_pix_new_beneficiary",
        "is_location_jump",
        "unusual_time",
        "fraud_score",
        "fraud_score_combined",
        "risk_level",
        "is_fraud",
        "fraud_type",
        "silver_processed_at"
    )
    
    query_alerts = df_high_risk.writeStream \
        .format("parquet") \
        .option("path", "s3a://fraud-data/streaming/gold/fraud_alerts") \
        .option("checkpointLocation", "s3a://fraud-data/streaming/checkpoints/gold_alerts") \
        .outputMode("append") \
        .trigger(processingTime="15 seconds") \
        .start()
    
    print("✅ Gold 1: Alertas de fraude (HIGH/CRITICAL)")
    
    # === GOLD 2: Métricas por Tipo de Transação ===
    df_metrics_type = df_silver.groupBy("type", "risk_level") \
        .agg(
            count("*").alias("total_transactions"),
            spark_round(spark_sum("amount_clean"), 2).alias("total_amount"),
            spark_round(avg("amount_clean"), 2).alias("avg_amount"),
            spark_round(avg("fraud_score_combined"), 2).alias("avg_fraud_score"),
            spark_sum(when(col("is_fraud") == True, 1).otherwise(0)).alias("fraud_count")
        )
    
    query_type = df_metrics_type.writeStream \
        .format("parquet") \
        .option("path", "s3a://fraud-data/streaming/gold/metrics_by_type") \
        .option("checkpointLocation", "s3a://fraud-data/streaming/checkpoints/gold_type") \
        .outputMode("complete") \
        .trigger(processingTime="30 seconds") \
        .start()
    
    print("✅ Gold 2: Métricas por tipo (PIX, CREDIT_CARD, etc)")
    
    # === GOLD 3: Métricas por Canal ===
    df_metrics_channel = df_silver.groupBy("channel", "risk_level") \
        .agg(
            count("*").alias("total_transactions"),
            spark_round(spark_sum("amount_clean"), 2).alias("total_amount"),
            spark_round(avg("fraud_score_combined"), 2).alias("avg_fraud_score"),
            spark_sum(when(col("is_fraud") == True, 1).otherwise(0)).alias("fraud_count")
        )
    
    query_channel = df_metrics_channel.writeStream \
        .format("parquet") \
        .option("path", "s3a://fraud-data/streaming/gold/metrics_by_channel") \
        .option("checkpointLocation", "s3a://fraud-data/streaming/checkpoints/gold_channel") \
        .outputMode("complete") \
        .trigger(processingTime="30 seconds") \
        .start()
    
    print("✅ Gold 3: Métricas por canal (MOBILE_APP, WEB_BANKING, etc)")
    
    # === GOLD 4: Métricas por Categoria de Merchant ===
    df_metrics_category = df_silver.groupBy("merchant_category", "mcc_risk_level") \
        .agg(
            count("*").alias("total_transactions"),
            spark_round(spark_sum("amount_clean"), 2).alias("total_amount"),
            spark_round(avg("amount_clean"), 2).alias("avg_amount"),
            spark_sum(when(col("is_fraud") == True, 1).otherwise(0)).alias("fraud_count"),
            spark_sum(when(col("is_pix_new_beneficiary") == True, 1).otherwise(0)).alias("pix_new_beneficiary_count")
        )
    
    query_category = df_metrics_category.writeStream \
        .format("parquet") \
        .option("path", "s3a://fraud-data/streaming/gold/metrics_by_category") \
        .option("checkpointLocation", "s3a://fraud-data/streaming/checkpoints/gold_category") \
        .outputMode("complete") \
        .trigger(processingTime="30 seconds") \
        .start()
    
    print("✅ Gold 4: Métricas por categoria de merchant")
    
    # === GOLD 5: Métricas por Card Brand ===
    df_metrics_brand = df_silver.filter(col("card_brand").isNotNull()) \
        .groupBy("card_brand", "card_type") \
        .agg(
            count("*").alias("total_transactions"),
            spark_round(spark_sum("amount_clean"), 2).alias("total_amount"),
            spark_round(avg("installments"), 1).alias("avg_installments"),
            spark_sum(when(col("is_fraud") == True, 1).otherwise(0)).alias("fraud_count"),
            spark_sum(when(col("is_manual_card_entry") == True, 1).otherwise(0)).alias("manual_entry_count")
        )
    
    query_brand = df_metrics_brand.writeStream \
        .format("parquet") \
        .option("path", "s3a://fraud-data/streaming/gold/metrics_by_card_brand") \
        .option("checkpointLocation", "s3a://fraud-data/streaming/checkpoints/gold_brand") \
        .outputMode("complete") \
        .trigger(processingTime="30 seconds") \
        .start()
    
    print("✅ Gold 5: Métricas por bandeira de cartão")
    
    print("")
    print("📊 Streaming Gold ativo!")
    print("   - Alertas de fraude")
    print("   - Métricas por tipo de transação")
    print("   - Métricas por canal")
    print("   - Métricas por categoria de merchant")
    print("   - Métricas por bandeira de cartão")
    print("=" * 60)
    
    # Aguardar todas as queries
    spark.streams.awaitAnyTermination()

if __name__ == "__main__":
    main()
