"""
🔄 STREAMING SUPERVISOR - Monitora e reinicia jobs de streaming
================================================================

Este DAG atua como supervisor dos jobs de streaming:
1. Verifica se o cluster Spark está saudável
2. Verifica se o job de streaming está rodando
3. Reinicia o job se cair
4. Envia alertas se houver problemas

Schedule: A cada 5 minutos
Recursos: Não consome cores do Spark (roda no Airflow)

ARQUITETURA DE WORKERS DEDICADOS:
- Workers 1-2: STREAMING (6GB, 2 cores) - Monitorado por este DAG
- Workers 3-4: BATCH (6GB, 2 cores) - Gerenciado pelo medallion_pipeline

Jobs monitorados:
- streaming_to_postgres (2 cores) - Kafka → PostgreSQL
"""

from airflow import DAG
from airflow.operators.python import PythonOperator, BranchPythonOperator
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from datetime import datetime, timedelta
import subprocess
import json
import urllib.request

# Importa notificador Discord
from discord_notifier import (
    notify_jobs_started,
    notify_job_failure,
    notify_cluster_unhealthy,
    notify_supervisor_execution
)

# ==========================================
# CONFIGURAÇÃO
# ==========================================
SPARK_MASTER_URL = "http://spark-master:8080/json/"  # Dentro do Docker
SPARK_MASTER_CONTAINER = "fraud_spark_master"

# Configuração dos jobs de streaming (APENAS streaming_to_postgres)
# streaming_realtime_dashboard removido - Metabase faz agregações via SQL
STREAMING_JOBS = {
    "streaming_to_postgres": {
        "script": "/jobs/streaming/streaming_to_postgres.py",
        "cores": 2,
        "memory": "2g",
        "process_name": "streaming_to_postgres"
    }
}

TOTAL_STREAMING_CORES = 2  # Workers 1-2 dedicados ao streaming
MAX_CLUSTER_USAGE = 0.5    # Streaming usa 50% do cluster (2 de 4 cores)

default_args = {
    'owner': 'abner',
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
    'email': ['abner.borda@gmail.com'],
    'email_on_failure': True,
}


def check_spark_cluster(**context):
    """
    Verifica se o cluster Spark está saudável.
    Retorna informações sobre workers e recursos disponíveis.
    """
    import urllib.request
    import json
    
    try:
        # Tenta conectar ao Spark Master
        with urllib.request.urlopen(SPARK_MASTER_URL, timeout=10) as response:
            data = json.loads(response.read().decode())
        
        alive_workers = data.get('aliveworkers', 0)
        total_cores = data.get('cores', 0)
        cores_used = data.get('coresused', 0)
        active_apps = len(data.get('activeapps', []))
        
        print(f"═══════════════════════════════════════════════")
        print(f"📊 STATUS DO CLUSTER SPARK")
        print(f"═══════════════════════════════════════════════")
        print(f"   Workers ativos: {alive_workers}")
        print(f"   Cores totais:   {total_cores}")
        print(f"   Cores em uso:   {cores_used} ({cores_used*100//total_cores if total_cores > 0 else 0}%)")
        print(f"   Apps ativos:    {active_apps}")
        print(f"═══════════════════════════════════════════════")
        
        # Salva no XCom para próximas tasks
        context['ti'].xcom_push(key='cluster_status', value={
            'healthy': alive_workers >= 2,  # Mínimo 2 workers (temos 4)
            'alive_workers': alive_workers,
            'total_cores': total_cores,
            'cores_used': cores_used,
            'cores_free': total_cores - cores_used,
            'active_apps': active_apps
        })
        
        if alive_workers < 2:
            reason = f"Apenas {alive_workers} workers ativos (mínimo: 2)"
            notify_cluster_unhealthy(
                cluster_status={
                    'alive_workers': alive_workers,
                    'total_cores': total_cores,
                    'cores_used': cores_used,
                    'active_apps': active_apps
                },
                reason=reason
            )
            raise Exception(f"❌ Cluster não saudável: {reason}")
        
        return True
        
    except urllib.error.URLError as e:
        error_msg = f"Não foi possível conectar ao Spark Master: {e}"
        notify_cluster_unhealthy(
            cluster_status={'alive_workers': 0, 'total_cores': 0, 'cores_used': 0, 'active_apps': 0},
            reason=error_msg
        )
        raise Exception(f"❌ {error_msg}")


def check_streaming_jobs(**context):
    """
    Verifica quais jobs de streaming estão rodando.
    Retorna lista de jobs que precisam ser iniciados.
    Verifica tanto processos quanto apps ativos no Spark cluster.
    """
    import subprocess
    import urllib.request
    import json
    
    jobs_to_start = []
    jobs_running = []
    
    print(f"═══════════════════════════════════════════════")
    print(f"🔍 VERIFICANDO JOBS DE STREAMING")
    print(f"═══════════════════════════════════════════════")
    
    # Verifica apps ativos no Spark para confirmar que estão usando o cluster
    try:
        with urllib.request.urlopen(SPARK_MASTER_URL, timeout=10) as response:
            data = json.loads(response.read().decode())
        active_apps = data.get('activeapps', [])
        print(f"   Apps ativos no cluster: {len(active_apps)}")
    except:
        active_apps = []
        print(f"   ⚠️ Não foi possível verificar apps ativos")
    
    for job_name, job_config in STREAMING_JOBS.items():
        # Verifica se o processo está rodando E se há app ativo no cluster
        cmd = f"docker exec {SPARK_MASTER_CONTAINER} pgrep -f '{job_config['process_name']}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        # Considera rodando se: processo existe E (tem app no cluster OU tem PIDs)
        has_process = result.returncode == 0 and result.stdout.strip()
        has_app = any(job_config['process_name'].lower() in app.get('name', '').lower() for app in active_apps)
        
        if has_process or has_app:
            pids = result.stdout.strip().split()[0] if has_process else 'N/A'
            status = '✅ CLUSTER' if has_app else '⚠️ LOCAL'
            print(f"   {status} {job_name}: RODANDO (PID: {pids})")
            jobs_running.append(job_name)
        else:
            print(f"   ❌ {job_name}: PARADO")
            jobs_to_start.append(job_name)
    
    print(f"═══════════════════════════════════════════════")
    print(f"   Jobs rodando:  {len(jobs_running)}")
    print(f"   Jobs parados:  {len(jobs_to_start)}")
    print(f"═══════════════════════════════════════════════")
    
    # Salva no XCom
    context['ti'].xcom_push(key='jobs_to_start', value=jobs_to_start)
    context['ti'].xcom_push(key='jobs_running', value=jobs_running)
    
    return jobs_to_start


def decide_action(**context):
    """
    Decide se precisa iniciar jobs ou se está tudo OK.
    """
    jobs_to_start = context['ti'].xcom_pull(key='jobs_to_start')
    
    if jobs_to_start and len(jobs_to_start) > 0:
        return 'start_streaming_jobs'
    else:
        return 'all_jobs_running'


def start_streaming_jobs(**context):
    """
    Inicia os jobs de streaming que não estão rodando.
    Respeita o limite de 60% dos recursos.
    """
    import subprocess
    import time
    
    jobs_to_start = context['ti'].xcom_pull(key='jobs_to_start')
    cluster_status = context['ti'].xcom_pull(key='cluster_status')
    
    if not jobs_to_start:
        print("✅ Todos os jobs já estão rodando!")
        return
    
    cores_free = cluster_status.get('cores_free', 0)
    
    print(f"═══════════════════════════════════════════════")
    print(f"🚀 INICIANDO JOBS DE STREAMING")
    print(f"═══════════════════════════════════════════════")
    print(f"   Cores livres: {cores_free}")
    print(f"   Jobs a iniciar: {jobs_to_start}")
    print(f"═══════════════════════════════════════════════")
    
    started_jobs = []
    failed_jobs = []
    
    for job_name in jobs_to_start:
        job_config = STREAMING_JOBS.get(job_name)
        if not job_config:
            print(f"   ⚠️ Job desconhecido: {job_name}")
            continue
        
        # Verifica se há cores suficientes
        if job_config['cores'] > cores_free:
            print(f"   ⚠️ {job_name}: Cores insuficientes ({job_config['cores']} necessários, {cores_free} disponíveis)")
            failed_jobs.append(job_name)
            continue
        
        # Monta o comando spark-submit
        cmd = f"""docker exec -d {SPARK_MASTER_CONTAINER} \
            /opt/spark/bin/spark-submit \
            --master spark://spark-master:7077 \
            --total-executor-cores {job_config['cores']} \
            --executor-memory {job_config['memory']} \
            --conf spark.streaming.stopGracefullyOnShutdown=true \
            --conf spark.sql.adaptive.enabled=true \
            {job_config['script']}"""
        
        print(f"   🔄 Iniciando {job_name}...")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"   ✅ {job_name}: Comando enviado!")
            started_jobs.append(job_name)
            cores_free -= job_config['cores']
            time.sleep(5)  # Aguarda entre jobs
        else:
            print(f"   ❌ {job_name}: Erro ao iniciar - {result.stderr}")
            failed_jobs.append(job_name)
    
    # Aguarda jobs iniciarem
    print(f"\n   ⏳ Aguardando jobs iniciarem...")
    time.sleep(15)
    
    # Verifica se realmente iniciaram
    for job_name in started_jobs:
        job_config = STREAMING_JOBS[job_name]
        cmd = f"docker exec {SPARK_MASTER_CONTAINER} pgrep -f '{job_config['process_name']}'"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"   ✅ {job_name}: Confirmado rodando!")
        else:
            print(f"   ❌ {job_name}: Não iniciou corretamente!")
            failed_jobs.append(job_name)
    
    print(f"═══════════════════════════════════════════════")
    print(f"📊 RESULTADO")
    print(f"═══════════════════════════════════════════════")
    print(f"   Iniciados: {len(started_jobs)}")
    print(f"   Falhas:    {len(failed_jobs)}")
    print(f"═══════════════════════════════════════════════")
    
    # Notifica no Discord sobre o resultado
    if started_jobs and not failed_jobs:
        # Sucesso total
        jobs_info = [{"name": job, "cores": STREAMING_JOBS[job]['cores'], "memory": STREAMING_JOBS[job]['memory']} 
                     for job in started_jobs]
        notify_jobs_started(jobs_info, cluster_status)
        notify_supervisor_execution('success', jobs_started=started_jobs, cluster_status=cluster_status)
    elif started_jobs and failed_jobs:
        # Sucesso parcial
        jobs_info = [{"name": job, "cores": STREAMING_JOBS[job]['cores'], "memory": STREAMING_JOBS[job]['memory']} 
                     for job in started_jobs]
        notify_jobs_started(jobs_info, cluster_status)
        notify_supervisor_execution('partial', jobs_started=started_jobs, jobs_failed=failed_jobs, cluster_status=cluster_status)
    elif failed_jobs:
        # Falha total
        notify_supervisor_execution('failed', jobs_failed=failed_jobs, cluster_status=cluster_status)
    
    if failed_jobs:
        # Notifica cada job que falhou individualmente
        for job_name in failed_jobs:
            notify_job_failure(
                job_name=job_name,
                error_message="Job não iniciou ou crashou após inicialização",
                cluster_status=cluster_status,
                attempted_restart=True
            )
        raise Exception(f"Falha ao iniciar jobs: {failed_jobs}")


# ==========================================
# DAG DEFINITION
# ==========================================
with DAG(
    dag_id='streaming_supervisor',
    default_args=default_args,
    description='Monitora e reinicia jobs de streaming automaticamente',
    # Executa a cada 5 minutos
    schedule_interval='*/5 * * * *',
    start_date=datetime(2025, 12, 1),
    catchup=False,
    tags=['streaming', 'supervisor', 'monitoring'],
    max_active_runs=1,  # Evita execuções paralelas
) as dag:
    
    # Task 1: Verifica saúde do cluster
    check_cluster = PythonOperator(
        task_id='check_spark_cluster',
        python_callable=check_spark_cluster,
    )
    
    # Task 2: Verifica jobs de streaming
    check_jobs = PythonOperator(
        task_id='check_streaming_jobs',
        python_callable=check_streaming_jobs,
    )
    
    # Task 3: Decide ação
    decide = BranchPythonOperator(
        task_id='decide_action',
        python_callable=decide_action,
    )
    
    # Task 4a: Inicia jobs se necessário
    start_jobs = PythonOperator(
        task_id='start_streaming_jobs',
        python_callable=start_streaming_jobs,
    )
    
    # Task 4b: Tudo OK
    all_ok = EmptyOperator(
        task_id='all_jobs_running',
    )
    
    # Task 5: Log final
    log_status = BashOperator(
        task_id='log_status',
        bash_command='''
            echo "════════════════════════════════════════════"
            echo "✅ Streaming Supervisor executado com sucesso"
            echo "📅 $(date '+%Y-%m-%d %H:%M:%S')"
            echo "════════════════════════════════════════════"
        ''',
        trigger_rule='none_failed_min_one_success',
    )
    
    # Dependências
    check_cluster >> check_jobs >> decide
    decide >> [start_jobs, all_ok]
    [start_jobs, all_ok] >> log_status
