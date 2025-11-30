"""
Verificar distribuição das flags no Silver
"""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col

spark = SparkSession.builder \
    .appName("Check_Silver_Flags") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123@@!!_2") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

df = spark.read.parquet("s3a://fraud-data/medallion/silver/transactions")
total = df.count()

print(f"\n{'='*60}")
print(f"ANALISE DAS FLAGS NO SILVER ({total:,} registros)")
print(f"{'='*60}")

flags = [
    "is_cross_state", 
    "is_night_transaction", 
    "is_high_value", 
    "is_high_velocity", 
    "is_gps_mismatch", 
    "is_first_purchase_in_state", 
    "is_international", 
    "had_travel_purchase_last_12m"
]

for flag in flags:
    true_count = df.filter(col(flag) == True).count()
    pct = (true_count / total) * 100
    print(f"{flag}: {true_count:,} ({pct:.1f}%)")

print(f"\n{'='*60}")
print("COMBINACOES CRITICAS:")
print(f"{'='*60}")

# GPS + High Value + Night
combo1 = df.filter(
    (col("is_gps_mismatch") == True) & 
    (col("is_high_value") == True) & 
    (col("is_night_transaction") == True)
).count()
print(f"GPS + High Value + Night: {combo1:,} ({(combo1/total)*100:.2f}%)")

# GPS + Cross-state + No Travel History
combo2 = df.filter(
    (col("is_gps_mismatch") == True) & 
    (col("is_cross_state") == True) & 
    (col("had_travel_purchase_last_12m") == False)
).count()
print(f"GPS + Cross-state + No Travel: {combo2:,} ({(combo2/total)*100:.2f}%)")

# High Velocity + GPS + High Value
combo3 = df.filter(
    (col("is_high_velocity") == True) & 
    (col("is_gps_mismatch") == True) & 
    (col("is_high_value") == True)
).count()
print(f"High Velocity + GPS + High Value: {combo3:,} ({(combo3/total)*100:.2f}%)")

spark.stop()
