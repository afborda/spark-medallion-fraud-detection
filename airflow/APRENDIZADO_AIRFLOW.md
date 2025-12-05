# 🎓 Aprendizado Apache Airflow - Progresso do Abner

> **Última atualização:** 2025-12-05
> **Status:** Em andamento - Módulo 3 CONCLUÍDO ✅
> **Método:** Ensino linha por linha, digitando código, com perguntas de fixação

---

## 📚 Método de Ensino Acordado

```
1. CONCEITO   → Explicação teórica (o que é, pra que serve)
2. ANALOGIA   → Comparação com algo do mundo real
3. CÓDIGO     → Aluno digita, professor explica linha por linha
4. EXERCÍCIO  → Pergunta para fixar o conhecimento
5. PRÓXIMO    → Só avança quando entendeu
```

**Regras:**
- Não copiar/colar código pronto - sempre digitar
- Entender cada linha antes de avançar
- Objetivo: saber fazer sozinho sem IA

---

## ✅ Conceitos Já Aprendidos

### Módulo 1: Fundamentos (CONCLUÍDO ✅)

#### 1.1 O que é Orquestração
- **Aprendido:** Orquestrador ≠ Processador
- **Analogia:** Chef de cozinha (Airflow) vs Cozinheiros (Spark, Kafka)
- **Pergunta respondida:** "Quem é o orquestrador no seu projeto hoje?" → Resposta: Você mesmo (executa scripts manualmente)

#### 1.2 O que é DAG (Directed Acyclic Graph)
- **Aprendido:** 
  - Graph = coisas conectadas
  - Directed = tem direção (setas)
  - Acyclic = sem ciclos (não volta pro início)
- **Analogia:** Mapa de metrô com direção única
- **Pergunta respondida:** "Por que Acyclic?" → Resposta: Para evitar loop infinito

#### 1.3 Estrutura de um DAG
- **Aprendido:** 4 partes principais:
  1. IMPORTS - ferramentas do Airflow
  2. DEFAULT_ARGS - configurações padrão (retries, email)
  3. DEFINIÇÃO DO DAG - nome, schedule, tags
  4. TASKS E DEPENDÊNCIAS - o que fazer e em que ordem
- **Analogia:** Receita de bolo (ingredientes, instruções, passos)

#### 1.4 Primeiro DAG - Hello World
- **Arquivo criado:** `airflow/dags/hello_world.py`
- **Conceitos aplicados:**
  - `from airflow import DAG`
  - `from airflow.operators.python import PythonOperator`
  - `default_args` com owner, retries, retry_delay, email
  - `with DAG(...) as dag:` para criar o DAG
  - `PythonOperator` para executar funções Python
  - `task_id` e `python_callable`
  - Dependências com `>>` (task_a >> task_b)

#### 1.5 Paralelismo
- **Aprendido:** Usar lista `[]` para tasks em paralelo
- **Exemplo:** `task_inicio >> [task_hello, task_fim]`
- **Pergunta respondida:** Escolheu C, era B (lista Python)

---

## 📍 Onde Paramos

**Próximo passo:** Módulo 4 - Operadores Avançados e TaskFlow API

**Pendente:**
- [ ] TaskFlow API (@task, @dag) - forma moderna de escrever DAGs
- [ ] Sensors (esperar arquivos/condições)
- [ ] XCom - passar dados entre tasks
- [ ] DAG Factory pattern

---

## 🗺️ Roteiro Completo

### Módulo 1: Fundamentos ✅ CONCLUÍDO
- [x] O que é orquestração
- [x] O que é DAG
- [x] Estrutura de um DAG
- [x] Primeiro DAG (Hello World)
- [x] Paralelismo com listas

### Módulo 2: Docker e UI ✅ CONCLUÍDO
- [x] Docker Compose para Airflow (arquivo separado)
- [x] Integração com Traefik (domínio airflow.abnerfonseca.com.br)
- [x] Resolução de problemas (permissões, URL encoding)
- [x] Acessar UI do Airflow
- [x] Executar DAG manualmente
- [x] Ver execução com tasks verdes

### Módulo 3: Integração com Spark ✅ CONCLUÍDO
- [x] BashOperator para executar docker exec
- [x] Docker-in-Docker (montar socket)
- [x] Dockerfile customizado com Docker CLI
- [x] DAG medallion_pipeline completo
- [x] Execução bem sucedida: Bronze → Silver → Gold → Postgres
- [x] Pipeline executou ~65M registros em ~1h40min

### Módulo 4: Operadores Avançados (PRÓXIMO 👈)
- [ ] TaskFlow API (@task, @dag)
- [ ] Sensors (esperar arquivos/condições)
- [ ] XCom - passar dados entre tasks
- [ ] Branching (condicionais)

### Módulo 5: Produção
- [ ] DAG Factory pattern
- [ ] Testes com pytest
- [ ] CI/CD

---

## 📝 Arquivos Criados

| Arquivo | Status | Descrição |
|---------|--------|-----------|
| `airflow/dags/hello_world.py` | ✅ Completo | Primeiro DAG de exemplo |
| `airflow/dags/medallion_pipeline.py` | ✅ Completo | Pipeline Spark completo |
| `airflow/APRENDIZADO_AIRFLOW.md` | ✅ Ativo | Este arquivo de progresso |
| `docker-compose.airflow.yml` | ✅ Completo | Docker Compose do Airflow |
| `Dockerfile.airflow` | ✅ Completo | Imagem customizada com Docker CLI |
| `airflow/logs/` | ✅ Criado | Logs do Airflow |
| `airflow/plugins/` | ✅ Criado | Plugins customizados |

---

## 🔑 Comandos/Códigos Importantes Aprendidos

```python
# Imports básicos
from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

# Default args
default_args = {
    'owner': 'abner',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

# Criar DAG
with DAG(
    dag_id='nome_do_dag',
    default_args=default_args,
    schedule_interval='@daily',
    start_date=datetime(2025, 12, 1),
    catchup=False,
) as dag:

# Criar task
task = PythonOperator(
    task_id='nome_task',
    python_callable=funcao_python,
)

# Dependências
task_a >> task_b           # sequencial
task_a >> [task_b, task_c] # paralelo
```

```bash
# Comandos Docker para Airflow

# Criar database airflow no PostgreSQL existente
docker exec -it fraud_postgres psql -U fraud_user -d fraud_db -c "CREATE DATABASE airflow;"

# Inicializar Airflow (criar tabelas e usuário admin)
docker compose -f docker-compose.yml -f docker-compose.airflow.yml run --rm airflow-init

# Subir Airflow (webserver + scheduler)
docker compose -f docker-compose.yml -f docker-compose.airflow.yml up -d airflow-webserver airflow-scheduler

# Verificar status
docker ps --filter "name=airflow"

# Ver logs
docker logs fraud_airflow_webserver
docker logs fraud_airflow_scheduler
```

```yaml
# Estrutura do docker-compose.airflow.yml

# Template reutilizável
x-airflow-common: &airflow-common
  image: apache/airflow:2.10.3
  environment:
    AIRFLOW__CORE__EXECUTOR: LocalExecutor
    AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: postgresql+psycopg2://user:pass@host/db

# Serviços
services:
  airflow-init:      # Inicialização (roda uma vez)
  airflow-webserver: # UI (porta 8888)
  airflow-scheduler: # Agendador
```

---

## 🐛 Problemas Resolvidos

### 1. Permissão de pastas (Permission denied)
**Problema:** Container Airflow não conseguia escrever em `logs/`
**Solução:** `sudo chmod -R 777 airflow/logs airflow/plugins airflow/dags`

### 2. URL Encoding (senha com caracteres especiais)
**Problema:** Senha `fraud_password@@!!_2` quebrava a URL de conexão
**Solução:** URL encoding manual: `@` = `%40`, `!` = `%21`
```
fraud_password@@!!_2 → fraud_password%40%40%21%21_2
```

### 3. Docker-in-Docker (executar docker de dentro do Airflow)
**Problema:** Airflow em container não tinha acesso ao Docker do host
**Solução:**
1. Montar socket: `- /var/run/docker.sock:/var/run/docker.sock`
2. Criar Dockerfile.airflow com Docker CLI instalado
3. Rodar como root: `user: "0:0"`

---

## 🏆 Resultados do Pipeline Medallion

**Execução bem sucedida em 2025-12-05:**

| Task | Tempo | Registros |
|------|-------|-----------|
| bronze_ingestion | ~20 min | 51M transações |
| silver_transformation | ~25 min | 51M registros |
| gold_aggregation | ~40 min | Métricas + Alertas |
| load_to_postgres | ~15 min | ~65M registros |
| **TOTAL** | **~1h40min** | **Pipeline completo!** |

---

## 💬 Instruções para Próxima Sessão

**Para a IA continuar de onde paramos:**

1. Ler este arquivo primeiro
2. Continuar do "Onde Paramos" (Módulo 3 - Integração com Spark)
3. Manter o método de ensino (explicar → digitar → perguntar)
4. Atualizar este arquivo ao final com "salvar"

**Para o aluno:**
- Comando "salvar" = atualiza este documento com o progresso
- Não pular etapas
- Perguntar se não entender

---

## 🌐 Acessos Configurados

| Serviço | URL Local | URL Domínio |
|---------|-----------|-------------|
| Airflow UI | http://localhost:8888 | https://airflow.abnerfonseca.com.br |
| Login | admin / admin | admin / admin |
