"""
Script temporário para testar leitura e verificar schema
"""
import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from config import apply_s3a_configs

spark = apply_s3a_configs(
    SparkSession.builder
    .appName("Test_Read_Schema")
).getOrCreate()

spark.sparkContext.setLogLevel("WARN")

print("\n" + "="*70)
print("TESTE DE LEITURA - SEM SCHEMA (INFERIR)")
print("="*70)

try:
    # Ler sem schema, deixar Spark inferir - mas só transactions
    df = spark.read \
        .option("recursiveFileLookup", "true") \
        .option("pathGlobFilter", "transactions_*.parquet") \
        .option("mergeSchema", "true") \
        .parquet("s3a://fraud-data/raw/batch")
    
    print(f"\nTotal de registros: {df.count()}")
    print("\nSchema inferido:")
    df.printSchema()
    
    # Mostrar tipo do timestamp
    for field in df.schema.fields:
        if 'timestamp' in field.name.lower() or 'time' in field.name.lower():
            print(f">>> Campo tempo: {field.name} = {field.dataType}")
            
    # Mostrar amostra
    print("\nAmostra de dados:")
    df.select("transaction_id", "timestamp", "amount").show(3, truncate=False)
    
except Exception as e:
    import traceback
    print(f"\nERRO: {e}")
    traceback.print_exc()

spark.stop()
