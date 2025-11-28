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
│   .json          /               /               summary/      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
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
│       └── gold_layer.py      # Agregações e métricas
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
```

---

## 📊 Resultados

### Dados Processados

| Entidade | Registros |
|----------|-----------|
| Clientes | 100 |
| Transações | 500 |

### Estatísticas de Fraude

| Métrica | Valor |
|---------|-------|
| Total de transações | 500 |
| Fraudes detectadas | 19 |
| Valor total fraudado | R$ 62.260,93 |
| Taxa de fraude | 3.8% |

---

## 📈 Progresso do Projeto

### ✅ Concluído

- [x] **Infraestrutura Docker** - PostgreSQL, MinIO, Kafka, Spark
- [x] **Geração de Dados** - Script para dados sintéticos
- [x] **Bronze Layer** - Ingestão JSON → Parquet
- [x] **Silver Layer** - Limpeza e validação
- [x] **Gold Layer** - Agregações (customer_summary, fraud_summary)

### 🔄 Em Desenvolvimento

- [ ] **Regras de Fraude** - Detecção baseada em regras de negócio
  - Transações > R$1000
  - Múltiplas transações em < 1 hora
  - Horários suspeitos (2h-5h)
  - Cliente novo + valor alto

### 📋 Planejado

- [ ] **Kafka Streaming** - Processamento em tempo real
- [ ] **Dashboard** - Visualização de métricas
- [ ] **Alertas** - Notificações de fraude
- [ ] **ML Models** - Detecção por machine learning

---

## 🔧 Serviços Docker

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| PostgreSQL | 5432 | Banco de dados |
| MinIO Console | 9003 | Object storage UI |
| MinIO API | 9002 | Object storage API |
| Kafka | 9092 | Message broker |
| Spark UI | 8081 | Interface Spark |

---

## 📚 Conceitos Aplicados

- **Arquitetura Medallion** - Padrão de organização de data lakes
- **Apache Spark** - Processamento distribuído em memória
- **Parquet** - Formato colunar otimizado para analytics
- **Data Quality** - Limpeza, validação e padronização
- **Agregações** - groupBy, sum, count, avg

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
