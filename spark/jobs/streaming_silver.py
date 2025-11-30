"""
Spark Streaming - Bronze para Silver Layer

Lê dados Bronze, aplica limpeza e cria indicadores de fraude.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, abs as spark_abs, sqrt, pow as spark_pow,
    current_timestamp, round as spark_round, lit
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    BooleanType, LongType, IntegerType, TimestampType
)

# Schema dos dados Bronze
bronze_schema = StructType([
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
    StructField("timestamp", LongType(), True),
    StructField("processed_at", TimestampType(), True)
])

def main():
    # Criar SparkSession
    spark = SparkSession.builder \
        .appName("Streaming_Bronze_to_Silver") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123@@!!_2") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    print("=" * 60)
    print("🔄 INICIANDO STREAMING - BRONZE → SILVER")
    print("=" * 60)
    
    # Ler dados Bronze como streaming
    df_bronze = spark.readStream \
        .format("parquet") \
        .schema(bronze_schema) \
        .option("path", "s3a://fraud-data/streaming/bronze/transactions") \
        .load()
    
    print("✅ Lendo Bronze Layer")
    
    # === TRANSFORMAÇÕES SILVER ===
    
    # 1. Limpar valores negativos de amount
    df_clean = df_bronze.withColumn(
        "amount_clean", 
        when(col("amount") < 0, spark_abs(col("amount"))).otherwise(col("amount"))
    )
    
    # 2. Calcular distância entre device e compra (fórmula simplificada)
    # Distância em graus (aproximada)
    df_clean = df_clean.withColumn(
        "distance_device_purchase",
        spark_round(
            sqrt(
                spark_pow(col("device_latitude") - col("purchase_latitude"), 2) +
                spark_pow(col("device_longitude") - col("purchase_longitude"), 2)
            ),
            4
        )
    )
    
    # 3. Flag: Compra em estado diferente do domicílio
    df_clean = df_clean.withColumn(
        "is_cross_state",
        when(col("customer_home_state") != col("purchase_state"), True).otherwise(False)
    )
    
    # 4. Flag: Compra na madrugada (00h-06h)
    df_clean = df_clean.withColumn(
        "is_night_transaction",
        when(col("transaction_hour") < 6, True).otherwise(False)
    )
    
    # 5. Flag: Valor muito acima da média (3x)
    df_clean = df_clean.withColumn(
        "is_high_value",
        when(col("amount_clean") > col("avg_transaction_amount_30d") * 3, True).otherwise(False)
    )
    
    # 6. Flag: Muitas transações em 24h (> 5)
    df_clean = df_clean.withColumn(
        "is_high_velocity",
        when(col("transactions_last_24h") > 5, True).otherwise(False)
    )
    
    # 7. Flag: GPS muito distante (> 5 graus ≈ 500km)
    df_clean = df_clean.withColumn(
        "is_gps_mismatch",
        when(col("distance_device_purchase") > 5, True).otherwise(False)
    )
    
    # 8. Flag: Cross-state sem passagem nos últimos 12 meses
    df_clean = df_clean.withColumn(
        "is_cross_state_no_travel",
        when(
            (col("is_cross_state") == True) & 
            (col("had_travel_purchase_last_12m") == False),
            True
        ).otherwise(False)
    )
    
    # 9. Calcular FRAUD SCORE baseado nos indicadores
    df_silver = df_clean.withColumn(
        "fraud_score_calculated",
        (
            when(col("is_cross_state"), 15).otherwise(0) +
            when(col("is_night_transaction"), 10).otherwise(0) +
            when(col("is_high_value"), 20).otherwise(0) +
            when(col("is_high_velocity"), 15).otherwise(0) +
            when(col("is_gps_mismatch"), 25).otherwise(0) +
            when(col("is_cross_state_no_travel"), 30).otherwise(0) +
            when(col("is_first_purchase_in_state"), 10).otherwise(0) +
            when(col("is_international"), 15).otherwise(0)
        )
    )
    
    # 10. Determinar nível de risco
    df_silver = df_silver.withColumn(
        "risk_level",
        when(col("fraud_score_calculated") >= 70, "CRÍTICO")
        .when(col("fraud_score_calculated") >= 50, "ALTO")
        .when(col("fraud_score_calculated") >= 30, "MÉDIO")
        .when(col("fraud_score_calculated") >= 15, "BAIXO")
        .otherwise("NORMAL")
    )
    
    # 11. Adicionar timestamp de processamento
    df_silver = df_silver.withColumn("processed_at", current_timestamp())
    
    # Selecionar colunas finais
    df_final = df_silver.select(
        "transaction_id",
        "customer_id",
        "amount_clean",
        "merchant",
        "category",
        "transaction_hour",
        "day_of_week",
        "customer_home_state",
        "purchase_state",
        "purchase_city",
        "payment_method",
        "card_brand",
        "installments",
        "distance_device_purchase",
        "is_cross_state",
        "is_night_transaction",
        "is_high_value",
        "is_high_velocity",
        "is_gps_mismatch",
        "is_cross_state_no_travel",
        "is_first_purchase_in_state",
        "is_international",
        "is_online",
        "fraud_score_calculated",
        "risk_level",
        "is_fraud",
        "timestamp",
        "processed_at"
    )
    
    print("✅ Transformações aplicadas:")
    print("   - Limpeza de valores negativos")
    print("   - Cálculo de distância GPS")
    print("   - Flags de comportamento suspeito")
    print("   - Fraud Score calculado")
    print("   - Nível de risco atribuído")
    
    # Escrever no Silver Layer
    query = df_final.writeStream \
        .format("parquet") \
        .option("path", "s3a://fraud-data/streaming/silver/transactions") \
        .option("checkpointLocation", "s3a://fraud-data/streaming/checkpoints/silver_transactions") \
        .outputMode("append") \
        .trigger(processingTime="15 seconds") \
        .start()
    
    print("")
    print("✅ Escrevendo no MinIO: s3a://fraud-data/streaming/silver/transactions")
    print("")
    print("📊 Streaming Silver ativo!")
    print("=" * 60)
    
    query.awaitTermination()

if __name__ == "__main__":
    main()
