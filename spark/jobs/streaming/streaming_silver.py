"""
🥈 SILVER LAYER - Bronze → Silver (STREAMING)
Spark Streaming - Bronze para Silver Layer

Lê dados Bronze, aplica limpeza e enriquece com indicadores de risco.

TIPO: STREAMING (tempo real)
FONTE: MinIO bronze/transactions (dados do fraud-generator v4-beta)
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, abs as spark_abs, current_timestamp, 
    round as spark_round, lit, to_timestamp, hour
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    BooleanType, IntegerType, TimestampType
)
from config import apply_s3a_configs

# Schema dos dados Bronze (fraud-generator v4-beta)
bronze_schema = StructType([
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
    StructField("fraud_type", StringType(), True),
    StructField("processed_at", TimestampType(), True)
])

def main():
    spark = apply_s3a_configs(
        SparkSession.builder.appName("Streaming_Bronze_to_Silver")
    ).getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    print("=" * 60)
    print("🔄 INICIANDO STREAMING - BRONZE → SILVER")
    print("   Fonte: fraud-generator v4-beta")
    print("=" * 60)
    
    # Ler dados Bronze como streaming
    df_bronze = spark.readStream \
        .format("parquet") \
        .schema(bronze_schema) \
        .option("path", "s3a://fraud-data/streaming/bronze/transactions") \
        .load()
    
    print("✅ Lendo Bronze Layer")
    
    # === TRANSFORMAÇÕES SILVER ===
    
    # 1. Converter timestamp para tipo correto e extrair hora
    df_clean = df_bronze.withColumn(
        "event_time", 
        to_timestamp(col("timestamp"))
    ).withColumn(
        "transaction_hour",
        hour(to_timestamp(col("timestamp")))
    )
    
    # 2. Limpar valores negativos de amount
    df_clean = df_clean.withColumn(
        "amount_clean", 
        when(col("amount") < 0, spark_abs(col("amount"))).otherwise(col("amount"))
    )
    
    # 3. Flag: PIX para novo beneficiário (alto risco)
    df_clean = df_clean.withColumn(
        "is_pix_new_beneficiary",
        when(
            (col("type") == "PIX") & (col("new_beneficiary") == True),
            True
        ).otherwise(False)
    )
    
    # 4. Flag: Valor alto (> R$ 5.000)
    df_clean = df_clean.withColumn(
        "is_high_value",
        when(col("amount_clean") > 5000, True).otherwise(False)
    )
    
    # 5. Flag: Muitas transações em 24h (> 10)
    df_clean = df_clean.withColumn(
        "is_high_velocity",
        when(col("transactions_last_24h") > 10, True).otherwise(False)
    )
    
    # 6. Flag: Acumulado alto em 24h (> R$ 10.000)
    df_clean = df_clean.withColumn(
        "is_high_accumulated",
        when(col("accumulated_amount_24h") > 10000, True).otherwise(False)
    )
    
    # 7. Flag: Distância grande desde última transação (> 100km)
    df_clean = df_clean.withColumn(
        "is_location_jump",
        when(col("distance_from_last_txn_km") > 100, True).otherwise(False)
    )
    
    # 8. Flag: Cartão digitado manualmente (maior risco)
    df_clean = df_clean.withColumn(
        "is_manual_card_entry",
        when(col("card_entry") == "MANUAL", True).otherwise(False)
    )
    
    # 9. Flag: Sem autenticação 3DS em transação online
    df_clean = df_clean.withColumn(
        "is_no_3ds_online",
        when(
            (col("channel") == "WEB_BANKING") & (col("auth_3ds") == False),
            True
        ).otherwise(False)
    )
    
    # 10. Calcular FRAUD SCORE ADICIONAL baseado nos novos indicadores
    df_silver = df_clean.withColumn(
        "fraud_score_additional",
        (
            when(col("is_pix_new_beneficiary"), 25).otherwise(0) +
            when(col("is_high_value"), 15).otherwise(0) +
            when(col("is_high_velocity"), 20).otherwise(0) +
            when(col("is_high_accumulated"), 15).otherwise(0) +
            when(col("is_location_jump"), 25).otherwise(0) +
            when(col("is_manual_card_entry"), 10).otherwise(0) +
            when(col("is_no_3ds_online"), 15).otherwise(0) +
            when(col("unusual_time") == True, 10).otherwise(0) +
            when(col("mcc_risk_level") == "high", 20).otherwise(
                when(col("mcc_risk_level") == "medium", 10).otherwise(0)
            )
        )
    )
    
    # 11. Combinar fraud_score original com adicional
    df_silver = df_silver.withColumn(
        "fraud_score_combined",
        spark_round(col("fraud_score") + (col("fraud_score_additional") * 0.5), 2)
    )
    
    # 12. Determinar nível de risco
    df_silver = df_silver.withColumn(
        "risk_level",
        when(col("fraud_score_combined") >= 80, "CRITICAL")
        .when(col("fraud_score_combined") >= 60, "HIGH")
        .when(col("fraud_score_combined") >= 40, "MEDIUM")
        .when(col("fraud_score_combined") >= 20, "LOW")
        .otherwise("NORMAL")
    )
    
    # 13. Adicionar timestamp de processamento Silver
    df_silver = df_silver.withColumn("silver_processed_at", current_timestamp())
    
    # Selecionar colunas finais
    df_final = df_silver.select(
        "transaction_id",
        "customer_id",
        "session_id",
        "device_id",
        "event_time",
        "transaction_hour",
        "type",
        "amount_clean",
        "currency",
        "channel",
        "ip_address",
        "geolocation_lat",
        "geolocation_lon",
        "merchant_id",
        "merchant_name",
        "merchant_category",
        "mcc_code",
        "mcc_risk_level",
        "card_brand",
        "card_type",
        "installments",
        "card_entry",
        "cvv_validated",
        "auth_3ds",
        "pix_key_type",
        "destination_bank",
        "distance_from_last_txn_km",
        "time_since_last_txn_min",
        "transactions_last_24h",
        "accumulated_amount_24h",
        "unusual_time",
        "new_beneficiary",
        "is_pix_new_beneficiary",
        "is_high_value",
        "is_high_velocity",
        "is_high_accumulated",
        "is_location_jump",
        "is_manual_card_entry",
        "is_no_3ds_online",
        "status",
        "fraud_score",
        "fraud_score_additional",
        "fraud_score_combined",
        "risk_level",
        "is_fraud",
        "fraud_type",
        "silver_processed_at"
    )
    
    print("✅ Transformações aplicadas:")
    print("   - Conversão de timestamp")
    print("   - Limpeza de valores negativos")
    print("   - Flags de risco (PIX novo beneficiário, alto valor, etc)")
    print("   - Fraud score combinado")
    print("   - Classificação de risco")
    
    # Escrever no MinIO (Silver Layer)
    query = df_final.writeStream \
        .format("parquet") \
        .option("path", "s3a://fraud-data/streaming/silver/transactions") \
        .option("checkpointLocation", "s3a://fraud-data/streaming/checkpoints/silver") \
        .outputMode("append") \
        .trigger(processingTime="15 seconds") \
        .start()
    
    print("✅ Escrevendo no MinIO: s3a://fraud-data/streaming/silver/transactions")
    print("")
    print("📊 Streaming ativo!")
    print("=" * 60)
    
    query.awaitTermination()

if __name__ == "__main__":
    main()
