# 📋 Ajustes Pendentes para o Repositório Oficial - Brazilian Fraud Data Generator

## 🎯 Objetivo

Este documento lista todas as mudanças feitas na branch `v4-beta` do repositório local que precisam ser enviadas para o repositório oficial `afborda/brazilian-fraud-data-generator`.

> **Última atualização:** 2025-12-23

---

## 📊 Resumo dos Commits

| Commit | Descrição | Status |
|--------|-----------|--------|
| `PENDING` | fix: timestamp compatibility with Spark (ns → μs/string) | ⚠️ **NÃO COMMITADO** |
| `PENDING` | feat: worker_generate_and_upload_parquet para ProcessPoolExecutor | ⚠️ **NÃO COMMITADO** |
| `9fea949` | fix: corrigido cálculo de tamanho para --size gerar tamanho real | ⚠️ **LOCAL ONLY** (não pushado) |
| `3ada733` | perf: otimizações de performance e feedback de progresso | ✅ Pushado no v4-beta |
| `b1ca344` | fix: multiprocessing bug + add MinIO format support | ✅ Pushado no v4-beta |

---

## 🔥 MUDANÇAS CRÍTICAS NÃO COMMITADAS (2025-12-23)

### Problema: Incompatibilidade de Timestamps com Apache Spark

O Spark 3.x não suporta timestamps em nanosegundos do PyArrow. Isso causava erros ao ler arquivos Parquet gerados.

### Arquivos Modificados:
- `generate.py` (+255 linhas)
- `src/fraud_generator/exporters/parquet_exporter.py` (+40 linhas)
- `src/fraud_generator/exporters/minio_exporter.py` (+10 linhas)

### Solução Implementada:

#### 1. `parquet_exporter.py` - Conversão de Timestamps
```python
def _convert_timestamps_to_micros(self, table):
    """Convert timestamp columns from nanoseconds to microseconds for Spark compatibility."""
    import pyarrow as pa
    
    new_schema = []
    new_columns = []
    for i, field in enumerate(table.schema):
        col = table.column(i)
        if pa.types.is_timestamp(field.type):
            new_field = pa.field(field.name, pa.timestamp('us'), nullable=field.nullable)
            new_col = col.cast(pa.timestamp('us'))
            new_schema.append(new_field)
            new_columns.append(new_col)
        else:
            new_schema.append(field)
            new_columns.append(col)
    
    return pa.table(dict(zip(table.column_names, new_columns)), schema=pa.schema(new_schema))
```

#### 2. `generate.py` - Timestamps como String para MinIO
```python
# IMPORTANTE: Manter timestamp como STRING para compatibilidade com Spark
# NÃO converter para datetime pois isso causa inconsistência de schema entre partições
for col in df.columns:
    if 'timestamp' in col.lower() or 'date' in col.lower() or col.endswith('_at'):
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            df[col] = df[col].dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
        else:
            df[col] = df[col].astype(str)
```

#### 3. `generate.py` - Nova Função para ProcessPoolExecutor
```python
def worker_generate_and_upload_parquet(args: tuple) -> str:
    """
    Standalone worker for ProcessPoolExecutor - generates and uploads parquet to MinIO.
    Must be picklable (top-level function, no closures).
    """
    # ... implementação completa ...
    
    # Write parquet with snappy compression (compatible with Spark 3.x)
    pq.write_table(
        table, 
        local_path, 
        compression='snappy',
        use_dictionary=False,  # Evita problemas de PlainLongDictionary
        write_statistics=False,
        version='2.4',  # Parquet format version compatível
    )
```

### Ação Necessária:
```bash
cd fraud-generator
git add .
git commit -m "fix: timestamp compatibility with Spark 3.x (ns → μs conversion)"
git push origin v4-beta
```

---

## 🔧 Mudança 1: Correção do Cálculo de Tamanho (NÃO PUSHADO)

### Problema
O parâmetro `--size 10GB` estava gerando apenas ~5GB de dados reais porque o cálculo de bytes por transação estava incorreto.

### Arquivo: `generate.py` (linhas 73-79)

**ANTES:**
```python
# Configuration
TARGET_FILE_SIZE_MB = 128  # Each file will be ~128MB
BYTES_PER_TRANSACTION = 1050  # ~1KB per JSON transaction
TRANSACTIONS_PER_FILE = (TARGET_FILE_SIZE_MB * 1024 * 1024) // BYTES_PER_TRANSACTION
BYTES_PER_RIDE = 1200  # ~1.2KB per JSON ride
RIDES_PER_FILE = (TARGET_FILE_SIZE_MB * 1024 * 1024) // BYTES_PER_RIDE
```

**DEPOIS:**
```python
# Configuration
TARGET_FILE_SIZE_MB = 128  # Each file will be ~128MB
# IMPORTANT: Real JSONL size is ~500 bytes per transaction after formatting
# Using 500 bytes ensures --size 10GB actually generates ~10GB of data
BYTES_PER_TRANSACTION = 500  # Adjusted from 1050 to match real output size
TRANSACTIONS_PER_FILE = (TARGET_FILE_SIZE_MB * 1024 * 1024) // BYTES_PER_TRANSACTION
BYTES_PER_RIDE = 600  # Adjusted from 1200 to match real output size
RIDES_PER_FILE = (TARGET_FILE_SIZE_MB * 1024 * 1024) // BYTES_PER_RIDE
```

### Impacto
- `--size 10GB` agora gera ~10GB de dados (antes gerava ~5GB)
- `--size 50GB` agora gera ~50GB de dados (antes gerava ~25GB)
- Importante para testes de performance com volumes específicos

### Ação Necessária
```bash
cd fraud-generator
git push origin v4-beta
```

---

## 🚀 Mudança 2: Otimizações de Performance (Commit `3ada733`)

### Arquivos Modificados (7 arquivos, +352/-75 linhas)
- `generate.py`
- `README.md`
- `README.pt-BR.md`
- `src/fraud_generator/config/rideshare.py`
- `src/fraud_generator/exporters/minio_exporter.py`
- `src/fraud_generator/exporters/parquet_exporter.py`
- `src/fraud_generator/utils/streaming.py`

### Principais Mudanças:

#### 2.1. Aumento do Limite de Workers
```python
# ANTES:
max_workers = min(workers, num_files, 8)

# DEPOIS:
max_workers = min(workers, num_files, 16)
```

#### 2.2. Otimização de Upload MinIO
```python
# ANTES: put_object() com dados em memória (duplicação)
s3_client.put_object(
    Bucket=bucket_name,
    Key=object_key,
    Body=buffer.getvalue()
)

# DEPOIS: upload_fileobj() evita duplicação
s3_client.upload_fileobj(
    buffer,
    bucket_name,
    object_key,
    ExtraArgs={'ContentType': content_type}
)
```

#### 2.3. Compressão Parquet Padrão
```python
# ANTES: snappy (padrão do PyArrow)
df.to_parquet(buffer, engine='pyarrow', compression='snappy')

# DEPOIS: zstd (~91% menor que snappy)
df.to_parquet(buffer, engine='pyarrow', compression='zstd')
```

#### 2.4. Novo Argumento `--compression`
```python
parser.add_argument(
    '--compression',
    type=str,
    default='zstd',
    choices=['snappy', 'zstd', 'gzip', 'brotli', 'none'],
    help='Compression for Parquet files. zstd offers best compression/speed ratio.'
)
```

#### 2.5. Barra de Progresso Visual
Nova classe `ProgressTracker` em `streaming.py`:
```python
class ProgressTracker:
    """
    Mostra progresso visual durante geração batch.
    - Porcentagem completa
    - Velocidade (registros/s)
    - ETA estimado
    """
```

#### 2.6. Bugfix KeyError
```python
# ANTES (rideshare.py):
'PASSAGEIRO': {...}

# DEPOIS:
'PASSENGER': {...}  # Alinhado com English field names
```

### Status
✅ **Já pushado** no branch `v4-beta`

---

## 🔧 Mudança 3: Multiprocessing Fix + MinIO Formats (Commit `b1ca344`)

### Arquivos Modificados (4 arquivos, +432/-173 linhas)
- `generate.py`
- `requirements.txt`
- `requirements-streaming.txt`
- `src/fraud_generator/exporters/minio_exporter.py`

### Principais Mudanças:

#### 3.1. Correção de Bug de Indentação
```python
# ANTES (bug - UnboundLocalError):
with mp.Pool(workers) as pool:
    results = pool.map(worker_fn, args)
# 'results' undefined se exceção ocorresse

# DEPOIS (corrigido):
results = []
with mp.Pool(workers) as pool:
    for result in pool.imap_unordered(worker_fn, args):
        results.append(result)
```

#### 3.2. ThreadPoolExecutor para MinIO
```python
# ANTES: processamento sequencial
for batch_id in range(num_files):
    generate_and_upload(batch_id)

# DEPOIS: paralelo com ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = {executor.submit(generate_and_upload, i): i for i in range(num_files)}
    for future in as_completed(futures):
        result = future.result()
```

#### 3.3. Suporte a Parquet e CSV no MinIO
```python
# ANTES: apenas JSONL
if args.format != 'jsonl':
    print("MinIO only supports JSONL")
    sys.exit(1)

# DEPOIS: jsonl, csv, parquet
supported_minio_formats = ('jsonl', 'csv', 'parquet')
if args.format not in supported_minio_formats:
    print(f"MinIO supports: {', '.join(supported_minio_formats)}")
```

#### 3.4. Atualização de Dependências
```txt
# requirements.txt
boto3>=1.26.0
pandas>=2.0.0
pyarrow>=14.0.0
```

### Status
✅ **Já pushado** no branch `v4-beta`

---

## 🎯 Mudança 4: ProcessPoolExecutor (v4) - A Grande Otimização

### Contexto
Esta é a mudança mais importante - a implementação do `ProcessPoolExecutor` que permite bypass do GIL do Python.

### Arquivo: `generate.py` (linhas 460-520)

```python
def worker_generate_and_upload_parquet(args: tuple) -> str:
    """
    Standalone worker for ProcessPoolExecutor - generates and uploads parquet to MinIO.
    Must be picklable (top-level function, no closures).
    
    IMPORTANTE:
    - Função top-level (não aninhada) para ser serializável
    - Credenciais passadas como argumentos (não herdam de os.environ)
    - Cria cliente boto3 dentro do worker
    """
    (batch_id, num_transactions, customer_indexes, device_indexes,
     start_date, end_date, fraud_rate, use_profiles, seed,
     minio_endpoint, minio_access_key, minio_secret_key, bucket_name, object_prefix) = args
    
    import pandas as pd
    import tempfile
    import os
    import gc
    import boto3
    
    # Gera transações
    transactions = minio_generate_transaction_batch(...)
    
    # Converte para DataFrame
    df = pd.json_normalize(transactions)
    
    # Cria arquivo temporário
    tmpf = tempfile.NamedTemporaryFile(delete=False, suffix=".parquet")
    local_path = tmpf.name
    
    try:
        # Escreve Parquet com ZSTD
        df.to_parquet(local_path, engine='pyarrow', compression='zstd')
        
        # Cria cliente boto3 NO PROCESSO FILHO
        s3_client = boto3.client(
            's3',
            endpoint_url=minio_endpoint,
            aws_access_key_id=minio_access_key,
            aws_secret_access_key=minio_secret_key,
        )
        
        # Upload
        with open(local_path, 'rb') as f:
            s3_client.put_object(
                Bucket=bucket_name,
                Key=f'{object_prefix}/transactions_{batch_id:05d}.parquet',
                Body=f.read(),
            )
        
        return f'transactions_{batch_id:05d}.parquet'
    finally:
        os.remove(local_path)
        del df, transactions
        gc.collect()
```

### Uso no Main (linhas 1240-1280)
```python
# Para MinIO + Parquet: usa ProcessPoolExecutor (bypass GIL)
if use_minio and args.format == 'parquet':
    minio_endpoint = os.environ.get('MINIO_ENDPOINT', 'http://minio:9000')
    minio_access = os.environ.get('MINIO_ACCESS_KEY')
    minio_secret = os.environ.get('MINIO_SECRET_KEY')
    
    worker_args = [...]  # Prepara argumentos com credenciais
    
    # ProcessPoolExecutor = 4 cores reais!
    with ProcessPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(worker_generate_and_upload_parquet, args): i 
                   for i, args in enumerate(worker_args)}
        for future in as_completed(futures):
            filename = future.result()
            tx_results.append(filename)
```

### Status
✅ **Já pushado** no branch `v4-beta`

---

## 📊 Resultados de Performance

### Comparativo de Versões

| Versão | Método | CPU Real | Tempo (1GB) | Speedup |
|--------|--------|----------|-------------|---------|
| v2 | ThreadPoolExecutor + Chunks 10K | 100% (1 core) | 60 min | 1x |
| v3 | ThreadPoolExecutor + Full File | 100% (1 core) | 8.3 min | 7.2x |
| **v4** | **ProcessPoolExecutor + Parquet** | **400% (4 cores)** | **1.3 min** | **46x** |

### Métricas v4 (Testado)
```
📊 Geração de 1GB:
├── Tempo: 1.3 minutos
├── CPU: ~400% (4 cores)
├── Memória: ~4 GB
├── Throughput: 28,595 transações/segundo
└── Status: ✅ Funcionando
```

---

## 🚀 Ações Necessárias

### 1. Push do Commit Local (URGENTE)
```bash
cd /home/ubuntu/Estudos/1_projeto_bank_Fraud_detection_data_pipeline/fraud-generator
git push origin v4-beta
```

### 2. Criar Pull Request v4-beta → master
```bash
# Via GitHub CLI (se disponível)
gh pr create \
  --title "feat: v4-beta - ProcessPoolExecutor + Performance Optimizations" \
  --body "## Changes
- ProcessPoolExecutor para bypass do GIL (6.4x speedup)
- Suporte a Parquet/CSV no MinIO
- Correção do cálculo de tamanho (--size agora gera tamanho real)
- Barra de progresso visual
- Compressão ZSTD padrão" \
  --base master \
  --head v4-beta

# Ou manualmente em:
# https://github.com/afborda/brazilian-fraud-data-generator/compare/master...v4-beta
```

### 3. Atualizar README com Performance
Adicionar seção no README:
```markdown
## Performance

| Method | Time (1GB) | CPU Usage |
|--------|------------|-----------|
| Local (multiprocessing) | ~2 min | 800% |
| MinIO + Threading | 8 min | 100% |
| MinIO + ProcessPool | **1.3 min** | **400%** |
```

### 4. Criar Tag v3.2.1 ou v4.0.0
```bash
# Após merge do PR
git checkout master
git pull
git tag -a v4.0.0 -m "feat: ProcessPoolExecutor + Performance Optimizations"
git push origin v4.0.0
```

---

## 📝 Checklist de Validação

### Antes do Merge:

- [ ] Push do commit `9fea949` (correção de tamanho)
- [ ] Testar geração de 1GB com `--size 1GB`
- [ ] Verificar que gera ~1GB de dados reais
- [ ] Testar com MinIO + Parquet
- [ ] Verificar CPU usage ~400%
- [ ] Validar memória (~4GB para 4 workers)

### Após o Merge:

- [ ] Criar tag de release
- [ ] Atualizar Docker Hub image
- [ ] Atualizar README principal
- [ ] Anunciar no LinkedIn (documentação criada em POSTAGENS/)

---

## 🔗 Referências

- **Branch Local:** `v4-beta` (HEAD: `9fea949`)
- **Branch Remoto:** `origin/v4-beta` (HEAD: `3ada733`)
- **Repositório:** https://github.com/afborda/brazilian-fraud-data-generator
- **Documentação GIL:** `docs/GIL_OPTIMIZATION_TECHNICAL_ANALYSIS.md`
- **Comparativo Versões:** `docs/COMPARATIVO_VERSOES_V1_A_V4.md`

---

**Última Atualização:** 11 de dezembro de 2025  
**Autor:** Alberto Borda
