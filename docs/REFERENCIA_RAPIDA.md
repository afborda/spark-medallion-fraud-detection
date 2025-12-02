# 🚀 REFERÊNCIA RÁPIDA - Comandos do Projeto

> **Última atualização:** 2025-12-02
> **Pipeline atual:** 51GB de dados brasileiros (51.2M transações)

## 📁 Diretório do projeto
```bash
cd /home/ubuntu/Estudos/1_projeto_bank_Fraud_detection_data_pipeline
```

---

## 📊 MÉTRICAS ATUAIS DO PIPELINE

| Métrica | Valor |
|---------|-------|
| **Transações Raw** | 51,281,996 |
| **Transações Processadas** | 48,445,853 |
| **Dados Raw** | 51 GB (479 arquivos JSON) |
| **Clientes** | 100,000 (Faker pt_BR) |
| **Dispositivos** | 300,102 |
| **Tempo Total** | ~34 min |
| **MinIO Total** | 12 GB |

---

## 🐳 DOCKER

### Subir tudo
```bash
docker-compose up -d
```

### Parar tudo
```bash
docker-compose down
```

### Ver containers
```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

### Reiniciar workers Spark
```bash
docker restart fraud_spark_worker_1 fraud_spark_worker_2 fraud_spark_worker_3 fraud_spark_worker_4 fraud_spark_worker_5
```

---

## 📨 KAFKA

### Listar topics
```bash
docker exec fraud_kafka kafka-topics --list --bootstrap-server localhost:9092
```

### Ver mensagens do topic
```bash
docker exec fraud_kafka kafka-console-consumer \
    --topic transactions \
    --bootstrap-server localhost:9092 \
    --from-beginning \
    --max-messages 5
```

### Criar topic
```bash
docker exec fraud_kafka kafka-topics --create \
    --topic NOME_DO_TOPIC \
    --bootstrap-server localhost:9092 \
    --partitions 5
```

---

## 🎭 SHADOWTRAFFIC (Gerar dados)

### Enviar 100 transações (teste)
```bash
docker run --rm \
    --network 1_projeto_bank_fraud_detection_data_pipeline_default \
    --env-file shadowtraffic/license.env \
    -v $(pwd)/shadowtraffic:/config \
    shadowtraffic/shadowtraffic:latest \
    --config /config/transactions.json \
    --sample 100
```

### Streaming contínuo (produção)
```bash
docker run --rm \
    --network 1_projeto_bank_fraud_detection_data_pipeline_default \
    --env-file shadowtraffic/license.env \
    -v $(pwd)/shadowtraffic:/config \
    shadowtraffic/shadowtraffic:latest \
    --config /config/transactions.json
```

---

## ⚡ SPARK

### Executar job Kafka → PostgreSQL
```bash
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --jars /jars/spark-sql-kafka-0-10_2.12-3.5.3.jar,/jars/kafka-clients-3.5.1.jar,/jars/commons-pool2-2.11.1.jar,/jars/spark-token-provider-kafka-0-10_2.12-3.5.3.jar,/jars/postgresql-42.7.4.jar \
    /jobs/kafka_to_postgres_batch.py
```

### Executar job Bronze → Silver → Gold (MinIO)
```bash
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --jars /jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar,/jars/spark-sql-kafka-0-10_2.12-3.5.3.jar,/jars/kafka-clients-3.5.1.jar,/jars/commons-pool2-2.11.1.jar \
    /jobs/batch_silver_gold.py
```

### Ver UI do Spark
```
http://localhost:8080
```

---

## 🐘 POSTGRESQL

### Conectar ao banco
```bash
docker exec -it fraud_postgres psql -U fraud_user -d fraud_db
```

### Ver tabelas
```bash
docker exec fraud_postgres psql -U fraud_user -d fraud_db -c "\dt"
```

### Contar transações
```bash
docker exec fraud_postgres psql -U fraud_user -d fraud_db -c "SELECT COUNT(*) FROM transactions"
```

### Ver distribuição de risco
```bash
docker exec fraud_postgres psql -U fraud_user -d fraud_db -c "
SELECT risk_level, COUNT(*) as total, ROUND(AVG(fraud_score)) as avg_score
FROM transactions 
GROUP BY risk_level 
ORDER BY total DESC"
```

### Ver alertas de fraude
```bash
docker exec fraud_postgres psql -U fraud_user -d fraud_db -c "SELECT COUNT(*) FROM fraud_alerts"
```

### Top transações críticas
```bash
docker exec fraud_postgres psql -U fraud_user -d fraud_db -c "
SELECT transaction_id, amount, merchant, fraud_score 
FROM transactions 
WHERE risk_level = 'CRÍTICO' 
ORDER BY fraud_score DESC 
LIMIT 10"
```

---

## 📦 MINIO

### Console Web
```
URL: http://localhost:9001
User: minioadmin
Pass: minioadmin123@@!!_2
```

---

## 🔧 DEBUG

### Ver logs do Spark Master
```bash
docker logs fraud_spark_master --tail 50
```

### Ver logs do Kafka
```bash
docker logs fraud_kafka --tail 50
```

### Matar jobs Spark travados
```bash
docker exec fraud_spark_master pkill -f spark-submit
```

### Verificar processos no container
```bash
docker exec fraud_spark_master ps aux
```

---

## 🔄 FLUXO COMPLETO (Copiar e colar)

```bash
# 1. Ir para o diretório
cd /home/ubuntu/Estudos/1_projeto_bank_Fraud_detection_data_pipeline

# 2. Verificar containers
docker ps --format "table {{.Names}}\t{{.Status}}" | grep fraud

# 3. Enviar 100 transações para Kafka
docker run --rm \
    --network 1_projeto_bank_fraud_detection_data_pipeline_default \
    --env-file shadowtraffic/license.env \
    -v $(pwd)/shadowtraffic:/config \
    shadowtraffic/shadowtraffic:latest \
    --config /config/transactions.json \
    --sample 100

# 4. Processar e salvar no PostgreSQL
docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --jars /jars/spark-sql-kafka-0-10_2.12-3.5.3.jar,/jars/kafka-clients-3.5.1.jar,/jars/commons-pool2-2.11.1.jar,/jars/spark-token-provider-kafka-0-10_2.12-3.5.3.jar,/jars/postgresql-42.7.4.jar \
    /jobs/kafka_to_postgres_batch.py

# 5. Verificar resultados
docker exec fraud_postgres psql -U fraud_user -d fraud_db -c "SELECT risk_level, COUNT(*) FROM transactions GROUP BY risk_level ORDER BY COUNT(*) DESC"
```

---

## 📋 CREDENCIAIS

| Serviço | Host | User | Password |
|---------|------|------|----------|
| PostgreSQL | fraud_postgres:5432 | fraud_user | fraud_password@@!!_2 |
| MinIO | minio:9000 | minioadmin | minioadmin123@@!!_2 |
| Kafka | fraud_kafka:9092 | - | - |
| Spark Master | spark-master:7077 | - | - |

---

## 📂 ESTRUTURA DE ARQUIVOS

```
/home/ubuntu/Estudos/1_projeto_bank_Fraud_detection_data_pipeline/
├── docker-compose.yml              # Infraestrutura
├── run_brazilian_pipeline.sh       # 🆕 Script para pipeline 51GB
├── spark/jobs/                     # Scripts Spark
│   ├── README.md                   # Índice principal
│   ├── production/                 # 🚀 USE ESTES em produção!
│   │   ├── bronze_brazilian.py    # JSON → MinIO bronze/ (~10min)
│   │   ├── silver_brazilian.py    # MinIO bronze/ → silver/ (~13min)
│   │   ├── gold_brazilian.py      # MinIO silver/ → gold/ (~11min)
│   │   └── load_to_postgres.py    # Gold → PostgreSQL
│   ├── streaming/                  # 🌊 Processamento tempo real
│   │   ├── streaming_bronze.py
│   │   ├── streaming_silver.py
│   │   ├── streaming_gold.py
│   │   └── streaming_to_postgres.py
│   ├── utils/                      # 🔧 Debug e validação
│   │   ├── check_flags.py
│   │   └── check_gps.py
│   └── experimental/               # 🧪 Testes
├── scripts/                        # 🆕 Geradores de dados
│   ├── generate_parallel.py       # Geração paralela (7 workers)
│   └── generate_brazilian_data.py # Faker pt_BR
├── jars/                           # JARs do Spark
├── data/raw/                       # 51GB de dados JSON
└── docs/                           # Documentação
    ├── GUIA_COMPLETO_ESTUDO.md
    └── REFERENCIA_RAPIDA.md
```

---

## 🇧🇷 PIPELINE BRASILEIRO (51GB)

### Gerar dados (já gerados - 51GB)
```bash
python scripts/generate_parallel.py --target-size 51
```

### Executar pipeline completo
```bash
# Bronze (51GB JSON → 5GB Parquet) ~10min
./run_brazilian_pipeline.sh bronze

# Silver (Limpeza e flags) ~13min  
./run_brazilian_pipeline.sh silver

# Gold (Agregações e scoring) ~11min
./run_brazilian_pipeline.sh gold

# PostgreSQL (carregar para dashboards)
./run_brazilian_pipeline.sh postgres

# Ou tudo de uma vez
./run_brazilian_pipeline.sh all
```

### Verificar tamanhos no MinIO
```bash
docker exec fraud_minio mc du -r local/fraud-data/medallion/
```

