"""
Spark Streaming - Silver para Gold Layer

Gera métricas agregadas e identifica fraudes em tempo real.
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, count, sum as spark_sum, avg, max as spark_max,
    current_timestamp, window, when
)

def main():
    # Criar SparkSession
    spark = SparkSession.builder \
        .appName("Streaming_Silver_to_Gold") \
        .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
        .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
        .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123@@!!_2") \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    print("=" * 60)
    print("🏆 INICIANDO STREAMING - SILVER → GOLD")
    print("=" * 60)
    
    # Ler dados Silver como streaming
    df_silver = spark.readStream \
        .format("parquet") \
        .option("path", "s3a://fraud-data/streaming/silver/transactions") \
        .load()
    
    print("✅ Lendo Silver Layer")
    
    # === GOLD 1: Transações de Alto Risco ===
    # Filtrar apenas transações com risco ALTO ou CRÍTICO
    df_high_risk = df_silver.filter(
        col("risk_level").isin("ALTO", "CRÍTICO")
    ).select(
        "transaction_id",
        "customer_id", 
        "amount_clean",
        "merchant",
        "category",
        "customer_home_state",
        "purchase_state",
        "purchase_city",
        "fraud_score_calculated",
        "risk_level",
        "is_cross_state_no_travel",
        "is_gps_mismatch",
        "is_high_value",
        "is_fraud",
        "processed_at"
    )
    
    # Escrever alertas de alto risco
    query_alerts = df_high_risk.writeStream \
        .format("parquet") \
        .option("path", "s3a://fraud-data/streaming/gold/fraud_alerts") \
        .option("checkpointLocation", "s3a://fraud-data/streaming/checkpoints/gold_alerts") \
        .outputMode("append") \
        .trigger(processingTime="15 seconds") \
        .start()
    
    print("✅ Gold 1: Alertas de fraude sendo salvos")
    
    # === GOLD 2: Métricas por Categoria ===
    df_metrics_category = df_silver.groupBy("category", "risk_level") \
        .agg(
            count("*").alias("total_transactions"),
            spark_sum("amount_clean").alias("total_amount"),
            avg("amount_clean").alias("avg_amount"),
            avg("fraud_score_calculated").alias("avg_fraud_score")
        )
    
    query_category = df_metrics_category.writeStream \
        .format("parquet") \
        .option("path", "s3a://fraud-data/streaming/gold/metrics_by_category") \
        .option("checkpointLocation", "s3a://fraud-data/streaming/checkpoints/gold_category") \
        .outputMode("complete") \
        .trigger(processingTime="30 seconds") \
        .start()
    
    print("✅ Gold 2: Métricas por categoria sendo agregadas")
    
    # === GOLD 3: Métricas por Estado ===
    df_metrics_state = df_silver.groupBy("purchase_state", "risk_level") \
        .agg(
            count("*").alias("total_transactions"),
            spark_sum(when(col("is_fraud") == True, 1).otherwise(0)).alias("total_frauds"),
            avg("fraud_score_calculated").alias("avg_fraud_score")
        )
    
    query_state = df_metrics_state.writeStream \
        .format("parquet") \
        .option("path", "s3a://fraud-data/streaming/gold/metrics_by_state") \
        .option("checkpointLocation", "s3a://fraud-data/streaming/checkpoints/gold_state") \
        .outputMode("complete") \
        .trigger(processingTime="30 seconds") \
        .start()
    
    print("✅ Gold 3: Métricas por estado sendo agregadas")
    
    print("")
    print("📊 Streaming Gold ativo!")
    print("   - Alertas de fraude")
    print("   - Métricas por categoria")
    print("   - Métricas por estado")
    print("=" * 60)
    
    # Aguardar todas as queries
    spark.streams.awaitAnyTermination()

if __name__ == "__main__":
    main()
