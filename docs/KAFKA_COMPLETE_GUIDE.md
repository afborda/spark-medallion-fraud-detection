# 🚨 Guia Completo: Kafka e Streaming no Pipeline

> **Última atualização:** 2025-12-23  
> **Versão:** 2.0 (Unificado)

---

## 📋 Índice

1. [O que é Kafka?](#o-que-é-kafka)
2. [O Problema das 3M Mensagens](#o-problema-das-3m-mensagens)
3. [Solução Implementada](#solução-implementada)
4. [Configurações Críticas](#configurações-críticas)
5. [Troubleshooting](#troubleshooting)
6. [Comandos Úteis](#comandos-úteis)

---

## 📚 O que é Kafka?

Apache Kafka é uma **plataforma de streaming** que funciona como:
- **Buffer/Fila:** Armazena mensagens temporariamente
- **Pub/Sub:** Publicadores enviam, consumidores recebem
- **Log distribuído:** Persiste dados em disco

### Componentes Principais

```
┌──────────────┐         ┌──────────────┐         ┌──────────────┐
│  Producer    │────────►│    Topic     │────────►│  Consumer    │
│  (Gerador)   │         │ (transactions)│         │  (Spark)     │
└──────────────┘         └──────────────┘         └──────────────┘
                               │
                         ┌─────▼────────┐
                         │ Partições    │
                         │ (distribuição)│
                         └──────────────┘
```

---

## 🚨 O Problema das 3M Mensagens

### O que Aconteceu?

No dia 11 de Dezembro de 2025, o sistema acumulou **3 milhões de mensagens** no tópico Kafka `transactions` sem serem consumidas.

```
Estado do Kafka (11/Dez/2025):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Topic: transactions
Mensagens: 3,000,000 acumuladas
Tamanho: ~6 GB
Retention: 10GB (quase cheio!)
Status: ⚠️ Kafka começando a dropar mensagens antigas
```

### Por que foi Problema?

#### 1. **Memória do Spark Esgotada**
```
Spark recebe: 3M × 2KB = 6GB de memória necessária
Spark disponível: 5GB (cluster de 2 workers × 2.5GB cada)
Resultado: ❌ OutOfMemoryError
```

#### 2. **Latência Insuperável**
```
Consumo rate: 10 transações/segundo (pior caso)
Tempo para processar backlog: 3,000,000 ÷ 10 = 300,000 segundos = 83 HORAS
Timeout padrão: 120 segundos ❌ (Spark cancela o job)
```

#### 3. **Offset Corrupto**
Spark não sabia de qual mensagem continuar lendo:
```
last_consumed_offset = 132,088  (antiga)
current_kafka_offset = 3,000,000 (atual)
Diferença: 2,867,912 mensagens para recuperar
```

#### 4. **Retenção do Kafka Atingindo Limite**
```
Retention configurado: 10GB
Mensagens atuais: ~6GB
Espaço livre: 4GB (somente!)
Kafka começou a descartar mensagens antigas
```

#### 5. **Deadlock com Micro-batches**
```
Spark Streaming (micro-batch a cada 5s):
Batch 1: 3M mensagens → Tenta carregar na memória → BOOM!
Timeout → Job cancela
Próximo batch: Tenta novamente, mas offset desincronizado
```

---

## ✅ Solução Implementada

### 1. **Limpar o Backlog do Kafka**
```bash
# Resetar consumer group para último offset
docker exec fraud_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group spark-streaming \
  --reset-offsets \
  --to-latest \
  --execute

# Resultado: Ignora 3M mensagens antigas, começa do zero
```

### 2. **Reduzir Retention do Kafka**
```properties
# docker-compose.yml
KAFKA_LOG_RETENTION_HOURS: 24      # Era 168 (7 dias)
KAFKA_LOG_RETENTION_BYTES: 1073741824  # 1GB (era 10GB)
```

**Impacto:**
- Kafka não accumula indefinidamente
- Auto-cleanup a cada 24h
- Espaço limitado = força consumo rápido

### 3. **Otimizar Spark Streaming**
```python
# spark-streaming.py
spark = SparkSession.builder \
    .config("spark.streaming.kafka.maxRatePerPartition", 10000) \
    .config("spark.streaming.backpressure.enabled", "true") \
    .config("spark.streaming.backpressure.initialRate", 5000) \
    .getOrCreate()

# Explicação:
# maxRatePerPartition: Max mensagens por partição por batch
# backpressure: Ajusta rate dinamicamente se Spark está atrás
```

### 4. **Aumentar Parallelismo**
```python
# Antes: 2 workers × 1 core = 2 cores
# Depois: 2 workers × 2 cores = 4 cores

# Antes: 5 segundo batch interval
# Depois: 2 segundo batch interval

# Resultado: 4x mais parallelismo + 2.5x mais batches/min
```

### 5. **Monitoramento Contínuo**
```bash
# Verificar lag do consumer group
docker exec fraud_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group spark-streaming \
  --describe

# Saída esperada:
# TOPIC    PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
# tx       0          123456          123456          0  ✅ Tudo consumido
```

---

## 🔧 Configurações Críticas

### Kafka (docker-compose.yml)
```yaml
KAFKA_LOG_RETENTION_HOURS: 24              # Limpar after 24h
KAFKA_LOG_RETENTION_BYTES: 1073741824      # 1GB máximo
KAFKA_LOG_SEGMENT_BYTES: 104857600         # 100MB por segmento
KAFKA_NUM_PARTITIONS: 3                    # 3 partições para paralelismo
KAFKA_DEFAULT_REPLICATION_FACTOR: 1        # 1 réplica (dev)
```

### Spark Streaming (jobs/streaming_realtime_dashboard.py)
```python
# Taxa de leitura
maxRatePerPartition = 50000           # Max msgs/s por partição
minPartitions = 4                     # Pelo menos 4 partições

# Backpressure (controla velocidade)
spark.streaming.backpressure.enabled = "true"
spark.streaming.backpressure.initialRate = 25000

# Intervalo de batch
batchInterval = 2                     # 2 segundos

# Timeout
spark.streaming.kafka.maxRetries = 3
spark.streaming.kafka.metadata.max.age.ms = 30000  # 30s
```

---

## 🐛 Troubleshooting

### Problema: "Consumer group is not active"
**Causa:** Spark parou de consumir, offset stuck
```bash
# Solução:
docker exec fraud_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group spark-streaming \
  --delete

# Recria o grupo na próxima execução
```

### Problema: "Timeout waiting for offset commit"
**Causa:** Spark processando muito lentamente
```python
# Solução 1: Aumentar workers
docker-compose up -d spark-worker-3 spark-worker-4

# Solução 2: Reduzir batch interval
batchInterval = 1  # De 2s para 1s

# Solução 3: Aumentar timeout
spark.streaming.kafka.maxRetries = 5
```

### Problema: "Partition assignment has failed"
**Causa:** Kafka não consegue rebalancear partições
```bash
# Solução: Reiniciar Kafka
docker-compose restart kafka

# Aguarde ~30s para rebalancear
docker exec fraud_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group spark-streaming \
  --describe
```

### Problema: "Message size exceeds broker's max.message.bytes"
**Causa:** Transação muito grande
```python
# Solução: Aumentar limite no Kafka
# docker-compose.yml
KAFKA_MAX_MESSAGE_BYTES: 16777216  # 16MB

# Depois: docker-compose restart kafka
```

---

## 📜 Comandos Úteis

### Monitorar Kafka em Tempo Real
```bash
# Ver tópicos
docker exec fraud_kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --list

# Ver estatísticas do tópico
docker exec fraud_kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --topic transactions \
  --describe

# Contar mensagens no tópico
docker exec fraud_kafka kafka-run-class kafka.tools.JmxTool \
  --object-name kafka.server:type=ReplicaManager,name=UnderReplicatedPartitions
```

### Consumir Mensagens Manualmente
```bash
# Ler últimas 10 mensagens
docker exec fraud_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic transactions \
  --from-beginning \
  --max-messages 10

# Ler a partir de um offset específico
docker exec fraud_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic transactions \
  --partition 0 \
  --offset 1000
```

### Resetar Offsets
```bash
# Para latest (ignora tudo que existe)
docker exec fraud_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group spark-streaming \
  --reset-offsets \
  --to-latest \
  --execute

# Para earliest (reprocessa tudo)
docker exec fraud_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group spark-streaming \
  --reset-offsets \
  --to-earliest \
  --execute

# Para offset específico
docker exec fraud_kafka kafka-consumer-groups \
  --bootstrap-server localhost:9092 \
  --group spark-streaming \
  --reset-offsets \
  --to-offset 0 \
  --execute
```

### Limpeza de Mensagens
```bash
# Deletar tópico (cuidado!)
docker exec fraud_kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --topic transactions \
  --delete

# Recri ar
docker exec fraud_kafka kafka-topics \
  --bootstrap-server localhost:9092 \
  --create \
  --topic transactions \
  --partitions 3 \
  --replication-factor 1
```

---

## 📊 Métricas de Saúde

### Bom Estado
```
LAG ≤ 100 mensagens     ✅ (Spark está consumindo rápido)
Msg/sec ≥ 100           ✅ (Taxa de produção healthy)
Retention ≤ 70% do max  ✅ (Espaço disponível)
Consumer lag trend: ↓   ✅ (Diminuindo backlog)
```

### Estado de Alerta
```
LAG > 1000 mensagens    ⚠️ (Começar a escalar)
Msg/sec = 0             🔴 (Producer parou!)
Retention ≥ 90% do max  🔴 (Quase cheio!)
Consumer lag trend: ↑   🔴 (Acumulando!)
```

---

## 🎓 Lições Aprendidas

1. **Kafka não é ilimitado** - Sempre configurar retention
2. **Spark tem limite de memória** - Backpressure é essencial
3. **Monitorar lag** - Diferença entre produced e consumed
4. **Múltiplas partições** - Aumenta paralelismo
5. **Testes de carga** - Descobrir problemas antes de produção

---

## 📚 Referências
- Kafka Documentation: https://kafka.apache.org/documentation/
- Spark Streaming Guide: https://spark.apache.org/docs/latest/streaming-programming-guide.html
- Our Project: `docs/ARQUITETURA_COMPLETA.md`, `docs/ANALISE_PROJETO_STATUS.md`
