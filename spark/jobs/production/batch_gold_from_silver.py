"""
🥇 GOLD LAYER - MinIO Silver → MinIO Gold (BATCH)
Agregações e tabelas analíticas para detecção de fraude

Este job processa os dados do Silver Layer:
- Lê de: s3a://fraud-data/silver/batch/transactions
- Escreve em: s3a://fraud-data/gold/batch/

Tabelas geradas:
1. fraud_detection: Transações com análise de risco
2. fraud_alerts: Alertas de fraude para investigação
3. fraud_metrics: Métricas agregadas de fraude

TIPO: BATCH (processamento em lote)
FONTE: fraud-generator v4-beta (campos em inglês)
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, when, lit, count, sum as spark_sum, avg, max as spark_max, min as spark_min,
    current_timestamp, round as spark_round, percent_rank, countDistinct,
    first, last, collect_set, array_contains, size, concat_ws
)
from pyspark.sql.window import Window
from config import apply_s3a_configs

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================
SILVER_PATH = "s3a://fraud-data/silver/batch/transactions"
GOLD_PATH = "s3a://fraud-data/gold/batch"
REPARTITION_COUNT = 16

def main():
    print("=" * 70)
    print("🥇 GOLD LAYER - BATCH PROCESSING")
    print("   Fonte: s3a://fraud-data/silver/batch/transactions")
    print("   Destino: s3a://fraud-data/gold/batch/")
    print("=" * 70)
    
    spark = apply_s3a_configs(
        SparkSession.builder
        .appName("Batch_Silver_to_Gold")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
    ).getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    # =========================================================================
    # LER DADOS DO SILVER
    # =========================================================================
    print("\n📂 Lendo dados do Silver...")
    
    # Não usar recursiveFileLookup para preservar partições (tx_year, tx_month)
    df_silver = spark.read.parquet(SILVER_PATH)
    
    total_records = df_silver.count()
    print(f"✅ Lidos {total_records:,} registros do Silver")
    
    # =========================================================================
    # 1. FRAUD DETECTION TABLE
    # =========================================================================
    print("\n" + "=" * 50)
    print("🚨 Criando FRAUD_DETECTION...")
    print("=" * 50)
    
    # Calcular pontos de risco baseado em múltiplos fatores
    df_fraud_detection = df_silver \
        .withColumn("risk_points", lit(0)) \
        .withColumn("risk_points", 
            col("risk_points") +
            # Horário incomum
            when(col("unusual_time"), 15).otherwise(0) +
            # Novo beneficiário
            when(col("new_beneficiary"), 10).otherwise(0) +
            # MCC de alto risco
            when(col("is_high_risk_mcc"), 20).otherwise(0) +
            # Valor alto
            when(col("amount") > 5000, 15).otherwise(0) +
            when(col("amount") > 10000, 15).otherwise(0) +
            # PIX (maior risco)
            when(col("type") == "PIX", 5).otherwise(0) +
            # Sem 3DS
            when(col("auth_3ds") == False, 10).otherwise(0) +
            # CVV não validado
            when(col("cvv_validated") == False, 10).otherwise(0) +
            # Madrugada
            when(col("period_of_day") == "NIGHT", 10).otherwise(0) +
            # Fraud score do gerador
            when(col("fraud_score") > 70, 20).otherwise(
                when(col("fraud_score") > 50, 10).otherwise(0)
            ) +
            # Distância da última transação
            when(col("distance_from_last_txn_km") > 500, 20).otherwise(
                when(col("distance_from_last_txn_km") > 100, 10).otherwise(0)
            ) +
            # Alta velocidade de transações
            when(col("transactions_last_24h") > 20, 15).otherwise(
                when(col("transactions_last_24h") > 10, 8).otherwise(0)
            ) +
            # Valor acumulado alto
            when(col("accumulated_amount_24h") > 50000, 20).otherwise(
                when(col("accumulated_amount_24h") > 20000, 10).otherwise(0)
            ) +
            # Cartão digitado manualmente
            when(col("card_entry") == "MANUAL", 15).otherwise(0)
        ) \
        .withColumn("risk_level",
            when(col("risk_points") >= 50, "CRITICAL")
            .when(col("risk_points") >= 30, "HIGH")
            .when(col("risk_points") >= 15, "MEDIUM")
            .otherwise("LOW")
        ) \
        .withColumn("requires_review",
            (col("risk_level").isin(["CRITICAL", "HIGH"])) | 
            (col("is_fraud") == True)
        ) \
        .withColumn("_gold_timestamp", current_timestamp())
    
    # Selecionar campos para tabela Gold
    df_fraud_gold = df_fraud_detection.select(
        "transaction_id",
        "customer_id",
        "session_id",
        "device_id",
        "timestamp_dt",
        "tx_date",
        "tx_year",
        "tx_month",
        "tx_hour",
        "type",
        "amount",
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
        "card_number_hash",
        "card_brand",
        "card_type",
        "installments",
        "card_entry",
        "cvv_validated",
        "auth_3ds",
        "pix_key_type",
        "pix_key_destination",
        "destination_bank",
        "distance_from_last_txn_km",
        "time_since_last_txn_min",
        "transactions_last_24h",
        "accumulated_amount_24h",
        "unusual_time",
        "new_beneficiary",
        "status",
        "refusal_reason",
        "fraud_score",
        "fraud_score_category",
        "is_fraud",
        "fraud_type",
        "is_high_risk_mcc",
        "period_of_day",
        "amount_range",
        "is_weekend",
        "risk_points",
        "risk_level",
        "requires_review",
        "_gold_timestamp"
    )
    
    fraud_count = df_fraud_gold.count()
    print(f"✅ {fraud_count:,} transações analisadas")
    
    # Estatísticas de risco
    print("\n📊 Distribuição por nível de risco:")
    df_fraud_gold.groupBy("risk_level").count().orderBy("count", ascending=False).show()
    
    df_fraud_gold \
        .repartition(REPARTITION_COUNT) \
        .write \
        .mode("overwrite") \
        .partitionBy("risk_level") \
        .parquet(f"{GOLD_PATH}/fraud_detection")
    
    print(f"💾 Salvo em: {GOLD_PATH}/fraud_detection")
    
    # =========================================================================
    # 2. FRAUD ALERTS TABLE
    # =========================================================================
    print("\n" + "=" * 50)
    print("⚠️ Criando FRAUD_ALERTS...")
    print("=" * 50)
    
    # Apenas transações que requerem investigação
    df_alerts = df_fraud_detection \
        .filter(col("requires_review") == True) \
        .select(
            "transaction_id",
            "customer_id",
            "timestamp_dt",
            "type",
            "amount",
            "merchant_name",
            "merchant_category",
            "risk_points",
            "risk_level",
            "fraud_score",
            "is_fraud",
            "fraud_type",
            "status",
            "distance_from_last_txn_km",
            "transactions_last_24h",
            "accumulated_amount_24h",
            when(col("unusual_time"), "UNUSUAL_TIME").alias("flag_time"),
            when(col("new_beneficiary"), "NEW_BENEFICIARY").alias("flag_beneficiary"),
            when(col("is_high_risk_mcc"), "HIGH_RISK_MCC").alias("flag_mcc"),
            when(col("distance_from_last_txn_km") > 100, "LOCATION_JUMP").alias("flag_location"),
            lit("PENDING").alias("investigation_status"),
            lit("").cast("string").alias("analyst_id"),
            lit("").cast("string").alias("investigation_notes"),
            current_timestamp().alias("created_at")
        )
    
    alert_count = df_alerts.count()
    print(f"✅ {alert_count:,} alertas gerados")
    
    df_alerts \
        .repartition(REPARTITION_COUNT) \
        .write \
        .mode("overwrite") \
        .parquet(f"{GOLD_PATH}/fraud_alerts")
    
    print(f"💾 Salvo em: {GOLD_PATH}/fraud_alerts")
    
    # =========================================================================
    # 3. FRAUD METRICS TABLE
    # =========================================================================
    print("\n" + "=" * 50)
    print("📈 Criando FRAUD_METRICS...")
    print("=" * 50)
    
    # Métricas agregadas por período
    df_metrics = df_fraud_detection \
        .groupBy("tx_year", "tx_month") \
        .agg(
            count("*").alias("total_transactions"),
            spark_round(spark_sum("amount"), 2).alias("total_volume"),
            spark_round(avg("amount"), 2).alias("avg_transaction_value"),
            spark_sum(when(col("is_fraud"), 1).otherwise(0)).alias("fraud_count"),
            spark_sum(when(col("is_fraud"), col("amount")).otherwise(0)).alias("fraud_volume"),
            spark_sum(when(col("risk_level") == "CRITICAL", 1).otherwise(0)).alias("critical_count"),
            spark_sum(when(col("risk_level") == "HIGH", 1).otherwise(0)).alias("high_count"),
            spark_sum(when(col("risk_level") == "MEDIUM", 1).otherwise(0)).alias("medium_count"),
            spark_sum(when(col("risk_level") == "LOW", 1).otherwise(0)).alias("low_count"),
            spark_sum(when(col("status") == "APPROVED", 1).otherwise(0)).alias("approved_count"),
            spark_sum(when(col("status") == "DECLINED", 1).otherwise(0)).alias("declined_count"),
            spark_sum(when(col("status") == "BLOCKED", 1).otherwise(0)).alias("blocked_count"),
            countDistinct("customer_id").alias("unique_customers"),
            spark_round(avg("fraud_score"), 2).alias("avg_fraud_score"),
            # Métricas por tipo
            spark_sum(when(col("type") == "PIX", 1).otherwise(0)).alias("pix_count"),
            spark_sum(when(col("type") == "CREDIT_CARD", 1).otherwise(0)).alias("credit_card_count"),
            spark_sum(when(col("type") == "DEBIT_CARD", 1).otherwise(0)).alias("debit_card_count"),
            spark_sum(when(col("type") == "TED", 1).otherwise(0)).alias("ted_count"),
            spark_sum(when(col("type") == "BOLETO", 1).otherwise(0)).alias("boleto_count"),
        ) \
        .withColumn("fraud_rate", 
            spark_round(col("fraud_count") / col("total_transactions") * 100, 4)
        ) \
        .withColumn("approval_rate",
            spark_round(col("approved_count") / col("total_transactions") * 100, 2)
        ) \
        .withColumn("_gold_timestamp", current_timestamp()) \
        .orderBy("tx_year", "tx_month")
    
    metrics_count = df_metrics.count()
    print(f"✅ {metrics_count} períodos analisados")
    
    df_metrics.show()
    
    df_metrics.write \
        .mode("overwrite") \
        .parquet(f"{GOLD_PATH}/fraud_metrics")
    
    print(f"💾 Salvo em: {GOLD_PATH}/fraud_metrics")
    
    # =========================================================================
    # 4. METRICS BY TYPE TABLE
    # =========================================================================
    print("\n" + "=" * 50)
    print("📊 Criando METRICS_BY_TYPE...")
    print("=" * 50)
    
    df_metrics_type = df_fraud_detection \
        .groupBy("type") \
        .agg(
            count("*").alias("total_transactions"),
            spark_round(spark_sum("amount"), 2).alias("total_volume"),
            spark_round(avg("amount"), 2).alias("avg_amount"),
            spark_sum(when(col("is_fraud"), 1).otherwise(0)).alias("fraud_count"),
            spark_round(avg("fraud_score"), 2).alias("avg_fraud_score"),
            countDistinct("customer_id").alias("unique_customers"),
        ) \
        .withColumn("fraud_rate", 
            spark_round(col("fraud_count") / col("total_transactions") * 100, 4)
        ) \
        .withColumn("_gold_timestamp", current_timestamp())
    
    df_metrics_type.show()
    
    df_metrics_type.write \
        .mode("overwrite") \
        .parquet(f"{GOLD_PATH}/metrics_by_type")
    
    print(f"💾 Salvo em: {GOLD_PATH}/metrics_by_type")
    
    # =========================================================================
    # 5. METRICS BY CHANNEL TABLE
    # =========================================================================
    print("\n" + "=" * 50)
    print("📊 Criando METRICS_BY_CHANNEL...")
    print("=" * 50)
    
    df_metrics_channel = df_fraud_detection \
        .groupBy("channel") \
        .agg(
            count("*").alias("total_transactions"),
            spark_round(spark_sum("amount"), 2).alias("total_volume"),
            spark_round(avg("amount"), 2).alias("avg_amount"),
            spark_sum(when(col("is_fraud"), 1).otherwise(0)).alias("fraud_count"),
            spark_round(avg("fraud_score"), 2).alias("avg_fraud_score"),
            countDistinct("customer_id").alias("unique_customers"),
        ) \
        .withColumn("fraud_rate", 
            spark_round(col("fraud_count") / col("total_transactions") * 100, 4)
        ) \
        .withColumn("_gold_timestamp", current_timestamp())
    
    df_metrics_channel.show()
    
    df_metrics_channel.write \
        .mode("overwrite") \
        .parquet(f"{GOLD_PATH}/metrics_by_channel")
    
    print(f"💾 Salvo em: {GOLD_PATH}/metrics_by_channel")
    
    # =========================================================================
    # SUMÁRIO FINAL
    # =========================================================================
    print("\n" + "=" * 70)
    print("✅ GOLD LAYER CONCLUÍDO!")
    print("=" * 70)
    print(f"📊 Tabelas criadas:")
    print(f"   🚨 fraud_detection:   {fraud_count:,} registros")
    print(f"   ⚠️  fraud_alerts:      {alert_count:,} registros")
    print(f"   📈 fraud_metrics:     {metrics_count} registros")
    print(f"   📊 metrics_by_type:   {df_metrics_type.count()} registros")
    print(f"   📊 metrics_by_channel: {df_metrics_channel.count()} registros")
    print(f"\n💾 Dados salvos em: {GOLD_PATH}/")
    print("=" * 70)
    
    spark.stop()

if __name__ == "__main__":
    main()
