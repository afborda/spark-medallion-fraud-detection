"""
📊 BENCHMARK: Pitágoras Simplificado vs Haversine UDF vs Haversine Nativo
Teste de performance para cálculo de distância geográfica
"""

import math
import time
from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, sqrt, pow as spark_pow, sin, cos, asin, radians, lit, udf
)
from pyspark.sql.types import DoubleType

print("=" * 70)
print("📊 BENCHMARK: Métodos de Cálculo de Distância Geográfica")
print("=" * 70)

# JARs
JARS_PATH = "/jars"
HADOOP_AWS = f"{JARS_PATH}/hadoop-aws-3.3.4.jar"
AWS_SDK = f"{JARS_PATH}/aws-java-sdk-bundle-1.12.262.jar"
JARS = f"{HADOOP_AWS},{AWS_SDK}"
CLASSPATH = f"{HADOOP_AWS}:{AWS_SDK}"

spark = SparkSession.builder \
    .appName("Benchmark_Haversine") \
    .config("spark.jars", JARS) \
    .config("spark.driver.extraClassPath", CLASSPATH) \
    .config("spark.executor.extraClassPath", CLASSPATH) \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123@@!!_2") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# ============================================================
# CARREGAR DADOS
# ============================================================
bronze_path = "s3a://fraud-data/medallion/bronze/transactions"
print(f"\n📂 Carregando dados de: {bronze_path}")

df = spark.read.parquet(bronze_path)
total = df.count()
print(f"✅ Total de registros: {total:,}")

# Usar uma amostra para teste (1M registros) ou todos se for menos
SAMPLE_SIZE = min(1_000_000, total)
if total > SAMPLE_SIZE:
    df_sample = df.limit(SAMPLE_SIZE)
    print(f"📊 Usando amostra de {SAMPLE_SIZE:,} registros para benchmark")
else:
    df_sample = df
    print(f"📊 Usando todos os {total:,} registros")

# Parsear JSON primeiro
from pyspark.sql.functions import from_json
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, BooleanType, LongType, IntegerType

schema = StructType([
    StructField("purchase_latitude", DoubleType(), True),
    StructField("purchase_longitude", DoubleType(), True),
    StructField("device_latitude", DoubleType(), True),
    StructField("device_longitude", DoubleType(), True),
])

df_parsed = df_sample \
    .select(from_json(col("raw_json"), schema).alias("data")) \
    .select("data.*") \
    .filter(col("purchase_latitude").isNotNull()) \
    .filter(col("device_latitude").isNotNull()) \
    .cache()

parsed_count = df_parsed.count()
print(f"✅ Registros parseados com coordenadas válidas: {parsed_count:,}")

# ============================================================
# MÉTODO 1: PITÁGORAS SIMPLIFICADO (ATUAL)
# Fórmula: √((lat2-lat1)² + (lon2-lon1)²) × 111
# ============================================================
print("\n" + "=" * 70)
print("🔷 MÉTODO 1: Pitágoras Simplificado (ATUAL)")
print("   Fórmula: √((lat2-lat1)² + (lon2-lon1)²) × 111")
print("=" * 70)

start_time = time.time()

df_pitagoras = df_parsed.withColumn(
    "distance_pitagoras_km",
    sqrt(
        spark_pow(col("device_latitude") - col("purchase_latitude"), 2) +
        spark_pow(col("device_longitude") - col("purchase_longitude"), 2)
    ) * 111
)

# Forçar execução com count
count1 = df_pitagoras.count()
time_pitagoras = time.time() - start_time

print(f"⏱️  Tempo: {time_pitagoras:.2f} segundos")
print(f"📊 Registros processados: {count1:,}")
print(f"🚀 Throughput: {count1/time_pitagoras:,.0f} registros/segundo")

# ============================================================
# MÉTODO 2: HAVERSINE COM UDF (da imagem)
# UDF Python - processamento row by row
# ============================================================
print("\n" + "=" * 70)
print("🔷 MÉTODO 2: Haversine UDF Python (da imagem)")
print("   Fórmula completa de Haversine como User Defined Function")
print("=" * 70)

# Definir UDF exatamente como na imagem
def haversine_distance(lat1, lon1, lat2, lon2):
    """Calculate distance between two points in kilometers"""
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None
    lat1_rad = math.radians(float(lat1))
    lon1_rad = math.radians(float(lon1))
    lat2_rad = math.radians(float(lat2))
    lon2_rad = math.radians(float(lon2))
    
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Raio da Terra em km
    return c * r

# Registrar UDF
haversine_udf = udf(haversine_distance, DoubleType())
spark.udf.register("haversine", haversine_distance, DoubleType())

start_time = time.time()

df_haversine_udf = df_parsed.withColumn(
    "distance_haversine_udf_km",
    haversine_udf(
        col("purchase_latitude"),
        col("purchase_longitude"),
        col("device_latitude"),
        col("device_longitude")
    )
)

count2 = df_haversine_udf.count()
time_haversine_udf = time.time() - start_time

print(f"⏱️  Tempo: {time_haversine_udf:.2f} segundos")
print(f"📊 Registros processados: {count2:,}")
print(f"🚀 Throughput: {count2/time_haversine_udf:,.0f} registros/segundo")

# ============================================================
# MÉTODO 3: HAVERSINE NATIVO SPARK (funções built-in)
# Usando funções nativas do Spark (otimizado)
# ============================================================
print("\n" + "=" * 70)
print("🔷 MÉTODO 3: Haversine Nativo Spark (funções built-in)")
print("   Mesma fórmula, mas usando apenas funções nativas Spark")
print("=" * 70)

start_time = time.time()

# Haversine com funções nativas do Spark
EARTH_RADIUS_KM = 6371

df_haversine_native = df_parsed \
    .withColumn("lat1_rad", radians(col("purchase_latitude"))) \
    .withColumn("lat2_rad", radians(col("device_latitude"))) \
    .withColumn("lon1_rad", radians(col("purchase_longitude"))) \
    .withColumn("lon2_rad", radians(col("device_longitude"))) \
    .withColumn("dlat", col("lat2_rad") - col("lat1_rad")) \
    .withColumn("dlon", col("lon2_rad") - col("lon1_rad")) \
    .withColumn("a",
        spark_pow(sin(col("dlat") / 2), 2) +
        cos(col("lat1_rad")) * cos(col("lat2_rad")) * spark_pow(sin(col("dlon") / 2), 2)
    ) \
    .withColumn("c", 2 * asin(sqrt(col("a")))) \
    .withColumn("distance_haversine_native_km", col("c") * EARTH_RADIUS_KM)

count3 = df_haversine_native.count()
time_haversine_native = time.time() - start_time

print(f"⏱️  Tempo: {time_haversine_native:.2f} segundos")
print(f"📊 Registros processados: {count3:,}")
print(f"🚀 Throughput: {count3/time_haversine_native:,.0f} registros/segundo")

# ============================================================
# COMPARAÇÃO DE RESULTADOS
# ============================================================
print("\n" + "=" * 70)
print("📊 COMPARAÇÃO DE RESULTADOS")
print("=" * 70)

# Juntar resultados para comparar precisão
df_compare = df_pitagoras \
    .join(df_haversine_udf.select("purchase_latitude", "purchase_longitude", "distance_haversine_udf_km"),
          ["purchase_latitude", "purchase_longitude"], "inner") \
    .join(df_haversine_native.select("purchase_latitude", "purchase_longitude", "distance_haversine_native_km"),
          ["purchase_latitude", "purchase_longitude"], "inner") \
    .limit(10)

print("\n🔍 Amostra de 10 registros comparando os 3 métodos:")
df_compare.select(
    "purchase_latitude", 
    "purchase_longitude",
    "distance_pitagoras_km",
    "distance_haversine_udf_km",
    "distance_haversine_native_km"
).show(10, truncate=False)

# ============================================================
# RESUMO FINAL
# ============================================================
print("\n" + "=" * 70)
print("📊 RESUMO FINAL DO BENCHMARK")
print("=" * 70)

# Calcular diferença percentual
baseline = time_pitagoras
diff_udf = ((time_haversine_udf - baseline) / baseline) * 100
diff_native = ((time_haversine_native - baseline) / baseline) * 100

print(f"""
┌────────────────────────────────────────────────────────────────────────┐
│ MÉTODO                        │ TEMPO      │ THROUGHPUT    │ vs ATUAL │
├────────────────────────────────────────────────────────────────────────┤
│ 1. Pitágoras Simplificado     │ {time_pitagoras:>6.2f}s    │ {count1/time_pitagoras:>10,.0f}/s │ baseline │
│ 2. Haversine UDF (Python)     │ {time_haversine_udf:>6.2f}s    │ {count2/time_haversine_udf:>10,.0f}/s │ {diff_udf:>+6.1f}%  │
│ 3. Haversine Nativo (Spark)   │ {time_haversine_native:>6.2f}s    │ {count3/time_haversine_native:>10,.0f}/s │ {diff_native:>+6.1f}%  │
└────────────────────────────────────────────────────────────────────────┘

📌 ANÁLISE:
""")

# Análise automática
if time_haversine_udf > time_pitagoras:
    print(f"   ❌ Haversine UDF é {diff_udf:.1f}% MAIS LENTO que Pitágoras")
else:
    print(f"   ✅ Haversine UDF é {abs(diff_udf):.1f}% MAIS RÁPIDO que Pitágoras")

if time_haversine_native > time_pitagoras:
    print(f"   ❌ Haversine Nativo é {diff_native:.1f}% MAIS LENTO que Pitágoras")
else:
    print(f"   ✅ Haversine Nativo é {abs(diff_native):.1f}% MAIS RÁPIDO que Pitágoras")

# Recomendação
print(f"""
📌 PRECISÃO:
   - Pitágoras: aproximação, erro maior em longas distâncias
   - Haversine: fórmula geodésica correta para superfície esférica
   
📌 RECOMENDAÇÃO:
""")

best_method = "Pitágoras"
reason = ""
if time_haversine_native <= time_pitagoras * 1.1:  # Se nativo for no máximo 10% mais lento
    best_method = "Haversine Nativo"
    reason = "Melhor precisão com performance similar"
elif time_haversine_udf <= time_pitagoras * 1.1:
    best_method = "Haversine UDF"
    reason = "Melhor precisão com performance aceitável"
else:
    reason = "Melhor performance, precisão suficiente para detecção de fraude"

print(f"   🏆 MELHOR: {best_method}")
print(f"   📝 Razão: {reason}")

print("\n" + "=" * 70)

# Limpar cache
df_parsed.unpersist()
spark.stop()
