"""Verificar distribuição GPS"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, percentile_approx, min as spark_min, max as spark_max

spark = SparkSession.builder \
    .appName("Check_GPS") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123@@!!_2") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .getOrCreate()

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
