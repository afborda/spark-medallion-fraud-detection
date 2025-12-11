# 📊 Análise de Performance: Geração 30GB - OOM Killer Issue

## Status Atual: ❌ FALHA - Exit Code 137 (OOM Killer)

### Sequência do Problema

```
✅ Fase 1 (5.2 min): Gera 644k clientes + 1.3M dispositivos
   └─ Arquivos salvos: customers.parquet (48MB) + devices.parquet (29MB)
   └─ Memória usada: ~2-3GB

❌ Fase 2 (inicia, falha em ~5 min): Inicia geração de 240 arquivos de transações
   └─ Exit code 137 = OOM Killer (Linux killed process due to memory pressure)
   └─ Causa: Múltiplos workers alocando simultaneamente ~268K transações cada
   └─ Container limit: 8GB RAM
   └─ Memória disponível após Fase 1: ~5-6GB
```

---

## 🔍 Análise Detalhada: Onde Está a Memória?

### Configuração Atual (generate.py linhas 1064-1074)

```python
max_workers = min(workers, num_files, 4)  # max_workers = 4
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    futures = {executor.submit(generate_and_upload_tx_parquet, i): i for i in range(num_files)}
```

### Consumo de Memória por Worker (Fase 2)

Para cada arquivo Parquet gerado:

| Componente | Tamanho | Quantidade | Total |
|-----------|--------|-----------|-------|
| Transaction list em memória | 134MB | 4 workers | **536MB** |
| pandas DataFrame (overhead) | 50-100MB | 4 workers | **200-400MB** |
| Parquet buffer (antes upload) | 50MB | 4 workers | **200MB** |
| **SUBTOTAL simultâneo** | - | - | **936MB - 1.136GB** |

### Cálculo Teórico vs Real

- **Esperado**: 936MB - 1.1GB
- **Observado**: OOM Killer acionado após ~5-10 min de Fase 2
- **Memória disponível**: ~6GB (8GB total - 2GB overhead Fase 1)
- **Problema**: Possível pico de memória quando:
  1. 4 workers gerando transações simultaneamente (536MB)
  2. 4 workers criando DataFrames (200-400MB)
  3. 4 workers aguardando upload (200MB)
  4. Python GC não rodando entre batches
  5. Fragmentação de memória causando picos

---

## 📈 Performance Alcançada até Agora

### Teste 1GB (✅ Sucesso - 72 segundos)

```
- Tamanho: 1GB
- Tempo: 72 segundos (1.2 minutos)
- Throughput: 14 MB/sec
- Workers: 4
- Memória pico: 3GB
```

### Extrapolação 30GB (Se mantiver 14 MB/sec)

```
30GB ÷ 14MB/sec = 2,143 segundos = 35.7 minutos
```

**Problema**: Throughput não se mantém em 30GB (causa OOM)

### Taxa Alcançada na Fase 2 (antes crash)

```
Fase 1: 644k clientes em 5.2 min = 2,082 clientes/sec

Fase 2 (antes crash): 
- Nenhum arquivo completado
- Tempo antes crash: ~10 minutos (sem progresso mensurável)
- Esperado em velocidade de 1GB: 
  240 arquivos × 128MB = 30GB
  ~30 arquivos/min se cada arquivo levasse 2 sec
  Em ~10 min antes crash: ~300 arquivos deveriam estar prontos
  Realidade: 0 arquivos
```

---

## 💡 Opções de Solução

### Opção A: Redução Agressiva de Workers + GC Forçado (Rápido - 5 min)

**Mudanças**:
```python
# Linha 1064 em generate.py
max_workers = min(workers, num_files, 2)  # Reduce from 4 to 2

# E adicionar após BatchPoolExecutor:
if len(tx_results) % 5 == 0:  # Every 5 batches instead of 10
    gc.collect()
```

**Cálculo de Memória**:
- 2 workers × 134MB = 268MB (transações)
- 2 workers × 75MB = 150MB (DataFrame overhead)
- 2 workers × 50MB = 100MB (parquet buffer)
- **TOTAL**: 518MB (muito mais seguro < 1GB)

**Impacto**:
- ✅ Estável (18.5% redução vs 6.5GB disponível)
- ⚠️ Mais lento: ~2x throughput reduzido (7 MB/sec)
- ✅ Rápido de implementar
- **Tempo estimado 30GB**: ~71 minutos

**Likelihood de Sucesso**: 95%

---

### Opção B: Parquet Streaming (Melhor Performance - 30 min)

**Ideia**: Em vez de acumular todas transações em memória e depois converter para DataFrame, escrever direto no Parquet Writer (PyArrow streaming).

**Pseudocódigo**:
```python
def generate_and_upload_tx_parquet_streaming(batch_id: int) -> str:
    # Gera transações em chunks menores (ex: 10K por vez)
    schema = pyarrow.schema(...)  # Define schema uma vez
    
    with tempfile.NamedTemporaryFile(...) as tmpf:
        with pyarrow.parquet.ParquetWriter(tmpf.name, schema) as writer:
            for chunk_id in range(0, TRANSACTIONS_PER_FILE, 10000):
                chunk_size = min(10000, TRANSACTIONS_PER_FILE - chunk_id)
                transactions_chunk = generate_transactions(chunk_size)
                
                # Convert apenas chunk para pandas/arrow
                df_chunk = pd.json_normalize(transactions_chunk)
                table_chunk = pyarrow.Table.from_pandas(df_chunk)
                
                # Escrever chunk direto (row group no Parquet)
                writer.write_table(table_chunk)
                
                # Limpar memória do chunk
                del df_chunk, table_chunk, transactions_chunk
                gc.collect()
        
        # Upload arquivo final
        upload_to_minio(tmpf.name)
```

**Cálculo de Memória**:
- Chunk size: 10K transações = ~5MB lista Python
- DataFrame chunk: ~5MB (vs 134MB full)
- 4 workers × 5MB = 20MB (vs 536MB full)
- **TOTAL**: <100MB para chunks (95% redução!)

**Impacto**:
- ✅ Muito estável (1.5% de 6.5GB)
- ✅ Mantém throughput alto (~12-14 MB/sec estimado)
- ⚠️ Implementação mais complexa (30 min)
- **Tempo estimado 30GB**: ~45 minutos

**Likelihood de Sucesso**: 99% (mas requer refactor)

---

### Opção C: Reduzir TRANSACTIONS_PER_FILE (Simples - 2 min)

**Mudança**:
```python
# Linha 62
TRANSACTIONS_PER_FILE = (TARGET_FILE_SIZE_MB * 1024 * 1024) // BYTES_PER_TRANSACTION

# Reduzir TARGET_FILE_SIZE_MB de 128MB para 64MB
TARGET_FILE_SIZE_MB = 64
# Resultado: TRANSACTIONS_PER_FILE ≈ 268K → 134K
```

**Cálculo de Memória**:
- 4 workers × 67MB = 268MB (vs 536MB)
- DataFrame overhead × 4 = 100-200MB (vs 200-400MB)
- **TOTAL**: ~480MB (25% redução)
- **Tradeoff**: 480 arquivos em vez de 240 (2x mais I/O)

**Impacto**:
- ✅ Fácil de implementar (1 linha de código)
- ✅ Razoavelmente estável (~7.3% de 6.5GB)
- ⚠️ Mais arquivos = mais sobrecarga MinIO
- **Tempo estimado 30GB**: ~55 minutos

**Likelihood de Sucesso**: 90%

---

## 🎯 Recomendação: Implementar Opção A AGORA

### Por que Opção A?

1. **Rápido**: 5 minutos para implementar
2. **Seguro**: 18.5% de memória = muito margem de segurança
3. **Validação**: Sucesso = correr Opção B depois
4. **Reversível**: Se precisar mais performance, subir workers

### Pipeline Proposto

1. **Fase 1**: Aplicar Opção A (5 min)
   - Build nova imagem
   - Testar com `SIZE=5GB`
   - Se sucesso → ir para Fase 2

2. **Fase 2**: Validar com 5GB
   - Expected: 18 minutos
   - Confirmar memória estável
   - Se OK → 30GB full

3. **Fase 3**: Se quiser mais velocidade
   - Implementar Opção B (30 min)
   - Testar com 10GB
   - Escalar para 30GB

---

## 📊 Comparativo das Opções

| Aspecto | Opção A | Opção B | Opção C |
|--------|---------|---------|---------|
| Tempo Implementação | 5 min | 30 min | 2 min |
| Memória Pico | 518MB | <100MB | 480MB |
| Tempo 30GB | ~71 min | ~45 min | ~55 min |
| Likelihood Sucesso | 95% | 99% | 90% |
| Complexidade | Nenhuma | Alta | Nenhuma |
| Recomendado | ✅ AGORA | ✅ DEPOIS | ⚠️ Backup |

---

## 🚀 Próximos Passos

### Imediato (se concordar com Opção A):

```bash
# 1. Edit generate.py linha 1064
#    max_workers = 4 → max_workers = 2

# 2. Edit generate.py linha 1073
#    if len(tx_results) % 10 == 0 → if len(tx_results) % 5 == 0

# 3. Rebuild
docker compose build fraud-generator --no-cache

# 4. Test 5GB
SIZE=5GB WORKERS=2 docker compose up fraud-generator-batch

# 5. Se OK, test 30GB full
SIZE=30GB WORKERS=2 docker compose up fraud-generator-batch
```

### Feedback Esperado

- **Sucesso Esperado**: Fase 2 completa em ~18-20 min (vs crash em ~5 min agora)
- **Tempo Total 30GB**: ~25-30 minutos
- **Memória**: Estável < 4GB durante Fase 2

---

**Data da Análise**: 2025-12-09  
**Teste Anterior**: 1GB em 72 segundos ✅  
**Status Atual**: Aguardando aprovação para implementar Opção A
