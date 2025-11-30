# 🔍 Fraud Detection Data Pipeline

> Pipeline de detecção de fraudes bancárias usando arquitetura Medallion com Apache Spark

[![Spark](https://img.shields.io/badge/Apache%20Spark-4.0.1-E25A1C?logo=apachespark&logoColor=white)](https://spark.apache.org/)
[![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)](https://python.org/)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)](https://docker.com/)
[![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-yellow)](https://github.com/afborda/spark-medallion-fraud-detection)

---

## 📋 Sobre o Projeto

Este projeto implementa um **pipeline de dados** para detecção de fraudes em transações bancárias, utilizando a arquitetura **Medallion** (Bronze → Silver → Gold) com processamento distribuído via Apache Spark.

### 🎯 Objetivos

- Processar transações bancárias em larga escala
- Identificar padrões de fraude através de regras de negócio
- Implementar arquitetura de dados moderna e escalável
- Preparar dados para análise e machine learning

---

## 🏗️ Arquitetura

### Arquitetura Atual (Batch)
```
┌─────────────────────────────────────────────────────────────────┐
│                     ARQUITETURA MEDALLION                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   📥 RAW          🔶 BRONZE        ⚪ SILVER        🥇 GOLD     │
│   ─────          ───────         ───────         ──────        │
│   JSON           Parquet         Parquet         Parquet       │
│   (origem)       (bruto)         (limpo)         (agregado)    │
│                                                                 │
│   customers  ──► customers   ──► customers   ──► customer_     │
│   .json          /               /               summary/      │
│                                                                 │
│   transactions──► transactions──► transactions──► fraud_       │
│   .json          /               /               detection/    │
│                                                  (partitioned) │
└─────────────────────────────────────────────────────────────────┘
```

### Arquitetura Objetivo (Streaming + Lakehouse)
```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LAKEHOUSE ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐    ┌─────────┐    ┌─────────────────┐    ┌─────────────┐ │
│  │ ShadowTraffic│───►│  Kafka  │───►│ Spark Streaming │───►│ MinIO Lake  │ │
│  │  (Generator) │    │ Topics  │    │   ETL Jobs      │    │ Bronze/     │ │
│  └──────────────┘    │customers│    │                 │    │ Silver/Gold │ │
│                      │ orders  │    └────────┬────────┘    └──────┬──────┘ │
│                      └─────────┘             │                    │        │
│                                              │                    ▼        │
│                                              │            ┌──────────────┐ │
│                                              └───────────►│  PostgreSQL  │ │
│                                                           │Data Warehouse│ │
│                                                           └───────┬──────┘ │
│                                                                   │        │
│                                                     ┌─────────────┴─────┐  │
│                                                     │                   │  │
│                                                ┌────▼────┐      ┌───────▼─┐│
│                                                │Metabase │      │Streamlit││
│                                                │Dashboard│      │  Apps   ││
│                                                └────┬────┘      └────┬────┘│
│                                                     │                │     │
│                                                     └───────┬────────┘     │
│                                                             │              │
│                                                       ┌─────▼─────┐        │
│                                                       │  Traefik  │        │
│                                                       │Rev. Proxy │        │
│                                                       └───────────┘        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Camadas

| Camada | Descrição | Formato |
|--------|-----------|---------|
| **Raw** | Dados brutos originais | JSON Lines |
| **Bronze** | Dados ingeridos com metadados | Parquet |
| **Silver** | Dados limpos e validados | Parquet |
| **Gold** | Dados agregados para análise | Parquet |

---

## 🛠️ Stack Tecnológica

| Tecnologia | Versão | Propósito |
|------------|--------|-----------|
| **Apache Spark** | 4.0.1 | Processamento distribuído |
| **PySpark** | 4.0.1 | Interface Python para Spark |
| **PostgreSQL** | 16 | Banco de dados relacional |
| **Apache Kafka** | 7.5.0 | Streaming de eventos |
| **MinIO** | latest | Object storage (S3-compatible) |
| **Docker** | Compose | Containerização |

---

## 📁 Estrutura do Projeto

```
spark-medallion-fraud-detection/
├── 📄 docker-compose.yml      # Infraestrutura containerizada
├── 📄 .gitignore
├── 📄 README.md
│
├── 📂 scripts/
│   └── generate_data.py       # Gerador de dados sintéticos
│
├── 📂 spark/
│   └── jobs/
│       ├── bronze_layer.py    # Ingestão: JSON → Parquet
│       ├── silver_layer.py    # Limpeza e validação
│       ├── gold_layer.py      # Agregações e métricas
│       └── fraud_detection.py # Regras de detecção de fraude
│
└── 📂 data/
    ├── raw/                   # Dados JSON originais
    ├── bronze/                # Parquet bruto
    ├── silver/                # Parquet limpo
    └── gold/                  # Parquet agregado
```

---

## 🚀 Como Executar

### Pré-requisitos

- Docker e Docker Compose
- Python 3.13+
- Java 17+

### 1. Clonar o repositório

```bash
git clone https://github.com/afborda/spark-medallion-fraud-detection.git
cd spark-medallion-fraud-detection
```

### 2. Subir a infraestrutura

```bash
docker compose up -d
```

### 3. Configurar ambiente Python

```bash
python3 -m venv venv
source venv/bin/activate
pip install pyspark==4.0.1
```

### 4. Gerar dados sintéticos

```bash
python scripts/generate_data.py
```

### 5. Executar o pipeline

```bash
# Bronze Layer - Ingestão
python spark/jobs/bronze_layer.py

# Silver Layer - Limpeza
python spark/jobs/silver_layer.py

# Gold Layer - Agregações
python spark/jobs/gold_layer.py

# Fraud Detection - Regras de Negócio
python spark/jobs/fraud_detection.py
```

---

## 📊 Resultados

### Evolução dos Testes de Performance

| Teste | Transações | Dados Raw | Tempo Total | Throughput | Cluster |
|-------|------------|-----------|-------------|------------|---------|
| Inicial | 500 | ~1 MB | ~10s | 50/s | Local |
| Escala 1 | 50,000 | 11 MB | ~30s | 1,700/s | Local |
| Escala 2 | 1,000,000 | 216 MB | ~2.5min | 6,700/s | 5 Workers |
| Escala 3 | 5,000,000 | 1.1 GB | ~3min | 28,000/s | 5 Workers |
| **Escala 4** | **10,000,000** | **2.2 GB** | **~3.5min** | **47,600/s** | **5 Workers** |

### Configuração Atual do Cluster

```
┌─────────────────────────────────────────────────────────────────┐
│                    SPARK CLUSTER (Docker)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│                    ┌─────────────────┐                          │
│                    │  SPARK MASTER   │                          │
│                    │  Port: 7077     │                          │
│                    │  UI: 8081       │                          │
│                    └────────┬────────┘                          │
│                             │                                   │
│     ┌───────────┬───────────┼───────────┬───────────┐          │
│     │           │           │           │           │          │
│ ┌───▼───┐ ┌─────▼───┐ ┌─────▼───┐ ┌─────▼───┐ ┌─────▼───┐      │
│ │Worker1│ │ Worker2 │ │ Worker3 │ │ Worker4 │ │ Worker5 │      │
│ │2 cores│ │ 2 cores │ │ 2 cores │ │ 2 cores │ │ 2 cores │      │
│ │ 3GB   │ │  3GB    │ │  3GB    │ │  3GB    │ │  3GB    │      │
│ └───────┘ └─────────┘ └─────────┘ └─────────┘ └─────────┘      │
│                                                                 │
│              Total: 10 cores | 15 GB RAM                        │
└─────────────────────────────────────────────────────────────────┘
```

### Performance por Camada (10M transações - Último Teste) 🚀

| Camada | Tempo | Registros | Tamanho |
|--------|-------|-----------|---------|
| 🔶 Bronze | 50s | 10,100,000 | 838 MB |
| ⚪ Silver | 74s | 10,100,000 | 861 MB |
| 🥇 Gold | 40s | Agregações | 866 MB |
| 🚨 Fraud Detection | 45s | 10,000,000 | (incluso) |
| **TOTAL** | **~210s** | - | **2.6 GB** |

### Compressão Parquet (10M transações)

| Camada | Formato | Tamanho | Economia |
|--------|---------|---------|----------|
| Raw | JSON | 2.2 GB | - |
| Bronze | Parquet | 838 MB | **62%** |
| Silver | Parquet | 861 MB | **61%** |
| Gold | Parquet | 866 MB | **61%** |

### 📈 Escalabilidade Comprovada

| Métrica | Local (50K) | Cluster (1M) | Cluster (5M) | Cluster (10M) | Melhoria |
|---------|-------------|--------------|--------------|---------------|----------|
| Transações | 50,000 | 1,000,000 | 5,000,000 | **10,000,000** | **200×** |
| Dados | 11 MB | 216 MB | 1.1 GB | **2.2 GB** | **200×** |
| Tempo | ~30s | ~150s | ~180s | **~210s** | **7×** |
| **Throughput** | 1,700/s | 6,700/s | 28,000/s | **47,600/s** | **28×** |

> **Conclusão:** Com 200× mais dados (50K → 10M), o tempo aumentou apenas 7× (30s → 210s). O throughput subiu de 1,700 para **47,600 transações/segundo** - uma melhoria de **28×**!

### Estatísticas de Fraude (10M transações)

| Nível de Risco | Quantidade | % do Total | Critério |
|----------------|------------|------------|----------|
| 🔴 Alto Risco | ~80,000 | 0.8% | Valor > R$1000 **E** horário 2h-5h |
| 🟠 Risco Médio | ~2,000,000 | 20% | Valor > R$1000 **OU** horário 2h-5h |
| 🟢 Baixo Risco | ~7,920,000 | 79% | Nenhuma regra acionada |
| **TOTAL** | **10,000,000** | 100% | - |

### Dados Atuais

| Entidade | Registros |
|----------|-----------|
| Clientes | 100,000 |
| Transações | 10,000,000 |
| Fraudes (is_fraud) | ~500,000 (5.0%) |

---

## 📈 Progresso do Projeto

### 📊 Relatório de Status (Novembro 2025)

#### ✅ O QUE ESTÁ FEITO

| Item | Status | Observações |
|------|--------|-------------|
| **Infraestrutura Docker** | ✅ | PostgreSQL, MinIO, Kafka, Zookeeper, Spark (1 Master + 5 Workers) |
| **Bronze Layer** | ✅ | `bronze_layer.py`, `medallion_bronze.py`, `streaming_bronze.py` |
| **Silver Layer** | ✅ | `silver_layer.py`, `medallion_silver.py`, `streaming_silver.py` |
| **Gold Layer** | ✅ | `gold_layer.py`, `medallion_gold.py`, `streaming_gold.py` |
| **Fraud Detection básico** | ✅ | `fraud_detection.py` com regras simples + flags avançadas |
| **Integração MinIO** | ✅ | Jobs `*_to_minio.py` e medallion |
| **Integração PostgreSQL** | ✅ | `load_to_postgres.py`, `kafka_to_postgres_batch.py`, `streaming_to_postgres.py` |
| **Geração de Dados** | ✅ | `generate_data.py`, `generate_10m_transactions.py`, ShadowTraffic |
| **Kafka Producer** | ✅ | `kafka_producer.py` |
| **Streaming Pipeline** | ✅ | Bronze→Silver→Gold streaming |
| **Batch Pipeline** | ✅ | Bronze→Silver→Gold batch |
| **Documentação Regras** | ✅ | `docs/REGRAS_FRAUDE.md` (14 regras documentadas) |
| **Escala 10M transações** | ✅ | Testado com sucesso (~3.5min, 47.6k tx/s) |

#### ❌ O QUE ESTÁ FALTANDO

##### 🔴 CRÍTICO (Alto Impacto)

| Item | Planejado | Atual | Ação Necessária |
|------|-----------|-------|-----------------|
| **8 Regras de Fraude Completas** | 8 regras complexas | 2 regras + 8 flags | Implementar regras faltantes |
| **Dashboard Metabase** | Configurado e rodando | ❌ Não existe | Adicionar ao docker-compose |
| **Dashboard Streamlit** | `streamlit/dashboard.py` | ❌ Não existe | Criar pasta e arquivo |
| **Escala 50GB** | Objetivo principal | 2.2GB testado | Gerar e processar 50GB |

##### 🟠 IMPORTANTE (Médio Impacto)

| Item | Planejado | Atual | Ação Necessária |
|------|-----------|-------|-----------------|
| **Entidade Cards** | Tabela de cartões | ❌ Não existe | Criar schema e dados |
| **Entidade Devices** | Tabela de dispositivos | ❌ Não existe | Criar schema e dados |
| **Chargebacks** | Processamento de disputas | ❌ Não existe | Criar pipeline |
| **Blocklist** | Lista de bloqueio | ❌ Não existe | Criar tabela e lógica |
| **Audit Log** | Log de compliance | ❌ Não existe | Implementar logging |
| **Traefik** | Reverse proxy + SSL | ❌ Não existe | Adicionar ao docker-compose |

##### 🟡 DESEJÁVEL (Baixo Impacto)

| Item | Planejado | Atual | Ação Necessária |
|------|-----------|-------|-----------------|
| **Notebooks** | `notebooks/exploration.ipynb` | ❌ Não existe | Criar análise exploratória |
| **Dicionário de Dados** | `docs/data_dictionary.md` | ❌ Não existe | Documentar campos |
| **Arquitetura Doc** | `docs/architecture.md` | ❌ Não existe | Criar diagrama |

#### 🎯 FASES DO PROJETO

| Fase | Descrição | Status | % |
|------|-----------|--------|---|
| **FASE 1** | Ambiente Docker + Dados | ✅ Completo | 100% |
| **FASE 2** | Pipeline Bronze/Silver/Gold | ✅ Completo | 100% |
| **FASE 3** | Regras de Fraude (8 regras) | ⚠️ Parcial | 40% |
| **FASE 4** | Operacional (Audit/Blocklist/Chargeback) | ❌ Não iniciado | 0% |
| **FASE 5** | Visualização (Metabase/Streamlit) | ❌ Não iniciado | 0% |
| **FASE 6** | Escala 50GB + Documentação | ⚠️ Parcial | 30% |

#### 📋 REGRAS DE FRAUDE: Planejado vs. Implementado

| # | Regra Planejada | Status |
|---|-----------------|--------|
| 1 | **Clonagem** (mesma conta, cidades diferentes, <30min) | ❌ |
| 2 | **Teste de Cartão** (3+ tx < R$10 em 5min) | ❌ |
| 3 | **Gasto Anormal** (valor > 50% média mensal) | ⚠️ Parcial |
| 4 | **Account Takeover** (device desconhecido + >R$500) | ❌ |
| 5 | **Anomalia Geográfica** (distância > 3x raio habitual) | ⚠️ Parcial |
| 6 | **Horário Atípico** (fora do horário usual) | ⚠️ Parcial |
| 7 | **Categoria Suspeita** (alto risco + primeira compra) | ❌ |
| 8 | **Incompatibilidade de Idade** (perfil vs compra) | ❌ |

---

### ✅ Concluído (Detalhado)

- [x] **Infraestrutura Docker** - PostgreSQL, MinIO, Kafka, Spark
- [x] **Geração de Dados** - Script para dados sintéticos com argparse
- [x] **Bronze Layer** - Ingestão JSON → Parquet
- [x] **Silver Layer** - Limpeza e validação
- [x] **Gold Layer** - Agregações (customer_summary, fraud_summary)
- [x] **Fraud Detection** - Regras de negócio para detecção
  - ✅ Transações > R$1000 (high_value)
  - ✅ Horários suspeitos 2h-5h (suspicious_hour)
  - ✅ Níveis de risco: Alto/Médio/Baixo
  - ✅ Particionamento por risk_level
  - ✅ 8 Flags de comportamento (cross_state, night, high_value, velocity, gps_mismatch, etc.)
- [x] **PostgreSQL Integration** - Gold Layer no Data Warehouse (5M registros)
- [x] **MinIO Data Lake** - Bronze Layer no storage S3-compatible (414 MB)
- [x] **Cluster Spark Distribuído** - 5 Workers (10 cores, 15GB RAM)
- [x] **Escala 10M transações** - Pipeline completo em ~3.5min (47.6k tx/s) 🚀
- [x] **Documentação de Regras** - 14 regras documentadas em `docs/REGRAS_FRAUDE.md`

### 🔄 Em Desenvolvimento

- [ ] **8 Regras de Fraude Completas** - Implementar regras avançadas
- [ ] **Escalar para 50GB** - Testar limites do cluster com volumes maiores

### 📋 Planejado

- [ ] **Metabase** - Dashboards de BI
- [ ] **Streamlit** - Apps interativos
- [ ] **Traefik** - Reverse proxy com domínios
- [ ] **Cards/Devices** - Entidades adicionais
- [ ] **Chargebacks/Blocklist/Audit** - Pipeline operacional

---

## 🖥️ Infraestrutura

### VPS OVH
| Recurso | Especificação |
|---------|---------------|
| **Modelo** | VPS-3 |
| **vCores** | 8 |
| **RAM** | 24 GB |
| **Disco** | 200 GB |
| **Objetivo** | Processar ~50 GB de dados |

### Serviços Docker

| Serviço | Container | Porta | Status |
|---------|-----------|-------|--------|
| Spark Master | fraud_spark_master | 7077, 8081 | ✅ Rodando |
| Spark Worker 1-5 | fraud_spark_worker_* | - | ✅ 5 Workers |
| PostgreSQL | fraud_postgres | 5432 | ✅ Rodando |
| MinIO Console | fraud_minio | 9003 | ✅ Rodando |
| MinIO API | fraud_minio | 9002 | ✅ Rodando |
| Kafka | fraud_kafka | 9092 | ✅ Rodando |
| Zookeeper | fraud_zookeeper | 2181 | ✅ Rodando |
| Metabase | - | - | 📋 Planejado |
| Streamlit | - | - | 📋 Planejado |
| Traefik | - | 80/443 | 📋 Planejado |

### Executar no Cluster Distribuído

```bash
# Gerar dados (local)
python scripts/generate_data.py --customers 10000 --transactions 1000000

# Executar pipeline no cluster Docker
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  --executor-memory 2g \
  --total-executor-cores 8 \
  /jobs/bronze_layer.py

docker exec fraud_spark_master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  /jobs/silver_layer.py

docker exec fraud_spark_master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  /jobs/gold_layer.py

docker exec fraud_spark_master /opt/spark/bin/spark-submit \
  --master spark://spark-master:7077 \
  /jobs/fraud_detection.py
```

---

## 📚 Conceitos Aplicados

- **Arquitetura Medallion** - Padrão de organização de data lakes
- **Apache Spark** - Processamento distribuído em memória
- **Parquet** - Formato colunar otimizado para analytics
- **Data Quality** - Limpeza, validação e padronização
- **Agregações** - groupBy, sum, count, avg
- **Lógica Condicional** - when/otherwise para regras de negócio
- **Particionamento** - partitionBy para otimização de queries

---

## 🤝 Contribuição

Este é um projeto de aprendizado. Sugestões e melhorias são bem-vindas!

---

## 📝 Licença

MIT License - veja [LICENSE](LICENSE) para detalhes.

---

<p align="center">
  <i>Desenvolvido como projeto de aprendizado em Data Engineering</i>
</p>
