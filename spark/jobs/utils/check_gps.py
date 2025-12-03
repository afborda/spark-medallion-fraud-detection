"""Verificar distribuição GPS"""
import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, percentile_approx, min as spark_min, max as spark_max
from config import get_spark_s3a_configs

# Obter configurações S3A do config.py
s3a_configs = get_spark_s3a_configs()

spark_builder = SparkSession.builder.appName("Check_GPS")
for key, value in s3a_configs.items():
    spark_builder = spark_builder.config(key, value)

spark = spark_builder.getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

df = spark.read.parquet("s3a://fraud-data/medallion/silver/transactions")

print("\n" + "="*60)
print("DISTRIBUICAO distance_gps (em graus)")
print("="*60)
df.select(
    spark_min("distance_gps").alias("min"),
    percentile_approx("distance_gps", 0.25).alias("p25"),
    percentile_approx("distance_gps", 0.5).alias("p50_median"),
    percentile_approx("distance_gps", 0.75).alias("p75"),
    percentile_approx("distance_gps", 0.90).alias("p90"),
    percentile_approx("distance_gps", 0.95).alias("p95"),
    percentile_approx("distance_gps", 0.99).alias("p99"),
    spark_max("distance_gps").alias("max")
).show(truncate=False)

spark.stop()
