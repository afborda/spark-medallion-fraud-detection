"""
Spark Batch - Bronze para Silver Layer

Processa dados Bronze e cria indicadores de fraude.
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, abs as spark_abs, sqrt, pow as spark_pow,
    current_timestamp, round as spark_round
)
from config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY

def main():
    # Criar SparkSession
    spark = SparkSession.builder \
        .appName("Batch_Bronze_to_Silver") \
        .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
        .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
        .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
        .config("spark.hadoop.fs.s3a.path.style.access", "true") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    print("=" * 60)
    print("🔄 PROCESSANDO BRONZE → SILVER (Batch)")
    print("=" * 60)
    
    # Ler dados Bronze
    df_bronze = spark.read.parquet("s3a://fraud-data/streaming/bronze/transactions")
    
    total_bronze = df_bronze.count()
    print(f"✅ Lidos {total_bronze} registros do Bronze")
    
    # === TRANSFORMAÇÕES SILVER ===
    
    # 1. Limpar valores negativos
    df_clean = df_bronze.withColumn(
        "amount_clean",
        when(col("amount") < 0, spark_abs(col("amount"))).otherwise(col("amount"))
    )
    
    # 2. Distância entre device e compra
    df_clean = df_clean.withColumn(
        "distance_device_purchase",
        spark_round(
            sqrt(
                spark_pow(col("device_latitude") - col("purchase_latitude"), 2) +
                spark_pow(col("device_longitude") - col("purchase_longitude"), 2)
            ), 4
        )
    )
    
    # 3. Flag: Cross-state
    df_clean = df_clean.withColumn(
        "is_cross_state",
        when(col("customer_home_state") != col("purchase_state"), True).otherwise(False)
    )
    
    # 4. Flag: Noturna
    df_clean = df_clean.withColumn(
        "is_night_transaction",
        when(col("transaction_hour") < 6, True).otherwise(False)
    )
    
    # 5. Flag: Valor alto (3x média)
    df_clean = df_clean.withColumn(
        "is_high_value",
        when(col("amount_clean") > col("avg_transaction_amount_30d") * 3, True).otherwise(False)
    )
    
    # 6. Flag: Alta velocidade
    df_clean = df_clean.withColumn(
        "is_high_velocity",
        when(col("transactions_last_24h") > 5, True).otherwise(False)
    )
    
    # 7. Flag: GPS mismatch
    df_clean = df_clean.withColumn(
        "is_gps_mismatch",
        when(col("distance_device_purchase") > 5, True).otherwise(False)
    )
    
    # 8. Flag: Cross-state sem passagem
    df_clean = df_clean.withColumn(
        "is_cross_state_no_travel",
        when(
            (col("is_cross_state") == True) & 
            (col("had_travel_purchase_last_12m") == False),
            True
        ).otherwise(False)
    )
    
    # 9. Calcular FRAUD SCORE
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
    
    # 10. Nível de risco
    df_silver = df_silver.withColumn(
        "risk_level",
        when(col("fraud_score_calculated") >= 70, "CRÍTICO")
        .when(col("fraud_score_calculated") >= 50, "ALTO")
        .when(col("fraud_score_calculated") >= 30, "MÉDIO")
        .when(col("fraud_score_calculated") >= 15, "BAIXO")
        .otherwise("NORMAL")
    )
    
    df_silver = df_silver.withColumn("processed_at", current_timestamp())
    
    # Mostrar estatísticas
    print("\n📊 Distribuição por nível de risco:")
    df_silver.groupBy("risk_level").count().orderBy("count", ascending=False).show()
    
    # Salvar Silver
    df_silver.write \
        .mode("overwrite") \
        .partitionBy("risk_level") \
        .parquet("s3a://fraud-data/streaming/silver/transactions_batch")
    
    print("✅ Silver Layer salvo!")
    
    # === GOLD: Alertas de Alto Risco ===
    df_alerts = df_silver.filter(col("risk_level").isin("ALTO", "CRÍTICO"))
    alerts_count = df_alerts.count()
    
    print(f"\n🚨 {alerts_count} transações de ALTO/CRÍTICO risco encontradas!")
    
    if alerts_count > 0:
        print("\n🔍 Exemplo de transações suspeitas:")
        df_alerts.select(
            "transaction_id", "customer_id", "amount_clean", 
            "customer_home_state", "purchase_state", 
            "fraud_score_calculated", "risk_level"
        ).show(5, truncate=False)
    
    df_alerts.write \
        .mode("overwrite") \
        .parquet("s3a://fraud-data/streaming/gold/fraud_alerts_batch")
    
    print("✅ Alertas de fraude salvos!")
    
    # === GOLD: Métricas por Categoria ===
    df_metrics = df_silver.groupBy("category", "risk_level") \
        .count() \
        .orderBy("category", "risk_level")
    
    print("\n📈 Métricas por categoria:")
    df_metrics.show(20)
    
    df_metrics.write \
        .mode("overwrite") \
        .parquet("s3a://fraud-data/streaming/gold/metrics_batch")
    
    print("✅ Métricas salvas!")
    print("\n" + "=" * 60)
    print("🎉 PROCESSAMENTO CONCLUÍDO!")
    print("=" * 60)
    
    spark.stop()

if __name__ == "__main__":
    main()
