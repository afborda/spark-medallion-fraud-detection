"""
🥈 SILVER LAYER - Limpeza e Transformação
Transforma dados brutos do Bronze em dados limpos e padronizados

Transformações aplicadas:
- Conversão de tipos (timestamps, valores numéricos)
- Remoção de duplicatas
- Padronização de strings
- Tratamento de nulos
- Criação de campos derivados
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
from pyspark.sql.types import *
from config import MINIO_ENDPOINT, MINIO_ACCESS_KEY, MINIO_SECRET_KEY, BRONZE_PATH, SILVER_PATH

print("=" * 60)
print("🥈 SILVER LAYER - Limpeza e Transformação")
print("🇧🇷 Dados brasileiros")
print("=" * 60)

# JARs para S3/MinIO
JARS_PATH = "/jars"
HADOOP_AWS = f"{JARS_PATH}/hadoop-aws-3.3.4.jar"
AWS_SDK = f"{JARS_PATH}/aws-java-sdk-bundle-1.12.262.jar"

spark = SparkSession.builder \
    .appName("Silver_Transform") \
    .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT) \
    .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY) \
    .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY) \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
    .config("spark.sql.adaptive.enabled", "true") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# Diretórios
BRONZE_BASE = BRONZE_PATH
SILVER_BASE = SILVER_PATH

# ============================================
# 1. TRANSFORMAR CLIENTES
# ============================================
print("\n" + "=" * 40)
print("🧑 Transformando CLIENTES...")
print("=" * 40)

df_customers = spark.read.parquet(f"{BRONZE_BASE}/customers")

# Limpeza e transformação
df_customers_silver = df_customers \
    .dropDuplicates(["customer_id"]) \
    .withColumn("cpf_limpo", regexp_replace(col("cpf"), r"[^\d]", "")) \
    .withColumn("telefone_limpo", regexp_replace(col("telefone_celular"), r"[^\d]", "")) \
    .withColumn("cep_limpo", regexp_replace(col("cep"), r"[^\d]", "")) \
    .withColumn("data_nascimento_dt", to_date(col("data_nascimento"))) \
    .withColumn("data_cadastro_dt", to_date(col("data_cadastro"))) \
    .withColumn("estado_upper", upper(trim(col("estado")))) \
    .withColumn("cidade_clean", trim(col("cidade"))) \
    .withColumn("nome_upper", upper(trim(col("nome_completo")))) \
    .withColumn("email_lower", lower(trim(col("email")))) \
    .withColumn("renda_mensal", spark_round(col("renda_mensal"), 2)) \
    .withColumn("limite_credito", spark_round(col("limite_credito"), 2)) \
    .withColumn("faixa_renda", 
        when(col("renda_mensal") < 2000, "ATÉ 2 SM")
        .when(col("renda_mensal") < 5000, "2-5 SM")
        .when(col("renda_mensal") < 10000, "5-10 SM")
        .when(col("renda_mensal") < 20000, "10-20 SM")
        .otherwise("ACIMA 20 SM")
    ) \
    .withColumn("faixa_score", 
        when(col("score_credito") < 400, "MUITO_BAIXO")
        .when(col("score_credito") < 500, "BAIXO")
        .when(col("score_credito") < 650, "MEDIO")
        .when(col("score_credito") < 750, "BOM")
        .otherwise("EXCELENTE")
    ) \
    .withColumn("_silver_timestamp", current_timestamp())

# Selecionar colunas finais
df_customers_final = df_customers_silver.select(
    "customer_id",
    "cpf_limpo",
    "rg",
    "nome_completo",
    "nome_upper",
    "nome_social",
    "data_nascimento_dt",
    "sexo",
    "estado_civil",
    "email_lower",
    "telefone_limpo",
    "telefone_fixo",
    "cep_limpo",
    "logradouro",
    "numero",
    "complemento",
    "bairro",
    "cidade_clean",
    "estado_upper",
    "banco_codigo",
    "banco_nome",
    "agencia",
    "conta",
    "tipo_conta",
    "profissao",
    "renda_mensal",
    "faixa_renda",
    "score_credito",
    "faixa_score",
    "limite_credito",
    "limite_pix_diario",
    "perfil_investidor",
    "pep",
    "data_cadastro_dt",
    "status",
    "nivel_verificacao",
    "is_premium",
    "aceita_marketing",
    "biometria_facial",
    "token_ativo",
    "_silver_timestamp",
)

customer_count = df_customers_final.count()
print(f"✅ {customer_count:,} clientes transformados")

df_customers_final.write.mode("overwrite").parquet(f"{SILVER_BASE}/customers")
print(f"💾 Clientes salvos em: {SILVER_BASE}/customers")

# ============================================
# 2. TRANSFORMAR DISPOSITIVOS
# ============================================
print("\n" + "=" * 40)
print("📱 Transformando DISPOSITIVOS...")
print("=" * 40)

df_devices = spark.read.parquet(f"{BRONZE_BASE}/devices")

df_devices_silver = df_devices \
    .dropDuplicates(["device_id"]) \
    .withColumn("first_seen_ts", to_timestamp(col("first_seen"))) \
    .withColumn("last_seen_ts", to_timestamp(col("last_seen"))) \
    .withColumn("os_full", concat_ws(" ", col("os_name"), col("os_version"))) \
    .withColumn("device_risk_category",
        when(col("is_rooted") | col("is_emulator"), "HIGH_RISK")
        .when(col("risk_score") > 70, "MEDIUM_RISK")
        .otherwise("LOW_RISK")
    ) \
    .withColumn("_silver_timestamp", current_timestamp())

device_count = df_devices_silver.count()
print(f"✅ {device_count:,} dispositivos transformados")

df_devices_silver.write.mode("overwrite").parquet(f"{SILVER_BASE}/devices")
print(f"💾 Dispositivos salvos em: {SILVER_BASE}/devices")

# ============================================
# 3. TRANSFORMAR TRANSAÇÕES
# ============================================
print("\n" + "=" * 40)
print("💳 Transformando TRANSAÇÕES...")
print("=" * 40)

df_transactions = spark.read.parquet(f"{BRONZE_BASE}/transactions")

df_transactions_silver = df_transactions \
    .dropDuplicates(["transaction_id"]) \
    .withColumn("timestamp_dt", to_timestamp(col("timestamp"))) \
    .withColumn("valor", spark_round(col("valor"), 2)) \
    .withColumn("tx_date", to_date(col("timestamp"))) \
    .withColumn("tx_year", year(col("timestamp"))) \
    .withColumn("tx_month", month(col("timestamp"))) \
    .withColumn("tx_hour", hour(col("timestamp"))) \
    .withColumn("tx_dayofweek", dayofweek(col("timestamp"))) \
    .withColumn("is_weekend", 
        when((col("tx_dayofweek") == 1) | (col("tx_dayofweek") == 7), True)
        .otherwise(False)
    ) \
    .withColumn("periodo_dia",
        when(col("tx_hour").between(6, 11), "MANHA")
        .when(col("tx_hour").between(12, 17), "TARDE")
        .when(col("tx_hour").between(18, 22), "NOITE")
        .otherwise("MADRUGADA")
    ) \
    .withColumn("faixa_valor",
        when(col("valor") < 50, "MICRO")
        .when(col("valor") < 200, "PEQUENO")
        .when(col("valor") < 1000, "MEDIO")
        .when(col("valor") < 5000, "GRANDE")
        .otherwise("MUITO_GRANDE")
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
    .withColumn("_silver_timestamp", current_timestamp())

tx_count = df_transactions_silver.count()
print(f"✅ {tx_count:,} transações transformadas")

# Salvar particionado por data para melhor performance
df_transactions_silver.write \
    .mode("overwrite") \
    .partitionBy("tx_year", "tx_month") \
    .parquet(f"{SILVER_BASE}/transactions")

print(f"💾 Transações salvas em: {SILVER_BASE}/transactions (particionado por ano/mês)")

# ============================================
# SUMÁRIO FINAL
# ============================================
print("\n" + "=" * 60)
print("✅ SILVER LAYER CONCLUÍDA!")
print("=" * 60)
print(f"📊 Resumo:")
print(f"   🧑 Clientes: {customer_count:,}")
print(f"   📱 Dispositivos: {device_count:,}")
print(f"   💳 Transações: {tx_count:,}")
print(f"\n💾 Dados salvos em: {SILVER_BASE}/")
print("=" * 60)

spark.stop()
