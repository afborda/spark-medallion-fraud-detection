# 🏦 Bank Fraud Detection - Data Pipeline
## Documentação Completa para Estudo e Reprodução

> **Última atualização:** 2025-12-02
> **Status atual:** 51GB de dados brasileiros processados com sucesso! 🇧🇷

---

## 📊 MÉTRICAS DO PIPELINE ATUAL

| Métrica | Valor |
|---------|-------|
| **Transações Raw** | 51,281,996 |
| **Transações Processadas** | 48,445,853 (5.5% removidas na limpeza) |
| **Dados Raw (JSON)** | 51 GB (479 arquivos) |
| **Bronze (Parquet)** | 5.0 GB |
| **Silver (Parquet)** | 5.4 GB |
| **Gold (Parquet)** | 2.0 GB |
| **Total MinIO** | 12 GB |
| **Clientes** | 100,000 (nomes brasileiros) |
| **Dispositivos** | 300,102 |
| **Tempo Total Pipeline** | ~34 min |
| **Compressão** | 90% (51GB → 5GB) |

---

# 📚 ÍNDICE

1. [Visão Geral do Projeto](#1-visão-geral-do-projeto)
2. [Arquitetura Medallion](#2-arquitetura-medallion)
3. [Stack Tecnológica](#3-stack-tecnológica)
4. [Infraestrutura Docker](#4-infraestrutura-docker)
5. [Configuração do Kafka](#5-configuração-do-kafka)
6. [ShadowTraffic - Gerador de Dados](#6-shadowtraffic---gerador-de-dados)
7. [Spark - Processamento de Dados](#7-spark---processamento-de-dados)
8. [MinIO - Data Lake](#8-minio---data-lake)
9. [PostgreSQL - Banco Analítico](#9-postgresql---banco-analítico)
10. [Fluxo Completo de Dados](#10-fluxo-completo-de-dados)
11. [Problemas Encontrados e Soluções](#11-problemas-encontrados-e-soluções)
12. [Comandos Úteis](#12-comandos-úteis)
13. [Como Reproduzir do Zero](#13-como-reproduzir-do-zero)

---

# 1. VISÃO GERAL DO PROJETO

## O que é este projeto?
Um pipeline de dados para **detecção de fraudes em transações bancárias** em tempo real/batch.

## Objetivo
Simular um cenário real de uma empresa que precisa:
1. Receber milhares de transações por segundo
2. Processar e enriquecer esses dados
3. Aplicar regras de detecção de fraude
4. Armazenar em camadas organizadas (Bronze → Silver → Gold)
5. Disponibilizar para dashboards e análises

## Fluxo Resumido
```
ShadowTraffic → Kafka → Spark → MinIO (Data Lake) → PostgreSQL → Dashboard
    (gera)      (fila)  (processa) (armazena)        (analítico)   (visualiza)
```

---

# 2. ARQUITETURA MEDALLION

## O que é?
Padrão de organização de dados em 3 camadas, usado por empresas como Databricks, Netflix, etc.

## As 3 Camadas

### 🥉 BRONZE (Raw/Crua)
- **O que é**: Dados brutos, exatamente como chegaram
- **Formato**: JSON original do Kafka
- **Transformações**: Nenhuma (apenas adiciona metadados como timestamp de ingestão)
- **Uso**: Auditoria, reprocessamento, debugging

### 🥈 SILVER (Cleaned/Limpa)
- **O que é**: Dados limpos e padronizados
- **Transformações aplicadas**:
  - Conversão de tipos (string → double, etc)
  - Tratamento de nulos
  - Remoção de duplicatas
  - Validação de schema
  - Cálculos derivados (distância GPS, flags de risco)
- **Uso**: Fonte para análises e modelos de ML

### 🥇 GOLD (Business/Negócio)
- **O que é**: Dados agregados e prontos para consumo
- **Transformações aplicadas**:
  - Cálculo do Fraud Score
  - Classificação de risco (CRÍTICO, ALTO, MÉDIO, BAIXO, NORMAL)
  - Agregações por categoria, período, etc
- **Uso**: Dashboards, relatórios, alertas

---

# 3. STACK TECNOLÓGICA

## Componentes e suas funções

| Tecnologia | Função | Por que usar? |
|------------|--------|---------------|
| **Apache Kafka** | Message Broker | Fila de mensagens distribuída, alta throughput |
| **Apache Spark** | Processamento | Engine de Big Data, batch e streaming |
| **MinIO** | Object Storage | Data Lake compatível com S3 |
| **PostgreSQL** | Banco Relacional | Armazenamento analítico para dashboards |
| **Metabase** | BI Dashboard | Visualização de dados (porta 3000) |
| **Faker pt_BR** | Gerador de Dados | Dados brasileiros realistas |
| **Docker** | Containerização | Ambiente isolado e reproduzível |

## Versões Importantes
```
Spark: 3.5.3 (NÃO usar 4.x - tem bug com MinIO)
Kafka: 3.5.1
PostgreSQL: 16
MinIO: Latest
Metabase: Latest
Python: 3.13
```

---

# 4. INFRAESTRUTURA DOCKER

## Arquivo: docker-compose.yml

### Containers criados:
1. **fraud_kafka** - Broker de mensagens (porta 9092)
2. **fraud_spark_master** - Coordenador Spark (porta 8081)
3. **fraud_spark_worker_1 a 5** - Workers Spark (10 cores, 15GB RAM total)
4. **fraud_minio** - Object Storage (porta 9002 API, 9003 console)
5. **fraud_postgres** - Banco de dados (porta 5432)
6. **fraud_metabase** - Dashboard BI (porta 3000)

### Network
Todos os containers estão na mesma rede Docker:
```
1_projeto_bank_fraud_detection_data_pipeline_default
```

### Volumes mapeados
```yaml
# Jobs Spark
./spark/jobs:/jobs

# JARs necessários
./jars:/jars

# Dados
./data:/data
```

### Como subir a infraestrutura
```bash
cd /home/ubuntu/Estudos/1_projeto_bank_Fraud_detection_data_pipeline
docker-compose up -d
```

### Como verificar se está tudo rodando
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

---

# 5. CONFIGURAÇÃO DO KAFKA

## O que é Kafka?
Sistema de mensageria distribuído. Funciona como uma "fila inteligente" onde:
- **Producers** enviam mensagens para **Topics**
- **Consumers** leem mensagens dos **Topics**
- Mensagens são persistidas e podem ser relidas

## Conceitos importantes

### Topics
"Categorias" de mensagens. Criamos 2:
- `transactions` - Transações bancárias (5 partições)
- `customers` - Dados de clientes (3 partições)

### Partições
Divisões dentro de um topic para paralelismo. Mais partições = mais throughput.

### Offsets
Posição de leitura no topic:
- `earliest` - Lê desde o início
- `latest` - Lê apenas novos dados

## Comandos Kafka

### Criar topics
```bash
docker exec fraud_kafka kafka-topics --create \
    --topic transactions \
    --bootstrap-server localhost:9092 \
    --partitions 5 \
    --replication-factor 1

docker exec fraud_kafka kafka-topics --create \
    --topic customers \
    --bootstrap-server localhost:9092 \
    --partitions 3 \
    --replication-factor 1
```

### Listar topics
```bash
docker exec fraud_kafka kafka-topics --list --bootstrap-server localhost:9092
```

### Ver mensagens de um topic
```bash
docker exec fraud_kafka kafka-console-consumer \
    --topic transactions \
    --bootstrap-server localhost:9092 \
    --from-beginning \
    --max-messages 5
```

### Verificar quantidade de mensagens
```bash
docker exec fraud_kafka kafka-run-class kafka.tools.GetOffsetShell \
    --broker-list localhost:9092 \
    --topic transactions
```

---

# 6. SHADOWTRAFFIC - GERADOR DE DADOS

## O que é?
Ferramenta que gera dados fake realistas para testes. Usa arquivos JSON de configuração.

## Arquivo de configuração: shadowtraffic/transactions.json

### Estrutura de uma transação gerada:
```json
{
  "transaction_id": "uuid",
  "customer_id": "uuid",
  "amount": 150.00,
  "merchant": "Amazon",
  "category": "Eletrônicos",
  "transaction_hour": 14,
  "day_of_week": "Segunda",
  "customer_home_state": "SP",
  "purchase_state": "RJ",
  "purchase_latitude": -22.9068,
  "purchase_longitude": -43.1729,
  "device_latitude": -23.5505,
  "device_longitude": -46.6333,
  "is_fraud": false,
  "had_travel_purchase_last_12m": true,
  "is_first_purchase_in_state": false,
  "transactions_last_24h": 3,
  "avg_transaction_amount_30d": 200.00,
  ...
}
```

### Campos importantes para detecção de fraude:
- **customer_home_state vs purchase_state** - Compra fora do estado?
- **device_latitude/longitude vs purchase_latitude/longitude** - GPS batendo?
- **transaction_hour** - Horário suspeito (madrugada)?
- **transactions_last_24h** - Muitas transações recentes?
- **amount vs avg_transaction_amount_30d** - Valor muito acima da média?

## Como executar

### Enviar dados de teste (amostra)
```bash
cd /home/ubuntu/Estudos/1_projeto_bank_Fraud_detection_data_pipeline

docker run --rm \
    --network 1_projeto_bank_fraud_detection_data_pipeline_default \
    --env-file shadowtraffic/license.env \
    -v $(pwd)/shadowtraffic:/config \
    shadowtraffic/shadowtraffic:latest \
    --config /config/transactions.json \
    --sample 100
```

### Enviar dados contínuos (streaming)
```bash
docker run --rm \
    --network 1_projeto_bank_fraud_detection_data_pipeline_default \
    --env-file shadowtraffic/license.env \
    -v $(pwd)/shadowtraffic:/config \
    shadowtraffic/shadowtraffic:latest \
    --config /config/transactions.json
```

### Licença
Arquivo `shadowtraffic/license.env` contém a licença trial (válida até 2025-12-29).

---

# 7. SPARK - PROCESSAMENTO DE DADOS

## O que é Apache Spark?
Engine de processamento distribuído para Big Data. Pode processar:
- **Batch**: Dados em lote (arquivo inteiro)
- **Streaming**: Dados em tempo real (micro-batches)

## Arquitetura Spark
```
Driver (Master) → Coordena o trabalho
    ↓
Executors (Workers) → Executam as tarefas em paralelo
```

## Modos de execução

### Modo Local
```python
spark = SparkSession.builder \
    .appName("MeuJob") \
    .master("local[*]") \  # Usa todos os cores locais
    .getOrCreate()
```

### Modo Cluster
```python
spark = SparkSession.builder \
    .appName("MeuJob") \
    .master("spark://spark-master:7077") \  # Envia para o cluster
    .getOrCreate()
```

## JARs necessários
Spark precisa de JARs extras para conectar com Kafka, MinIO e PostgreSQL:

```
/jars/
├── hadoop-aws-3.3.4.jar              # Conexão com S3/MinIO
├── aws-java-sdk-bundle-1.12.262.jar  # SDK AWS para MinIO
├── spark-sql-kafka-0-10_2.12-3.5.3.jar    # Conector Kafka
├── kafka-clients-3.5.1.jar           # Cliente Kafka
├── commons-pool2-2.11.1.jar          # Pool de conexões
├── spark-token-provider-kafka-0-10_2.12-3.5.3.jar  # Auth Kafka
└── postgresql-42.7.4.jar             # Conector PostgreSQL
```

### Como baixar JARs
```bash
cd /home/ubuntu/Estudos/1_projeto_bank_Fraud_detection_data_pipeline/jars

# Hadoop AWS
wget https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/3.3.4/hadoop-aws-3.3.4.jar

# AWS SDK
wget https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/1.12.262/aws-java-sdk-bundle-1.12.262.jar

# Kafka
wget https://repo1.maven.org/maven2/org/apache/spark/spark-sql-kafka-0-10_2.12/3.5.3/spark-sql-kafka-0-10_2.12-3.5.3.jar
wget https://repo1.maven.org/maven2/org/apache/kafka/kafka-clients/3.5.1/kafka-clients-3.5.1.jar
wget https://repo1.maven.org/maven2/org/apache/commons/commons-pool2/2.11.1/commons-pool2-2.11.1.jar
wget https://repo1.maven.org/maven2/org/apache/spark/spark-token-provider-kafka-0-10_2.12/3.5.3/spark-token-provider-kafka-0-10_2.12-3.5.3.jar

# PostgreSQL
wget https://repo1.maven.org/maven2/org/postgresql/postgresql/42.7.4/postgresql-42.7.4.jar
```

### Como copiar JARs para containers
```bash
for jar in /home/ubuntu/Estudos/1_projeto_bank_Fraud_detection_data_pipeline/jars/*.jar; do
    docker cp "$jar" fraud_spark_master:/jars/
    for i in 1 2 3 4 5; do
        docker cp "$jar" fraud_spark_worker_$i:/jars/
    done
done
```

## Jobs Spark criados

### 1. streaming_bronze.py
- **Função**: Lê do Kafka em streaming e salva no MinIO (Bronze)
- **Input**: Kafka topic `transactions`
- **Output**: MinIO `s3a://fraud-data/streaming/bronze/transactions/`

### 2. batch_silver_gold.py
- **Função**: Processa Bronze → Silver → Gold em batch
- **Input**: MinIO Bronze
- **Output**: MinIO Silver e Gold + métricas de fraude

### 3. kafka_to_postgres_batch.py
- **Função**: Lê do Kafka e salva direto no PostgreSQL
- **Input**: Kafka topic `transactions`
- **Output**: PostgreSQL tabelas `transactions` e `fraud_alerts`

## Como executar jobs Spark

### Formato do comando
```bash
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --jars /jars/jar1.jar,/jars/jar2.jar \
    /jobs/nome_do_job.py
```

### Exemplo completo - Kafka para PostgreSQL
```bash
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --jars /jars/spark-sql-kafka-0-10_2.12-3.5.3.jar,/jars/kafka-clients-3.5.1.jar,/jars/commons-pool2-2.11.1.jar,/jars/spark-token-provider-kafka-0-10_2.12-3.5.3.jar,/jars/postgresql-42.7.4.jar \
    /jobs/kafka_to_postgres_batch.py
```

---

# 8. MINIO - DATA LAKE

## O que é MinIO?
Object Storage open-source, 100% compatível com AWS S3.

## Credenciais
```
Endpoint: http://minio:9000
Access Key: minioadmin
Secret Key: minioadmin123@@!!_2
Bucket: fraud-data
```

## Console Web
Acesse: http://localhost:9001 (ou IP do servidor:9001)

## Estrutura de pastas no bucket
```
fraud-data/
├── streaming/
│   ├── bronze/
│   │   └── transactions/     # Dados brutos do Kafka
│   ├── silver/
│   │   └── transactions_batch/  # Dados limpos
│   └── gold/
│       ├── fraud_alerts_batch/  # Alertas de fraude
│       └── metrics_batch/       # Métricas agregadas
```

## Configuração Spark para MinIO
```python
spark = SparkSession.builder \
    .appName("MeuJob") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123@@!!_2") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .getOrCreate()
```

## IMPORTANTE - Bug do Spark 4.x
Spark 4.x usa AWS SDK v2 que tem bug com endpoints HTTP (não-HTTPS).
**Solução**: Usar Spark 3.5.x com AWS SDK v1.

---

# 9. POSTGRESQL - BANCO ANALÍTICO

## Credenciais
```
Host: fraud_postgres (dentro do Docker) ou localhost:5432 (fora)
Database: fraud_db
User: fraud_user
Password: fraud_password@@!!_2
```

## Tabelas criadas

### transactions
```sql
CREATE TABLE transactions (
    transaction_id VARCHAR(50) PRIMARY KEY,
    customer_id VARCHAR(50),
    amount DECIMAL(10,2),
    merchant VARCHAR(100),
    category VARCHAR(50),
    fraud_score INTEGER,
    risk_level VARCHAR(20),
    is_fraud BOOLEAN,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### fraud_alerts
```sql
CREATE TABLE fraud_alerts (
    alert_id SERIAL PRIMARY KEY,
    transaction_id VARCHAR(50),
    customer_id VARCHAR(50),
    amount DECIMAL(10,2),
    merchant VARCHAR(100),
    fraud_score INTEGER,
    risk_level VARCHAR(20),
    is_fraud BOOLEAN,
    customer_home_state VARCHAR(2),
    purchase_state VARCHAR(2),
    alert_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Comandos úteis

### Conectar ao PostgreSQL
```bash
docker exec -it fraud_postgres psql -U fraud_user -d fraud_db
```

### Ver tabelas
```sql
\dt
```

### Consultas úteis
```sql
-- Total de transações
SELECT COUNT(*) FROM transactions;

-- Distribuição por risco
SELECT risk_level, COUNT(*) as total 
FROM transactions 
GROUP BY risk_level 
ORDER BY total DESC;

-- Top fraudes
SELECT * FROM transactions 
WHERE risk_level = 'CRÍTICO' 
ORDER BY fraud_score DESC 
LIMIT 10;

-- Alertas recentes
SELECT * FROM fraud_alerts 
ORDER BY alert_at DESC 
LIMIT 10;
```

---

# 10. FLUXO COMPLETO DE DADOS

## Passo a passo do que acontece

### 1. Geração de dados (ShadowTraffic)
```
ShadowTraffic → gera JSON → envia para Kafka topic "transactions"
```

### 2. Kafka recebe e armazena
```
Kafka recebe mensagem → persiste no topic → aguarda consumers
```

### 3. Spark lê do Kafka
```python
df = spark.read \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "fraud_kafka:9092") \
    .option("subscribe", "transactions") \
    .load()
```

### 4. Parse do JSON
```python
df_parsed = df \
    .selectExpr("CAST(value AS STRING) as json") \
    .select(from_json(col("json"), schema).alias("data")) \
    .select("data.*")
```

### 5. Transformações Silver
```python
# Limpar valores negativos
df = df.withColumn("amount", abs(col("amount")))

# Calcular distância GPS
df = df.withColumn("distance_gps",
    sqrt(pow(col("device_lat") - col("purchase_lat"), 2) +
         pow(col("device_lon") - col("purchase_lon"), 2)))

# Flag de compra fora do estado
df = df.withColumn("is_cross_state",
    col("customer_home_state") != col("purchase_state"))
```

### 6. Cálculo do Fraud Score (Gold)
```python
df = df.withColumn("fraud_score",
    when(col("is_cross_state"), 15).otherwise(0) +
    when(col("is_night"), 10).otherwise(0) +
    when(col("is_high_value"), 20).otherwise(0) +
    when(col("distance_gps") > 5, 25).otherwise(0) +
    # ... outras regras
)
```

### 7. Classificação de risco
```python
df = df.withColumn("risk_level",
    when(col("fraud_score") >= 70, "CRÍTICO")
    .when(col("fraud_score") >= 50, "ALTO")
    .when(col("fraud_score") >= 30, "MÉDIO")
    .when(col("fraud_score") >= 15, "BAIXO")
    .otherwise("NORMAL"))
```

### 8. Salvamento no PostgreSQL
```python
df.write.jdbc(
    url="jdbc:postgresql://fraud_postgres:5432/fraud_db",
    table="transactions",
    mode="append",
    properties={
        "user": "fraud_user",
        "password": "fraud_password@@!!_2",
        "driver": "org.postgresql.Driver"
    }
)
```

---

# 11. PROBLEMAS ENCONTRADOS E SOLUÇÕES

## Problema 1: MinIO hostname inválido
**Erro**: `Invalid hostname: fraud_minio`
**Causa**: Underscore (_) não é permitido em hostnames
**Solução**: Renomear serviço para `minio` (sem underscore)

## Problema 2: Spark 4.x não conecta no MinIO
**Erro**: `software.amazon.awssdk.core.exception.SdkClientException: Unable to execute HTTP request`
**Causa**: AWS SDK v2 (usado no Spark 4.x) tem bug com endpoints HTTP
**Solução**: Usar Spark 3.5.x com AWS SDK v1:
- hadoop-aws-3.3.4.jar
- aws-java-sdk-bundle-1.12.262.jar

## Problema 3: 403 Forbidden no MinIO
**Erro**: `Status Code: 403; Error Code: AccessDenied`
**Causa**: Senha errada do MinIO
**Solução**: Verificar senha no docker-compose.yml e usar a correta

## Problema 4: NoClassDefFoundError Kafka
**Erro**: `NoClassDefFoundError: org/apache/spark/kafka010/KafkaTokenUtil$`
**Causa**: Faltava JAR do token provider
**Solução**: Adicionar `spark-token-provider-kafka-0-10_2.12-3.5.3.jar`

## Problema 5: Streaming travando
**Erro**: Terminal trava sem processar
**Causa**: Streaming com `startingOffsets: latest` não vê dados antigos
**Solução**: Usar modo batch ou `startingOffsets: earliest`

## Problema 6: Workers sem JAR
**Erro**: `ClassNotFoundException` nos workers
**Causa**: JARs só estavam no master
**Solução**: Copiar JARs para todos os workers também

---

# 12. COMANDOS ÚTEIS

## Docker
```bash
# Ver containers rodando
docker ps

# Ver logs de um container
docker logs fraud_kafka
docker logs -f fraud_spark_master  # -f = follow (tempo real)

# Entrar em um container
docker exec -it fraud_spark_master bash

# Reiniciar container
docker restart fraud_spark_worker_1

# Parar tudo
docker-compose down

# Subir tudo
docker-compose up -d
```

## Kafka
```bash
# Listar topics
docker exec fraud_kafka kafka-topics --list --bootstrap-server localhost:9092

# Ver mensagens
docker exec fraud_kafka kafka-console-consumer \
    --topic transactions \
    --bootstrap-server localhost:9092 \
    --from-beginning --max-messages 5

# Criar topic
docker exec fraud_kafka kafka-topics --create \
    --topic novo_topic \
    --bootstrap-server localhost:9092 \
    --partitions 3
```

## Spark
```bash
# Executar job
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --jars /jars/jar1.jar,/jars/jar2.jar \
    /jobs/meu_job.py

# Ver UI do Spark
# Acesse: http://localhost:8080
```

## PostgreSQL
```bash
# Conectar
docker exec -it fraud_postgres psql -U fraud_user -d fraud_db

# Executar query direta
docker exec fraud_postgres psql -U fraud_user -d fraud_db -c "SELECT COUNT(*) FROM transactions"
```

## MinIO
```bash
# Console web: http://localhost:9001
# Login: minioadmin / minioadmin123@@!!_2
```

---

# 13. COMO REPRODUZIR DO ZERO

## Pré-requisitos
- Docker e Docker Compose instalados
- 8GB+ de RAM disponível
- Portas livres: 9092, 8080, 9000, 9001, 5432

## Passo 1: Clonar/criar projeto
```bash
mkdir -p ~/fraud-detection-pipeline
cd ~/fraud-detection-pipeline
```

## Passo 2: Criar estrutura de pastas
```bash
mkdir -p spark/jobs jars data shadowtraffic
```

## Passo 3: Criar docker-compose.yml
(copiar do projeto atual)

## Passo 4: Subir infraestrutura
```bash
docker-compose up -d
```

## Passo 5: Baixar JARs
```bash
cd jars
# wget para cada JAR (ver seção 7)
```

## Passo 6: Copiar JARs para containers
```bash
for jar in *.jar; do
    docker cp "$jar" fraud_spark_master:/jars/
done
```

## Passo 7: Criar topics Kafka
```bash
docker exec fraud_kafka kafka-topics --create \
    --topic transactions \
    --bootstrap-server localhost:9092 \
    --partitions 5
```

## Passo 8: Configurar ShadowTraffic
- Criar shadowtraffic/transactions.json
- Criar shadowtraffic/license.env

## Passo 9: Criar tabelas PostgreSQL
```bash
docker exec -i fraud_postgres psql -U fraud_user -d fraud_db << 'EOF'
CREATE TABLE IF NOT EXISTS transactions (...);
CREATE TABLE IF NOT EXISTS fraud_alerts (...);
EOF
```

## Passo 10: Enviar dados de teste
```bash
docker run --rm \
    --network $(docker network ls --filter name=fraud -q | head -1) \
    --env-file shadowtraffic/license.env \
    -v $(pwd)/shadowtraffic:/config \
    shadowtraffic/shadowtraffic:latest \
    --config /config/transactions.json \
    --sample 100
```

## Passo 11: Executar pipeline
```bash
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --jars /jars/spark-sql-kafka-0-10_2.12-3.5.3.jar,/jars/kafka-clients-3.5.1.jar,/jars/commons-pool2-2.11.1.jar,/jars/spark-token-provider-kafka-0-10_2.12-3.5.3.jar,/jars/postgresql-42.7.4.jar \
    /jobs/kafka_to_postgres_batch.py
```

## Passo 12: Verificar resultados
```bash
docker exec fraud_postgres psql -U fraud_user -d fraud_db \
    -c "SELECT risk_level, COUNT(*) FROM transactions GROUP BY risk_level"
```

---

# 📝 RESUMO FINAL

## O que você aprendeu:
1. ✅ Arquitetura Medallion (Bronze/Silver/Gold)
2. ✅ Kafka como message broker
3. ✅ Spark para processamento distribuído
4. ✅ MinIO como Data Lake (S3-compatible)
5. ✅ PostgreSQL para dados analíticos
6. ✅ Docker para orquestração
7. ✅ Detecção de fraude com regras de negócio

## Próximos passos sugeridos:
1. 📊 Adicionar dashboard (Metabase ou Grafana)
2. 🤖 Implementar modelo de ML para detecção
3. ⚡ Fazer streaming real funcionar (resolver problema dos JARs)
4. 📈 Adicionar mais métricas e agregações
5. 🔔 Implementar sistema de alertas (email, Slack)

---

**Criado em**: 30/11/2025
**Autor**: Estudo de Data Engineering
**Versão**: 1.0
