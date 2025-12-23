"""
🏅 MEDALLION PIPELINE - Orquestrado pelo Airflow
Pipeline completo: Bronze → Silver → Gold → Postgres

ARQUITETURA DE WORKERS DEDICADOS:
- Workers 1-2: STREAMING (6GB total, 2 cores) - SEMPRE ATIVOS
- Workers 3-4: BATCH (6GB total, 2 cores) - Usados por este DAG

✅ COEXISTÊNCIA: Streaming e Batch rodam SIMULTANEAMENTE
   Sem competição por recursos, sem parar/reiniciar streaming!

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
# CONFIGURAÇÃO DE RECURSOS - WORKERS DEDICADOS
# Workers 1-2: Streaming (não tocamos)
# Workers 3-4: Batch (usamos aqui)
# ==========================================
BATCH_WORKERS = 2         # Workers 3 e 4
BATCH_CORES = 2           # 1 core por worker = 2 cores total
BATCH_MEMORY = "2g"       # 2GB por executor (workers têm 3GB cada)

default_args = {
    'owner': 'abner',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email': ['abner.borda@gmail.com'],
    'email_on_failure': True,
}

# ==========================================
# COMANDO SPARK-SUBMIT PARA BATCH
# Usa apenas workers 3-4 (batch dedicados)
# Streaming continua rodando nos workers 1-2
# ==========================================
SPARK_SUBMIT_BATCH = """
docker exec fraud_spark_master \
    /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --total-executor-cores {cores} \
    --executor-memory {memory} \
    --conf spark.sql.adaptive.enabled=true \
    --conf spark.dynamicAllocation.enabled=false \
    /jobs/production/{script}
"""

# ==========================================
# VERIFICAÇÃO PRÉ-BATCH
# Verifica se workers batch (3-4) estão disponíveis
# NÃO interfere no streaming (workers 1-2)
# ==========================================
CHECK_BATCH_WORKERS = """
echo "🔍 Verificando workers dedicados ao batch..."

# Verifica status do cluster
CLUSTER_INFO=$(curl -s http://spark-master:8080/json/ 2>/dev/null || curl -s http://localhost:8081/json/)
WORKERS_ALIVE=$(echo $CLUSTER_INFO | python3 -c "import sys,json; d=json.load(sys.stdin); print(len([w for w in d.get('workers',[]) if w.get('state')=='ALIVE']))" 2>/dev/null || echo "0")

echo "📊 Workers ativos: $WORKERS_ALIVE"

if [ "$WORKERS_ALIVE" -lt "2" ]; then
    echo "⚠️ Menos de 2 workers ativos! Batch pode ser mais lento."
fi

# Verifica cores disponíveis para batch
CORES_TOTAL=$(echo $CLUSTER_INFO | python3 -c "import sys,json; print(json.load(sys.stdin).get('cores',0))" 2>/dev/null || echo "0")
CORES_USED=$(echo $CLUSTER_INFO | python3 -c "import sys,json; print(json.load(sys.stdin).get('coresused',0))" 2>/dev/null || echo "0")

echo "📊 Cores total: $CORES_TOTAL, Em uso: $CORES_USED"
echo "✅ Batch usará {cores} cores dos workers dedicados"
echo ""
echo "ℹ️  NOTA: Streaming continua rodando nos workers 1-2 (não será interrompido)"
"""

# ==========================================
# COMANDO PARA RESTAURAR STREAMING (após batch)
# Devolve recursos completos ao streaming
# ==========================================
# VERIFICAÇÃO PÓS-BATCH
# Confirma que streaming continua saudável
# ==========================================
VERIFY_STREAMING_HEALTHY = """
echo "🔍 Verificando saúde do streaming após batch..."

# Verifica se streaming ainda está rodando
STREAMING_PID=$(docker exec fraud_spark_master pgrep -f "streaming_to_postgres" || echo "")

if [ -n "$STREAMING_PID" ]; then
    echo "✅ Streaming continua ativo (PID: $STREAMING_PID)"
else
    echo "⚠️ Streaming não está rodando - pode precisar reiniciar manualmente"
    echo "   Execute: ./scripts/start_streaming.sh"
fi

# Verifica recursos do cluster
CLUSTER_INFO=$(curl -s http://spark-master:8080/json/ 2>/dev/null || curl -s http://localhost:8081/json/)
CORES_USED=$(echo $CLUSTER_INFO | python3 -c "import sys,json; print(json.load(sys.stdin).get('coresused',0))" 2>/dev/null || echo "0")

echo "📊 Cores em uso após batch: $CORES_USED"
echo "✅ Batch concluído! Workers 3-4 liberados."
"""


def on_batch_failure(context):
    """
    Callback executado se qualquer task falhar.
    Com workers dedicados, streaming NÃO precisa ser restaurado!
    Apenas notifica Discord sobre a falha.
    """
    # Notifica Discord sobre a falha
    dag_run = context.get('dag_run')
    task_instance = context.get('task_instance')
    exception = context.get('exception')
    
    # Identifica tasks que completaram
    completed_tasks = []
    task_order = ['check_resources', 'bronze_ingestion', 'silver_transformation', 
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
    
    print("ℹ️  Workers dedicados: Streaming continua rodando normalmente nos workers 1-2")


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
    description='Pipeline Medallion com workers dedicados (Batch: workers 3-4, Streaming: workers 1-2)',
    start_date=datetime(2025, 12, 1),
    # Executa diariamente às 03:00 (horário de menor uso do sistema)
    schedule_interval='0 3 * * *',
    catchup=False,
    tags=['medallion', 'spark', 'producao', 'batch', 'workers-dedicados'],
    on_failure_callback=on_batch_failure,
) as dag:

    # ==========================================
    # TASK: NOTIFICAR INÍCIO
    # ==========================================
    notify_start = PythonOperator(
        task_id='notify_start',
        python_callable=notify_pipeline_start,
    )

    # ==========================================
    # TASK 0: VERIFICAR RECURSOS
    # Verifica workers batch disponíveis (NÃO para streaming)
    # ==========================================
    check_resources = BashOperator(
        task_id='check_resources',
        bash_command=CHECK_BATCH_WORKERS.format(cores=BATCH_CORES),
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
            memory=BATCH_MEMORY,
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
            memory=BATCH_MEMORY,
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
            memory=BATCH_MEMORY,
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
            memory=BATCH_MEMORY,
            script='batch_postgres_from_gold.py'
        ),
    )

    # ==========================================
    # TASK 5: VERIFICAR STREAMING
    # Confirma que streaming continua saudável
    # ==========================================
    verify_streaming = BashOperator(
        task_id='verify_streaming',
        bash_command=VERIFY_STREAMING_HEALTHY,
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
    # notify_start → check_resources → bronze → silver → gold → postgres → verify_streaming → notify_success
    # ==========================================
    notify_start >> check_resources >> bronze >> silver >> gold >> postgres >> verify_streaming >> notify_success