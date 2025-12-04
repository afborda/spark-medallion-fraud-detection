"""
📊 BENCHMARK: JDBC Write Performance
Compara escrita ATUAL vs OTIMIZADA para PostgreSQL

Testa:
1. Escrita SEM otimização (baseline atual)
2. Escrita COM repartition + batchsize + numPartitions

Usa tabela temporária para não afetar dados de produção.
"""

import sys
sys.path.insert(0, '/jobs')

import time
from pyspark.sql import SparkSession
from pyspark.sql.functions import col
from config import POSTGRES_URL, POSTGRES_PROPERTIES, GOLD_PATH, apply_s3a_configs

# ============================================
# CONFIGURAÇÃO DO BENCHMARK
# ============================================
SAMPLE_SIZE = 10_000_000  # 10M registros
TABLE_BASELINE = "benchmark_baseline"
TABLE_OPTIMIZED = "benchmark_optimized"

print("=" * 70)
print("📊 BENCHMARK: JDBC Write Performance")
print("=" * 70)
print(f"🎯 Amostra: {SAMPLE_SIZE:,} registros")
print(f"📦 Tabelas: {TABLE_BASELINE} vs {TABLE_OPTIMIZED}")
print("=" * 70)

# ============================================
# INICIALIZAR SPARK
# ============================================
spark = apply_s3a_configs(
    SparkSession.builder.appName("Benchmark_Postgres_Write")
).getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# ============================================
# CARREGAR DADOS DO GOLD
# ============================================
print("\n📂 Carregando dados do Gold Layer...")
start_load = time.time()

df_full = spark.read.parquet(f"{GOLD_PATH}/fraud_detection")

# Selecionar mesmos campos do load_to_postgres.py
df_tx = df_full.select(
    "transaction_id",
    "customer_id",
    "timestamp_dt",
    "tx_date",
    "tx_year",
    "tx_month",
    "tx_hour",
    "tipo",
    col("valor").alias("amount"),
    "canal",
    "merchant_name",
    "merchant_category",
    "mcc_code",
    "mcc_risk_level",
    "bandeira",
    "entrada_cartao",
    "status",
    "motivo_recusa",
    "fraud_score",
    "fraud_score_category",
    "is_fraud",
    "fraud_type",
    "risk_points",
    "risk_level",
    "requires_review",
    "periodo_dia",
    "faixa_valor",
    "is_weekend",
    "_gold_timestamp"
)

# Limitar a amostra
df_sample = df_tx.limit(SAMPLE_SIZE)

# Cache para reutilizar nos testes
df_sample.cache()
actual_count = df_sample.count()
elapsed_load = time.time() - start_load

print(f"✅ {actual_count:,} registros carregados em {elapsed_load:.1f}s")
print(f"📊 Partições atuais: {df_sample.rdd.getNumPartitions()}")

# ============================================
# TESTE 1: BASELINE (sem otimização)
# ============================================
print("\n" + "=" * 70)
print("🔵 TESTE 1: BASELINE (configuração atual)")
print("=" * 70)
print("   - Sem repartition")
print("   - batchsize padrão (1000)")
print("   - Escrita direta")

start_baseline = time.time()

df_sample.write \
    .mode("overwrite") \
    .jdbc(POSTGRES_URL, TABLE_BASELINE, properties=POSTGRES_PROPERTIES)

elapsed_baseline = time.time() - start_baseline
throughput_baseline = actual_count / elapsed_baseline

print(f"\n⏱️  Tempo: {elapsed_baseline:.1f}s")
print(f"🚀 Throughput: {throughput_baseline:,.0f} registros/s")

# ============================================
# TESTE 2: OTIMIZADO (com boas práticas)
# ============================================
print("\n" + "=" * 70)
print("🟢 TESTE 2: OTIMIZADO (boas práticas)")
print("=" * 70)

# Configurações otimizadas
NUM_PARTITIONS = 16  # Conexões paralelas ao PostgreSQL
BATCH_SIZE = 10000   # Linhas por INSERT

print(f"   - repartition({NUM_PARTITIONS})")
print(f"   - batchsize: {BATCH_SIZE}")
print(f"   - rewriteBatchedInserts: true")

# Properties otimizadas
optimized_properties = POSTGRES_PROPERTIES.copy()
optimized_properties["batchsize"] = str(BATCH_SIZE)
optimized_properties["rewriteBatchedInserts"] = "true"

start_optimized = time.time()

df_sample.repartition(NUM_PARTITIONS).write \
    .mode("overwrite") \
    .option("numPartitions", NUM_PARTITIONS) \
    .option("truncate", "true") \
    .jdbc(POSTGRES_URL, TABLE_OPTIMIZED, properties=optimized_properties)

elapsed_optimized = time.time() - start_optimized
throughput_optimized = actual_count / elapsed_optimized

print(f"\n⏱️  Tempo: {elapsed_optimized:.1f}s")
print(f"🚀 Throughput: {throughput_optimized:,.0f} registros/s")

# ============================================
# COMPARATIVO
# ============================================
print("\n" + "=" * 70)
print("📊 RESULTADO DO BENCHMARK")
print("=" * 70)

speedup = elapsed_baseline / elapsed_optimized if elapsed_optimized > 0 else 0
improvement = ((throughput_optimized - throughput_baseline) / throughput_baseline * 100) if throughput_baseline > 0 else 0

print(f"""
┌─────────────────────┬─────────────────┬─────────────────┐
│ Métrica             │ BASELINE        │ OTIMIZADO       │
├─────────────────────┼─────────────────┼─────────────────┤
│ Registros           │ {actual_count:>15,} │ {actual_count:>15,} │
│ Tempo (s)           │ {elapsed_baseline:>15.1f} │ {elapsed_optimized:>15.1f} │
│ Throughput (reg/s)  │ {throughput_baseline:>15,.0f} │ {throughput_optimized:>15,.0f} │
│ Partições           │ {df_sample.rdd.getNumPartitions():>15} │ {NUM_PARTITIONS:>15} │
│ Batch Size          │ {1000:>15} │ {BATCH_SIZE:>15} │
└─────────────────────┴─────────────────┴─────────────────┘

🎯 SPEEDUP: {speedup:.2f}x mais rápido
📈 MELHORIA: {improvement:+.1f}% throughput
""")

# Limpar cache
df_sample.unpersist()

# ============================================
# LIMPAR TABELAS TEMPORÁRIAS
# ============================================
print("🧹 Limpando tabelas temporárias...")

try:
    from py4j.java_gateway import java_import
    java_import(spark._jvm, "java.sql.DriverManager")
    
    conn = spark._jvm.DriverManager.getConnection(
        POSTGRES_URL,
        POSTGRES_PROPERTIES["user"],
        POSTGRES_PROPERTIES["password"]
    )
    stmt = conn.createStatement()
    stmt.execute(f"DROP TABLE IF EXISTS {TABLE_BASELINE}")
    stmt.execute(f"DROP TABLE IF EXISTS {TABLE_OPTIMIZED}")
    stmt.close()
    conn.close()
    print("✅ Tabelas temporárias removidas")
except Exception as e:
    print(f"⚠️  Erro ao limpar: {e}")
    print("   Execute: DROP TABLE IF EXISTS benchmark_baseline, benchmark_optimized;")

print("\n" + "=" * 70)
print("✅ BENCHMARK CONCLUÍDO!")
print("=" * 70)

spark.stop()
