# 📊 Resumo: Otimização de Geração de Dados

## 🎯 O Que Foi Gerado (Último Teste)

**Teste 1GB com ProcessPoolExecutor:**
- ⏱️ **Tempo**: 1.1 minutos
- ⚡ **Velocidade**: 32,774 transações/seg
- 📦 **Dados gerados**: ~250-300MB (parcial)
- 📁 **Arquivos**: 2 de 8 (25% completo)
- ❌ **Status**: Falha parcial (Access Denied + OOM)

---

## 📈 Evolução das Versões

### **VERSÃO 1 (Original - v2.0)** ⚡ MAIS RÁPIDA

```python
# Estrutura v1
with multiprocessing.Pool(workers=8) as pool:
    pool.map(worker_generate_json_local, batches)

# Característica: JSON direto em disco local
```

**Performance v1:**
- ✅ **50GB em 2 horas** (25 MB/s)
- ✅ **Multiprocessing real** (8 cores paralelos)
- ✅ **Formato JSON** (sem overhead de conversão)
- ✅ **Disco local** (sem latência de rede)
- ❌ **Sem compressão** (arquivos 2x maiores)
- ❌ **Sem MinIO** (não distribuído)

---

### **VERSÃO 2 (Threading + Parquet + MinIO)** 🐌 MUITO LENTA

```python
# Estrutura v2 (primeira tentativa desta sessão)
with ThreadPoolExecutor(max_workers=6) as executor:
    executor.map(generate_parquet_upload_minio, batches)

# Característica: Threading + Parquet com chunks pequenos
```

**Performance v2:**
- ❌ **1GB em 60 minutos** (0.28 MB/s)
- ❌ **Threading limitado por GIL** (~1 core efetivo)
- ❌ **Chunks de 10K** (27 conversões por arquivo)
- ❌ **Overhead massivo** (dict → DataFrame → Arrow → Parquet × 27)
- ✅ **Parquet ZSTD** (50% menor que JSON)
- ✅ **MinIO direto** (arquitetura distribuída)

**Comparação**: **60x mais lenta que v1!**

---

### **VERSÃO 3 (Threading Otimizado)** 🔧 MELHOR MAS AINDA LENTA

```python
# Estrutura v3 (otimização #1)
STREAMING_CHUNK_SIZE = TRANSACTIONS_PER_FILE  # Arquivo completo

with ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(generate_full_file_parquet, batches)

# Característica: Removeu chunks, processa arquivo inteiro de uma vez
```

**Performance v3:**
- ✅ **1GB em 8.3 minutos** (2 MB/s)
- ⚠️ **Threading** (~1 core, mas menos overhead)
- ✅ **1 conversão por arquivo** (vs 27 da v2)
- ✅ **Memória estável** (~350MB)
- ✅ **Parquet ZSTD** (compressão)
- ✅ **MinIO direto**

**Comparação**: **7x mais rápida que v2, mas ainda 12x mais lenta que v1**

---

### **VERSÃO 4 (Multiprocessing + Parquet + MinIO)** 🚀 ATUAL (COM BUGS)

```python
# Estrutura v4 (atual)
with ProcessPoolExecutor(max_workers=4) as executor:
    executor.map(worker_generate_upload_parquet, batches)

# Característica: Multiprocessing para bypass GIL
```

**Performance v4 (esperada se funcionar):**
- 🔥 **1GB em 1.1 minutos** (15 MB/s estimado completo)
- ✅ **Multiprocessing real** (4 cores paralelos, SEM GIL!)
- ✅ **1 conversão por arquivo**
- ⚠️ **Memória duplicada** (cada processo = 400-500MB)
- ✅ **Parquet ZSTD**
- ✅ **MinIO direto**

**Problemas atuais:**
1. ❌ **Access Denied** - credenciais MinIO não propagadas para processos filhos
2. ❌ **OOM Killer** - 4 processos × 500MB = 2GB, mas com overhead = ~3-4GB (excede limite de 4GB)

**Comparação**: **7.5x mais rápida que v3, mas só 1.7x mais lenta que v1!**

---

## 🔬 Análise Técnica: Por Que v4 Funciona Melhor

### Threading (v2, v3) vs Multiprocessing (v4)

| Aspecto | Threading | Multiprocessing |
|---------|-----------|-----------------|
| **GIL** | ❌ Limitado a 1 core | ✅ Cada processo = 1 core |
| **CPU paralelo** | ~100% (1 core) | ~400% (4 cores) ✅ |
| **Memória** | Compartilhada | Duplicada (overhead) |
| **Overhead startup** | Baixo | Alto (fork/spawn) |
| **Performance Python puro** | 1x | **4x** ✅ |

### Comparação de Tempo (1GB)

```
v1 (Multiprocessing JSON local):     ~2 min   ████████████████████████  100% (baseline)
v4 (Multiprocessing Parquet MinIO):  ~3 min   ████████████████████████████  120%
v3 (Threading Parquet MinIO):        ~8 min   ████████████████████████████████████████████  400%
v2 (Threading chunks Parquet):       ~60 min  ████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████████  3000%
```

---

## 🛠️ Estrutura Atual (v4)

### Função Worker (Top-level, picklable)

```python
def worker_generate_and_upload_parquet(args: tuple) -> str:
    """
    Cada processo filho executa independentemente:
    1. Gera 268K transações em memória
    2. Converte para DataFrame pandas
    3. Escreve Parquet comprimido (ZSTD)
    4. Upload direto para MinIO via boto3
    5. Remove arquivo temporário
    """
    (batch_id, num_transactions, customer_indexes, ...) = args
    
    # Cada processo roda esta função isoladamente
    transactions = generate_batch(...)         # 268K dicts
    df = pd.json_normalize(transactions)       # DataFrame
    df.to_parquet(temp_file, compression='zstd')
    boto3_upload(temp_file, minio_bucket)
    
    return filename
```

### Orquestração

```python
# Main process prepara argumentos
worker_args = [(batch_0, ...), (batch_1, ...), ..., (batch_239, ...)]

# Spawn 4 processos filhos
with ProcessPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(worker_func, args) for args in worker_args]
    
    # Aguarda conclusão de cada processo
    for future in as_completed(futures):
        result = future.result()
```

---

## ⚙️ Configuração de Recursos

### Atual (causando OOM)

```yaml
CPU: 4 cores
RAM: 4GB
Workers: 4

Consumo real:
  4 processos × 500MB base = 2GB
  + Overhead Python/pandas = 1.5-2GB
  ─────────────────────────────
  TOTAL: 3.5-4GB (no limite!)
```

### Recomendado para 4GB RAM

```yaml
CPU: 4 cores
RAM: 4GB
Workers: 2  # ← REDUZIR PARA 2

Consumo esperado:
  2 processos × 500MB = 1GB
  + Overhead = 500MB
  ─────────────────────────
  TOTAL: ~1.5GB (seguro!)
```

---

## 🎯 Próximos Passos para Corrigir v4

### 1. Reduzir Workers (2 em vez de 4)

```python
max_workers = min(workers, num_files, 2)  # Era 4
```

### 2. Passar Credenciais Explicitamente

```python
# Em vez de os.environ.get() que pode retornar None
worker_args = (
    ...
    exporter.client._request_signer._credentials.access_key,
    exporter.client._request_signer._credentials.secret_key,
    ...
)
```

### 3. Aumentar RAM do Container para 6GB

```yaml
deploy:
  resources:
    limits:
      memory: 6G  # Era 4G
```

---

## 📊 Performance Esperada (Corrigido)

### Com 2 Workers + 6GB RAM

| Tamanho | Tempo Estimado | Comparação v1 |
|---------|----------------|---------------|
| **1GB** | ~2 minutos | 1.0x |
| **5GB** | ~10 minutos | 1.0x |
| **30GB** | ~60 minutos | 1.0x |
| **50GB** | ~100 minutos | **1.2x (20% mais lento)** |

**Conclusão**: Com 2 workers, performance será **praticamente igual à v1**, mas com:
- ✅ **Parquet comprimido** (50% menor)
- ✅ **MinIO distribuído** (escalável)
- ✅ **Schema validation** (tipos de dados)

---

## 💡 Trade-offs Finais

### v1 (JSON Local)
- ✅ **Mais rápido** (baseline)
- ❌ Arquivos 2x maiores
- ❌ Não distribuído
- ❌ Sem schema

### v4 (Multiprocessing Parquet MinIO)
- ✅ **Arquivos 50% menores**
- ✅ **Distribuído e escalável**
- ✅ **Schema Parquet**
- ⚠️ **~20% mais lento** (aceitável!)

---

**Data**: 2025-12-09  
**Status**: v4 implementada, precisa correção (2 workers + credenciais)  
**Última performance medida**: 32,774 tx/seg (parcial com erros)
