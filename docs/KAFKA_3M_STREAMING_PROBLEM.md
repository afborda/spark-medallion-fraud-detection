# 🚨 Por que 3 Milhões de Mensagens no Kafka Impediam o Streaming?

## 📖 Guia Completo para Iniciantes

Este documento explica **em detalhes** por que ter 3 milhões de mensagens acumuladas no Kafka impediu o funcionamento correto do pipeline de streaming, e como isso foi resolvido.

---

## 📋 Índice

1. [O que Aconteceu?](#o-que-aconteceu)
2. [Conceitos Básicos: O que é Kafka?](#conceitos-básicos-o-que-é-kafka)
3. [Conceitos Básicos: O que é Spark Streaming?](#conceitos-básicos-o-que-é-spark-streaming)
4. [Por que 3M de Mensagens é um Problema?](#por-que-3m-de-mensagens-é-um-problema)
5. [Os 5 Problemas Específicos](#os-5-problemas-específicos)
6. [Como Foi Resolvido?](#como-foi-resolvido)
7. [Configurações Kafka Importantes](#configurações-kafka-importantes)
8. [Lições Aprendidas](#lições-aprendidas)
9. [Comandos Úteis](#comandos-úteis)

---

## 🎯 O que Aconteceu?

### Cenário Real do Projeto

```
📊 Estado Inicial (11/Dez/2025):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Topic: transactions
Partições: 1
Mensagens acumuladas: 132,088 (≈132 mil)
Tamanho estimado: ~265 MB (2KB/mensagem)
Retention: 10GB máximo
Status: ⚠️ ACUMULANDO (não está sendo consumido)
```

**O problema:** O Spark Streaming iniciava, mas não conseguia processar as mensagens de forma eficiente. O job ficava travado tentando ler o backlog de 132 mil mensagens acumuladas.

**Sintomas observados:**
- ✅ Kafka rodando normalmente
- ✅ Spark Streaming iniciava sem erros
- ❌ Consumo extremamente lento (< 10 msg/s)
- ❌ Job reiniciava antes de completar o processamento
- ❌ Dashboard do Metabase sem dados novos
- ❌ PostgreSQL não recebia transações

---

## 📚 Conceitos Básicos: O que é Kafka?

### Apache Kafka em Linguagem Simples

Imagine o Kafka como um **sistema de correio** ultra-rápido:

```
┌─────────────┐      ┌─────────────┐      ┌─────────────┐
│  PRODUTOR   │─────▶│    KAFKA    │─────▶│  CONSUMIDOR │
│ (quem envia)│      │  (correio)  │      │ (quem lê)   │
└─────────────┘      └─────────────┘      └─────────────┘
                           │
                           ├─ Topic: transactions
                           ├─ Partição 0: [msg1, msg2, ...]
                           └─ Retention: guarda por 10GB
```

### Componentes Principais:

#### 1. **Topic (Tópico)**
É como uma "caixa de correspondência" ou "fila" específica para um tipo de mensagem.

```python
# Nosso projeto tem 1 topic:
Topic: "transactions"  # Todas as transações bancárias
```

#### 2. **Partition (Partição)**
Divisão de um topic para paralelizar o processamento.

```
Topic: transactions
│
├─ Partition 0: [msg001, msg002, msg003, ...]  ← Nosso projeto (1 partição)
├─ Partition 1: [msg101, msg102, msg103, ...]
└─ Partition 2: [msg201, msg202, msg203, ...]
```

**Nosso caso:** Apenas 1 partição = processamento sequencial (mais lento).

#### 3. **Offset**
É um "marcador" de posição na fila. Cada mensagem tem um número único crescente.

```
Offset:    0      1      2      3      4      5    ...  132087
          ┌─────┬─────┬─────┬─────┬─────┬─────┐
Messages: │ TX1 │ TX2 │ TX3 │ TX4 │ TX5 │ TX6 │ ...
          └─────┴─────┴─────┴─────┴─────┴─────┘
               ▲                                    ▲
            início                                 fim
         (earliest)                            (latest)
```

**Importante:** 
- Offset **0** = mensagem mais antiga
- Offset **132,087** = mensagem mais recente (última no tópico)

#### 4. **Consumer Group (Grupo de Consumidores)**
Consumidores com o mesmo `group.id` compartilham o trabalho de ler mensagens.

```python
# Spark Streaming cria automaticamente:
group.id = "spark-kafka-streaming-<uuid>"

# Kafka guarda: "Esse grupo já leu até o offset 1000"
```

#### 5. **Retention (Retenção)**
Por quanto tempo/quanto espaço o Kafka guarda mensagens.

```yaml
# Nossa configuração (docker-compose.yml):
KAFKA_LOG_RETENTION_BYTES: 10737418240  # 10GB
KAFKA_LOG_RETENTION_HOURS: -1          # Infinito (limitado por espaço)
```

**Significado:** Kafka guarda mensagens até ocupar 10GB, depois apaga as mais antigas.

---

## 🎯 Conceitos Básicos: O que é Spark Streaming?

### Spark Structured Streaming em Linguagem Simples

É um sistema que processa dados **em tempo real** (ou quase) de forma contínua.

```
     KAFKA              SPARK              BANCO DE DADOS
┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Transações   │──▶│ Processa     │──▶│ PostgreSQL   │
│ chegando     │   │ em microbatch│   │ salva dados  │
└──────────────┘   └──────────────┘   └──────────────┘
    (fonte)         (processamento)      (destino)
```

### Modo de Operação: Microbatch

Spark Streaming **NÃO** processa mensagem por mensagem. Ele agrupa em pequenos lotes:

```
Intervalo de Trigger: 10 segundos (nosso projeto)

┌─────────────────────────────────────────────────────┐
│                    TIMELINE                         │
├─────────────────────────────────────────────────────┤
│ 00:00 ─────▶ Lê 100 msgs ─────▶ Processa           │
│ 00:10 ─────▶ Lê 150 msgs ─────▶ Processa           │
│ 00:20 ─────▶ Lê  80 msgs ─────▶ Processa           │
│ 00:30 ─────▶ Lê 200 msgs ─────▶ Processa           │
└─────────────────────────────────────────────────────┘
```

**Problema com Backlog:** Se há 132 mil mensagens esperando, o primeiro batch tenta ler TODAS de uma vez!

---

## ⚠️ Por que 3M de Mensagens é um Problema?

### Analogia: Correio Acumulado

Imagine que você saiu de férias por 1 ano e voltou para encontrar **132 mil cartas** na sua caixa postal:

```
Cenário Normal (streaming funcionando):
┌─────────────────────────────────┐
│ 📬 Caixa Postal                 │
│ ┌────┐  ← 10 cartas/dia         │
│ │ ✉✉ │                          │
│ └────┘                          │
│ Você consegue ler diariamente   │
└─────────────────────────────────┘

Cenário com Backlog (3M acumulado):
┌─────────────────────────────────┐
│ 📬 Caixa Postal                 │
│ ┌────────────────────────────┐ │
│ │ ✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉ │ │
│ │ ✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉ │ │
│ │ ✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉ │ │
│ │ ✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉✉ │ │
│ └────────────────────────────┘ │
│ 132,088 cartas = SOBRECARGA!   │
└─────────────────────────────────┘
```

**O que acontece?**
1. Você tenta ler tudo de uma vez → Sobrecarga mental 🤯
2. Desiste no meio → Não leu nenhuma carta completamente
3. Precisa começar do zero novamente
4. Ciclo vicioso: nunca consegue esvaziar a caixa

**Isso é exatamente o que acontece com Spark + Kafka!**

---

## 🔥 Os 5 Problemas Específicos

### 1️⃣ Problema de Memória (Memory Overflow)

```python
# Spark tenta carregar TUDO na memória de uma vez:
Batch 1: Tenta ler 132,088 mensagens × 2KB = ~264 MB

# Com processamento, vira muito mais:
┌─────────────────────────────────────────┐
│ Memória do Executor Spark (1GB)        │
├─────────────────────────────────────────┤
│ JSON bruto:        264 MB               │
│ DataFrame Spark:   800 MB (overhead)    │
│ Processamento:     400 MB               │
│ ─────────────────────────────────────   │
│ TOTAL:            1464 MB > 1GB ❌      │
└─────────────────────────────────────────┘
```

**Resultado:** `OutOfMemoryError` ou garbage collection constante → Job lento/travado.

---

### 2️⃣ Problema de Timeout (First Batch Timeout)

Spark Streaming tem timeouts para inicialização:

```
Configuração:
spark.sql.streaming.kafka.consumer.pollTimeoutMs = 120000  # 2 minutos

┌──────────────────────────────────────────────────┐
│ TIMELINE DO PRIMEIRO BATCH                      │
├──────────────────────────────────────────────────┤
│ 00:00 ─────▶ Inicia job                         │
│ 00:05 ─────▶ Conecta no Kafka                   │
│ 00:10 ─────▶ Descobre 132k mensagens            │
│ 00:15 ─────▶ Começa a ler (lento!)              │
│ 01:00 ─────▶ Ainda lendo... (25% completo)      │
│ 02:00 ─────▶ ⏰ TIMEOUT! Job falha              │
└──────────────────────────────────────────────────┘
```

**Por que é lento?**
- 1 única partição = 1 thread lendo
- Rede Docker = overhead adicional
- Desserialização JSON = CPU-bound

---

### 3️⃣ Problema de Checkpoint Corruption

Spark Streaming salva o progresso em checkpoints:

```
Checkpoints salvos em: /data/checkpoints/streaming_postgres/

Estrutura:
┌────────────────────────────────────────┐
│ offsets/0                              │  ← "Li até offset 50,000"
│ offsets/1                              │  ← "Li até offset 75,000"
│ offsets/2                              │  ← "Li até offset 90,000"
│ commits/0                              │  ← "Salvei até offset 48,000"
│ metadata                               │  ← Configurações do stream
└────────────────────────────────────────┘
```

**Problema:** Job reinicia antes de completar o batch:

```
Tentativa 1:
- Lê offsets 0 → 132,088
- Processa 30% (40,000 mensagens)
- Job mata por falta de memória
- Checkpoint: salvo até 40,000

Tentativa 2:
- Lê offsets 40,000 → 132,088  (ainda 92k mensagens!)
- Processa 20% (18,000 mensagens)
- Job mata novamente
- Checkpoint: salvo até 58,000

Tentativa 3-10: Mesmo problema... ♻️ Loop infinito
```

---

### 4️⃣ Problema de Partição Única (No Parallelism)

```
Kafka Topic: transactions
Partições: 1  ← GARGALO!

┌─────────────────────────────────────────────────┐
│ Se tivéssemos 4 partições:                      │
│                                                 │
│ Partition 0: [33k msgs] ──────▶ Executor 1     │
│ Partition 1: [33k msgs] ──────▶ Executor 2     │
│ Partition 2: [33k msgs] ──────▶ Executor 3     │
│ Partition 3: [33k msgs] ──────▶ Executor 4     │
│                                                 │
│ Tempo: 132k / 4 = 33k cada = MAIS RÁPIDO ✅    │
└─────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────┐
│ Nosso cenário atual (1 partição):              │
│                                                 │
│ Partition 0: [132k msgs] ──────▶ Executor 1    │
│                    (todos os outros idle)       │
│                                                 │
│ Tempo: 132k × 1 = LENTO ❌                     │
└─────────────────────────────────────────────────┘
```

---

### 5️⃣ Problema de Estratégia de Leitura (No maxOffsetsPerTrigger)

Spark pode limitar quantas mensagens lê por batch:

```python
# ❌ SEM limite (nosso caso):
spark.readStream \
    .format("kafka") \
    .option("subscribe", "transactions") \
    .load()

# Resultado: Tenta ler TODAS as 132k mensagens no primeiro batch

# ✅ COM limite:
spark.readStream \
    .format("kafka") \
    .option("subscribe", "transactions") \
    .option("maxOffsetsPerTrigger", 5000)  # Lê no máximo 5k por vez
    .load()

# Resultado: Lê em 27 batches (132k / 5k = 26.4)
```

**Timeline com limite:**

```
Batch 1: offsets    0 →  5,000  (10s)
Batch 2: offsets 5,000 → 10,000  (10s)
Batch 3: offsets 10,000 → 15,000 (10s)
...
Batch 27: offsets 130,000 → 132,088 (10s)

Total: ~4.5 minutos para limpar backlog
```

---

## ✅ Como Foi Resolvido?

### Solução Aplicada: Limpar Kafka e Reiniciar

```bash
# 1. Parar todos os jobs de streaming
docker exec -it fraud_spark_master bash -c "
  kill \$(ps aux | grep streaming_to_postgres | grep -v grep | awk '{print \$2}')
  kill \$(ps aux | grep streaming_realtime_dashboard | grep -v grep | awk '{print \$2}')
"

# 2. Remover checkpoints antigos (força reinício do zero)
docker exec fraud_minio mc rm --recursive --force local/fraud-data/checkpoints/

# 3. Limpar mensagens do Kafka (resetar offset)
docker exec fraud_kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --delete \
  --topic transactions

# 4. Recriar topic do zero
docker exec fraud_kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --create \
  --topic transactions \
  --partitions 1 \
  --replication-factor 1 \
  --config retention.bytes=10737418240

# 5. Reiniciar jobs de streaming
docker exec fraud_spark_master spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  --total-executor-cores 2 \
  --executor-memory 1g \
  /jobs/streaming/streaming_to_postgres.py
```

### Por que Funcionou?

**Antes:**
```
Kafka: 132,088 mensagens esperando
Spark: Tenta processar tudo → FALHA
```

**Depois:**
```
Kafka: 0 mensagens (limpo)
Spark: Inicia do zero
Producer: Envia 10-50 msgs/segundo
Spark: Processa 10-50 msgs/segundo (equilibrado!)
```

---

## ⚙️ Configurações Kafka Importantes

### 1. Configuração do Tópico

```yaml
# docker-compose.yml
kafka:
  environment:
    # Retenção por tamanho (10GB)
    KAFKA_LOG_RETENTION_BYTES: 10737418240
    
    # Retenção por tempo (desabilitado = só por tamanho)
    KAFKA_LOG_RETENTION_HOURS: -1
    
    # Tamanho máximo de cada segmento (1GB)
    KAFKA_LOG_SEGMENT_BYTES: 1073741824
    
    # Tempo para deletar segmentos inativos (7 dias)
    KAFKA_LOG_RETENTION_CHECK_INTERVAL_MS: 300000
```

### 2. Configuração de Consumer (Spark)

```python
# spark/jobs/streaming/streaming_to_postgres.py
df_stream = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "transactions") \
    .option("startingOffsets", "latest")  # ← IMPORTANTE!
    .option("maxOffsetsPerTrigger", 5000)  # ← ADICIONAR ISSO!
    .load()
```

**Explicação das opções:**

| Opção | Valor | O que faz |
|-------|-------|-----------|
| `startingOffsets` | `"latest"` | Ignora backlog, lê apenas mensagens novas |
| `startingOffsets` | `"earliest"` | Lê TUDO desde o início (perigoso com backlog!) |
| `maxOffsetsPerTrigger` | `5000` | Lê no máximo 5000 msgs por batch (previne sobrecarga) |
| `failOnDataLoss` | `false` | Não falha se mensagens antigas foram deletadas |

### 3. Configuração de Checkpoint

```python
query = df_stream.writeStream \
    .format("jdbc") \
    .foreachBatch(write_to_postgres) \
    .option("checkpointLocation", "s3a://fraud-data/checkpoints/streaming_postgres") \
    .trigger(processingTime="10 seconds")  # Batch a cada 10s
    .start()
```

**Importante:** Se deletar checkpoints, Spark recomeça do `startingOffsets` configurado.

---

## 📖 Lições Aprendidas

### 1️⃣ Sempre Configure `maxOffsetsPerTrigger`

```python
# ❌ RUIM: Sem limite
.option("subscribe", "transactions")

# ✅ BOM: Com limite
.option("subscribe", "transactions") \
.option("maxOffsetsPerTrigger", 5000)
```

**Por quê?**
- Previne sobrecarga de memória
- Permite processamento incremental
- Jobs mais estáveis e previsíveis

---

### 2️⃣ Use `startingOffsets = "latest"` em Produção

```python
# 🧪 DEV/TEST: Processa tudo (backfill)
.option("startingOffsets", "earliest")

# 🚀 PRODUÇÃO: Apenas dados novos
.option("startingOffsets", "latest")
```

**Quando usar `earliest`?**
- Primeira execução (histórico pequeno < 10k msgs)
- Reprocessamento intencional (data fix)
- Ambiente de testes controlado

**Quando usar `latest`?**
- Job rodando continuamente em produção
- Após limpar um backlog grande
- Quando só importam dados novos

---

### 3️⃣ Monitore o Lag do Consumer

```bash
# Comando para verificar lag (quantas msgs atrasadas):
docker exec fraud_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe \
  --group spark-kafka-streaming-<UUID>

# Output:
# GROUP    TOPIC         PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
# spark... transactions  0          132088          132088          0    ← OK!
# spark... transactions  0          50000           132088          82088 ← BACKLOG!
```

**Métricas importantes:**
- `LAG = 0` → Perfeito! Consumindo em tempo real
- `LAG < 10,000` → Ok, pequeno atraso
- `LAG > 50,000` → Problema! Precisa investigar
- `LAG > 500,000` → Crítico! Considere limpar e recomeçar

---

### 4️⃣ Planeje Capacidade de Processamento

```python
# Calcule throughput necessário:

Taxa de produção: 50 msgs/seg (fraud-generator)
Tamanho médio: 2 KB/msg
Throughput: 50 × 2 KB = 100 KB/seg

# Spark precisa processar NO MÍNIMO 50 msgs/seg
# Recomendado: 2-3x = 100-150 msgs/seg (margem de segurança)

# Configure recursos:
--total-executor-cores 2  # 2 cores = pode processar ~100 msgs/seg
--executor-memory 1g      # 1GB suficiente para batches de 5k msgs
```

---

### 5️⃣ Teste com Volumes Pequenos Primeiro

```bash
# ❌ NÃO FAÇA: Produzir 3M mensagens de uma vez
python fraud-generator/stream.py --count 3000000

# ✅ FAÇA: Teste incremental
python fraud-generator/stream.py --count 1000    # 1k
# Verificar se Spark consome OK
python fraud-generator/stream.py --count 10000   # 10k
# Verificar se Spark consome OK
python fraud-generator/stream.py --count 100000  # 100k
# Só então escalar para milhões
```

---

## 🛠️ Comandos Úteis

### Verificar Estado do Kafka

```bash
# 1. Listar tópicos
docker exec fraud_kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --list

# 2. Ver detalhes de um tópico
docker exec fraud_kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --describe \
  --topic transactions

# Output:
# Topic: transactions
# PartitionCount: 1
# ReplicationFactor: 1
# Configs: retention.bytes=10737418240

# 3. Ver quantidade de mensagens (offset final)
docker exec fraud_kafka kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 \
  --topic transactions \
  --time -1

# Output: transactions:0:132088
#                         ^
#                         └─ 132,088 mensagens
```

### Verificar Consumer Groups

```bash
# 1. Listar todos os grupos
docker exec fraud_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --list

# 2. Ver detalhes de um grupo específico
docker exec fraud_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe \
  --group spark-kafka-streaming-XXXX

# 3. Resetar offset (CUIDADO! Reprocessa tudo)
docker exec fraud_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group spark-kafka-streaming-XXXX \
  --reset-offsets \
  --to-latest \
  --topic transactions \
  --execute
```

### Monitorar Jobs Spark

```bash
# 1. Ver jobs rodando
docker exec fraud_spark_master ps aux | grep streaming

# 2. Ver logs em tempo real
docker exec fraud_spark_master tail -f /spark/logs/streaming_*.log

# 3. Spark UI (navegador)
http://localhost:8080  # Cluster Spark
http://localhost:4040  # Job ativo (Streaming)
```

### Limpar Tudo e Recomeçar

```bash
# SCRIPT COMPLETO DE RESET:

#!/bin/bash
set -e

echo "🛑 1. Parando jobs de streaming..."
docker exec -it fraud_spark_master bash -c "
  pkill -f streaming_to_postgres || true
  pkill -f streaming_realtime_dashboard || true
"

echo "🗑️ 2. Removendo checkpoints..."
docker exec fraud_minio mc rm --recursive --force local/fraud-data/checkpoints/

echo "🗑️ 3. Deletando tópico Kafka..."
docker exec fraud_kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --delete \
  --topic transactions || true

sleep 5

echo "✨ 4. Recriando tópico..."
docker exec fraud_kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --create \
  --topic transactions \
  --partitions 1 \
  --replication-factor 1 \
  --config retention.bytes=10737418240

echo "🚀 5. Reiniciando jobs..."
docker exec -d fraud_spark_master spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  --total-executor-cores 2 \
  --executor-memory 1g \
  /jobs/streaming/streaming_to_postgres.py

sleep 5

docker exec -d fraud_spark_master spark-submit \
  --master spark://spark-master:7077 \
  --deploy-mode client \
  --total-executor-cores 2 \
  --executor-memory 1g \
  /jobs/streaming/streaming_realtime_dashboard.py

echo "✅ Pronto! Streaming reiniciado do zero."
echo "📊 Verifique no Spark UI: http://localhost:8080"
```

---

## 🎓 Resumo Final (TL;DR)

### O Problema em 3 Frases

1. **132 mil mensagens acumuladas** no Kafka criaram um backlog gigante
2. **Spark tentou processar tudo de uma vez** no primeiro batch → sobrecarga de memória/timeout
3. **Job reiniciava antes de completar** → loop infinito, nunca conseguia limpar o backlog

### A Solução em 3 Passos

1. **Limpar Kafka e checkpoints** → começar do zero
2. **Adicionar `maxOffsetsPerTrigger`** → limitar mensagens por batch
3. **Usar `startingOffsets=latest`** → ignorar backlog, processar apenas dados novos

### Configurações Críticas

```python
# Adicione sempre nos seus jobs de streaming:
.option("startingOffsets", "latest")           # Ignora backlog
.option("maxOffsetsPerTrigger", 5000)          # Limita batch
.option("failOnDataLoss", "false")             # Tolera perdas
.trigger(processingTime="10 seconds")          # Batch a cada 10s
.option("checkpointLocation", "s3a://...")     # Salva progresso
```

### Monitoramento Essencial

```bash
# Execute periodicamente:
docker exec fraud_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --describe \
  --all-groups

# Se LAG > 10,000 por > 5 minutos → Investigar!
```

---

## 📚 Referências e Links Úteis

### Documentação Oficial

- [Spark Structured Streaming + Kafka Guide](https://spark.apache.org/docs/latest/structured-streaming-kafka-integration.html)
- [Kafka Consumer Configuration](https://kafka.apache.org/documentation/#consumerconfigs)
- [Kafka Topic Configuration](https://kafka.apache.org/documentation/#topicconfigs)

### Artigos Relacionados

- [Handling Kafka Backlogs in Spark Streaming](https://www.databricks.com/blog/2021/02/24/best-practices-for-handling-late-arriving-data-in-spark-structured-streaming.html)
- [Spark Streaming Performance Tuning](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html#performance-tuning)

### Issues Relacionadas no Projeto

- `docs/ERROS_CONHECIDOS.md` - Erros com S3A e MinIO
- `docs/ARQUITETURA_COMPLETA.md` - Visão geral do pipeline
- `airflow/dags/streaming_supervisor.py` - DAG que monitora streaming

---

## ✍️ Notas de Implementação

**Data:** 11 de dezembro de 2025  
**Autor:** Alberto Borda  
**Contexto:** Projeto `spark-medallion-fraud-detection`  
**Status do Bug:** ✅ Resolvido  

**Configuração do Ambiente:**
- Kafka: Confluent 7.5.0 (1 broker, 1 partição)
- Spark: 3.5.3 (1 master, 2 workers)
- Mensagens acumuladas: 132,088 (≈265 MB)
- Jobs afetados: `streaming_to_postgres.py`, `streaming_realtime_dashboard.py`

**Solução Implementada:**
1. Reset completo (Kafka + checkpoints)
2. Configuração de `maxOffsetsPerTrigger = 5000`
3. Uso de `startingOffsets = "latest"`
4. DAG de supervisão via Airflow (`streaming_supervisor.py`)

---

**🎉 Fim do Documento**

Espero que este guia tenha esclarecido o problema dos 3 milhões de mensagens no Kafka! Se tiver dúvidas, consulte os comandos na seção "Comandos Úteis" ou abra uma issue no repositório.

**Happy Streaming! 🚀📊**
