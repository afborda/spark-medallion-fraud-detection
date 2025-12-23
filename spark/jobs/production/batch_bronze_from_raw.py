"""
🥉 BRONZE LAYER - MinIO Raw → MinIO Bronze (BATCH)
Ingestão de dados brutos do MinIO raw para o Bronze Layer

Este job processa os dados gerados pelo fraud-generator no MinIO:
- Lê de: s3a://fraud-data/raw/batch/ (estrutura plana do fraud-generator)
- Fallback: s3a://fraud-data/raw/year=*/month=*/day=*/ (estrutura particionada)
- Escreve em: s3a://fraud-data/bronze/batch/

OTIMIZAÇÕES IMPLEMENTADAS:
1. Leitura em blocos de 128MB (maxPartitionBytes) para melhor paralelismo
2. Suporte a dois formatos de entrada:
   - Estrutura plana: fraud-generator original (transactions_*.parquet)
   - Estrutura particionada: year=YYYY/month=MM/day=DD/

TIPO: BATCH (processamento em lote)
FONTE: fraud-generator v4-beta (campos em inglês)
"""

import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    current_timestamp, col, lit, input_file_name, 
    to_timestamp, year, month, dayofmonth
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    BooleanType, IntegerType
)
from config import apply_s3a_configs

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

# Paths no MinIO - Suporta estrutura plana e particionada
RAW_PATH_FLAT = "s3a://fraud-data/raw/batch"          # fraud-generator original
RAW_PATH_PARTITIONED = "s3a://fraud-data/raw"          # estrutura particionada
BRONZE_PATH = "s3a://fraud-data/bronze/batch"

# Otimização de particionamento (alinhado com 4 cores totais)
REPARTITION_COUNT = 8
MAX_PARTITION_BYTES = 134217728  # 128MB em bytes

# Schema das transações do Brazilian Fraud Data Generator (v4-beta - English)
# NOTA: installments e time_since_last_txn_min são Double porque o fraud-generator
# pode gerar valores decimais ou nulos que são salvos como Double no Parquet
transaction_schema = StructType([
    StructField("transaction_id", StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("session_id", StringType(), True),
    StructField("device_id", StringType(), True),
    StructField("timestamp", StringType(), True),
    StructField("type", StringType(), True),
    StructField("amount", DoubleType(), True),
    StructField("currency", StringType(), True),
    StructField("channel", StringType(), True),
    StructField("ip_address", StringType(), True),
    StructField("geolocation_lat", DoubleType(), True),
    StructField("geolocation_lon", DoubleType(), True),
    StructField("merchant_id", StringType(), True),
    StructField("merchant_name", StringType(), True),
    StructField("merchant_category", StringType(), True),
    StructField("mcc_code", StringType(), True),
    StructField("mcc_risk_level", StringType(), True),
    StructField("card_number_hash", StringType(), True),
    StructField("card_brand", StringType(), True),
    StructField("card_type", StringType(), True),
    StructField("installments", DoubleType(), True),  # Double no Parquet original
    StructField("card_entry", StringType(), True),
    StructField("cvv_validated", BooleanType(), True),
    StructField("auth_3ds", BooleanType(), True),
    StructField("pix_key_type", StringType(), True),
    StructField("pix_key_destination", StringType(), True),
    StructField("destination_bank", StringType(), True),
    StructField("distance_from_last_txn_km", DoubleType(), True),
    StructField("time_since_last_txn_min", DoubleType(), True),  # Double no Parquet original
    StructField("transactions_last_24h", IntegerType(), True),
    StructField("accumulated_amount_24h", DoubleType(), True),
    StructField("unusual_time", BooleanType(), True),
    StructField("new_beneficiary", BooleanType(), True),
    StructField("status", StringType(), True),
    StructField("refusal_reason", StringType(), True),
    StructField("fraud_score", DoubleType(), True),
    StructField("is_fraud", BooleanType(), True),
    StructField("fraud_type", StringType(), True)
])

def main():
    print("=" * 70)
    print("🥉 BRONZE LAYER - BATCH PROCESSING")
    print("   Fonte 1: s3a://fraud-data/raw/batch/ (fraud-generator)")
    print("   Fonte 2: s3a://fraud-data/raw/year=*/month=*/day=*/ (particionado)")
    print("   Destino: s3a://fraud-data/bronze/batch")
    print("   Leitura: blocos de 128MB (maxPartitionBytes)")
    print("=" * 70)
    
    # Configurações S3 via variáveis de ambiente
    spark = apply_s3a_configs(
        SparkSession.builder
        .appName("Batch_Raw_to_Bronze")
        .config("spark.sql.adaptive.enabled", "true")
        .config("spark.sql.adaptive.coalescePartitions.enabled", "true")
        .config("spark.hadoop.fs.s3a.multipart.size", "104857600")
        .config("spark.hadoop.fs.s3a.fast.upload", "true")
        # Otimização de leitura: blocos de 128MB
        .config("spark.sql.files.maxPartitionBytes", str(MAX_PARTITION_BYTES))
        .config("spark.sql.files.openCostInBytes", "4194304")  # 4MB - custo de abertura
        # S3A Committer - evita problema de rename no S3
        .config("spark.hadoop.fs.s3a.committer.name", "directory")
        .config("spark.hadoop.fs.s3a.committer.staging.conflict-mode", "replace")
        .config("spark.hadoop.mapreduce.outputcommitter.factory.scheme.s3a", 
                "org.apache.hadoop.fs.s3a.commit.S3ACommitterFactory")
        # Suporte para timestamps INT96/NANOS do PyArrow
        .config("spark.sql.parquet.int96RebaseModeInRead", "CORRECTED")
        .config("spark.sql.parquet.datetimeRebaseModeInRead", "CORRECTED")
        .config("spark.sql.parquet.outputTimestampType", "TIMESTAMP_MICROS")
        .config("spark.sql.legacy.parquet.nanosAsLong", "true")
        # FIX: Suporte para TIMESTAMP(NANOS) do PyArrow - converte para TIMESTAMP_MICROS
        .config("spark.sql.parquet.inferTimestampNTZ.enabled", "true")
        .config("spark.sql.parquet.enableVectorizedReader", "false")
    ).getOrCreate()
    
    spark.sparkContext.setLogLevel("WARN")
    
    # =========================================================================
    # LER DADOS DO RAW - TENTA ESTRUTURA PLANA PRIMEIRO, DEPOIS PARTICIONADA
    # =========================================================================
    print("\n📂 Verificando arquivos no RAW...")
    print(f"   📊 Lendo em blocos de {MAX_PARTITION_BYTES // (1024*1024)}MB")
    
    df_raw = None
    file_format = None
    source_path = None
    
    # TENTATIVA 1: Estrutura plana do fraud-generator (raw/batch/) - Parquet
    print("\n🔍 Tentando estrutura plana (fraud-generator)...")
    try:
        # Ler diretamente o diretório transactions_*.parquet
        # MinIO armazena como diretórios, então lemos o path diretamente
        # NÃO usar schema fixo - deixar inferir para compatibilidade
        df_test = spark.read \
            .parquet(f"{RAW_PATH_FLAT}/transactions_*.parquet")
        
        if df_test.head(1):
            df_raw = df_test
            file_format = "parquet"
            source_path = f"{RAW_PATH_FLAT}/transactions_*.parquet"
            print(f"   ✅ Encontrados arquivos Parquet em {RAW_PATH_FLAT}")
    except Exception as e:
        print(f"   ⚠️ Parquet não encontrado em raw/batch/: {e}")
    
    # TENTATIVA 2: Estrutura plana JSONL (raw/batch/)
    if df_raw is None:
        print("\n🔍 Tentando JSONL em estrutura plana...")
        try:
            df_test = spark.read \
                .schema(transaction_schema) \
                .option("recursiveFileLookup", "true") \
                .json(RAW_PATH_FLAT)
            
            if df_test.head(1):
                df_raw = df_test
                file_format = "jsonl"
                source_path = RAW_PATH_FLAT
                print(f"   ✅ Encontrados arquivos JSONL em {RAW_PATH_FLAT}")
        except Exception as e:
            print(f"   ⚠️ JSONL não encontrado em raw/batch/")
    
    # TENTATIVA 3: Estrutura particionada Parquet (year=/month=/day=)
    if df_raw is None:
        print("\n🔍 Tentando estrutura particionada...")
        try:
            df_test = spark.read \
                .schema(transaction_schema) \
                .option("recursiveFileLookup", "true") \
                .option("pathGlobFilter", "transactions_*.parquet") \
                .option("basePath", RAW_PATH_PARTITIONED) \
                .parquet(f"{RAW_PATH_PARTITIONED}/year=*/month=*/day=*/")
            
            if df_test.head(1):
                df_raw = df_test
                file_format = "parquet"
                source_path = f"{RAW_PATH_PARTITIONED}/year=*/month=*/day=*/"
                print(f"   ✅ Encontrados arquivos Parquet particionados")
        except Exception as e:
            print(f"   ⚠️ Parquet particionado não encontrado: {e}")
    
    # TENTATIVA 4: Estrutura particionada JSONL
    if df_raw is None:
        print("\n🔍 Tentando JSONL particionado...")
        try:
            df_test = spark.read \
                .schema(transaction_schema) \
                .option("recursiveFileLookup", "true") \
                .option("basePath", RAW_PATH_PARTITIONED) \
                .json(f"{RAW_PATH_PARTITIONED}/year=*/month=*/day=*/")
            
            if df_test.head(1):
                df_raw = df_test
                file_format = "jsonl"
                source_path = f"{RAW_PATH_PARTITIONED}/year=*/month=*/day=*/"
                print(f"   ✅ Encontrados arquivos JSONL particionados")
        except Exception as e:
            print(f"   ❌ JSONL particionado não encontrado")
    
    if df_raw is None:
        raise Exception("❌ Nenhum arquivo de transações encontrado no RAW!")
    
    # Filtrar apenas transações (ignorar customers e devices se existirem)
    if "transaction_id" in df_raw.columns:
        df_raw = df_raw.filter(col("transaction_id").isNotNull())
    
    total_records = df_raw.count()
    print(f"\n✅ Lidos {total_records:,} registros do RAW")
    print(f"   📁 Fonte: {source_path}")
    print(f"   📄 Formato: {file_format}")
    
    # =========================================================================
    # ADICIONAR METADADOS BRONZE
    # =========================================================================
    print("\n🔄 Adicionando metadados Bronze...")
    
    df_bronze = df_raw \
        .withColumn("ingestion_timestamp", current_timestamp()) \
        .withColumn("source_layer", lit("raw")) \
        .withColumn("source_format", lit(file_format)) \
        .withColumn("processing_date", current_timestamp().cast("date"))
    
    # Adicionar partições de data se o timestamp existir
    if "timestamp" in df_bronze.columns:
        df_bronze = df_bronze \
            .withColumn("ts_parsed", to_timestamp(col("timestamp"))) \
            .withColumn("year", year(col("ts_parsed"))) \
            .withColumn("month", month(col("ts_parsed"))) \
            .withColumn("day", dayofmonth(col("ts_parsed"))) \
            .drop("ts_parsed")
    
    # =========================================================================
    # REPARTITION E ESCRITA
    # =========================================================================
    print(f"\n📊 Reparticionando para {REPARTITION_COUNT} partições...")
    
    df_bronze = df_bronze.repartition(REPARTITION_COUNT)
    
    print(f"\n💾 Escrevendo no Bronze: {BRONZE_PATH}/transactions")
    
    # Escrever particionado por ano/mês/dia
    df_bronze.write \
        .mode("overwrite") \
        .partitionBy("year", "month", "day") \
        .parquet(f"{BRONZE_PATH}/transactions")
    
    print("=" * 70)
    print("✅ BRONZE LAYER CONCLUÍDO!")
    print(f"   📊 Registros processados: {total_records:,}")
    print(f"   📁 Partições: {REPARTITION_COUNT}")
    print(f"   📂 Destino: {BRONZE_PATH}/transactions")
    print("=" * 70)
    
    # Mostrar estatísticas
    print("\n📈 Estatísticas:")
    df_bronze.groupBy("type").count().orderBy("count", ascending=False).show(10)
    
    spark.stop()

if __name__ == "__main__":
    main()
