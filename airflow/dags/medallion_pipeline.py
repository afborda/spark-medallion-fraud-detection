"""
🏅 MEDALLION PIPELINE - Orquestrado pelo Airflow
Pipeline completo: Bronze → Silver → Gold → Postgres
Com gerenciamento dinâmico de recursos Streaming/Batch

Fluxo de recursos:
- Antes do batch: Streaming reduzido para 40% (4 cores)
- Durante batch: Batch usa 60% (6 cores)
- Após batch: Streaming restaurado para 100% (10 cores)
"""

from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

# ==========================================
# CONFIGURAÇÃO DE RECURSOS DO CLUSTER
# ==========================================
TOTAL_CORES = 10          # Total de cores no cluster Spark (5 workers x 2 cores)
STREAMING_CORES = 4       # 40% para streaming durante batch
BATCH_CORES = 6           # 60% para batch
STREAMING_FULL_CORES = 10 # 100% quando batch não está rodando

default_args = {
    'owner': 'abner',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email': ['abner.borda@gmail.com'],
    'email_on_failure': True,
}

# ==========================================
# COMANDO SPARK-SUBMIT PARA BATCH (com limite de cores)
# ==========================================
SPARK_SUBMIT_BATCH = """
docker exec fraud_spark_master \
    /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --total-executor-cores {cores} \
    --executor-memory 2g \
    --conf spark.sql.adaptive.enabled=true \
    /jobs/production/{script}
"""

# ==========================================
# COMANDO PARA REDUZIR STREAMING (antes do batch)
# Para o streaming atual e reinicia com menos recursos
# SEMPRE inicia streaming se não estiver rodando
# ==========================================
REDUCE_STREAMING = """
echo "🔄 Configurando streaming para {streaming_cores} cores (40%)..."

# 1. Para streaming existente (se houver)
echo "📍 Verificando streaming existente..."
docker exec fraud_spark_master pkill -f "streaming_to_postgres" 2>/dev/null || true

# 2. Aguarda processos finalizarem
sleep 10

# 3. SEMPRE inicia streaming com recursos reduzidos
echo "🚀 Iniciando streaming com {streaming_cores} cores..."
docker exec -d fraud_spark_master \
    /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --total-executor-cores {streaming_cores} \
    --executor-memory 1g \
    --conf spark.streaming.stopGracefullyOnShutdown=true \
    --conf spark.sql.adaptive.enabled=true \
    /jobs/streaming/streaming_to_postgres.py

# 4. Aguarda streaming iniciar e verifica
sleep 10
STREAMING_CHECK=$(docker exec fraud_spark_master pgrep -f "streaming_to_postgres" || echo "")
if [ -n "$STREAMING_CHECK" ]; then
    echo "✅ Streaming iniciado com {streaming_cores} cores (40%)"
else
    echo "⚠️ Streaming pode não ter iniciado - verifique logs"
fi

echo "✅ Recursos preparados para batch (streaming: 40%, batch: 60%)"
"""

# ==========================================
# COMANDO PARA RESTAURAR STREAMING (após batch)
# Devolve recursos completos ao streaming
# ==========================================
RESTORE_STREAMING = """
echo "🔄 Restaurando streaming para {full_cores} cores (100%)..."

# 1. Verifica se streaming está rodando (com recursos reduzidos)
STREAMING_PID=$(docker exec fraud_spark_master pgrep -f "streaming_to_postgres" || echo "")

if [ -n "$STREAMING_PID" ]; then
    echo "📍 Streaming encontrado (PID: $STREAMING_PID). Atualizando recursos..."
    
    # 2. Para o streaming reduzido
    docker exec fraud_spark_master pkill -f "streaming_to_postgres" || true
    
    # 3. Aguarda processos finalizarem
    sleep 10
fi

# 4. Reinicia streaming com recursos completos
echo "🚀 Reiniciando streaming com {full_cores} cores..."
docker exec -d fraud_spark_master \
    /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --total-executor-cores {full_cores} \
    --executor-memory 2g \
    --conf spark.streaming.stopGracefullyOnShutdown=true \
    --conf spark.sql.adaptive.enabled=true \
    /jobs/streaming/streaming_to_postgres.py

echo "✅ Streaming restaurado com {full_cores} cores (100%)"
"""


def restore_streaming_on_failure(context):
    """
    Callback executado se qualquer task falhar.
    Garante que streaming volta ao normal mesmo com erro no batch.
    """
    import subprocess
    print("⚠️ Pipeline falhou! Restaurando streaming para 100%...")
    cmd = RESTORE_STREAMING.format(full_cores=STREAMING_FULL_CORES)
    subprocess.run(cmd, shell=True, check=False)
    print("✅ Streaming restaurado após falha")


with DAG(
    dag_id='medallion_pipeline',
    default_args=default_args,
    description='Pipeline Medallion com gerenciamento de recursos Streaming/Batch (40%/60%)',
    start_date=datetime(2025, 12, 1),
    schedule_interval='@daily',
    catchup=False,
    tags=['medallion', 'spark', 'producao', 'resource-management'],
    on_failure_callback=restore_streaming_on_failure,
) as dag:

    # ==========================================
    # TASK 0: PREPARAR RECURSOS
    # Reduz streaming para liberar cores para batch
    # ==========================================
    prepare_resources = BashOperator(
        task_id='prepare_resources',
        bash_command=REDUCE_STREAMING.format(streaming_cores=STREAMING_CORES),
        retries=1,
        retry_delay=timedelta(seconds=30),
    )

    # ==========================================
    # TASK 1: BRONZE - Ingestão de dados brutos
    # ==========================================
    bronze = BashOperator(
        task_id='bronze_ingestion',
        bash_command=SPARK_SUBMIT_BATCH.format(
            cores=BATCH_CORES,
            script='batch_bronze_from_raw.py'
        ),
    )

    # ==========================================
    # TASK 2: SILVER - Limpeza e transformação
    # ==========================================
    silver = BashOperator(
        task_id='silver_transformation',
        bash_command=SPARK_SUBMIT_BATCH.format(
            cores=BATCH_CORES,
            script='batch_silver_from_bronze.py'
        ),
    )

    # ==========================================
    # TASK 3: GOLD - Agregações e métricas
    # ==========================================
    gold = BashOperator(
        task_id='gold_aggregation',
        bash_command=SPARK_SUBMIT_BATCH.format(
            cores=BATCH_CORES,
            script='batch_gold_from_silver.py'
        ),
    )

    # ==========================================
    # TASK 4: POSTGRES - Carregar para BI
    # ==========================================
    postgres = BashOperator(
        task_id='load_to_postgres',
        bash_command=SPARK_SUBMIT_BATCH.format(
            cores=BATCH_CORES,
            script='batch_postgres_from_gold.py'
        ),
    )

    # ==========================================
    # TASK 5: RESTAURAR RECURSOS
    # Devolve recursos completos ao streaming
    # ==========================================
    restore_resources = BashOperator(
        task_id='restore_resources',
        bash_command=RESTORE_STREAMING.format(full_cores=STREAMING_FULL_CORES),
        trigger_rule='all_done',  # Executa mesmo se tasks anteriores falharem
    )

    # ==========================================
    # DEPENDÊNCIAS - Define a ordem de execução
    # prepare_resources → bronze → silver → gold → postgres → restore_resources
    # ==========================================
    prepare_resources >> bronze >> silver >> gold >> postgres >> restore_resources