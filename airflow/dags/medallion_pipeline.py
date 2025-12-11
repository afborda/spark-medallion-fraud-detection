"""
🏅 MEDALLION PIPELINE - Orquestrado pelo Airflow
Pipeline completo: Bronze → Silver → Gold → Postgres
Com gerenciamento dinâmico de recursos Streaming/Batch

Fluxo de recursos (VPS 8 cores, 24 GB):
- Antes do batch: Streaming reduzido para 25% (1 core)
- Durante batch: Batch usa 75% (3 cores)
- Após batch: Streaming restaurado para 100% (4 cores)

Schedule: Diário às 03:00 (horário de menor uso)
"""

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta

# Importa notificador Discord
from discord_notifier import (
    notify_batch_started,
    notify_batch_completed,
    notify_batch_failed
)

# ==========================================
# CONFIGURAÇÃO DE RECURSOS DO CLUSTER
# VPS: 8 vCores, 24 GB RAM
# Cluster Spark: 4 workers x 1 core = 4 cores total
# ==========================================
TOTAL_CORES = 4           # Total de cores no cluster Spark (4 workers x 1 core)
STREAMING_CORES = 1       # 25% para streaming durante batch
BATCH_CORES = 3           # 75% para batch
STREAMING_FULL_CORES = 4  # 100% quando batch não está rodando

default_args = {
    'owner': 'abner',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email': ['abner.borda@gmail.com'],
    'email_on_failure': True,
}

# ==========================================
# COMANDO SPARK-SUBMIT PARA BATCH (com limite de cores)
# Cluster: 4 workers x 1 core = 4 cores total
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
# Batch usa 3 cores, deixa 1 core para streaming
# SEMPRE inicia streaming se não estiver rodando
# ==========================================
REDUCE_STREAMING = """
echo "🔄 Configurando streaming para {streaming_cores} cores (25%)..."

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
    echo "✅ Streaming iniciado com {streaming_cores} cores (25%)"
else
    echo "⚠️ Streaming pode não ter iniciado - verifique logs"
fi

echo "✅ Recursos preparados para batch (streaming: 25%, batch: 75%)"
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
    Envia notificação Discord sobre a falha.
    """
    import subprocess
    
    # Restaura streaming
    print("⚠️ Pipeline falhou! Restaurando streaming para 100%...")
    cmd = RESTORE_STREAMING.format(full_cores=STREAMING_FULL_CORES)
    subprocess.run(cmd, shell=True, check=False)
    print("✅ Streaming restaurado após falha")
    
    # Notifica Discord sobre a falha
    dag_run = context.get('dag_run')
    task_instance = context.get('task_instance')
    exception = context.get('exception')
    
    # Identifica tasks que completaram
    completed_tasks = []
    task_order = ['prepare_resources', 'bronze_ingestion', 'silver_transformation', 
                  'gold_aggregation', 'load_to_postgres']
    
    failed_task = task_instance.task_id if task_instance else 'unknown'
    
    for task in task_order:
        if task == failed_task:
            break
        completed_tasks.append(task)
    
    notify_batch_failed(
        dag_run_id=dag_run.run_id if dag_run else 'unknown',
        failed_task=failed_task,
        error_message=str(exception) if exception else 'Erro desconhecido',
        tasks_completed=completed_tasks
    )


def notify_pipeline_start(**context):
    """Task para notificar início do pipeline."""
    dag_run = context.get('dag_run')
    notify_batch_started(
        dag_run_id=dag_run.run_id if dag_run else 'manual',
        scheduled_time=dag_run.execution_date.strftime('%Y-%m-%d %H:%M') if dag_run else 'manual'
    )


def notify_pipeline_success(**context):
    """Task para notificar conclusão do pipeline."""
    dag_run = context.get('dag_run')
    
    # Calcula duração (aproximada)
    if dag_run and dag_run.start_date:
        duration = (datetime.now() - dag_run.start_date.replace(tzinfo=None)).total_seconds()
    else:
        duration = 0
    
    tasks_status = {
        'prepare_resources': 'success',
        'bronze_ingestion': 'success',
        'silver_transformation': 'success',
        'gold_aggregation': 'success',
        'load_to_postgres': 'success',
        'restore_resources': 'success'
    }
    
    notify_batch_completed(
        dag_run_id=dag_run.run_id if dag_run else 'manual',
        total_duration_seconds=duration,
        tasks_status=tasks_status
    )


with DAG(
    dag_id='medallion_pipeline',
    default_args=default_args,
    description='Pipeline Medallion com gerenciamento de recursos Streaming/Batch (25%/75%)',
    start_date=datetime(2025, 12, 1),
    # Executa diariamente às 03:00 (horário de menor uso do sistema)
    schedule_interval='0 3 * * *',
    catchup=False,
    tags=['medallion', 'spark', 'producao', 'resource-management', 'batch'],
    on_failure_callback=restore_streaming_on_failure,
) as dag:

    # ==========================================
    # TASK: NOTIFICAR INÍCIO
    # ==========================================
    notify_start = PythonOperator(
        task_id='notify_start',
        python_callable=notify_pipeline_start,
    )

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
    # TASK: NOTIFICAR SUCESSO
    # ==========================================
    notify_success = PythonOperator(
        task_id='notify_success',
        python_callable=notify_pipeline_success,
        trigger_rule='all_success',  # Só executa se tudo deu certo
    )

    # ==========================================
    # DEPENDÊNCIAS - Define a ordem de execução
    # notify_start → prepare_resources → bronze → silver → gold → postgres → restore_resources → notify_success
    # ==========================================
    notify_start >> prepare_resources >> bronze >> silver >> gold >> postgres >> restore_resources >> notify_success