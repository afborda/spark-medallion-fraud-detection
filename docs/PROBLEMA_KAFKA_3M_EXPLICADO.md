# 🚨 Por que 3 Milhões de Mensagens no Kafka Bloquearam o Streaming?

## 📚 Guia Completo para Iniciantes

> **Situação:** Geramos 3 milhões de transações e enviamos para o Kafka. Quando tentamos processar com Spark Streaming, o pipeline travou ou ficou extremamente lento, não conseguindo finalizar o processamento.

Este documento explica **em detalhes** o que aconteceu, por que aconteceu, e como resolver.

---

## 🎯 Índice

1. [O Que É Kafka? (Conceitos Básicos)](#1-o-que-é-kafka-conceitos-básicos)
2. [O Que É Spark Streaming?](#2-o-que-é-spark-streaming)
3. [O Problema dos 3 Milhões de Mensagens](#3-o-problema-dos-3-milhões-de-mensagens)
4. [Por Que o Streaming Travou?](#4-por-que-o-streaming-travou)
5. [Analogia do Mundo Real](#5-analogia-do-mundo-real)
6. [Conceitos Técnicos Explicados](#6-conceitos-técnicos-explicados)
7. [Soluções e Boas Práticas](#7-soluções-e-boas-práticas)
8. [Como Evitar Este Problema](#8-como-evitar-este-problema)
9. [Comandos Úteis para Diagnóstico](#9-comandos-úteis-para-diagnóstico)
10. [Resumo Final](#10-resumo-final)

---

## 1. O Que É Kafka? (Conceitos Básicos)

### 🔹 Apache Kafka em Linguagem Simples

Imagine o Kafka como uma **fila de mensagens gigante** (como uma fila de banco, mas para dados).

```
┌─────────────┐      ┌─────────────────┐      ┌─────────────┐
│  Produtor   │ ───▶ │  KAFKA (Fila)   │ ───▶ │ Consumidor  │
│ (Gerador)   │      │   3M mensagens  │      │   (Spark)   │
└─────────────┘      └─────────────────┘      └─────────────┘
```

**Componentes principais:**

#### A) **Produtor** (Producer)
- Quem **envia** mensagens para o Kafka
- No nosso caso: `fraud-generator` em modo streaming
- Exemplo: Gera 100 transações/segundo

#### B) **Tópico** (Topic)
- O "endereço" onde as mensagens ficam armazenadas
- Como uma "caixa de correio" específica
- No nosso caso: tópico `transactions`

#### C) **Partições** (Partitions)
- Divisões do tópico para paralelização
- Cada partição é como uma "sub-fila" independente
- Mais partições = mais paralelismo

```
Tópico: transactions
├── Partition 0: [msg1, msg4, msg7, ...]
├── Partition 1: [msg2, msg5, msg8, ...]
└── Partition 2: [msg3, msg6, msg9, ...]
```

#### D) **Consumidor** (Consumer)
- Quem **lê** mensagens do Kafka
- No nosso caso: Spark Streaming
- Processa as mensagens e faz algo útil com elas

#### E) **Offset**
- Um **número sequencial** que marca a posição de cada mensagem
- Como um "marcador de página" em um livro
- Exemplo: Partition 0, Offset 0 = primeira mensagem
- Partition 0, Offset 1000 = milésima primeira mensagem

```
Partition 0:
┌────────┬────────┬────────┬────────┬─────────────┐
│ Msg 0  │ Msg 1  │ Msg 2  │ Msg 3  │  ... 999999 │
└────────┴────────┴────────┴────────┴─────────────┘
   ↑
 Offset 0
```

#### F) **Consumer Group**
- Grupo de consumidores trabalhando juntos
- Cada partition é lida por apenas 1 consumidor do grupo
- Permite paralelização

---

## 2. O Que É Spark Streaming?

### 🔹 Processamento de Dados em Tempo Real

Spark Streaming é uma biblioteca que permite processar dados **continuamente**, em vez de tudo de uma vez.

**Dois modos principais:**

### A) **Batch Processing** (Processamento em Lote)
```python
# Processa TUDO de uma vez
df = spark.read.parquet("s3a://fraud-data/raw/")
df.write.parquet("s3a://fraud-data/bronze/")
```

✅ **Vantagens:**
- Simples
- Mais rápido para grandes volumes
- Controle total sobre os dados

❌ **Desvantagens:**
- Não é "tempo real"
- Precisa esperar todos os dados estarem prontos

### B) **Stream Processing** (Processamento Contínuo)
```python
# Processa dados conforme chegam
df = spark.readStream.format("kafka").load()
df.writeStream.start()
```

✅ **Vantagens:**
- Processamento em "tempo real"
- Latência baixa (segundos)
- Ideal para dashboards ao vivo

❌ **Desvantagens:**
- Mais complexo
- Requer gerenciamento de estado (checkpoints)
- Pode ser mais lento para grandes volumes acumulados

---

## 3. O Problema dos 3 Milhões de Mensagens

### 🚨 O Que Aconteceu?

```
┌─────────────────────────────────────────────────┐
│  FASE 1: Geração de Dados                       │
│                                                  │
│  fraud-generator → Kafka                         │
│  Tempo: ~30 minutos                              │
│  Resultado: 3.000.000 mensagens acumuladas       │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│  FASE 2: Tentativa de Processar com Streaming   │
│                                                  │
│  spark.readStream.format("kafka")                │
│  .option("startingOffsets", "earliest") ← 🔴     │
│                                                  │
│  Status: TRAVADO / LENTÍSSIMO                    │
│  Problema: Tentando processar 3M msgs de uma vez │
└─────────────────────────────────────────────────┘
```

### 📊 Números do Problema

| Métrica | Valor | Impacto |
|---------|-------|---------|
| Mensagens acumuladas | 3.000.000 | ⚠️ ALTO |
| Taxa de processamento | ~1.000/s | 🐌 LENTO |
| Tempo para processar tudo | 50 minutos | ❌ INACEITÁVEL |
| Memória necessária | ~15 GB | 💥 ESTOURO |
| CPU utilizada | 100% | 🔥 SOBRECARGA |

### ❓ Por Que Isso É Um Problema?

**Streaming foi feito para processar dados NOVOS, não um backlog gigante!**

---

## 4. Por Que o Streaming Travou?

### 🔍 Análise Técnica Detalhada

#### A) **startingOffsets = "earliest"**

```python
df_kafka = spark.readStream \
    .format("kafka") \
    .option("startingOffsets", "earliest")  # ← PROBLEMA!
    .load()
```

**O que isso significa?**
- `"earliest"` = "Comece do PRIMEIRO offset de cada partição"
- Se você tem 3M mensagens acumuladas, ele vai tentar processar TODAS

**Analogia:**
- É como chegar em uma fila de 3 milhões de pessoas e gritar "Vou atender todo mundo agora!"
- Ao invés de: "Vou atender quem chegar a partir de agora"

#### B) **maxOffsetsPerTrigger = 10.000**

```python
.option("maxOffsetsPerTrigger", "10000")  # Lê 10k msgs por vez
```

**O que acontece:**
```
Total de mensagens: 3.000.000
Mensagens por batch: 10.000
Número de batches necessários: 3.000.000 / 10.000 = 300 batches

Se cada batch leva 10 segundos:
300 batches × 10s = 3.000 segundos = 50 MINUTOS! 😱
```

#### C) **Overhead do Streaming**

Cada micro-batch tem overhead:
1. **Leitura do Kafka** (~2s)
2. **Deserialização JSON** (~1s)
3. **Transformações Spark** (~3s)
4. **Escrita no destino** (~3s)
5. **Checkpoint (salvar estado)** (~1s)

**Total por batch: ~10 segundos**

#### D) **Memória e Checkpoints**

Spark Streaming mantém:
- **Estado interno** (offsets, metadados)
- **Checkpoints** (para recovery)
- **Buffers de dados** (dados em processamento)

Com 3M mensagens:
- Checkpoint file cresce muito
- Spark tenta carregar tudo na inicialização
- Pode dar **OOM** (Out of Memory)

---

## 5. Analogia do Mundo Real

### 🍕 A Pizzaria e o Delivery

Imagine que você tem uma pizzaria com sistema de delivery em tempo real:

#### ✅ **Cenário Normal (Streaming Funcionando Bem)**

```
📞 Pedido 1 chega   → 🍕 Faz pizza → 🚗 Entrega (10 min)
📞 Pedido 2 chega   → 🍕 Faz pizza → 🚗 Entrega (10 min)
📞 Pedido 3 chega   → 🍕 Faz pizza → 🚗 Entrega (10 min)

⏱️ Tempo total: 10 minutos por pedido
😊 Clientes felizes: Pizza chegou quente!
```

#### ❌ **Cenário Problema (3M Mensagens Acumuladas)**

```
A pizzaria ficou fechada 1 semana.
3.000.000 pedidos acumularam no telefone.

Quando reabre:
📞 Pedido 1 (7 dias atrás) → 🍕 Faz pizza → 🚗 Entrega
📞 Pedido 2 (7 dias atrás) → 🍕 Faz pizza → 🚗 Entrega
📞 Pedido 3 (7 dias atrás) → 🍕 Faz pizza → 🚗 Entrega
...
📞 Pedido 3.000.000 → 🍕 Faz pizza → 🚗 Entrega

⏱️ Tempo total: 50 MINUTOS para o primeiro pedido
😡 Clientes: "Cancelei há 1 semana!"
💀 Sistema: Travado processando pedidos antigos
```

**O problema:**
- Sistema de "tempo real" tentando processar backlog histórico
- Clientes novos não conseguem fazer pedidos (streaming travado)
- Desperdício de recursos processando dados obsoletos

**A solução:**
- "Desculpe pelos pedidos antigos, vamos recomeçar do zero"
- Atender apenas pedidos NOVOS a partir de agora
- Processar backlog em batch separado (se necessário)

---

## 6. Conceitos Técnicos Explicados

### 🔑 Termos Importantes

#### A) **Consumer Lag**

**Definição:** Diferença entre mensagens disponíveis e mensagens consumidas

```
Producer escreve até offset:   1.000.000
Consumer leu até offset:             100
                              ─────────
Consumer Lag:                    999.900  ← PROBLEMA!
```

**Analogia:** Você está no episódio 100 de uma série, mas já lançaram 1 milhão de episódios.

#### B) **Backpressure**

**Definição:** Mecanismo que limita a velocidade de leitura quando o consumidor não consegue acompanhar.

```
Producer: 10.000 msgs/s
Consumer: 1.000 msgs/s
          ─────────────
Lag cresce: +9.000 msgs/s  ← Backpressure ativa!
```

**O que Spark faz:**
- Reduz `maxOffsetsPerTrigger` automaticamente
- Aumenta intervalo entre batches
- Tenta não sobrecarregar o sistema

#### C) **Checkpoint**

**Definição:** Snapshot do estado do streaming para recovery.

```
Checkpoint contém:
├── Offsets processados (Partition 0: offset 45000)
├── Metadados do batch
├── Estado de agregações (se houver)
└── Configuração do streaming
```

**Por que é importante:**
- Se Spark crashar, ele continua de onde parou
- Evita processar mesma mensagem 2 vezes
- Garante "exactly-once" semantics

**Problema com 3M mensagens:**
- Checkpoint fica GIGANTE
- Lentidão para ler/escrever checkpoint
- Pode corromper com volume muito alto

#### D) **Watermark**

**Definição:** Marca de tempo que define até quando aceitar dados atrasados.

```python
df.withWatermark("event_time", "10 minutes")
```

**Significa:**
- Aceito dados com até 10 minutos de atraso
- Depois disso, descarto

**Com 3M mensagens antigas:**
- Todas podem estar "fora do watermark"
- Spark pode descartar tudo (dependendo config)

---

## 7. Soluções e Boas Práticas

### ✅ Solução 1: Usar `startingOffsets = "latest"`

**Para streaming em tempo real:**

```python
df_kafka = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "transactions") \
    .option("startingOffsets", "latest")  # ← CORRETO para streaming
    .option("maxOffsetsPerTrigger", "10000") \
    .option("failOnDataLoss", "false") \
    .load()
```

**O que muda:**
- `"latest"` = Ignora mensagens antigas, processa só novas
- Streaming começa "limpo"
- Baixa latência

**Quando usar:**
- ✅ Dashboard em tempo real
- ✅ Alertas/notificações
- ✅ Agregações de última hora/dia
- ✅ Quando backlog não é importante

### ✅ Solução 2: Processar Backlog em Batch

**Para processar os 3M históricos:**

```python
# BATCH MODE (não streaming)
df = spark.read \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "kafka:9092") \
    .option("subscribe", "transactions") \
    .option("startingOffsets", "earliest") \
    .option("endingOffsets", "latest") \
    .load()

# Processa tudo de uma vez
df.selectExpr("CAST(value AS STRING) as json") \
  .write.mode("overwrite") \
  .parquet("s3a://fraud-data/backlog/")
```

**Vantagens:**
- ✅ MUITO mais rápido (sem overhead de streaming)
- ✅ Processa 3M em ~5 minutos (vs 50 no streaming)
- ✅ Não trava o streaming

**Workflow recomendado:**

```
1. Tem 3M mensagens acumuladas? 
   ↓
2. Roda JOB BATCH para processar backlog
   ↓
3. Limpa Kafka ou reseta offsets
   ↓
4. Inicia STREAMING com "latest"
   ↓
5. Streaming processa apenas msgs novas (tempo real)
```

### ✅ Solução 3: Resetar Offsets do Kafka

**Apagar mensagens antigas do Kafka:**

```bash
# 1. Parar streaming
docker stop fraud_spark_worker_1

# 2. Deletar tópico (apaga todas as mensagens)
docker exec fraud_kafka kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --delete --topic transactions

# 3. Recriar tópico limpo
docker exec fraud_kafka kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --create --topic transactions \
    --partitions 3 \
    --replication-factor 1

# 4. Limpar checkpoints do Spark
docker exec fraud_spark_master rm -rf /tmp/streaming_checkpoints/*

# 5. Reiniciar streaming
# Agora ele começa do zero, sem backlog
```

### ✅ Solução 4: Aumentar Recursos

**Se você REALMENTE precisa processar 3M via streaming:**

```yaml
# docker-compose.yml
spark-worker:
  environment:
    - SPARK_WORKER_CORES=8      # 4 → 8 cores
    - SPARK_WORKER_MEMORY=16G   # 8G → 16G
  deploy:
    resources:
      limits:
        cpus: '8'
        memory: 16G
```

```python
# Aumentar paralelismo
df.writeStream \
    .option("maxOffsetsPerTrigger", "50000")  # 10k → 50k
    .trigger(processingTime="5 seconds")      # 10s → 5s
```

**Resultado esperado:**
- Processa 50k msgs a cada 5s
- 3M / 50k = 60 batches
- 60 × 5s = 5 minutos (vs 50 minutos)

### ✅ Solução 5: Usar Structured Streaming com Melhor Configuração

```python
spark = SparkSession.builder \
    .config("spark.sql.streaming.checkpointLocation", "/checkpoints") \
    .config("spark.sql.streaming.schemaInference", "true") \
    .config("spark.sql.adaptive.enabled", "true") \
    .config("spark.streaming.kafka.maxRatePerPartition", "10000") \
    .getOrCreate()
```

---

## 8. Como Evitar Este Problema

### 🛡️ Boas Práticas

#### ✅ **1. Sempre inicie Streaming ANTES de gerar dados**

```bash
# ❌ ERRADO
docker-compose up -d fraud-generator  # Gera 3M msgs
docker-compose up -d spark-streaming  # Tenta processar tudo

# ✅ CORRETO
docker-compose up -d kafka           # Sobe Kafka vazio
docker-compose up -d spark-streaming # Streaming aguardando
docker-compose up -d fraud-generator # Gera dados, streaming processa
```

#### ✅ **2. Use `startingOffsets = "latest"` por padrão**

```python
# Para produção/streaming real
.option("startingOffsets", "latest")

# Apenas use "earliest" se:
# - É um teste pontual
# - Você tem CERTEZA que não tem backlog
# - Está debugando
```

#### ✅ **3. Monitore Consumer Lag**

```bash
# Ver lag atual
docker exec fraud_kafka kafka-consumer-groups.sh \
    --bootstrap-server localhost:9092 \
    --describe --group spark-streaming-group
```

**Output:**
```
TOPIC         PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
transactions  0          100             150             50
transactions  1          120             140             20
transactions  2          90              130             40

Total LAG: 110 mensagens ← Aceitável
```

**Alerta se:**
- Lag > 100.000: ⚠️ Streaming lento
- Lag > 1.000.000: 🚨 Problema sério

#### ✅ **4. Configure Retenção do Kafka**

```bash
# Kafka apaga mensagens antigas automaticamente
docker exec fraud_kafka kafka-configs.sh \
    --bootstrap-server localhost:9092 \
    --entity-type topics \
    --entity-name transactions \
    --alter \
    --add-config retention.ms=86400000  # 24 horas
```

**Benefícios:**
- Mensagens > 24h são apagadas automaticamente
- Previne acúmulo infinito
- Libera espaço em disco

#### ✅ **5. Use Batch para Cargas Iniciais**

```python
# Script: initial_load.py (roda 1x)
df = spark.read.format("kafka") \
    .option("startingOffsets", "earliest") \
    .option("endingOffsets", "latest") \
    .load()

df.write.mode("overwrite").parquet("s3a://fraud-data/initial/")

# Depois, streaming processa apenas novos
```

#### ✅ **6. Dimensione Recursos Adequadamente**

**Regra geral:**
```
Taxa de entrada: X mensagens/segundo
Taxa de saída: Y mensagens/segundo

Se Y < X → Lag cresce infinitamente! ❌
Se Y >= X × 1.2 → Sustentável ✅

Exemplo:
- Entrada: 1.000 msgs/s
- Saída necessária: 1.200 msgs/s (20% margem)
```

---

## 9. Comandos Úteis para Diagnóstico

### 🔍 Verificar Estado do Kafka

#### Ver quantas mensagens tem no tópico:
```bash
docker exec fraud_kafka kafka-run-class.sh \
    kafka.tools.GetOffsetShell \
    --broker-list localhost:9092 \
    --topic transactions \
    --time -1 \
    | awk -F: '{sum+=$3} END {print "Total: " sum " mensagens"}'
```

#### Ver consumer groups e lag:
```bash
docker exec fraud_kafka kafka-consumer-groups.sh \
    --bootstrap-server localhost:9092 \
    --describe --all-groups
```

#### Ver detalhes do tópico:
```bash
docker exec fraud_kafka kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --describe --topic transactions
```

### 🔍 Verificar Estado do Spark Streaming

#### Ver jobs ativos:
```bash
# Acessar UI do Spark
http://localhost:4040  # Porta padrão

# Ou via CLI
docker exec fraud_spark_master curl http://spark-master:8080/json/ | jq
```

#### Ver checkpoint atual:
```bash
docker exec fraud_spark_master ls -lh /tmp/streaming_checkpoints/
```

#### Ver logs de erro:
```bash
docker logs fraud_spark_worker_1 --tail 100 | grep -i "error\|exception"
```

### 🔍 Limpar/Resetar Sistema

#### Limpar checkpoints:
```bash
docker exec fraud_spark_master rm -rf /tmp/streaming_checkpoints/*
```

#### Limpar tópico Kafka:
```bash
docker exec fraud_kafka kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --delete --topic transactions

docker exec fraud_kafka kafka-topics.sh \
    --bootstrap-server localhost:9092 \
    --create --topic transactions \
    --partitions 3 --replication-factor 1
```

#### Resetar consumer group:
```bash
docker exec fraud_kafka kafka-consumer-groups.sh \
    --bootstrap-server localhost:9092 \
    --group spark-streaming-group \
    --reset-offsets --to-latest \
    --topic transactions --execute
```

---

## 10. Resumo Final

### 📋 TL;DR (Resumo Executivo)

| Problema | Causa | Solução |
|----------|-------|---------|
| 3M mensagens acumuladas | Gerou dados antes de iniciar streaming | Iniciar streaming ANTES de gerar dados |
| Streaming travado | `startingOffsets: earliest` + 3M msgs | Usar `startingOffsets: latest` |
| Lag crescente | Taxa saída < taxa entrada | Aumentar recursos / batch processing |
| Checkpoint corrompido | Volume muito alto | Limpar checkpoints, recomeçar |
| OOM (Out of Memory) | Tentando processar tudo de uma vez | Batch para backlog, streaming para novos |

### ✅ Checklist de Implementação

**Antes de iniciar streaming:**
- [ ] Kafka está rodando e saudável
- [ ] Tópico foi criado (ou está vazio)
- [ ] Spark tem recursos suficientes (CPU/RAM)
- [ ] Checkpoints foram limpos (se for reiniciar)

**Ao configurar streaming:**
- [ ] Usar `startingOffsets: latest` (a menos que tenha motivo específico)
- [ ] Configurar `maxOffsetsPerTrigger` adequado (10k-50k)
- [ ] Definir `failOnDataLoss: false` (evita falhas em dev)
- [ ] Configurar checkpoint em local persistente

**Durante operação:**
- [ ] Monitorar consumer lag regularmente
- [ ] Alertar se lag > threshold (ex: 100k)
- [ ] Verificar logs de erro no Spark
- [ ] Validar que dados estão sendo escritos no destino

**Se acumular backlog:**
- [ ] Parar streaming
- [ ] Processar backlog em BATCH
- [ ] Limpar checkpoints
- [ ] Resetar offsets (se necessário)
- [ ] Reiniciar streaming com `latest`

### 🎓 Lições Aprendidas

1. **Streaming ≠ Batch**: Cada um tem seu propósito
   - Streaming: Dados novos, baixa latência
   - Batch: Grandes volumes, processamento histórico

2. **"Tempo real" não significa "processar backlog"**: 
   - Streaming processa o fluxo contínuo
   - Backlog deve ser processado separadamente

3. **Monitore sempre o consumer lag**:
   - Lag crescendo = problema iminente
   - Lag estável = sistema saudável

4. **Recursos adequados são críticos**:
   - CPU/RAM insuficientes = lag infinito
   - Dimensione para 120% da carga esperada

5. **Kafka não é storage infinito**:
   - Configure retenção adequada
   - Não acumule milhões de mensagens

### 📚 Leitura Adicional

- [Kafka Documentation - Streams](https://kafka.apache.org/documentation/streams/)
- [Spark Structured Streaming Guide](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html)
- [Handling Large Kafka Backlogs](https://www.confluent.io/blog/handling-large-message-backlogs-apache-kafka/)
- [Spark Streaming Tuning](https://spark.apache.org/docs/latest/streaming-programming-guide.html#performance-tuning)

---

## 🎯 Próximos Passos Sugeridos

1. **Implementar monitoramento**:
   - Dashboard com lag do Kafka
   - Alertas no Discord/Slack
   - Grafana + Prometheus

2. **Automatizar recovery**:
   - Script que detecta lag alto
   - Pausa streaming, roda batch, reinicia

3. **Otimizar pipeline**:
   - Testar diferentes valores de `maxOffsetsPerTrigger`
   - Ajustar intervalo de trigger
   - Adicionar mais workers Spark

4. **Documentar processo**:
   - Runbook de troubleshooting
   - Alertas e resoluções
   - Casos de uso específicos

---

**Data:** Dezembro 2025  
**Versão:** 1.0  
**Autor:** Documentação Técnica - Projeto Fraud Detection  
**Objetivo:** Educar iniciantes sobre streaming e problemas com backlog no Kafka

---

## 🆘 Precisa de Ajuda?

Se você está enfrentando este problema agora:

1. **Diagnóstico rápido**:
   ```bash
   # Quantas mensagens tem?
   docker exec fraud_kafka kafka-run-class.sh kafka.tools.GetOffsetShell \
       --broker-list localhost:9092 --topic transactions --time -1
   
   # Streaming está travado?
   docker logs fraud_spark_worker_1 --tail 50
   ```

2. **Solução rápida**:
   ```bash
   # Limpar tudo e recomeçar
   ./scripts/reset_kafka_streaming.sh  # Se tiver
   
   # Ou manualmente:
   docker-compose down spark-streaming
   docker exec fraud_kafka kafka-topics.sh --delete --topic transactions
   docker exec fraud_kafka kafka-topics.sh --create --topic transactions --partitions 3
   docker-compose up -d spark-streaming
   ```

3. **Verificar saúde**:
   - Spark UI: http://localhost:4040
   - Kafka Manager: http://localhost:9000 (se tiver)
   - Logs: `docker logs -f fraud_spark_worker_1`

Boa sorte! 🚀
