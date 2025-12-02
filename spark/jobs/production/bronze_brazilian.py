"""
🥉 BRONZE LAYER - JSON Local → MinIO
Ingestão de dados brutos de arquivos JSON para o Data Lake

Este job processa os dados brasileiros gerados pelo script generate_brazilian_data.py:
- customers.json: Dados de clientes
- devices.json: Dispositivos dos clientes  
- transactions_batch_*.json: Transações financeiras
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import current_timestamp, col, lit, input_file_name
from pyspark.sql.types import *
import os

print("=" * 60)
print("🥉 BRONZE LAYER - JSON Local → MinIO")
print("🇧🇷 Processando dados brasileiros")
print("=" * 60)

# JARs para S3/MinIO
JARS_PATH = "/jars"
HADOOP_AWS = f"{JARS_PATH}/hadoop-aws-3.3.4.jar"
AWS_SDK = f"{JARS_PATH}/aws-java-sdk-bundle-1.12.262.jar"
JARS = f"{HADOOP_AWS},{AWS_SDK}"
CLASSPATH = f"{HADOOP_AWS}:{AWS_SDK}"

spark = SparkSession.builder \
    .appName("Bronze_JSON_to_MinIO") \
    .config("spark.jars", JARS) \
    .config("spark.driver.extraClassPath", CLASSPATH) \
    .config("spark.executor.extraClassPath", CLASSPATH) \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123@@!!_2") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
    .config("spark.sql.adaptive.enabled", "true") \
    .config("spark.sql.adaptive.coalescePartitions.enabled", "true") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# Diretórios
RAW_DIR = "/data/raw"
BRONZE_BASE = "s3a://fraud-data/medallion/bronze"

# ============================================
# 1. PROCESSAR CLIENTES
# ============================================
print("\n" + "=" * 40)
print("🧑 Processando CLIENTES...")
print("=" * 40)

customers_path = f"{RAW_DIR}/customers.json"

# Schema completo de clientes
customer_schema = StructType([
    StructField("customer_id", StringType(), False),
    StructField("cpf", StringType(), True),
    StructField("rg", StringType(), True),
    StructField("nome_completo", StringType(), True),
    StructField("nome_social", StringType(), True),
    StructField("data_nascimento", StringType(), True),
    StructField("sexo", StringType(), True),
    StructField("estado_civil", StringType(), True),
    StructField("email", StringType(), True),
    StructField("telefone_celular", StringType(), True),
    StructField("telefone_fixo", StringType(), True),
    StructField("cep", StringType(), True),
    StructField("logradouro", StringType(), True),
    StructField("numero", StringType(), True),
    StructField("complemento", StringType(), True),
    StructField("bairro", StringType(), True),
    StructField("cidade", StringType(), True),
    StructField("estado", StringType(), True),
    StructField("banco_codigo", StringType(), True),
    StructField("banco_nome", StringType(), True),
    StructField("agencia", StringType(), True),
    StructField("conta", StringType(), True),
    StructField("tipo_conta", StringType(), True),
    StructField("profissao", StringType(), True),
    StructField("renda_mensal", DoubleType(), True),
    StructField("score_credito", IntegerType(), True),
    StructField("limite_credito", DoubleType(), True),
    StructField("limite_pix_diario", DoubleType(), True),
    StructField("perfil_investidor", StringType(), True),
    StructField("pep", BooleanType(), True),
    StructField("data_cadastro", StringType(), True),
    StructField("status", StringType(), True),
    StructField("nivel_verificacao", StringType(), True),
    StructField("is_premium", BooleanType(), True),
    StructField("aceita_marketing", BooleanType(), True),
    StructField("biometria_facial", BooleanType(), True),
    StructField("token_ativo", BooleanType(), True),
])

df_customers = spark.read \
    .schema(customer_schema) \
    .json(customers_path)

# Adicionar metadados de ingestão
df_customers_bronze = df_customers \
    .withColumn("_ingestion_timestamp", current_timestamp()) \
    .withColumn("_source_file", lit("customers.json"))

customer_count = df_customers_bronze.count()
print(f"✅ {customer_count:,} clientes lidos")

# Salvar no MinIO
customers_output = f"{BRONZE_BASE}/customers"
df_customers_bronze.write \
    .mode("overwrite") \
    .parquet(customers_output)

print(f"💾 Clientes salvos em: {customers_output}")

# ============================================
# 2. PROCESSAR DISPOSITIVOS
# ============================================
print("\n" + "=" * 40)
print("📱 Processando DISPOSITIVOS...")
print("=" * 40)

devices_path = f"{RAW_DIR}/devices.json"

device_schema = StructType([
    StructField("device_id", StringType(), False),
    StructField("customer_id", StringType(), True),
    StructField("device_fingerprint", StringType(), True),
    StructField("manufacturer", StringType(), True),
    StructField("model", StringType(), True),
    StructField("os_name", StringType(), True),
    StructField("os_version", StringType(), True),
    StructField("app_version", StringType(), True),
    StructField("screen_resolution", StringType(), True),
    StructField("is_rooted", BooleanType(), True),
    StructField("is_emulator", BooleanType(), True),
    StructField("first_seen", StringType(), True),
    StructField("last_seen", StringType(), True),
    StructField("is_trusted", BooleanType(), True),
    StructField("risk_score", IntegerType(), True),
])

df_devices = spark.read \
    .schema(device_schema) \
    .json(devices_path)

df_devices_bronze = df_devices \
    .withColumn("_ingestion_timestamp", current_timestamp()) \
    .withColumn("_source_file", lit("devices.json"))

device_count = df_devices_bronze.count()
print(f"✅ {device_count:,} dispositivos lidos")

devices_output = f"{BRONZE_BASE}/devices"
df_devices_bronze.write \
    .mode("overwrite") \
    .parquet(devices_output)

print(f"💾 Dispositivos salvos em: {devices_output}")

# ============================================
# 3. PROCESSAR TRANSAÇÕES
# ============================================
print("\n" + "=" * 40)
print("💳 Processando TRANSAÇÕES...")
print("=" * 40)

transaction_schema = StructType([
    StructField("transaction_id", StringType(), False),
    StructField("customer_id", StringType(), True),
    StructField("session_id", StringType(), True),
    StructField("device_id", StringType(), True),
    StructField("timestamp", StringType(), True),
    StructField("tipo", StringType(), True),
    StructField("valor", DoubleType(), True),
    StructField("moeda", StringType(), True),
    StructField("canal", StringType(), True),
    StructField("ip_address", StringType(), True),
    StructField("geolocalizacao_lat", DoubleType(), True),
    StructField("geolocalizacao_lon", DoubleType(), True),
    StructField("merchant_id", StringType(), True),
    StructField("merchant_name", StringType(), True),
    StructField("merchant_category", StringType(), True),
    StructField("mcc_code", StringType(), True),
    StructField("mcc_risk_level", StringType(), True),
    StructField("numero_cartao_hash", StringType(), True),
    StructField("bandeira", StringType(), True),
    StructField("tipo_cartao", StringType(), True),
    StructField("parcelas", IntegerType(), True),
    StructField("entrada_cartao", StringType(), True),
    StructField("cvv_validado", BooleanType(), True),
    StructField("autenticacao_3ds", BooleanType(), True),
    StructField("chave_pix_tipo", StringType(), True),
    StructField("chave_pix_destino", StringType(), True),
    StructField("banco_destino", StringType(), True),
    StructField("distancia_ultima_transacao_km", DoubleType(), True),
    StructField("tempo_desde_ultima_transacao_min", IntegerType(), True),
    StructField("transacoes_ultimas_24h", IntegerType(), True),
    StructField("valor_acumulado_24h", DoubleType(), True),
    StructField("horario_incomum", BooleanType(), True),
    StructField("novo_beneficiario", BooleanType(), True),
    StructField("status", StringType(), True),
    StructField("motivo_recusa", StringType(), True),
    StructField("fraud_score", DoubleType(), True),
    StructField("is_fraud", BooleanType(), True),
    StructField("fraud_type", StringType(), True),
])

# Ler todos os arquivos de transações (transactions_*.json ou transactions_batch_*.json)
transactions_pattern = f"{RAW_DIR}/transactions_*.json"

df_transactions = spark.read \
    .schema(transaction_schema) \
    .json(transactions_pattern)

df_transactions_bronze = df_transactions \
    .withColumn("_ingestion_timestamp", current_timestamp()) \
    .withColumn("_source_file", input_file_name())

tx_count = df_transactions_bronze.count()
print(f"✅ {tx_count:,} transações lidas")

transactions_output = f"{BRONZE_BASE}/transactions"
df_transactions_bronze.write \
    .mode("overwrite") \
    .parquet(transactions_output)

print(f"💾 Transações salvas em: {transactions_output}")

# ============================================
# SUMÁRIO FINAL
# ============================================
print("\n" + "=" * 60)
print("✅ BRONZE LAYER CONCLUÍDA!")
print("=" * 60)
print(f"📊 Resumo:")
print(f"   🧑 Clientes: {customer_count:,}")
print(f"   📱 Dispositivos: {device_count:,}")
print(f"   💳 Transações: {tx_count:,}")
print(f"\n💾 Dados salvos em: {BRONZE_BASE}/")
print("=" * 60)

spark.stop()
