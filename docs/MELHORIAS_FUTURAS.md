# 🚀 Melhorias Futuras - Pipeline de Detecção de Fraudes

> **Documento de Evolução do Projeto**  
> Este documento descreve melhorias planejadas para tornar o projeto ainda mais profissional e production-ready.

---

## 📊 Status Atual do Projeto

### ✅ Já Implementado
| Componente | Tecnologia | Status |
|------------|------------|--------|
| Orquestração | Docker Compose | ✅ Manual |
| Data Lake | MinIO (S3-compatible) | ✅ Funcionando |
| Processamento Batch | Apache Spark 3.5.3 | ✅ 51GB processados |
| Processamento Streaming | Spark Structured Streaming | ✅ Funcionando |
| Mensageria | Apache Kafka | ✅ 5M+ mensagens |
| Banco de Dados | PostgreSQL 16 | ✅ 48M transações |
| Visualização | Metabase | ✅ Dashboards públicos |
| Geração de Dados | ShadowTraffic | ✅ Real-time |

---

## 🎯 Melhorias Prioritárias

### 1. 🔄 Apache Airflow - Orquestração de Pipelines

**Por que adicionar?**
- Agendamento automático de jobs
- Monitoramento visual de DAGs
- Retry automático em falhas
- Alertas por email/Slack
- Histórico de execuções

**Arquitetura Proposta:**
```
┌─────────────────────────────────────────────────────────────┐
│                    APACHE AIRFLOW                           │
├─────────────────────────────────────────────────────────────┤
│  DAG: fraud_detection_daily                                 │
│  ├── Task 1: check_new_data (Sensor)                       │
│  ├── Task 2: bronze_ingestion (SparkSubmitOperator)        │
│  ├── Task 3: silver_transformation (SparkSubmitOperator)   │
│  ├── Task 4: gold_aggregation (SparkSubmitOperator)        │
│  ├── Task 5: export_to_postgres (SparkSubmitOperator)      │
│  └── Task 6: notify_completion (SlackOperator)             │
└─────────────────────────────────────────────────────────────┘
```

**Configuração Docker:**
```yaml
# Adicionar ao docker-compose.yml
airflow-webserver:
  image: apache/airflow:2.8.1-python3.11
  environment:
    - AIRFLOW__CORE__EXECUTOR=LocalExecutor
    - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@airflow-postgres:5432/airflow
    - AIRFLOW__WEBSERVER__SECRET_KEY=your-secret-key
    - AIRFLOW__CORE__FERNET_KEY=your-fernet-key
  volumes:
    - ./airflow/dags:/opt/airflow/dags
    - ./airflow/logs:/opt/airflow/logs
    - ./airflow/plugins:/opt/airflow/plugins
  ports:
    - "8080:8080"
  depends_on:
    - airflow-postgres
  command: webserver

airflow-scheduler:
  image: apache/airflow:2.8.1-python3.11
  environment:
    - AIRFLOW__CORE__EXECUTOR=LocalExecutor
    - AIRFLOW__DATABASE__SQL_ALCHEMY_CONN=postgresql+psycopg2://airflow:airflow@airflow-postgres:5432/airflow
  volumes:
    - ./airflow/dags:/opt/airflow/dags
    - ./airflow/logs:/opt/airflow/logs
  depends_on:
    - airflow-webserver
  command: scheduler

airflow-postgres:
  image: postgres:16
  environment:
    - POSTGRES_USER=airflow
    - POSTGRES_PASSWORD=airflow
    - POSTGRES_DB=airflow
  volumes:
    - ./docker_volumes/airflow_postgres:/var/lib/postgresql/data
```

**Exemplo de DAG:**
```python
# airflow/dags/fraud_detection_dag.py
from airflow import DAG
from airflow.providers.apache.spark.operators.spark_submit import SparkSubmitOperator
from airflow.operators.python import PythonOperator
from airflow.sensors.filesystem import FileSensor
from datetime import datetime, timedelta

default_args = {
    'owner': 'data_engineering',
    'depends_on_past': False,
    'start_date': datetime(2024, 1, 1),
    'email_on_failure': True,
    'email': ['alerts@company.com'],
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'fraud_detection_pipeline',
    default_args=default_args,
    description='Pipeline de Detecção de Fraudes - Medallion Architecture',
    schedule_interval='0 */6 * * *',  # A cada 6 horas
    catchup=False,
    tags=['fraud', 'spark', 'medallion'],
) as dag:

    bronze_task = SparkSubmitOperator(
        task_id='bronze_ingestion',
        application='/opt/spark/jobs/batch/bronze_ingestion.py',
        conn_id='spark_default',
        conf={
            'spark.executor.memory': '4g',
            'spark.driver.memory': '2g',
        },
    )

    silver_task = SparkSubmitOperator(
        task_id='silver_transformation',
        application='/opt/spark/jobs/batch/silver_transformation.py',
        conn_id='spark_default',
    )

    gold_task = SparkSubmitOperator(
        task_id='gold_aggregation',
        application='/opt/spark/jobs/batch/gold_aggregation.py',
        conn_id='spark_default',
    )

    bronze_task >> silver_task >> gold_task
```

---

### 2. 📈 Apache Superset - BI Avançado

**Por que adicionar?**
- Visualizações mais avançadas que Metabase
- Suporte nativo a SQL Lab
- Dashboards interativos com drill-down
- Alertas e relatórios automatizados
- Melhor para grandes volumes de dados

**Configuração Docker:**
```yaml
superset:
  image: apache/superset:3.1.0
  environment:
    - SUPERSET_SECRET_KEY=your-secret-key
    - DATABASE_URL=postgresql://superset:superset@superset-postgres:5432/superset
  ports:
    - "8088:8088"
  volumes:
    - ./docker_volumes/superset:/app/superset_home
  depends_on:
    - superset-postgres
```

---

### 3. 🔍 Great Expectations - Data Quality

**Por que adicionar?**
- Validação automática de qualidade de dados
- Documentação de expectativas
- Alertas quando dados não conformes
- Integração com Airflow

**Exemplo de Expectativas:**
```python
# great_expectations/expectations/transactions_suite.py
import great_expectations as gx

context = gx.get_context()

suite = context.add_expectation_suite("transactions_suite")

# Expectativas para transações
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToBeUnique(column="transaction_id")
)
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToBeBetween(
        column="amount", min_value=0.01, max_value=1000000
    )
)
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToNotBeNull(column="customer_id")
)
suite.add_expectation(
    gx.expectations.ExpectColumnValuesToBeInSet(
        column="payment_method",
        value_set=["credit_card", "debit_card", "pix", "boleto"]
    )
)
```

---

### 4. 🛡️ Vault - Gerenciamento de Secrets

**Por que adicionar?**
- Centralização de credenciais
- Rotação automática de senhas
- Auditoria de acesso
- Eliminação de hardcoded credentials

**Configuração Docker:**
```yaml
vault:
  image: hashicorp/vault:1.15
  cap_add:
    - IPC_LOCK
  environment:
    - VAULT_DEV_ROOT_TOKEN_ID=myroot
    - VAULT_DEV_LISTEN_ADDRESS=0.0.0.0:8200
  ports:
    - "8200:8200"
  volumes:
    - ./docker_volumes/vault:/vault/data
```

---

### 5. 📊 Prometheus + Grafana - Observabilidade

**Por que adicionar?**
- Métricas de infraestrutura em tempo real
- Alertas configuráveis
- Dashboards de performance
- SLAs e SLOs

**Configuração Docker:**
```yaml
prometheus:
  image: prom/prometheus:v2.48.0
  ports:
    - "9090:9090"
  volumes:
    - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml
    - ./docker_volumes/prometheus:/prometheus
  command:
    - '--config.file=/etc/prometheus/prometheus.yml'
    - '--storage.tsdb.path=/prometheus'

grafana:
  image: grafana/grafana:10.2.3
  ports:
    - "3000:3000"
  environment:
    - GF_SECURITY_ADMIN_PASSWORD=admin
    - GF_USERS_ALLOW_SIGN_UP=false
  volumes:
    - ./docker_volumes/grafana:/var/lib/grafana
    - ./monitoring/grafana/dashboards:/etc/grafana/provisioning/dashboards
  depends_on:
    - prometheus
```

**Exemplo prometheus.yml:**
```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'spark'
    static_configs:
      - targets: ['spark-master:4040', 'spark-master:8080']
  
  - job_name: 'kafka'
    static_configs:
      - targets: ['kafka:9092']
  
  - job_name: 'postgres'
    static_configs:
      - targets: ['postgres-exporter:9187']
```

---

### 6. 🔄 dbt (Data Build Tool) - Transformações SQL

**Por que adicionar?**
- Transformações versionadas
- Testes automatizados
- Documentação gerada automaticamente
- Lineage de dados

**Estrutura de Projeto dbt:**
```
dbt/
├── dbt_project.yml
├── profiles.yml
├── models/
│   ├── staging/
│   │   ├── stg_transactions.sql
│   │   └── stg_customers.sql
│   ├── intermediate/
│   │   └── int_transaction_enriched.sql
│   └── marts/
│       ├── fct_fraud_alerts.sql
│       └── dim_customers.sql
├── tests/
│   └── assert_positive_amounts.sql
└── macros/
    └── fraud_rules.sql
```

**Exemplo de Modelo dbt:**
```sql
-- models/marts/fct_fraud_alerts.sql
{{ config(materialized='incremental', unique_key='alert_id') }}

WITH transactions AS (
    SELECT * FROM {{ ref('stg_transactions') }}
    {% if is_incremental() %}
    WHERE transaction_date > (SELECT MAX(transaction_date) FROM {{ this }})
    {% endif %}
),

fraud_detection AS (
    SELECT
        transaction_id,
        customer_id,
        amount,
        CASE
            WHEN amount > 10000 THEN 'HIGH_VALUE'
            WHEN velocity_score > 5 THEN 'HIGH_VELOCITY'
            WHEN distance_km > 500 AND time_diff_minutes < 60 THEN 'IMPOSSIBLE_TRAVEL'
            ELSE NULL
        END AS fraud_type
    FROM transactions
)

SELECT * FROM fraud_detection WHERE fraud_type IS NOT NULL
```

---

### 7. 🧪 MLflow - Machine Learning Ops

**Por que adicionar?**
- Versionamento de modelos
- Tracking de experimentos
- Deploy de modelos
- A/B testing

**Configuração Docker:**
```yaml
mlflow:
  image: ghcr.io/mlflow/mlflow:v2.10.0
  ports:
    - "5000:5000"
  environment:
    - MLFLOW_BACKEND_STORE_URI=postgresql://mlflow:mlflow@mlflow-postgres:5432/mlflow
    - MLFLOW_DEFAULT_ARTIFACT_ROOT=s3://mlflow-artifacts/
    - AWS_ACCESS_KEY_ID=minioadmin
    - AWS_SECRET_ACCESS_KEY=minioadmin123@@!!_2
    - MLFLOW_S3_ENDPOINT_URL=http://minio:9000
  volumes:
    - ./docker_volumes/mlflow:/mlflow
  command: mlflow server --host 0.0.0.0 --port 5000
```

**Exemplo de Treinamento:**
```python
# ml/train_fraud_model.py
import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_score, recall_score, f1_score

mlflow.set_tracking_uri("http://mlflow:5000")
mlflow.set_experiment("fraud_detection")

with mlflow.start_run(run_name="random_forest_v1"):
    # Parâmetros
    params = {
        "n_estimators": 100,
        "max_depth": 10,
        "min_samples_split": 5,
    }
    mlflow.log_params(params)
    
    # Treinamento
    model = RandomForestClassifier(**params)
    model.fit(X_train, y_train)
    
    # Métricas
    y_pred = model.predict(X_test)
    mlflow.log_metrics({
        "precision": precision_score(y_test, y_pred),
        "recall": recall_score(y_test, y_pred),
        "f1": f1_score(y_test, y_pred),
    })
    
    # Salvar modelo
    mlflow.sklearn.log_model(model, "fraud_model")
```

---

### 8. 📝 Elasticsearch + Kibana - Logs Centralizados

**Por que adicionar?**
- Logs centralizados de todos os serviços
- Busca full-text em logs
- Dashboards de análise de logs
- Alertas baseados em padrões

**Configuração Docker:**
```yaml
elasticsearch:
  image: docker.elastic.co/elasticsearch/elasticsearch:8.11.3
  environment:
    - discovery.type=single-node
    - xpack.security.enabled=false
    - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
  ports:
    - "9200:9200"
  volumes:
    - ./docker_volumes/elasticsearch:/usr/share/elasticsearch/data

kibana:
  image: docker.elastic.co/kibana/kibana:8.11.3
  ports:
    - "5601:5601"
  environment:
    - ELASTICSEARCH_HOSTS=http://elasticsearch:9200
  depends_on:
    - elasticsearch

filebeat:
  image: docker.elastic.co/beats/filebeat:8.11.3
  volumes:
    - ./monitoring/filebeat.yml:/usr/share/filebeat/filebeat.yml
    - /var/lib/docker/containers:/var/lib/docker/containers:ro
    - /var/run/docker.sock:/var/run/docker.sock:ro
  depends_on:
    - elasticsearch
```

---

## 🏗️ Arquitetura Completa Proposta

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              ARQUITETURA PRODUCTION-READY                                │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│                                                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐              │
│  │ ShadowTraffic│    │   Airflow   │    │    Vault    │    │   MLflow    │              │
│  │  (Geração)  │    │(Orquestração)│    │  (Secrets)  │    │    (ML)     │              │
│  └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘              │
│         │                  │                  │                  │                      │
│         ▼                  ▼                  ▼                  ▼                      │
│  ┌─────────────────────────────────────────────────────────────────────┐               │
│  │                          APACHE KAFKA                                │               │
│  │                     (Mensageria Central)                             │               │
│  └───────────────────────────────┬─────────────────────────────────────┘               │
│                                  │                                                      │
│         ┌────────────────────────┼────────────────────────┐                            │
│         │                        │                        │                            │
│         ▼                        ▼                        ▼                            │
│  ┌─────────────┐          ┌─────────────┐          ┌─────────────┐                     │
│  │    Spark    │          │    Spark    │          │Great Expect.│                     │
│  │   Batch     │          │  Streaming  │          │(Data Quality)│                    │
│  └──────┬──────┘          └──────┬──────┘          └──────┬──────┘                     │
│         │                        │                        │                            │
│         ▼                        ▼                        ▼                            │
│  ┌─────────────────────────────────────────────────────────────────────┐               │
│  │                    MinIO DATA LAKE (S3)                              │               │
│  │        ┌──────────┐  ┌──────────┐  ┌──────────┐                     │               │
│  │        │  Bronze  │→ │  Silver  │→ │   Gold   │                     │               │
│  │        └──────────┘  └──────────┘  └──────────┘                     │               │
│  └───────────────────────────────┬─────────────────────────────────────┘               │
│                                  │                                                      │
│         ┌────────────────────────┼────────────────────────┐                            │
│         │                        │                        │                            │
│         ▼                        ▼                        ▼                            │
│  ┌─────────────┐          ┌─────────────┐          ┌─────────────┐                     │
│  │ PostgreSQL  │          │    dbt      │          │  Superset   │                     │
│  │   (OLTP)    │          │(Transform)  │          │(Visualização)│                    │
│  └─────────────┘          └─────────────┘          └─────────────┘                     │
│                                                                                         │
│  ┌─────────────────────────────────────────────────────────────────────┐               │
│  │                      OBSERVABILIDADE                                 │               │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐            │               │
│  │  │Prometheus│  │ Grafana  │  │  Kibana  │  │Elasticsearch│          │               │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘            │               │
│  └─────────────────────────────────────────────────────────────────────┘               │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Roadmap de Implementação

### Fase 1: Orquestração (1-2 semanas)
| Tarefa | Prioridade | Complexidade |
|--------|------------|--------------|
| Instalar Apache Airflow | 🔴 Alta | Média |
| Criar DAGs para batch pipeline | 🔴 Alta | Média |
| Configurar alertas de falha | 🟡 Média | Baixa |
| Documentar DAGs | 🟡 Média | Baixa |

### Fase 2: Qualidade de Dados (1 semana)
| Tarefa | Prioridade | Complexidade |
|--------|------------|--------------|
| Instalar Great Expectations | 🟡 Média | Média |
| Criar expectation suites | 🟡 Média | Média |
| Integrar com Airflow | 🟡 Média | Baixa |

### Fase 3: Observabilidade (1-2 semanas)
| Tarefa | Prioridade | Complexidade |
|--------|------------|--------------|
| Instalar Prometheus + Grafana | 🟡 Média | Média |
| Configurar exporters | 🟡 Média | Média |
| Criar dashboards de infra | 🟡 Média | Média |
| Instalar ELK Stack | 🟢 Baixa | Alta |

### Fase 4: Machine Learning (2-3 semanas)
| Tarefa | Prioridade | Complexidade |
|--------|------------|--------------|
| Instalar MLflow | 🟡 Média | Média |
| Treinar modelo de fraude | 🟡 Média | Alta |
| Deploy do modelo | 🟡 Média | Alta |
| Integrar com pipeline | 🟡 Média | Média |

### Fase 5: Segurança (1 semana)
| Tarefa | Prioridade | Complexidade |
|--------|------------|--------------|
| Instalar Vault | 🟢 Baixa | Média |
| Migrar secrets | 🟢 Baixa | Média |
| Configurar rotação | 🟢 Baixa | Baixa |

---

## 💰 Estimativa de Recursos

### Recursos Atuais
```
Total: ~16GB RAM, 8 vCPUs
- Spark Master: 2GB
- Spark Workers (2x): 4GB cada
- Kafka: 2GB
- PostgreSQL: 1GB
- MinIO: 1GB
- Metabase: 1GB
- Outros: 1GB
```

### Recursos com Todas Melhorias
```
Total: ~32GB RAM, 16 vCPUs (recomendado)
+ Airflow: 2GB
+ Prometheus/Grafana: 2GB
+ Elasticsearch/Kibana: 4GB
+ MLflow: 2GB
+ Vault: 512MB
+ Superset: 2GB
+ dbt: 512MB
```

---

## 🎯 Quick Wins (Implementação Rápida)

### 1. Adicionar Health Checks no Docker Compose
```yaml
services:
  spark-master:
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080"]
      interval: 30s
      timeout: 10s
      retries: 3
```

### 2. Adicionar Labels para Organização
```yaml
services:
  spark-master:
    labels:
      - "com.fraud.service=spark"
      - "com.fraud.layer=processing"
      - "com.fraud.tier=core"
```

### 3. Adicionar Limites de Recursos
```yaml
services:
  spark-master:
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          memory: 2G
```

### 4. Adicionar Rede Dedicada
```yaml
networks:
  fraud-network:
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16
```

---

## 📚 Recursos de Aprendizado

### Airflow
- [Documentação Oficial](https://airflow.apache.org/docs/)
- [Astronomer Guides](https://www.astronomer.io/guides/)
- [Curso Gratuito - Udemy](https://www.udemy.com/course/the-complete-hands-on-course-to-master-apache-airflow/)

### MLflow
- [MLflow Docs](https://mlflow.org/docs/latest/index.html)
- [ML Engineering for Production](https://www.coursera.org/specializations/machine-learning-engineering-for-production-mlops)

### Great Expectations
- [Getting Started](https://docs.greatexpectations.io/docs/tutorials/getting_started/tutorial_overview)
- [Integração com Airflow](https://docs.greatexpectations.io/docs/deployment_patterns/how_to_use_great_expectations_in_airflow)

### Observabilidade
- [Prometheus + Grafana](https://prometheus.io/docs/visualization/grafana/)
- [ELK Stack](https://www.elastic.co/guide/index.html)

---

## ✅ Checklist de Implementação

```
[ ] Apache Airflow
    [ ] Instalação e configuração
    [ ] DAG batch pipeline
    [ ] DAG streaming pipeline
    [ ] Alertas configurados
    [ ] Documentação

[ ] Great Expectations
    [ ] Instalação
    [ ] Transaction expectations
    [ ] Customer expectations
    [ ] Integração Airflow

[ ] Prometheus + Grafana
    [ ] Instalação
    [ ] Exporters configurados
    [ ] Dashboards criados
    [ ] Alertas configurados

[ ] MLflow
    [ ] Instalação
    [ ] Modelo treinado
    [ ] Deploy em produção
    [ ] Integração pipeline

[ ] Vault
    [ ] Instalação
    [ ] Secrets migrados
    [ ] Rotação configurada

[ ] ELK Stack (Opcional)
    [ ] Instalação
    [ ] Filebeat configurado
    [ ] Dashboards Kibana
```

---

## 📝 Conclusão

Este documento serve como guia para evolução do projeto. As melhorias foram priorizadas considerando:

1. **Impacto no portfólio** - Demonstra conhecimento de ferramentas enterprise
2. **Complexidade** - Balanceando tempo de implementação vs benefício
3. **Recursos** - Considerando limitações de hardware

**Recomendação**: Começar pelo **Apache Airflow**, pois é a melhoria com maior visibilidade e demonstra habilidades de orquestração de pipelines, muito demandada no mercado.

---

> **Autor**: Abner Fonseca  
> **Data**: Dezembro 2024  
> **Versão**: 1.0
