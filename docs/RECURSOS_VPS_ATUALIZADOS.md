# 🖥️ Recursos VPS Atualizados - 8 vCores, 24 GB RAM

**Data:** 10 de dezembro de 2025  
**Autor:** Sistema de otimização automática

---

## 📊 Especificações da VPS

```yaml
Modelo: VPS-3
vCores: 8
Memória: 24 GB
Armazenamento: 200 GB
```

---

## 🔄 Mudanças Implementadas

### ❌ Configuração Antiga (PROBLEMÁTICA)

```
SPARK CLUSTER:
- Master: sem limite
- Workers: 5 x (2 cores + 3 GB) = 10 cores + 15 GB
- TOTAL: 10 cores + ~16 GB

GERADORES:
- Streaming: 3.0 CPUs + 2 GB
- Batch: 4.0 CPUs + 8 GB

PROBLEMA:
✗ 17 cores configurados (212% overcommit!)
✗ 25 GB memória (104% de uso)
```

### ✅ Nova Configuração (OTIMIZADA)

---

## 📦 Distribuição de Recursos por Serviço

### 🔧 Infraestrutura (sempre ligada)

| Serviço | CPU | Memória | Limite CPU | Limite RAM |
|---------|-----|---------|-----------|-----------|
| PostgreSQL | 0.25 | 256 MB | 0.5 | 512 MB |
| Kafka | 0.25 | 512 MB | 0.5 | 1.0 GB |
| Zookeeper | 0.1 | 128 MB | 0.25 | 256 MB |
| MinIO | 0.1 | 256 MB | 0.25 | 512 MB |
| Airflow Web | 0.25 | 512 MB | 0.5 | 1.5 GB |
| Airflow Scheduler | 0.25 | 512 MB | 0.5 | 1.0 GB |
| Metabase | 0.25 | 512 MB | 0.5 | 1.5 GB |
| **SUBTOTAL** | **1.35** | **2.68 GB** | **3.0** | **6.25 GB** |

### ⚡ Spark Cluster

| Componente | CPU | Memória | Limite CPU | Limite RAM |
|------------|-----|---------|-----------|-----------|
| Master | 0.25 | 512 MB | 0.5 | 1.0 GB |
| Worker 1 | 0.5 | 1.0 GB | 1.0 | 2.5 GB |
| Worker 2 | 0.5 | 1.0 GB | 1.0 | 2.5 GB |
| Worker 3 | 0.5 | 1.0 GB | 1.0 | 2.5 GB |
| Worker 4 | 0.5 | 1.0 GB | 1.0 | 2.5 GB |
| ~~Worker 5~~ | ❌ REMOVIDO | ❌ | - | - |
| **SUBTOTAL** | **2.25** | **4.5 GB** | **4.5** | **11.0 GB** |

### 🔄 Geradores de Dados

| Modo | CPU | Memória | Limite CPU | Limite RAM | Status |
|------|-----|---------|-----------|-----------|--------|
| Streaming | 0.25 | 256 MB | 0.5 | 1.0 GB | ✅ Sempre ligado |
| Batch | 2.0 | 2.0 GB | 4.0 | 6.0 GB | ⚠️ Usar SEM streaming |

---

## 🎯 Modos de Operação

### 🟢 MODO STREAMING (Padrão - 24/7)

```
╔═══════════════════════════════════════════════════════════════╗
║ MODO STREAMING - Operação Normal                             ║
╠═══════════════════════════════════════════════════════════════╣
║ Infraestrutura:  3.0 cores  +  6.25 GB                       ║
║ Spark Cluster:   4.5 cores  + 11.0 GB                        ║
║ Streaming Gen:   0.5 cores  +  1.0 GB                        ║
╠═══════════════════════════════════════════════════════════════╣
║ TOTAL:           8.0 cores  + 18.25 GB  ✅                    ║
║ MARGEM:          0 cores    +  5.75 GB (reserva sistema)     ║
╚═══════════════════════════════════════════════════════════════╝

JOBS SPARK ATIVOS:
- streaming_to_postgres: 2 cores + 1g executor memory
- streaming_realtime_dashboard: 2 cores + 1g executor memory
TOTAL JOBS: 4 cores (100% do cluster)
```

### 🔵 MODO BATCH (Agendado - 03:00 diariamente)

```
╔═══════════════════════════════════════════════════════════════╗
║ MODO BATCH - Processamento Pesado                            ║
╠═══════════════════════════════════════════════════════════════╣
║ Infraestrutura:  3.0 cores  +  6.25 GB                       ║
║ Spark Cluster:   4.5 cores  + 11.0 GB                        ║
║ Batch Generator: 4.0 cores  +  6.0 GB                        ║
╠═══════════════════════════════════════════════════════════════╣
║ TOTAL:          11.5 cores  + 23.25 GB  ⚠️                    ║
║ MARGEM:         -3.5 cores  +  0.75 GB (overcommit)          ║
╚═══════════════════════════════════════════════════════════════╝

⚠️ ATENÇÃO: Streaming DEVE estar parado durante batch!

RECURSOS BATCH:
- Medallion Pipeline: 3 cores (75% do cluster)
- Streaming reduzido: 1 core (25% do cluster)
```

---

## 🔄 Fluxo de Recursos Automatizado

### Durante Pipeline Batch (Airflow)

```mermaid
graph LR
    A[Pipeline Batch Inicia] -->|1| B[Reduz Streaming para 1 core]
    B -->|2| C[Executa Batch com 3 cores]
    C -->|3| D[Restaura Streaming para 4 cores]
    D --> E[Pipeline Completo]
```

**Automação pelo Airflow:**
1. **prepare_resources**: Para streaming completo, reinicia com 1 core
2. **bronze/silver/gold**: Executa com 3 cores cada
3. **restore_resources**: Restaura streaming para 4 cores

---

## 📝 Arquivos Modificados

### ✅ Docker Compose

```bash
/docker-compose.yml
- Spark Workers: 5 → 4 workers
- Worker cores: 2 → 1 core/worker
- Worker memory: 3GB → 2.5GB/worker
- fraud-generator: 3 CPUs → 0.5 CPU
- fraud-generator-batch: 8GB → 6GB
+ Limites adicionados em todos os serviços
```

### ✅ Airflow

```bash
/docker/docker-compose.airflow.yml
+ Webserver: limite 0.5 CPU, 1.5 GB
+ Scheduler: limite 0.5 CPU, 1.0 GB
```

### ✅ DAGs Airflow

```bash
/airflow/dags/medallion_pipeline.py
- TOTAL_CORES: 10 → 4
- STREAMING_CORES: 4 → 1
- BATCH_CORES: 6 → 3
- STREAMING_FULL_CORES: 10 → 4

/airflow/dags/streaming_supervisor.py
- streaming_to_postgres cores: 4 → 2
- streaming_realtime_dashboard cores: 2 → 2
- TOTAL_STREAMING_CORES: 6 → 4
- MAX_CLUSTER_USAGE: 60% → 100%

/airflow/dags/discord_notifier.py
- Atualizado valores de cores para notificações
```

### ✅ Scripts

```bash
/scripts/start_streaming.sh
- STREAMING_POSTGRES_CORES: 4 → 2
- STREAMING_DASHBOARD_CORES: 2 → 2
- TOTAL_STREAMING_CORES: 6 → 4
```

---

## 🚀 Como Aplicar as Mudanças

### 1️⃣ Parar Streaming Atual

```bash
docker exec fraud_spark_master pkill -9 -f "streaming" && sleep 2
```

### 2️⃣ Recriar Containers com Novos Limites

```bash
# Parar e remover worker 5
docker compose stop fraud_spark_worker_5
docker compose rm -f fraud_spark_worker_5

# Recriar workers com novos limites
docker compose up -d --force-recreate \
  fraud_spark_worker_1 \
  fraud_spark_worker_2 \
  fraud_spark_worker_3 \
  fraud_spark_worker_4

# Recriar serviços de infraestrutura
docker compose up -d --force-recreate \
  postgres kafka zookeeper minio metabase

# Recriar Airflow
docker compose -f docker-compose.yml \
  -f docker/docker-compose.airflow.yml \
  up -d --force-recreate
```

### 3️⃣ Reiniciar Streaming com Novos Recursos

```bash
./scripts/start_streaming.sh
```

### 4️⃣ Verificar Recursos

```bash
docker stats --no-stream
```

---

## 📊 Verificação de Recursos

### Comando para verificar uso real:

```bash
docker stats --no-stream --format \
  "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}"
```

### Verificar Spark UI:

- Master: http://localhost:8081
- Jobs: http://localhost:4040

### Verificar Airflow:

- UI: http://localhost:8888
- Login: admin/admin

---

## ⚠️ IMPORTANTE: Regras de Uso

### ✅ PERMITIDO

- ✅ Rodar streaming 24/7
- ✅ Batch agendado às 03:00 (automático)
- ✅ Análises leves no Metabase
- ✅ Consultas SQL no PostgreSQL

### ❌ NÃO PERMITIDO

- ❌ Rodar batch + streaming ao mesmo tempo manualmente
- ❌ Executar gerações de dados grandes durante o dia
- ❌ Iniciar Worker 5 (removido permanentemente)
- ❌ Ultrapassar limites de memória configurados

---

## 🎯 Benefícios da Nova Configuração

1. **✅ Recursos dentro do limite da VPS**
   - CPU: 8.0 cores no modo streaming (100% utilização eficiente)
   - RAM: 18.25 GB no modo streaming (76% da VPS, margem de 24%)

2. **✅ Gerenciamento automático via Airflow**
   - Pipeline batch reduz streaming automaticamente
   - Restaura recursos após conclusão

3. **✅ Limites Docker evitam OOM (Out of Memory)**
   - Cada container tem limite definido
   - Sistema operacional protegido

4. **✅ Monitoramento melhorado**
   - Docker stats mostra uso real vs limites
   - Alertas via Discord quando batch inicia/termina

5. **✅ Performance otimizada**
   - Streaming usa 100% quando batch não roda
   - Batch tem 75% dedicado quando necessário

---

## 🔍 Troubleshooting

### Problema: Container sendo morto (OOMKilled)

```bash
# Verificar logs
docker logs <container_name> --tail 50

# Ajustar limite de memória no docker-compose.yml
# Reiniciar container
docker compose up -d --force-recreate <service_name>
```

### Problema: Spark jobs não iniciam

```bash
# Verificar recursos disponíveis
curl -s http://localhost:8081/json/ | python3 -m json.tool

# Ver workers conectados
docker exec fraud_spark_master \
  curl -s http://localhost:8080/json/ | grep -i workers
```

### Problema: Batch e Streaming rodando simultaneamente

```bash
# Parar tudo
docker exec fraud_spark_master pkill -9 -f "spark-submit"

# Reiniciar apenas streaming
./scripts/start_streaming.sh
```

---

## 📈 Próximos Passos

1. **Monitorar uso por 1 semana**
   - Verificar picos de memória
   - Ajustar limites se necessário

2. **Otimizar ainda mais se necessário**
   - Considerar compressão de dados
   - Tune Spark configurations

3. **Documentar padrões de uso**
   - Horários de pico
   - Consumo médio por job

---

**✅ CONFIGURAÇÃO COMPLETA E OTIMIZADA PARA VPS 8 vCores / 24 GB RAM**
