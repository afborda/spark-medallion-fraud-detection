"""Teste simples de leitura dos Parquet"""
import sys
sys.path.insert(0, '/jobs')

from pyspark.sql import SparkSession
from config import apply_s3a_configs

spark = apply_s3a_configs(
    SparkSession.builder
    .appName("Test_Simple_Read")
    .config("spark.sql.parquet.enableVectorizedReader", "false")
).getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

print("\n" + "="*60)
print("TESTE SIMPLES DE LEITURA")
print("="*60)

try:
    # Listar arquivos primeiro
    hadoop_conf = spark._jsc.hadoopConfiguration()
    fs = spark._jvm.org.apache.hadoop.fs.FileSystem.get(
        spark._jvm.java.net.URI("s3a://fraud-data"), 
        hadoop_conf
    )
    path = spark._jvm.org.apache.hadoop.fs.Path("s3a://fraud-data/raw/batch/")
    files = fs.listStatus(path)
    
    print(f"\nArquivos em raw/batch/:")
    parquet_files = []
    for f in files[:10]:
        name = f.getPath().getName()
        if name.startswith("transactions_") and name.endswith(".parquet"):
            parquet_files.append(f"s3a://fraud-data/raw/batch/{name}")
            print(f"  {name}")
    
    if parquet_files:
        # Ler apenas 1 arquivo
        print(f"\nLendo primeiro arquivo: {parquet_files[0]}")
        df = spark.read.parquet(parquet_files[0])
        count = df.count()
        print(f"  Registros: {count}")
        print(f"  Colunas: {len(df.columns)}")
        df.select("transaction_id", "timestamp", "amount").show(3, truncate=False)
    else:
        print("Nenhum arquivo transactions encontrado!")
        
except Exception as e:
    print(f"ERRO: {e}")
    import traceback
    traceback.print_exc()

spark.stop()
print("\n✅ Teste finalizado")
