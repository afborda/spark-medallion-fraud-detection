"""
Batch Job - Kafka para PostgreSQL
Lê dados do Kafka e carrega no PostgreSQL (modo batch simples)
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, when, abs as spark_abs, sqrt, pow as spark_pow,
    current_timestamp, round as spark_round, lit
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    BooleanType, LongType, IntegerType
)

# Schema das transações
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

def main():
    print("=" * 60)
    print("🚀 BATCH: KAFKA → POSTGRESQL")
    print("=" * 60)
    
    spark = SparkSession.builder \
        .appName("Kafka_to_PostgreSQL_Batch") \
        .getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    # Ler do Kafka (modo batch)
    print("📡 Lendo dados do Kafka...")
    df_kafka = spark.read \
        .format("kafka") \
        .option("kafka.bootstrap.servers", "fraud_kafka:9092") \
        .option("subscribe", "transactions") \
        .option("startingOffsets", "earliest") \
        .option("endingOffsets", "latest") \
        .load()
    
    total_kafka = df_kafka.count()
    print(f"✅ {total_kafka} mensagens encontradas no Kafka")
    
    if total_kafka == 0:
        print("⚠️ Nenhum dado no Kafka!")
        spark.stop()
        return
    
    # Parsear JSON
    df_transactions = df_kafka \
        .selectExpr("CAST(value AS STRING) as json_value") \
        .select(from_json(col("json_value"), transaction_schema).alias("data")) \
        .select("data.*") \
        .filter(col("transaction_id").isNotNull())
    
    print(f"📊 {df_transactions.count()} transações válidas")
    
    # Aplicar regras de fraude
    print("🔍 Aplicando regras de detecção de fraude...")
    
    df_processed = df_transactions \
        .withColumn("amount_clean", 
            when(col("amount") < 0, spark_abs(col("amount"))).otherwise(col("amount"))) \
        .withColumn("distance_gps",
            spark_round(sqrt(
                spark_pow(col("device_latitude") - col("purchase_latitude"), 2) +
                spark_pow(col("device_longitude") - col("purchase_longitude"), 2)
            ), 4)) \
        .withColumn("is_cross_state",
            when(col("customer_home_state") != col("purchase_state"), True).otherwise(False)) \
        .withColumn("is_night",
            when(col("transaction_hour") < 6, True).otherwise(False)) \
        .withColumn("is_high_value",
            when(col("amount") > col("avg_transaction_amount_30d") * 3, True).otherwise(False))
    
    # Calcular Fraud Score
    df_scored = df_processed.withColumn("fraud_score",
        (when(col("is_cross_state"), 15).otherwise(0) +
         when(col("is_night"), 10).otherwise(0) +
         when(col("is_high_value"), 20).otherwise(0) +
         when(col("distance_gps") > 5, 25).otherwise(0) +
         when((col("is_cross_state")) & (col("had_travel_purchase_last_12m") == False), 30).otherwise(0) +
         when(col("is_first_purchase_in_state"), 10).otherwise(0) +
         when(col("is_international"), 15).otherwise(0) +
         when(col("transactions_last_24h") > 5, 15).otherwise(0))
    )
    
    # Risk Level
    df_final = df_scored.withColumn("risk_level",
        when(col("fraud_score") >= 70, "CRÍTICO")
        .when(col("fraud_score") >= 50, "ALTO")
        .when(col("fraud_score") >= 30, "MÉDIO")
        .when(col("fraud_score") >= 15, "BAIXO")
        .otherwise("NORMAL")
    )
    
    # Mostrar estatísticas
    print("\n📈 ESTATÍSTICAS DE RISCO:")
    df_final.groupBy("risk_level").count().orderBy("count", ascending=False).show()
    
    # Preparar para PostgreSQL
    df_to_postgres = df_final.select(
        col("transaction_id"),
        col("customer_id"),
        col("amount_clean").alias("amount"),
        col("merchant"),
        col("category"),
        col("fraud_score").cast("integer"),
        col("risk_level"),
        col("is_fraud")
    )
    
    # Salvar no PostgreSQL
    print("💾 Salvando no PostgreSQL...")
    
    postgres_url = "jdbc:postgresql://fraud_postgres:5432/fraud_db"
    postgres_props = {
        "user": "fraud_user",
        "password": "fraud_password@@!!_2",
        "driver": "org.postgresql.Driver"
    }
    
    df_to_postgres.write \
        .jdbc(postgres_url, "transactions", mode="append", properties=postgres_props)
    
    print(f"✅ {df_to_postgres.count()} transações salvas na tabela 'transactions'!")
    
    # Alertas de fraude (ALTO e CRÍTICO)
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
            .jdbc(postgres_url, "fraud_alerts", mode="append", properties=postgres_props)
        print(f"🚨 {alerts_count} ALERTAS de fraude salvos!")
    
    print("\n" + "=" * 60)
    print("✅ PROCESSAMENTO CONCLUÍDO!")
    print("=" * 60)
    
    spark.stop()

if __name__ == "__main__":
    main()
