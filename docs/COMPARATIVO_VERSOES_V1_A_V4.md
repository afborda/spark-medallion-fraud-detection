# 📊 Comparativo Completo: Versões do Gerador de Dados (v1 a v4)

## 🎯 Resumo Executivo

Este documento compara todas as versões do **Brazilian Fraud Data Generator**, mostrando a evolução de performance e as lições aprendidas.

---

## 📈 Tabela Comparativa Principal

| Versão | Método | CPU Real | Memória | Tempo (1GB) | Velocidade | Status |
|--------|--------|----------|---------|-------------|------------|--------|
| **v1** | multiprocessing.Pool + JSON | 800% (8 cores) | ~2 GB | ~2 min | 8.3 MB/s | ✅ Funcional |
| **v2** | ThreadPoolExecutor + Chunks 10K | 100% (1 core) | ~350 MB | 60 min | 0.28 MB/s | ✅ Funcional (lento) |
| **v3** | ThreadPoolExecutor + Full File | 100% (1 core) | ~350 MB | 8.3 min | 2 MB/s | ✅ Funcional |
| **v4** | ProcessPoolExecutor + Parquet | 400% (4 cores) | ~4 GB | 1.3 min | 13 MB/s | ✅ Funcional |

---

## 📊 Comparativo Visual

### ⏱️ Tempo para Processar 1GB

```
v2 (Threading + Chunks):  ████████████████████████████████████████████████████████████  60 min
v3 (Threading + Full):    ████████  8.3 min
v1 (Multiprocessing JSON): ██  2 min
v4 (Multiprocessing Parq): █  1.3 min ⚡ MAIS RÁPIDO!
```

### 🖥️ Uso de CPU

```
v2 (Threading):
Core 1: ████████████ 100%
Core 2: ░░░░░░░░░░░░ 0%
Core 3: ░░░░░░░░░░░░ 0%
Core 4: ░░░░░░░░░░░░ 0%
TOTAL: 100% (25% do sistema)

v3 (Threading Otimizado):
Core 1: ████████████ 100%
Core 2: ░░░░░░░░░░░░ 0%
Core 3: ░░░░░░░░░░░░ 0%
Core 4: ░░░░░░░░░░░░ 0%
TOTAL: 100% (25% do sistema)

v1 (Multiprocessing + JSON):
Core 1: ████████████ 100%
Core 2: ████████████ 100%
Core 3: ████████████ 100%
Core 4: ████████████ 100%
Core 5: ████████████ 100%
Core 6: ████████████ 100%
Core 7: ████████████ 100%
Core 8: ████████████ 100%
TOTAL: 800% (100% do sistema - 8 cores)

v4 (Multiprocessing + Parquet):
Core 1: ████████████ 100%
Core 2: ████████████ 100%
Core 3: ████████████ 100%
Core 4: ██████████░░ 90%
TOTAL: 390% (97% do sistema - 4 cores) 🔥
```

### 💾 Uso de Memória RAM

```
v2: █░░░░░░░░░  350 MB (mais econômico)
v3: █░░░░░░░░░  350 MB (mais econômico)
v1: ██░░░░░░░░  2 GB
v4: ████░░░░░░  4 GB (mais consumidor)
```

---

## 🔍 Análise Detalhada de Cada Versão

---

### 📦 Versão 1 (v1) - Baseline Original

| Característica | Valor |
|----------------|-------|
| **Método** | `multiprocessing.Pool` |
| **Workers** | 8 |
| **Formato** | JSON (sem compressão) |
| **Destino** | Disco local (`/data/raw/`) |
| **Chunk Size** | Variável |

#### Performance Medida:
```
📊 MÉTRICAS v1:
├── Tempo (1GB): ~2 minutos
├── Tempo (50GB): ~2 horas
├── Throughput: 8.3 MB/s
├── CPU Usage: ~800% (8 cores)
├── Memória Peak: ~2 GB
└── Status: ✅ Funcional (baseline)
```

#### Código Principal:
```python
import multiprocessing

def generate_batch(args):
    """Worker function para multiprocessing.Pool"""
    batch_id, num_transactions = args
    transactions = []
    for i in range(num_transactions):
        tx = generate_single_transaction(...)
        transactions.append(tx)
    
    # Salva como JSON no disco local
    with open(f'/data/raw/batch_{batch_id}.json', 'w') as f:
        json.dump(transactions, f)
    return batch_id

# Execução paralela
with multiprocessing.Pool(processes=8) as pool:
    results = pool.map(generate_batch, batch_args)
```

#### ✅ Vantagens:
- Paralelismo real (cada processo tem seu GIL)
- Alta velocidade de geração
- Uso eficiente de todos os cores

#### ❌ Desvantagens:
- Formato JSON é ~2x maior que Parquet
- Sem compressão dos dados
- Não grava direto no Object Storage (MinIO)
- Requer etapa adicional de ingestão

---

### 📦 Versão 2 (v2) - Threading com Chunks Pequenos

| Característica | Valor |
|----------------|-------|
| **Método** | `ThreadPoolExecutor` |
| **Workers** | 6 |
| **Formato** | Parquet + ZSTD |
| **Destino** | MinIO (S3-compatible) |
| **Chunk Size** | 10.000 transações |

#### Performance Medida:
```
📊 MÉTRICAS v2:
├── Tempo (1GB): 60 minutos ⚠️ MUITO LENTO
├── Tempo (50GB): ~50 horas (estimado)
├── Throughput: 0.28 MB/s
├── CPU Usage: ~100% (apenas 1 core!)
├── Memória Peak: ~350 MB
└── Status: ✅ Funcional mas inviável
```

#### O Problema: GIL + Chunks Pequenos

```
🔒 PROBLEMA DO GIL:
Threading em Python NÃO paraleliza código CPU-bound.
Apenas 1 thread executa Python por vez!

📦 PROBLEMA DOS CHUNKS:
1 arquivo = 268.000 transações
268.000 ÷ 10.000 = 27 chunks por arquivo

Cada chunk tem overhead de:
  ├── Gerar dicts Python      (CPU-bound)
  ├── Criar DataFrame Pandas  (CPU-bound)
  ├── Serializar Parquet      (CPU-bound)
  ├── Escrever em BytesIO     (I/O)
  └── Upload para MinIO       (I/O)

TOTAL: 27 × overhead = 60 minutos! 😱
```

#### Código Principal:
```python
from concurrent.futures import ThreadPoolExecutor

def generate_chunk(args):
    """Worker para gerar um chunk de 10K transações"""
    chunk_id, chunk_size = args
    transactions = []
    for i in range(chunk_size):
        tx = generate_transaction(...)
        transactions.append(tx)
    
    df = pd.DataFrame(transactions)
    buffer = BytesIO()
    df.to_parquet(buffer, compression='zstd')
    
    # Upload para MinIO
    s3_client.put_object(
        Bucket='fraud-data',
        Key=f'batch_{chunk_id}.parquet',
        Body=buffer.getvalue()
    )

# 6 workers, mas só 1 trabalha por vez (GIL)
with ThreadPoolExecutor(max_workers=6) as executor:
    futures = [executor.submit(generate_chunk, args) for args in chunk_args]
```

#### ⚠️ Lição Aprendida:
> **Threading NÃO paraleliza código CPU-bound em Python!**
> O GIL (Global Interpreter Lock) permite apenas 1 thread executar código Python por vez.

---

### 📦 Versão 3 (v3) - Threading Otimizado

| Característica | Valor |
|----------------|-------|
| **Método** | `ThreadPoolExecutor` |
| **Workers** | 4 |
| **Formato** | Parquet + ZSTD |
| **Destino** | MinIO (S3-compatible) |
| **Chunk Size** | 268.000 (arquivo inteiro) |

#### Performance Medida:
```
📊 MÉTRICAS v3:
├── Tempo (1GB): 8.3 minutos
├── Tempo (50GB): ~7 horas
├── Throughput: 2 MB/s
├── CPU Usage: ~100% (ainda 1 core)
├── Memória Peak: ~350 MB
└── Status: ✅ Funcional e estável
```

#### Otimização: Eliminar Overhead de Chunks

```
v2: 27 chunks × overhead = 60 min
v3: 1 chunk × overhead = 8.3 min

MELHORIA: 7.2x mais rápido! 🎉
(apenas removendo a fragmentação)
```

#### Código Principal:
```python
from concurrent.futures import ThreadPoolExecutor

TRANSACTIONS_PER_FILE = 268_000  # Arquivo completo

def generate_full_file(args):
    """Worker para gerar arquivo completo (sem chunks)"""
    file_id, num_transactions = args
    transactions = []
    
    # Gera TODAS as transações de uma vez
    for i in range(num_transactions):
        tx = generate_transaction(...)
        transactions.append(tx)
    
    # UMA ÚNICA conversão para DataFrame
    df = pd.DataFrame(transactions)
    buffer = BytesIO()
    df.to_parquet(buffer, compression='zstd')
    
    # Upload para MinIO
    s3_client.put_object(
        Bucket='fraud-data',
        Key=f'batch_{file_id}.parquet',
        Body=buffer.getvalue()
    )

with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(generate_full_file, args) for args in file_args]
```

#### ✅ Vantagens sobre v2:
- 7.2x mais rápido
- Mesma memória baixa (~350 MB)
- Estável e confiável
- Sem erros de credenciais

#### ❌ Ainda limitado:
- CPU: apenas 1 core (GIL)
- 4x mais lento que v1
- Não aproveita múltiplos cores

---

### 📦 Versão 4 (v4) - Multiprocessing com Parquet ⭐ ATUAL

| Característica | Valor |
|----------------|-------|
| **Método** | `ProcessPoolExecutor` |
| **Workers** | 4 |
| **Formato** | Parquet + ZSTD |
| **Destino** | MinIO (S3-compatible) |
| **Chunk Size** | 268.000 (arquivo inteiro) |

#### Performance Medida:
```
📊 MÉTRICAS v4:
├── Tempo (1GB): 1.3 minutos ⚡
├── Tempo (5GB): ~6.5 minutos
├── Tempo (50GB): ~65 minutos
├── Throughput: 13 MB/s
├── Transações/segundo: 28.595
├── CPU Usage: ~400% (4 cores reais!)
├── Memória Peak: ~4 GB
└── Status: ✅ Funcional 🎉
```

#### A Grande Mudança: Thread → Process

```python
# ❌ v3: Threading (limitado pelo GIL)
from concurrent.futures import ThreadPoolExecutor
with ThreadPoolExecutor(max_workers=4) as executor:
    # CPU: ~100% (apenas 1 core)

# ✅ v4: Multiprocessing (bypassa o GIL)
from concurrent.futures import ProcessPoolExecutor
with ProcessPoolExecutor(max_workers=4) as executor:
    # CPU: ~400% (4 cores reais!)
```

#### Código Principal:
```python
from concurrent.futures import ProcessPoolExecutor

def worker_generate_and_upload_parquet(args: tuple) -> str:
    """
    Worker para ProcessPoolExecutor.
    IMPORTANTE: Função top-level (picklable).
    Credenciais passadas como argumentos (não herdam do ambiente).
    """
    (batch_id, num_transactions, 
     minio_endpoint, minio_access_key, minio_secret_key,
     bucket_name, object_prefix) = args
    
    import boto3
    import pandas as pd
    
    # Cria cliente boto3 no processo filho
    s3_client = boto3.client(
        's3',
        endpoint_url=minio_endpoint,
        aws_access_key_id=minio_access_key,
        aws_secret_access_key=minio_secret_key
    )
    
    # Gera transações
    transactions = []
    for i in range(num_transactions):
        tx = generate_transaction(...)
        transactions.append(tx)
    
    # Converte e faz upload
    df = pd.DataFrame(transactions)
    buffer = BytesIO()
    df.to_parquet(buffer, compression='zstd')
    
    s3_client.put_object(
        Bucket=bucket_name,
        Key=f'{object_prefix}/batch_{batch_id}.parquet',
        Body=buffer.getvalue()
    )
    
    return f'batch_{batch_id}.parquet'

# Execução com multiprocessing REAL
with ProcessPoolExecutor(max_workers=4) as executor:
    futures = []
    for batch_id in range(num_files):
        args = (
            batch_id, num_transactions,
            minio_endpoint, access_key, secret_key,  # Credenciais explícitas!
            bucket_name, object_prefix
        )
        future = executor.submit(worker_generate_and_upload_parquet, args)
        futures.append(future)
```

#### ⚠️ Pontos Críticos da v4:

1. **Credenciais Explícitas:**
```python
# ❌ ERRADO: variáveis de ambiente não propagam
def worker():
    key = os.environ.get('MINIO_ACCESS_KEY')  # None!

# ✅ CORRETO: passar como argumentos
def worker(args):
    (batch_id, ..., access_key, secret_key) = args
```

2. **Função Top-Level (Picklable):**
```python
# ❌ ERRADO: função aninhada não serializa
def main():
    def worker(x):  # Função local
        return x * 2
    executor.submit(worker, 1)  # Erro!

# ✅ CORRETO: função no nível do módulo
def worker(x):  # Top-level
    return x * 2
```

3. **Trade-off de Memória:**
```
v3: 1 processo × 350 MB = 350 MB total
v4: 4 processos × 1 GB = 4 GB total

Paga-se com memória, ganha-se em velocidade!
```

---

## 📊 Comparativo de Speedup

### Speedup Relativo (base = v2)

| Versão | Tempo (1GB) | Speedup vs v2 | Speedup vs v3 |
|--------|-------------|---------------|---------------|
| v2 | 60 min | 1x | - |
| v3 | 8.3 min | 7.2x | 1x |
| v1 | 2 min | 30x | 4.1x |
| **v4** | **1.3 min** | **46x** | **6.4x** |

### Visualização do Speedup:

```
SPEEDUP vs v2 (mais lento):

v2: █ (1x baseline)
v3: ███████ (7.2x)
v1: ██████████████████████████████ (30x)
v4: ██████████████████████████████████████████████ (46x) 🏆
```

---

## 🎯 Recomendações de Uso

### Quando Usar Cada Versão:

| Cenário | Versão Recomendada | Motivo |
|---------|-------------------|--------|
| **Produção (alta performance)** | v4 | Mais rápido, Parquet comprimido |
| **Memória limitada (<2GB)** | v3 | Baixo consumo de RAM |
| **Disco local apenas** | v1 | Funciona sem Object Storage |
| **Debug/Desenvolvimento** | v3 | Estável, logs claros |

### Regra de Ouro:

```
📌 RESUMO:

✅ Precisa de VELOCIDADE? → v4 (ProcessPoolExecutor)
✅ Precisa de ECONOMIA de RAM? → v3 (ThreadPoolExecutor)
✅ Não tem MinIO/S3? → v1 (Disco local)
❌ NUNCA use v2 (chunks pequenos são ineficientes)
```

---

## 📈 Projeções de Tempo

### Estimativas para Diferentes Volumes:

| Volume | v2 | v3 | v1 | v4 |
|--------|-----|-----|-----|-----|
| 1 GB | 60 min | 8.3 min | 2 min | 1.3 min |
| 5 GB | 5 horas | 41 min | 10 min | 6.5 min |
| 10 GB | 10 horas | 1.4 horas | 20 min | 13 min |
| 50 GB | 50 horas | 7 horas | 1.7 horas | 65 min |
| 100 GB | 100 horas | 14 horas | 3.3 horas | 2.2 horas |

### Economia de Tempo com v4:

```
📦 Geração de 50GB:

v2: ████████████████████████████████████████████████████ 50 horas
v3: ███████ 7 horas
v1: █░ 1.7 horas
v4: █ 65 min ⚡

ECONOMIA v4 vs v3: 5.9 horas (85% de redução!)
ECONOMIA v4 vs v2: 49 horas (98% de redução!)
```

---

## 🔧 Configurações de Ambiente

### Docker Compose (v4):

```yaml
# docker-compose.yml
fraud-generator-batch:
  image: brazilian-fraud-generator:latest
  environment:
    SIZE: ${SIZE:-1GB}
    WORKERS: ${WORKERS:-4}
    MINIO_ENDPOINT: http://minio:9000
    MINIO_ACCESS_KEY: minioadmin
    MINIO_SECRET_KEY: Brasil03
    OUTPUT_FORMAT: parquet
  deploy:
    resources:
      limits:
        cpus: '4'
        memory: 6G
      reservations:
        cpus: '2'
        memory: 2G
```

### Execução:

```bash
# Gerar 1GB com 4 workers
SIZE=1GB WORKERS=4 docker-compose run --rm fraud-generator-batch

# Gerar 5GB com 4 workers
SIZE=5GB WORKERS=4 docker-compose run --rm fraud-generator-batch

# Gerar 50GB com 8 workers (se tiver 8+ cores)
SIZE=50GB WORKERS=8 docker-compose run --rm fraud-generator-batch
```

---

## 📝 Conclusão

### Evolução da Performance:

```
v2 (60 min) → v3 (8.3 min) → v4 (1.3 min)
     │              │              │
     │              │              └── ProcessPoolExecutor
     │              └── Eliminou chunks
     └── Threading com chunks (PROBLEMA: GIL + overhead)

MELHORIA TOTAL: 46x mais rápido! 🚀
```

### Lições Aprendidas:

1. **Threading ≠ Paralelismo em Python** (GIL limita a 1 core)
2. **Chunks pequenos = overhead gigante** (27 conversões vs 1)
3. **ProcessPoolExecutor bypassa o GIL** (cada processo tem seu GIL)
4. **Credenciais devem ser explícitas** (processos não herdam ambiente)
5. **Trade-off velocidade/memória** (4x RAM para 6.4x velocidade)

---

**Última Atualização:** 11 de dezembro de 2025  
**Projeto:** spark-medallion-fraud-detection  
**Repositório:** github.com/afborda/spark-medallion-fraud-detection
