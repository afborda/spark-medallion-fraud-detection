"""
Spark Streaming - Pipeline Real-Time para Dashboard

Este job:
1. Lê transações do Kafka em tempo real
2. Aplica regras de detecção de fraude
3. Calcula métricas agregadas
4. Escreve no PostgreSQL para visualização no Metabase
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, current_timestamp, window, count, sum as spark_sum,
    avg, max as spark_max, min as spark_min, when, lit, expr,
    date_format, hour, minute, round as spark_round
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    BooleanType, LongType, IntegerType, TimestampType
)
from datetime import datetime

# Schema das transações do ShadowTraffic
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

# Configurações
KAFKA_BROKER = "kafka:9092"
KAFKA_TOPIC = "transactions"
POSTGRES_URL = "jdbc:postgresql://postgres:5432/fraud_db"
POSTGRES_USER = "fraud_user"
POSTGRES_PASSWORD = "fraud_password@@!!_2"

def create_postgres_tables(spark):
    """Cria tabelas no PostgreSQL se não existirem"""
    
    # Conectar via JDBC para criar tabelas
    driver = "org.postgresql.Driver"
    
    create_tables_sql = """
    -- Tabela de métricas em tempo real (atualizada a cada batch)
    CREATE TABLE IF NOT EXISTS streaming_metrics (
        id SERIAL PRIMARY KEY,
        window_start TIMESTAMP,
        window_end TIMESTAMP,
        total_transactions BIGINT,
        total_amount DECIMAL(18,2),
        fraud_count BIGINT,
        fraud_amount DECIMAL(18,2),
        fraud_rate DECIMAL(5,4),
        avg_amount DECIMAL(18,2),
        max_amount DECIMAL(18,2),
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Tabela de métricas por categoria
    CREATE TABLE IF NOT EXISTS streaming_metrics_by_category (
        id SERIAL PRIMARY KEY,
        window_start TIMESTAMP,
        window_end TIMESTAMP,
        category VARCHAR(100),
        transaction_count BIGINT,
        total_amount DECIMAL(18,2),
        fraud_count BIGINT,
        fraud_rate DECIMAL(5,4),
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Tabela de métricas por estado
    CREATE TABLE IF NOT EXISTS streaming_metrics_by_state (
        id SERIAL PRIMARY KEY,
        window_start TIMESTAMP,
        window_end TIMESTAMP,
        state VARCHAR(50),
        transaction_count BIGINT,
        total_amount DECIMAL(18,2),
        fraud_count BIGINT,
        fraud_rate DECIMAL(5,4),
        processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Tabela de fraudes detectadas (últimas fraudes)
    CREATE TABLE IF NOT EXISTS streaming_recent_frauds (
        id SERIAL PRIMARY KEY,
        transaction_id VARCHAR(100),
        customer_id VARCHAR(100),
        amount DECIMAL(18,2),
        merchant VARCHAR(200),
        category VARCHAR(100),
        purchase_state VARCHAR(50),
        purchase_city VARCHAR(100),
        payment_method VARCHAR(50),
        card_brand VARCHAR(50),
        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    -- Índices para performance
    CREATE INDEX IF NOT EXISTS idx_streaming_metrics_window ON streaming_metrics(window_start DESC);
    CREATE INDEX IF NOT EXISTS idx_streaming_metrics_cat_window ON streaming_metrics_by_category(window_start DESC);
    CREATE INDEX IF NOT EXISTS idx_streaming_metrics_state_window ON streaming_metrics_by_state(window_start DESC);
    CREATE INDEX IF NOT EXISTS idx_recent_frauds_detected ON streaming_recent_frauds(detected_at DESC);
    """
    
    print("📊 Criando tabelas no PostgreSQL...")
    
    # Usar psycopg2 via subprocess para criar tabelas
    import subprocess
    result = subprocess.run([
        'psql', '-h', 'postgres', '-U', POSTGRES_USER, '-d', 'fraud_db', '-c', create_tables_sql
    ], capture_output=True, text=True, env={'PGPASSWORD': POSTGRES_PASSWORD})
    
    if result.returncode == 0:
        print("✅ Tabelas criadas/verificadas com sucesso")
    else:
        print(f"⚠️ Aviso ao criar tabelas: {result.stderr}")


def write_to_postgres(df, epoch_id, table_name, mode="append"):
    """Escreve DataFrame no PostgreSQL"""
    if df.count() > 0:
        df.write \
            .format("jdbc") \
            .option("url", POSTGRES_URL) \
            .option("dbtable", table_name) \
            .option("user", POSTGRES_USER) \
            .option("password", POSTGRES_PASSWORD) \
            .option("driver", "org.postgresql.Driver") \
            .mode(mode) \
            .save()


def process_batch_metrics(batch_df, epoch_id):
    """Processa cada micro-batch e escreve métricas no PostgreSQL"""
    
    if batch_df.count() == 0:
        print(f"📭 Batch {epoch_id}: Vazio, pulando...")
        return
    
    print(f"\n{'='*60}")
    print(f"📦 Processando Batch {epoch_id}")
    print(f"{'='*60}")
    
    # Adicionar timestamp de processamento
    batch_df = batch_df.withColumn("event_time", 
        (col("timestamp") / 1000).cast(TimestampType())
    )
    
    # 1. MÉTRICAS GERAIS (janela de 1 minuto)
    metrics_df = batch_df.groupBy(
        window(col("event_time"), "1 minute")
    ).agg(
        count("*").alias("total_transactions"),
        spark_round(spark_sum("amount"), 2).alias("total_amount"),
        spark_sum(when(col("is_fraud") == True, 1).otherwise(0)).alias("fraud_count"),
        spark_round(spark_sum(when(col("is_fraud") == True, col("amount")).otherwise(0)), 2).alias("fraud_amount"),
        spark_round(avg("amount"), 2).alias("avg_amount"),
        spark_round(spark_max("amount"), 2).alias("max_amount")
    ).withColumn(
        "fraud_rate", 
        spark_round(col("fraud_count") / col("total_transactions"), 4)
    ).withColumn(
        "window_start", col("window.start")
    ).withColumn(
        "window_end", col("window.end")
    ).withColumn(
        "processed_at", current_timestamp()
    ).select(
        "window_start", "window_end", "total_transactions", "total_amount",
        "fraud_count", "fraud_amount", "fraud_rate", "avg_amount", "max_amount", "processed_at"
    )
    
    # Escrever métricas gerais
    write_to_postgres(metrics_df, epoch_id, "streaming_metrics")
    
    tx_count = batch_df.count()
    fraud_count = batch_df.filter(col("is_fraud") == True).count()
    total_amount = batch_df.agg(spark_sum("amount")).collect()[0][0] or 0
    
    print(f"   📈 Transações: {tx_count}")
    print(f"   🚨 Fraudes: {fraud_count} ({(fraud_count/tx_count*100):.2f}%)")
    print(f"   💰 Valor Total: R$ {total_amount:,.2f}")
    
    # 2. MÉTRICAS POR CATEGORIA
    cat_metrics_df = batch_df.groupBy(
        window(col("event_time"), "1 minute"),
        col("category")
    ).agg(
        count("*").alias("transaction_count"),
        spark_round(spark_sum("amount"), 2).alias("total_amount"),
        spark_sum(when(col("is_fraud") == True, 1).otherwise(0)).alias("fraud_count")
    ).withColumn(
        "fraud_rate",
        spark_round(col("fraud_count") / col("transaction_count"), 4)
    ).withColumn(
        "window_start", col("window.start")
    ).withColumn(
        "window_end", col("window.end")
    ).withColumn(
        "processed_at", current_timestamp()
    ).select(
        "window_start", "window_end", "category", "transaction_count", 
        "total_amount", "fraud_count", "fraud_rate", "processed_at"
    )
    
    write_to_postgres(cat_metrics_df, epoch_id, "streaming_metrics_by_category")
    
    # 3. MÉTRICAS POR ESTADO
    state_metrics_df = batch_df.groupBy(
        window(col("event_time"), "1 minute"),
        col("purchase_state").alias("state")
    ).agg(
        count("*").alias("transaction_count"),
        spark_round(spark_sum("amount"), 2).alias("total_amount"),
        spark_sum(when(col("is_fraud") == True, 1).otherwise(0)).alias("fraud_count")
    ).withColumn(
        "fraud_rate",
        spark_round(col("fraud_count") / col("transaction_count"), 4)
    ).withColumn(
        "window_start", col("window.start")
    ).withColumn(
        "window_end", col("window.end")
    ).withColumn(
        "processed_at", current_timestamp()
    ).select(
        "window_start", "window_end", "state", "transaction_count",
        "total_amount", "fraud_count", "fraud_rate", "processed_at"
    )
    
    write_to_postgres(state_metrics_df, epoch_id, "streaming_metrics_by_state")
    
    # 4. FRAUDES RECENTES (últimas 100)
    frauds_df = batch_df.filter(col("is_fraud") == True) \
        .select(
            "transaction_id", "customer_id", "amount", "merchant",
            "category", "purchase_state", "purchase_city", 
            "payment_method", "card_brand"
        ).withColumn("detected_at", current_timestamp()) \
        .limit(100)
    
    if frauds_df.count() > 0:
        write_to_postgres(frauds_df, epoch_id, "streaming_recent_frauds")
        print(f"   🔴 {frauds_df.count()} fraudes registradas!")
    
    print(f"✅ Batch {epoch_id} processado e salvo no PostgreSQL")


def main():
    print("=" * 70)
    print("🚀 SPARK STREAMING - PIPELINE REAL-TIME PARA DASHBOARD")
    print("=" * 70)
    print(f"📅 Iniciado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📡 Kafka: {KAFKA_BROKER} / Tópico: {KAFKA_TOPIC}")
    print(f"🗄️ PostgreSQL: {POSTGRES_URL}")
    print("=" * 70)
    
    # Criar SparkSession
    spark = SparkSession.builder \
        .appName("Streaming_Realtime_Dashboard") \
        .config("spark.sql.streaming.metricsEnabled", "true") \
        .config("spark.sql.shuffle.partitions", "4") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    print("\n✅ SparkSession criada")
    
    # Ler do Kafka
    df_kafka = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", KAFKA_BROKER) \
        .option("subscribe", KAFKA_TOPIC) \
        .option("startingOffsets", "latest") \
        .option("maxOffsetsPerTrigger", "10000") \
        .load()
    
    print("✅ Conectado ao Kafka")
    
    # Parse JSON
    df_transactions = df_kafka \
        .selectExpr("CAST(value AS STRING) as json_value") \
        .select(from_json(col("json_value"), transaction_schema).alias("data")) \
        .select("data.*") \
        .filter(col("transaction_id").isNotNull())
    
    print("✅ Schema aplicado")
    
    # Streaming query com foreachBatch para escrever no PostgreSQL
    query = df_transactions.writeStream \
        .foreachBatch(process_batch_metrics) \
        .outputMode("update") \
        .trigger(processingTime="30 seconds") \
        .option("checkpointLocation", "/tmp/streaming_dashboard_checkpoint") \
        .start()
    
    print("\n" + "=" * 70)
    print("📊 STREAMING ATIVO - Métricas sendo enviadas ao PostgreSQL")
    print("   🔄 Atualização: a cada 30 segundos")
    print("   📈 Dashboard: http://localhost:3000 (Metabase)")
    print("   ⏹️ Pressione Ctrl+C para parar")
    print("=" * 70 + "\n")
    
    query.awaitTermination()


if __name__ == "__main__":
    main()
