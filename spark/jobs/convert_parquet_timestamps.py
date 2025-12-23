"""
Script para converter arquivos Parquet com TIMESTAMP(NANOS) para formato compatível com Spark.
Usa PyArrow para ler e reescrever com timestamps em microsegundos.
"""
import pyarrow.parquet as pq
import pyarrow as pa
import pyarrow.fs as pafs
import os
from datetime import datetime

print("="*60)
print("CONVERSOR DE PARQUET - TIMESTAMP NANOS → MICROS")
print("="*60)

# Conectar ao MinIO
s3 = pafs.S3FileSystem(
    endpoint_override='minio:9000',
    access_key='minioadmin',
    secret_key='minioadmin',
    scheme='http'
)

# Listar arquivos
print("\n📂 Listando arquivos em raw/batch/...")
try:
    files = s3.get_file_info(pafs.FileSelector('fraud-data/raw/batch/', recursive=False))
    parquet_files = [f.path for f in files if f.path.endswith('.parquet') and 'transactions_' in f.path]
    print(f"   Encontrados {len(parquet_files)} arquivos de transações")
except Exception as e:
    print(f"ERRO ao listar: {e}")
    exit(1)

# Criar diretório de destino
dest_path = 'fraud-data/raw/batch_converted'
try:
    s3.create_dir(dest_path)
except:
    pass  # já existe

# Converter cada arquivo
converted = 0
errors = 0

for file_path in parquet_files:
    filename = os.path.basename(file_path)
    print(f"\n🔄 Convertendo {filename}...")
    
    try:
        # Ler arquivo
        with s3.open_input_file(file_path) as f:
            table = pq.read_table(f)
        
        # Converter schema - trocar TIMESTAMP[ns] por TIMESTAMP[us]
        new_schema = []
        for field in table.schema:
            if pa.types.is_timestamp(field.type):
                # Converter para microsegundos sem timezone
                new_field = pa.field(field.name, pa.timestamp('us'), nullable=field.nullable)
                new_schema.append(new_field)
            else:
                new_schema.append(field)
        
        new_schema = pa.schema(new_schema)
        
        # Converter colunas timestamp
        new_columns = []
        for i, col in enumerate(table.columns):
            if pa.types.is_timestamp(table.schema[i].type):
                # Cast para microsegundos
                new_col = col.cast(pa.timestamp('us'))
                new_columns.append(new_col)
            else:
                new_columns.append(col)
        
        new_table = pa.table(dict(zip(table.column_names, new_columns)), schema=new_schema)
        
        # Salvar
        dest_file = f"{dest_path}/{filename}"
        with s3.open_output_stream(dest_file) as f:
            pq.write_table(new_table, f, use_dictionary=True, compression='snappy')
        
        converted += 1
        print(f"   ✅ Convertido: {len(table)} registros")
        
    except Exception as e:
        errors += 1
        print(f"   ❌ Erro: {e}")

print("\n" + "="*60)
print(f"✅ CONVERSÃO CONCLUÍDA!")
print(f"   Convertidos: {converted}")
print(f"   Erros: {errors}")
print(f"   Destino: s3a://fraud-data/raw/batch_converted/")
print("="*60)
