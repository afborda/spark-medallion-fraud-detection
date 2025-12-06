"""
📦 LOAD TO POSTGRES - Gold → PostgreSQL (BATCH)
Carrega dados da camada Gold para PostgreSQL para BI/Metabase

🚀 OTIMIZADO: Escrita paralela com repartition + batchsize

FONTE: s3a://fraud-data/gold/batch/
DESTINO: PostgreSQL (fraud_db)
"""

import sys
sys.path.insert(0, '/jobs')

import time
from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from config import POSTGRES_URL, POSTGRES_PROPERTIES, apply_s3a_configs

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================
GOLD_PATH = "s3a://fraud-data/gold/batch"
NUM_PARTITIONS_LARGE = 16   # Para tabelas grandes
NUM_PARTITIONS_SMALL = 4    # Para tabelas pequenas
BATCH_SIZE = 10000

# Properties otimizadas para PostgreSQL
WRITE_PROPERTIES = POSTGRES_PROPERTIES.copy()
WRITE_PROPERTIES["batchsize"] = str(BATCH_SIZE)
WRITE_PROPERTIES["rewriteBatchedInserts"] = "true"

def main():
    print("=" * 70)
    print("📦 LOAD TO POSTGRES - Gold → PostgreSQL")
    print("🚀 Modo: ESCRITA PARALELA OTIMIZADA")
    print(f"   Partições: {NUM_PARTITIONS_LARGE} (grandes) / {NUM_PARTITIONS_SMALL} (pequenas)")
    print(f"   Batch size: {BATCH_SIZE}")
    print("=" * 70)
    
    spark = apply_s3a_configs(
        SparkSession.builder.appName("Batch_Gold_to_Postgres")
    ).getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    start_total = time.time()
    
    # =========================================================================
    # 1. CARREGAR FRAUD_DETECTION → transactions
    # =========================================================================
    print("\n" + "=" * 50)
    print("💳 Carregando FRAUD_DETECTION → transactions...")
    print(f"   🔀 Partições: {NUM_PARTITIONS_LARGE}")
    print("=" * 50)
    
    start_tx = time.time()
    # Ler parquet incluindo colunas de partição (risk_level)
    df_transactions = spark.read.parquet(f"{GOLD_PATH}/fraud_detection")
    
    # Selecionar campos para PostgreSQL
    df_tx_pg = df_transactions.select(
        "transaction_id",
        "customer_id",
        "timestamp_dt",
        "tx_date",
        "tx_year",
        "tx_month",
        "tx_hour",
        "type",
        "amount",
        "currency",
        "channel",
        "merchant_name",
        "merchant_category",
        "mcc_code",
        "mcc_risk_level",
        "card_brand",
        "card_entry",
        "status",
        "refusal_reason",
        "fraud_score",
        "fraud_score_category",
        "is_fraud",
        "fraud_type",
        "risk_points",
        "risk_level",
        "requires_review",
        "period_of_day",
        "amount_range",
        "is_weekend",
        "_gold_timestamp"
    )
    
    tx_count = df_tx_pg.count()
    print(f"✅ {tx_count:,} transações para carregar")
    
    df_tx_pg.repartition(NUM_PARTITIONS_LARGE).write \
        .mode("overwrite") \
        .option("truncate", "true") \
        .jdbc(POSTGRES_URL, "batch_transactions", properties=WRITE_PROPERTIES)
    
    elapsed_tx = time.time() - start_tx
    throughput_tx = tx_count / elapsed_tx if elapsed_tx > 0 else 0
    print(f"💾 Tabela 'batch_transactions' criada em {elapsed_tx:.1f}s ({throughput_tx:,.0f} reg/s)")
    
    # =========================================================================
    # 2. CARREGAR FRAUD_ALERTS
    # =========================================================================
    print("\n" + "=" * 50)
    print("⚠️ Carregando FRAUD_ALERTS...")
    print(f"   🔀 Partições: {NUM_PARTITIONS_LARGE}")
    print("=" * 50)
    
    start_alerts = time.time()
    df_alerts = spark.read.parquet(f"{GOLD_PATH}/fraud_alerts")
    
    alert_count = df_alerts.count()
    print(f"✅ {alert_count:,} alertas para carregar")
    
    df_alerts.repartition(NUM_PARTITIONS_LARGE).write \
        .mode("overwrite") \
        .option("truncate", "true") \
        .jdbc(POSTGRES_URL, "batch_fraud_alerts", properties=WRITE_PROPERTIES)
    
    elapsed_alerts = time.time() - start_alerts
    throughput_alerts = alert_count / elapsed_alerts if elapsed_alerts > 0 else 0
    print(f"💾 Tabela 'batch_fraud_alerts' criada em {elapsed_alerts:.1f}s ({throughput_alerts:,.0f} reg/s)")
    
    # =========================================================================
    # 3. CARREGAR FRAUD_METRICS
    # =========================================================================
    print("\n" + "=" * 50)
    print("📈 Carregando FRAUD_METRICS...")
    print("=" * 50)
    
    start_metrics = time.time()
    df_metrics = spark.read.parquet(f"{GOLD_PATH}/fraud_metrics")
    
    metrics_count = df_metrics.count()
    print(f"✅ {metrics_count} métricas para carregar")
    
    df_metrics.write \
        .mode("overwrite") \
        .option("truncate", "true") \
        .jdbc(POSTGRES_URL, "batch_fraud_metrics", properties=WRITE_PROPERTIES)
    
    elapsed_metrics = time.time() - start_metrics
    print(f"💾 Tabela 'batch_fraud_metrics' criada em {elapsed_metrics:.1f}s")
    
    # =========================================================================
    # 4. CARREGAR METRICS_BY_TYPE
    # =========================================================================
    print("\n" + "=" * 50)
    print("📊 Carregando METRICS_BY_TYPE...")
    print("=" * 50)
    
    start_type = time.time()
    df_type = spark.read.parquet(f"{GOLD_PATH}/metrics_by_type")
    
    type_count = df_type.count()
    print(f"✅ {type_count} registros para carregar")
    
    df_type.write \
        .mode("overwrite") \
        .option("truncate", "true") \
        .jdbc(POSTGRES_URL, "batch_metrics_by_type", properties=WRITE_PROPERTIES)
    
    elapsed_type = time.time() - start_type
    print(f"💾 Tabela 'batch_metrics_by_type' criada em {elapsed_type:.1f}s")
    
    # =========================================================================
    # 5. CARREGAR METRICS_BY_CHANNEL
    # =========================================================================
    print("\n" + "=" * 50)
    print("📊 Carregando METRICS_BY_CHANNEL...")
    print("=" * 50)
    
    start_channel = time.time()
    df_channel = spark.read.parquet(f"{GOLD_PATH}/metrics_by_channel")
    
    channel_count = df_channel.count()
    print(f"✅ {channel_count} registros para carregar")
    
    df_channel.write \
        .mode("overwrite") \
        .option("truncate", "true") \
        .jdbc(POSTGRES_URL, "batch_metrics_by_channel", properties=WRITE_PROPERTIES)
    
    elapsed_channel = time.time() - start_channel
    print(f"💾 Tabela 'batch_metrics_by_channel' criada em {elapsed_channel:.1f}s")
    
    # =========================================================================
    # SUMÁRIO FINAL
    # =========================================================================
    elapsed_total = time.time() - start_total
    total_records = tx_count + alert_count + metrics_count + type_count + channel_count
    throughput_total = total_records / elapsed_total if elapsed_total > 0 else 0
    
    print("\n" + "=" * 70)
    print("✅ LOAD TO POSTGRES CONCLUÍDO!")
    print("=" * 70)
    print(f"📊 Tabelas criadas no PostgreSQL:")
    print(f"   💳 batch_transactions:      {tx_count:>12,} registros ({elapsed_tx:.1f}s)")
    print(f"   ⚠️  batch_fraud_alerts:      {alert_count:>12,} registros ({elapsed_alerts:.1f}s)")
    print(f"   📈 batch_fraud_metrics:     {metrics_count:>12} registros ({elapsed_metrics:.1f}s)")
    print(f"   📊 batch_metrics_by_type:   {type_count:>12} registros ({elapsed_type:.1f}s)")
    print(f"   📊 batch_metrics_by_channel: {channel_count:>12} registros ({elapsed_channel:.1f}s)")
    print("-" * 70)
    print(f"📦 TOTAL: {total_records:,} registros em {elapsed_total:.1f}s")
    print(f"🚀 Throughput médio: {throughput_total:,.0f} registros/segundo")
    print("=" * 70)
    
    spark.stop()

if __name__ == "__main__":
    main()
