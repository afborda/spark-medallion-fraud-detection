"""
🥈 SILVER LAYER - MinIO Bronze → MinIO Silver (BATCH)
Limpeza e transformação de dados do Bronze para Silver

Este job processa os dados do Bronze Layer:
- Lê de: s3a://fraud-data/bronze/batch/transactions
- Escreve em: s3a://fraud-data/silver/batch/transactions

TIPO: BATCH (processamento em lote)
FONTE: fraud-generator v4-beta (campos em inglês)
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, lit, trim, upper, lower, 
    to_timestamp, to_date, current_timestamp,
    regexp_replace, coalesce, year, month, dayofweek, hour,
    round as spark_round, abs as spark_abs, concat_ws
)
from config import apply_s3a_configs

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================
BRONZE_PATH = "s3a://fraud-data/bronze/batch/transactions"
SILVER_PATH = "s3a://fraud-data/silver/batch/transactions"
REPARTITION_COUNT = 16

def main():
    print("=" * 70)
    print("🥈 SILVER LAYER - BATCH PROCESSING")
    print("   Fonte: s3a://fraud-data/bronze/batch/transactions")
    print("   Destino: s3a://fraud-data/silver/batch/transactions")
    print("=" * 70)
    
    spark = apply_s3a_configs(
        SparkSession.builder
        .appName("Batch_Bronze_to_Silver")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
    ).getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    # =========================================================================
    # LER DADOS DO BRONZE
    # =========================================================================
    print("\n📂 Lendo dados do Bronze...")
    
    df_bronze = spark.read \
        .option("recursiveFileLookup", "true") \
        .parquet(BRONZE_PATH)
    
    total_records = df_bronze.count()
    print(f"✅ Lidos {total_records:,} registros do Bronze")
    
    # =========================================================================
    # TRANSFORMAÇÕES SILVER
    # =========================================================================
    print("\n🔄 Aplicando transformações Silver...")
    
    df_silver = df_bronze \
        .dropDuplicates(["transaction_id"]) \
        .withColumn("timestamp_dt", to_timestamp(col("timestamp"))) \
        .withColumn("amount", spark_round(col("amount"), 2)) \
        .withColumn("tx_date", to_date(col("timestamp"))) \
        .withColumn("tx_year", year(col("timestamp"))) \
        .withColumn("tx_month", month(col("timestamp"))) \
        .withColumn("tx_hour", hour(col("timestamp"))) \
        .withColumn("tx_dayofweek", dayofweek(col("timestamp"))) \
        .withColumn("is_weekend", 
            when((col("tx_dayofweek") == 1) | (col("tx_dayofweek") == 7), True)
            .otherwise(False)
        ) \
        .withColumn("period_of_day",
            when(col("tx_hour").between(6, 11), "MORNING")
            .when(col("tx_hour").between(12, 17), "AFTERNOON")
            .when(col("tx_hour").between(18, 22), "EVENING")
            .otherwise("NIGHT")
        ) \
        .withColumn("amount_range",
            when(col("amount") < 50, "MICRO")
            .when(col("amount") < 200, "SMALL")
            .when(col("amount") < 1000, "MEDIUM")
            .when(col("amount") < 5000, "LARGE")
            .otherwise("VERY_LARGE")
        ) \
        .withColumn("is_high_risk_mcc", 
            col("mcc_risk_level").isin(["high", "HIGH"])
        ) \
        .withColumn("fraud_score_category",
            when(col("fraud_score") < 30, "LOW")
            .when(col("fraud_score") < 60, "MEDIUM")
            .when(col("fraud_score") < 80, "HIGH")
            .otherwise("CRITICAL")
        ) \
        .withColumn("channel_upper", upper(trim(col("channel")))) \
        .withColumn("type_upper", upper(trim(col("type")))) \
        .withColumn("card_brand_upper", 
            when(col("card_brand").isNotNull(), upper(trim(col("card_brand"))))
            .otherwise(lit(None))
        ) \
        .withColumn("_silver_timestamp", current_timestamp())
    
    # =========================================================================
    # REPARTITION E ESCRITA
    # =========================================================================
    silver_count = df_silver.count()
    print(f"✅ {silver_count:,} registros após transformação")
    
    print(f"\n📊 Reparticionando para {REPARTITION_COUNT} partições...")
    df_silver = df_silver.repartition(REPARTITION_COUNT)
    
    print(f"\n💾 Escrevendo no Silver: {SILVER_PATH}")
    df_silver.write \
        .mode("overwrite") \
        .partitionBy("tx_year", "tx_month") \
        .parquet(SILVER_PATH)
    
    # =========================================================================
    # ESTATÍSTICAS
    # =========================================================================
    print("\n" + "=" * 70)
    print("✅ SILVER LAYER CONCLUÍDO!")
    print(f"   📊 Registros processados: {silver_count:,}")
    print(f"   📂 Destino: {SILVER_PATH}")
    print("=" * 70)
    
    print("\n📈 Distribuição por tipo de transação:")
    df_silver.groupBy("type").count().orderBy("count", ascending=False).show(10)
    
    print("\n📈 Distribuição por faixa de valor:")
    df_silver.groupBy("amount_range").count().orderBy("count", ascending=False).show()
    
    print("\n📈 Distribuição por categoria de fraud_score:")
    df_silver.groupBy("fraud_score_category").count().orderBy("count", ascending=False).show()
    
    spark.stop()

if __name__ == "__main__":
    main()
