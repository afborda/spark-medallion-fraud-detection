# 🎓 PROGRESSO DE APRENDIZADO - Fraud Detection Pipeline

> **IMPORTANTE PARA A IA:** Este arquivo contém o contexto completo do projeto de aprendizado.
> O aluno está aprendendo passo a passo (baby steps). NÃO faça código automaticamente.
> Siga a metodologia: explicar → aluno pergunta → aluno digita → executar juntos.

---

## 👤 PERFIL DO ALUNO

- Nível: Iniciante/Intermediário em Data Engineering
- Objetivo: Aprender construindo, não copiando
- Preferência: Explicações em português, passo a passo
- Frase-chave: "eu nunca fiz um projeto desses do 0, quero bb steps passo a passo, sentir que eu fiz, não que foi tudo automático"

---

## 📍 STATUS ATUAL

**Último checkpoint completado:** 11.9 - Escala 30M transações ✅
**Próximo checkpoint:** 12 - Streaming Real com Kafka
**Data da última sessão:** 2025-12-01

---

## 🎯 RESULTADO FINAL: 30M Transações

### Pipeline Executado com Sucesso!

| Métrica | Valor |
|---------|-------|
| **Transações Processadas** | 30,000,000 |
| **Dados Raw (JSON)** | 19.2 GB |
| **Clientes** | 50,000 |
| **Fraudes Injetadas** | 1,500,000 (5%) |
| **Tempo Total** | ~15 min |
| **Throughput** | ~110,000 tx/s |

### Distribuição de Risco

| Nível | Total | % | Valor Médio | Score Médio |
|-------|-------|---|-------------|-------------|
| ✅ NORMAL | 27,077,000 | 90.26% | R$ 334 | 0.6 |
| 🔴 CRÍTICO | 1,468,416 | 4.89% | R$ 1,493 | 71.0 |
| 🟠 MÉDIO | 696,770 | 2.32% | R$ 2,304 | 21.5 |
| 🟡 ALTO | 620,423 | 2.07% | R$ 556 | 40.5 |
| 🟢 BAIXO | 137,391 | 0.46% | R$ 1,423 | 15.0 |

### PostgreSQL

| Tabela | Registros |
|--------|-----------|
| **transactions** | 30,000,000 |
| **fraud_alerts** | 2,088,839 |

### Precisão da Detecção

| Métrica | Valor |
|---------|-------|
| Total de Alertas | 2,088,839 |
| Fraudes Reais Detectadas | 842,997 |
| **Precisão** | **40.36%** |

---

## 🚀 EVOLUÇÃO DO CLUSTER SPARK

### Antes (Single Node)
| Configuração | Valor |
|--------------|-------|
| Imagem | bitnami/spark:3.5.0 |
| Modo | Master + Worker único |
| Cores | 1 |
| RAM | Não configurado |
| Versão | 3.5.0 |

### Depois (Cluster Distribuído)
| Configuração | Valor |
|--------------|-------|
| Imagem | apache/spark:4.0.0-preview2 |
| Modo | 1 Master + 5 Workers |
| Cores | **10 (5×2)** |
| RAM | **15 GB (5×3GB)** |
| Versão | 4.0.0-preview2 |

### Configurações Adicionadas
```python
# Em todos os jobs Spark:
.config("spark.sql.files.maxPartitionBytes", "128m")
```

---

## 📊 TESTES DE ESCALABILIDADE

### Teste 1: 50k transações (Local - Antes do Cluster)
| Métrica | Valor |
|---------|-------|
| Transações | 50,000 |
| Clientes | 1,000 |
| Dados Raw | 11 MB |
| Dados Bronze | 2.8 MB |
| Dados Silver | 2.9 MB |
| Dados Gold | 3.2 MB |
| Fraudes | 2,545 (5.09%) |
| Valor Fraudado | R$ 7,720,557.36 |
| **Modo** | **Local (1 worker)** |
| **Tempo estimado** | **~15-30s** |

### Teste 2: 1M transações (Cluster 5 Workers)
| Métrica | Valor |
|---------|-------|
| Transações | **1,000,000** |
| Clientes | 10,000 |
| Dados Raw | **216 MB** |
| Dados Bronze | 54 MB |
| Dados Silver | 56 MB |
| Dados Gold | 60 MB |
| Fraudes | 49,603 (5.0%) |
| **Modo** | **Cluster (5 workers × 2 cores)** |
| **Tempo total** | **~2min 30s** |

### 📊 Estatísticas de Fraude Detalhadas (1M transações)

| Nível de Risco | Quantidade | % | Valor Total | Ticket Médio |
|----------------|------------|---|-------------|--------------|
| 🔴 Alto Risco | 8,259 | 0.83% | R$ 24.6M | R$ 2,982.87 |
| 🟠 Risco Médio | 200,235 | 20.02% | R$ 164.5M | R$ 821.38 |
| 🟢 Baixo Risco | 791,506 | 79.15% | R$ 201.7M | R$ 254.82 |
| **TOTAL** | **1,000,000** | 100% | **R$ 390.8M** | - |

### 🔄 Comparativo: Antes vs Depois do Cluster

| Métrica | Antes (Local) | Depois (5 Workers) | Melhoria |
|---------|---------------|---------------------|----------|
| Transações | 50,000 | 1,000,000 | **20× mais** |
| Dados Raw | 11 MB | 216 MB | **20× mais** |
| Workers | 1 | 5 | **5× mais** |
| Cores | 1 | 10 | **10× mais** |
| RAM | ~1 GB | 15 GB | **15× mais** |
| Tempo | ~30s | ~150s | **5× mais** |
| **Throughput** | **~1.7k/s** | **~6.7k/s** | **4× mais rápido** |

> **Conclusão:** Com 20× mais dados, o tempo aumentou apenas 5×. Isso demonstra **escalabilidade sub-linear** graças ao processamento distribuído.

### Tempo de Execução por Camada (1M transações)
| Camada | Tempo |
|--------|-------|
| 🔶 Bronze | 37s |
| ⚪ Silver | 46s |
| 🥇 Gold | 34s |
| 🚨 Fraud Detection | 33s |
| **TOTAL** | **~2min 30s** |

### Compressão Parquet
| Camada | Formato | Tamanho | Compressão |
|--------|---------|---------|------------|
| Raw | JSON | 216 MB | - |
| Bronze | Parquet | 54 MB | 75% |
| Silver | Parquet | 56 MB | 74% |
| Gold | Parquet | 60 MB | 72% |

### Escalabilidade
| Métrica | 50k → 1M | Resultado |
|---------|----------|-----------|
| Dados | 20× mais | ✅ |
| Tempo | 5× mais | ✅ Sub-linear! |

---

## ✅ CHECKPOINTS COMPLETADOS

### Checkpoint 1-5: Infraestrutura Docker ✅
- [x] docker-compose.yml criado com 6 serviços
- [x] PostgreSQL 16 (porta 5432)
- [x] MinIO (portas 9002/9003) - bucket "fraud-data" criado via UI
- [x] Zookeeper 7.5.0 + Kafka 7.5.0 (porta 9092) - topic "transactions" criado
- [x] Spark Master + Worker apache/spark:3.5.3 (UI porta 8081)
- [x] Todos containers rodando

### Checkpoint 6-7: Geração de Dados ✅
- [x] scripts/generate_data.py criado
- [x] Funções: generate_customers(), generate_transactions(), save_to_json()
- [x] Formato: JSON Lines (um registro por linha) - corrigido durante a sessão
- [x] Dados gerados: 100 clientes + 500 transações (~5% fraude = ~25 fraudes)

### Checkpoint 8: Bronze Layer ✅
- [x] spark/jobs/bronze_layer.py criado
- [x] PySpark 4.0.1 instalado no venv (compatível com Spark 4.0.1 do sistema)
- [x] Conversão JSON → Parquet funcionando
- [x] Metadados adicionados: _ingestion_time, _process_date
- [x] Output: data/bronze/customers/ e data/bronze/transactions/

### Checkpoint 9: Silver Layer ✅
- [x] spark/jobs/silver_layer.py criado
- [x] Limpeza de dados: dropDuplicates(), dropna()
- [x] Padronização: lower(), trim() para emails e nomes
- [x] Filtros: apenas transações com amount > 0
- [x] Metadados: _silver_timestamp, processed_date
- [x] Output: data/silver/customers/ e data/silver/transactions/

**Conceitos aprendidos:**
- Funções Python: definição e chamada, parâmetros vs variáveis globais
- `if __name__ == "__main__":` - código que só roda quando executas o arquivo diretamente
- Transformações Spark: withColumn(), filter(), dropDuplicates(), dropna()

### Checkpoint 10: Gold Layer ✅
- [x] spark/jobs/gold_layer.py criado
- [x] customer_summary: total_gasto, qtd_transacoes, ticket_medio, qtd_fraudes por cliente
- [x] fraud_summary: estatísticas gerais de fraude (19 fraudes, R$ 62.260,93, 3.8%)
- [x] Output: data/gold/customer_summary/ e data/gold/fraud_summary/

**Conceitos aprendidos:**
- Agregações: groupBy().agg(), sum(), count(), avg()
- .alias() para nomear colunas resultantes
- round() do Python vs spark_round() do Spark (tipos diferentes!)
- collect() - trazer dados do Spark para Python (usar com cuidado em Big Data!)
- .cast("int") para converter boolean para inteiro

### Checkpoint 11: Fraud Detection ✅
- [x] spark/jobs/fraud_detection.py criado
- [x] Regra 1: Valor alto (amount > R$ 1.000) → flag high_value
- [x] Regra 2: Horário suspeito (2h-5h da manhã) → flag suspicious_hour
- [x] Regra 3: Níveis de risco combinados (Alto/Médio/Baixo)
- [x] Output particionado por risk_level: data/gold/fraud_detection/
- [x] Resultados: 4 Alto Risco, 83 Médio Risco, 413 Baixo Risco

**Conceitos aprendidos:**
- when()/otherwise() - lógica condicional em colunas Spark
- col() - referenciar colunas pelo nome para operações
- withColumn() - criar ou substituir colunas (DataFrames são imutáveis)
- hour() e to_timestamp() - extrair hora de um timestamp
- partitionBy() - salvar dados particionados em pastas separadas

### Checkpoint 11.5: PostgreSQL Integration ✅
- [x] spark/jobs/load_to_postgres.py criado
- [x] JDBC driver baixado (postgresql-42.7.4.jar)
- [x] Conexão Spark → PostgreSQL funcionando
- [x] Tabelas criadas e carregadas:
  - fraud_detections: **5,000,000 registros** (fraud_detection Gold Layer)
  - customer_summary: **50,000 registros** (customer_summary Gold Layer)
- [x] Tempo de carga: ~2 min para 5M registros

**Conexão PostgreSQL:**
```
Host: localhost (ou fraud_postgres no Docker)
Port: 5432
Database: fraud_db
User: fraud_user
Password: fraud_password@@!!_2
```

### Checkpoint 11.6: MinIO como Data Lake ✅
- [x] spark/jobs/bronze_to_minio.py criado
- [x] JARs Hadoop-AWS configurados (hadoop-aws, aws-java-sdk-bundle)
- [x] Bucket "fraud-data" criado via MinIO Client (mc)
- [x] Escrita s3a://fraud-data/bronze/ funcionando
- [x] Dados visíveis no MinIO Console (http://localhost:9003)

**MinIO Storage (5M transações):**
| Path | Arquivos | Tamanho |
|------|----------|---------|
| s3a://fraud-data/bronze/customers | 3 parquet | 3 MB |
| s3a://fraud-data/bronze/transactions | 9 parquet | 411 MB |
| **Total** | **12 arquivos** | **414 MB** |

**Conexão MinIO:**
```
Endpoint: http://localhost:9002 (API) / http://localhost:9003 (Console)
Access Key: minioadmin
Secret Key: minioadmin123@@!!_2
Bucket: fraud-data
```

### Checkpoint 11.7: Scale Data (Cluster Distribuído) ✅
- [x] Cluster Spark: 1 Master + 5 Workers
- [x] Cada Worker: 2 cores, 3GB RAM (total: 10 cores, 15GB)
- [x] Imagem Docker: apache/spark:4.0.0-preview2-scala2.13-java21-python3-r-ubuntu
- [x] Configuração 128MB partitions em todos os jobs
- [x] Caminhos dinâmicos (/data vs data) para Docker/Local
- [x] argparse no generate_data.py (--customers, --transactions, --fraud-rate)
- [x] ✅ Teste 1M: ~2min 30s (6.7k tx/s)
- [x] ✅ Teste 5M: ~3min (28k tx/s)
- [x] ✅ **Teste 10M: ~3.5min (47.6k tx/s)** 🚀

**Conceitos aprendidos:**
- spark.sql.files.maxPartitionBytes - tamanho das partições (128m otimizado)
- SPARK_WORKER_CORES e SPARK_WORKER_MEMORY - configuração de workers
- Diferença entre spark-submit local vs cluster (--master spark://...)
- Permissões Docker (chmod 777 para volume mounts)
- Escalabilidade horizontal: 28× melhoria com 10 cores vs 1
- Compressão Parquet (~61% menor que JSON para Big Data)
- Throughput escala melhor com dados maiores (overhead fixo diluído)

---

## 🎯 ARQUITETURA OBJETIVO

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ARQUITETURA LAKEHOUSE COMPLETA                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [ShadowTraffic] ──► [Kafka] ──► [Spark Streaming] ──► [MinIO Data Lake]   │
│                         │              │                      │             │
│                    customers      ETL Jobs              Bronze/Silver/Gold  │
│                    orders                                     │             │
│                                                               ▼             │
│                                                        [PostgreSQL]         │
│                                                         Data Warehouse      │
│                                                               │             │
│                                                    ┌──────────┴──────────┐  │
│                                                    │                     │  │
│                                               [Metabase]           [Streamlit]│
│                                               Dashboards           Apps      │
│                                                    │                     │  │
│                                                    └──────────┬──────────┘  │
│                                                               │             │
│                                                          [Traefik]          │
│                                                        Reverse Proxy        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### VPS OVH Specs:
- **vCores:** 8
- **RAM:** 24 GB
- **Disco:** 200 GB
- **Objetivo:** Processar ~50 GB de dados

### 📈 Projeção para Escalas Maiores

| Volume | Transações | Tamanho Raw | Tempo Real | Throughput | Status |
|--------|------------|-------------|------------|------------|--------|
| ✅ Teste 1 | 50K | 11 MB | ~30s | 1.7k/s | Concluído (Local) |
| ✅ Teste 2 | 1M | 216 MB | ~2.5min | 6.7k/s | Concluído (Cluster) |
| ✅ Teste 3 | 5M | 1.1 GB | ~3min | 28k/s | Concluído (Cluster) |
| ✅ Teste 4 | 10M | 2.2 GB | ~3.5min | 47.6k/s | Concluído (Cluster) |
| ✅ **Teste 5** | **30M** | **19.2 GB** | **~15min** | **110k/s** | **Concluído!** 🎉 |
| 📋 Teste 6 | 50M | ~32 GB | ~25min | ~55k/s | Planejado |
| 📋 Final | 230M | ~50 GB | ~1h | ~60k/s | Objetivo |

### ✅ Teste 3: 5M transações (Cluster 5 Workers)
| Métrica | Valor |
|---------|-------|
| Transações | **5,000,000** |
| Clientes | 50,000 |
| Dados Raw | **1.1 GB** |
| Dados Bronze | 417 MB |
| Dados Silver | 428 MB |
| Dados Gold | 430 MB |
| Fraudes | 250,307 (5.0%) |
| **Tempo total** | **~3 min** |
| **Throughput** | **~28k transações/segundo** |

### ✅ Teste 4: 10M transações (Cluster 5 Workers) 🚀
| Métrica | Valor |
|---------|-------|
| Transações | **10,000,000** |
| Clientes | 100,000 |
| Dados Raw | **2.2 GB** |
| Dados Bronze | 838 MB |
| Dados Silver | 861 MB |
| Dados Gold | 866 MB |
| Fraudes | ~500,000 (5.0%) |
| **Tempo total** | **~3.5 min (210s)** |
| **Throughput** | **~47,600 transações/segundo** |

### ✅ Teste 5: 30M transações (Cluster 5 Workers) 🎉 NOVO!
| Métrica | Valor |
|---------|-------|
| Transações | **30,000,000** |
| Clientes | 50,000 |
| Dados Raw | **19.2 GB** |
| Fraudes Injetadas | 1,500,000 (5.0%) |
| **Tempo total** | **~15 min** |
| **Throughput** | **~110,000 transações/segundo** |

**Breakdown dos tempos (30M):**
| Etapa | Tempo | Throughput |
|-------|-------|------------|
| Bronze Layer | 4.5min | 110,830/s |
| Silver Layer | 5min | 100,000/s |
| Gold Layer | 5min | 100,000/s |
| **Total Pipeline** | **~15min** | **~110k tx/s** |

**Resultados de Detecção:**
| Nível | Quantidade | % |
|-------|------------|---|
| NORMAL | 27,077,000 | 90.26% |
| CRÍTICO | 1,468,416 | 4.89% |
| MÉDIO | 696,770 | 2.32% |
| ALTO | 620,423 | 2.07% |
| BAIXO | 137,391 | 0.46% |

**Breakdown dos tempos (10M):**
| Etapa | Tempo | Descrição |
|-------|-------|-----------|
| Bronze Layer | 50s | JSON → Parquet |
| Silver Layer | 74s | Limpeza e validação |
| Gold Layer | 40s | Agregações |
| Fraud Detection | 45s | Regras + Particionamento |
| **Total Pipeline** | **~210s** | **47.6k tx/s** |

### 🚀 Evolução do Throughput
| Configuração | Transações | Tempo | Throughput | Melhoria |
|--------------|------------|-------|------------|----------|
| Local (1 core) | 50K | ~30s | 1,700/s | baseline |
| Cluster (10 cores) - 1M | 1M | 150s | 6,700/s | **4×** |
| Cluster (10 cores) - 5M | 5M | 180s | 28,000/s | **16×** |
| Cluster (10 cores) - 10M | 10M | 210s | 47,600/s | **28×** |
| Cluster (10 cores) - 30M | 30M | 900s | **110,000/s** | **65×** |

### 💾 Compressão Parquet vs JSON Raw
| Teste | Raw (JSON) | Parquet | Compressão |
|-------|------------|---------|------------|
| 50K | 11 MB | 3 MB | 73% |
| 1M | 216 MB | 56 MB | 74% |
| 5M | 1.1 GB | 430 MB | 61% |
| 10M | 2.2 GB | 866 MB | 61% |

---

## 🔜 CHECKPOINTS PENDENTES

### Fase 1: Completar Infraestrutura de Dados

### Checkpoint 11.8: MinIO como Storage Principal ✅
**Objetivo:** Migrar todo o pipeline para usar MinIO como storage principal
**Status:** ✅ CONCLUÍDO

**O que foi feito:**
- [x] bronze_to_minio.py - Bronze Layer → s3a://fraud-data/bronze/ ✅
- [x] silver_to_minio.py - Silver Layer → s3a://fraud-data/silver/ ✅
- [x] gold_to_minio.py - Gold Layer → s3a://fraud-data/gold/ ✅
- [x] Script unificado run_spark_job.sh para executar qualquer job
- [x] Documentação de erros em docs/ERROS_CONHECIDOS.md

**MinIO Storage Final (10M transações):**
| Path | Dados |
|------|-------|
| s3a://fraud-data/bronze/customers | 100K clientes |
| s3a://fraud-data/bronze/transactions | 10M transações |
| s3a://fraud-data/silver/customers | 100K clientes |
| s3a://fraud-data/silver/transactions | 10M transações |
| s3a://fraud-data/gold/customer_summary | 100K resumos |
| s3a://fraud-data/gold/fraud_summary | 1 resumo geral |
| s3a://fraud-data/gold/fraud_detection | 10M (particionado) |
| **Total** | **83 arquivos, 2.5 GB** |

**🚨 ERROS IMPORTANTES RESOLVIDOS:**

1. **`hostname cannot be null` / `URISyntaxException`**
   - **Causa 1:** Spark 4.x usa AWS SDK v2 que tem BUG com endpoints HTTP
   - **Causa 2:** Hostname `fraud_minio` tem underscore (inválido RFC 952)
   - **Solução:** Usar Spark 3.5.3 + hostname `minio` (service name)
   - **Documentação completa:** `docs/ERROS_CONHECIDOS.md`

2. **JARs corretos para MinIO:**
   ```
   jars/
   ├── hadoop-aws-3.3.4.jar          # Conector S3A (SDK v1)
   ├── aws-java-sdk-bundle-1.12.262.jar  # AWS SDK v1 (NÃO v2!)
   └── postgresql-42.7.4.jar         # JDBC PostgreSQL
   ```

3. **Por que scripts .sh são necessários no cluster:**
   - `spark-submit` cria a JVM ANTES de ler o código Python
   - Configurações `spark.jars` no Python são ignoradas
   - JARs devem ser passados via `--jars` na linha de comando
   - Solução: `run_spark_job.sh` script unificado

**Como executar jobs no cluster:**
```bash
./run_spark_job.sh bronze_to_minio   # RAW → MinIO Bronze
./run_spark_job.sh silver_to_minio   # Silver → MinIO Silver
./run_spark_job.sh gold_to_minio     # Gold → MinIO Gold
./run_spark_job.sh bronze_layer      # RAW → Bronze local
./run_spark_job.sh silver_layer      # Bronze → Silver local
./run_spark_job.sh gold_layer        # Silver → Gold local
```

#### Checkpoint 11.9: Escalar para 50M+ transações
**Objetivo:** Testar limites do cluster com volumes maiores

| Etapa | Volume | Transações | Status |
|-------|--------|------------|--------|
| ✅ Teste 1 | 11 MB | 50k | Concluído |
| ✅ Teste 2 | 216 MB | 1M | Concluído |
| ✅ Teste 3 | 1.1 GB | 5M | Concluído |
| ✅ Teste 4 | 2.2 GB | 10M | **Concluído** |
| 📋 Teste 5 | ~11 GB | 50M | Próximo |
| 📋 Teste 6 | ~50 GB | 230M | Objetivo Final |

### Fase 2: Streaming Real

#### Checkpoint 12: ShadowTraffic + Kafka Producer
**Objetivo:** Gerar dados em streaming para Kafka
**Arquivo:** shadowtraffic/config.json

Conceitos:
- ShadowTraffic configuração
- Kafka topics: customers, orders
- Geração contínua de dados

#### Checkpoint 13: Spark Structured Streaming
**Objetivo:** Consumir Kafka em tempo real
**Arquivo:** spark/jobs/streaming_etl.py

Conceitos:
- readStream vs read
- writeStream vs write
- Trigger, watermark, checkpointing

#### Checkpoint 14: Pipeline Streaming Completo
**Objetivo:** Kafka → Bronze → Silver → Gold em tempo real

### Fase 3: Visualização

#### Checkpoint 15: Metabase
**Objetivo:** Dashboards de BI conectados ao PostgreSQL

Dashboards:
- Fraudes por período
- Customer Lifetime Value
- Sales by city/product

#### Checkpoint 16: Streamlit
**Objetivo:** App interativo de análise

Features:
- Filtros dinâmicos
- Alertas de fraude
- Exploração de dados

#### Checkpoint 17: Traefik
**Objetivo:** Reverse proxy com domínios

Conceitos:
- Routing por domínio
- HTTPS/SSL
- Load balancing

---

## 🛠️ AMBIENTE TÉCNICO

```yaml
Sistema: Ubuntu 25.04 (plucky) - VPS
IP: 54.36.100.35
Shell: zsh

Python: 3.13
PySpark: 4.0.1
Spark: 4.0.1 (SPARK_HOME=/home/ubuntu/Estudos/apache-spark/spark-4.0.1-bin-hadoop3)
Java: OpenJDK 17

Docker: docker.io (não docker-ce - incompatível com Ubuntu 25.04)
```

### Comandos para iniciar sessão:
```bash
cd ~/Estudos/1_projeto_bank_Fraud_detection_data_pipeline
source venv/bin/activate
docker compose ps  # verificar containers
```

---

## 📁 ESTRUTURA DO PROJETO

```
1_projeto_bank_Fraud_detection_data_pipeline/
├── LEARNING_PROGRESS.md    ← Este arquivo (contexto para IA)
├── PROJECT_PLAN.md         ← Plano completo do projeto
├── docker-compose.yml      ← Infraestrutura (Spark 3.5.3 + MinIO + PostgreSQL)
├── run_spark_job.sh        ← 🆕 Script unificado para executar jobs no cluster
├── venv/                   ← Virtual environment Python
│
├── docs/
│   └── ERROS_CONHECIDOS.md ← 🆕 Documentação de erros e soluções
│
├── jars/                   ← JARs necessários
│   ├── hadoop-aws-3.3.4.jar           ← S3A connector (SDK v1)
│   ├── aws-java-sdk-bundle-1.12.262.jar ← AWS SDK v1
│   └── postgresql-42.7.4.jar          ← JDBC PostgreSQL
│
├── scripts/
│   └── generate_data.py    ← Gerador de dados sintéticos
│
├── spark/
│   └── jobs/
│       ├── bronze_layer.py     ← JSON → Parquet local ✅
│       ├── silver_layer.py     ← Limpeza local ✅
│       ├── gold_layer.py       ← Agregações local ✅
│       ├── fraud_detection.py  ← Regras de fraude ✅
│       ├── bronze_to_minio.py  ← 🆕 RAW → MinIO Bronze ✅
│       ├── silver_to_minio.py  ← 🆕 Silver → MinIO Silver ✅
│       ├── gold_to_minio.py    ← 🆕 Gold → MinIO Gold ✅
│       └── load_to_postgres.py ← Gold → PostgreSQL ✅
│
└── data/
    ├── raw/                ← JSON Lines (origem)
    ├── bronze/             ← Parquet local ✅
    ├── silver/             ← Parquet local ✅
    └── gold/               ← Parquet local ✅

MinIO (Data Lake):
s3a://fraud-data/
├── bronze/
│   ├── customers/      ← 100K clientes
│   └── transactions/   ← 10M transações
├── silver/
│   ├── customers/      ← 100K clientes
│   └── transactions/   ← 10M transações
└── gold/
    ├── customer_summary/   ← 100K resumos
    ├── fraud_summary/      ← 1 resumo geral
    └── fraud_detection/    ← 10M (particionado por risk_level)
```

---

## 📝 METODOLOGIA DE ENSINO

### Regras para a IA:

1. **NÃO escreva código automaticamente** - guie o aluno
2. **Explique o conceito primeiro** (teoria breve)
3. **Mostre o código a digitar** em blocos pequenos
4. **Espere o aluno confirmar** que digitou
5. **Execute junto** e analise o resultado
6. **Se der erro**, explique o porquê antes de corrigir

### Formato de aula:
```
## 📝 AULA X.Y: [Nome do Conceito]

[Explicação teórica em 2-3 parágrafos]

---

Agora digita no arquivo [nome]:

```python
# código aqui
```

Me avisa quando terminar!
```

---

## 🐛 PROBLEMAS RESOLVIDOS (para referência)

| Problema | Causa | Solução |
|----------|-------|---------|
| docker-ce não instala | Ubuntu 25.04 incompatível | Usar docker.io nativo |
| Porta 9000 ocupada | Portainer usando | MinIO mudou para 9002/9003 |
| Porta 8080 ocupada | Open-WebUI usando | Spark UI mudou para 8081 |
| Bitnami Spark não funciona | Imagens pagas agora | Usar apache/spark oficial |
| pip não funciona | PEP 668 (externally-managed) | Criar venv |
| PySpark 3.5.3 erro | SPARK_HOME aponta p/ 4.0.1 | Instalar PySpark 4.0.1 |
| JSON corrupt record | Formato array [...] | Mudar para JSON Lines |
| **hostname cannot be null** | **Spark 4.x + AWS SDK v2 bug** | **Usar Spark 3.5.3** |
| **hostname cannot be null** | **Underscore em hostname** | **Usar `minio` não `fraud_minio`** |
| **403 Forbidden MinIO** | **Credenciais erradas** | **Verificar MINIO_ROOT_PASSWORD** |
| **ClassNotFoundException S3A** | **JARs não no classpath** | **--jars no spark-submit** |

---

## 🚀 COMO CONTINUAR

Quando o aluno voltar, dizer:

> "Bem-vindo de volta! Vi no LEARNING_PROGRESS.md que completaste o Bronze Layer.
> Pronto para começar a Silver Layer? Vamos limpar e validar os dados!"

Primeiro passo da próxima sessão:
1. Verificar se containers estão rodando: `docker compose ps`
2. Ativar venv: `source venv/bin/activate`
3. Verificar dados bronze existem: `ls data/bronze/`
4. Começar explicação da Silver Layer

---

*Última atualização: 2025-11-29 (MinIO Integration completado - Bronze/Silver/Gold)*
