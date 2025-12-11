"""
🔄 STREAMING SUPERVISOR (SIMPLIFICADO)
Monitora e reinicia streaming_to_postgres se necessário

Verifica a cada 5 minutos:
- Cluster tem 3+ workers ativos
- Job streaming_to_postgres está rodando
- App está registrado no cluster

Se algo falhar, reinicia automaticamente.
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import subprocess
import requests
import time

SPARK_MASTER_URL = "http://fraud_spark_master:8080/json/"

default_args = {
    'owner': 'abner',
    'retries': 1,
    'retry_delay': timedelta(minutes=1),
}

def check_and_restart_if_needed():
    """Verifica streaming e reinicia se necessário"""
    
    print("=" * 60)
    print("🔍 VERIFICANDO STREAMING")
    print("=" * 60)
    
    # 1. Verificar cluster
    try:
        response = requests.get(SPARK_MASTER_URL.replace('fraud_spark_master', 'localhost').replace('8080', '8081'), timeout=10)
        spark_status = response.json()
        
        workers = spark_status.get('aliveworkers', 0)
        cores_used = spark_status.get('coresused', 0)
        active_apps = spark_status.get('activeapps', [])
        
        print(f"Workers: {workers}/4")
        print(f"Cores em uso: {cores_used}/4")
        print(f"Apps ativos: {len(active_apps)}")
        
        if workers < 3:
            print(f"❌ Poucos workers: {workers} < 3")
            return
            
    except Exception as e:
        print(f"❌ Erro ao consultar cluster: {e}")
        return
    
    # 2. Verificar processo Python
    ps_result = subprocess.run(
        ["docker", "exec", "fraud_spark_master", "pgrep", "-a", "python3"],
        capture_output=True,
        text=True
    )
    
    has_process = 'streaming_to_postgres' in ps_result.stdout
    print(f"Processo Python: {'✅' if has_process else '❌'}")
    
    # 3. Verificar app no cluster
    streaming_apps = [app for app in active_apps if 'PostgreSQL' in app.get('name', '')]
    has_app = len(streaming_apps) > 0
    print(f"App no cluster: {'✅' if has_app else '❌'}")
    
    # 4. Decidir ação
    is_healthy = has_process and has_app
    
    if is_healthy:
        print("✅ STREAMING SAUDÁVEL")
        print("=" * 60)
    else:
        print("❌ STREAMING COM PROBLEMA - REINICIANDO...")
        print("=" * 60)
        
        # Reiniciar
        subprocess.run([
            "bash", 
            "/opt/airflow/dags/../../../scripts/start_streaming_simple.sh"
        ], check=False)
        
        print("🔄 Reiniciado! Aguardando 30s...")
        time.sleep(30)


with DAG(
    dag_id='streaming_supervisor_simple',
    default_args=default_args,
    description='Monitor simples do streaming (apenas PostgreSQL)',
    schedule_interval='*/5 * * * *',  # A cada 5 minutos
    start_date=datetime(2025, 12, 10),
    catchup=False,
    tags=['streaming', 'monitor', 'production'],
) as dag:
    
    check_task = PythonOperator(
        task_id='check_and_restart',
        python_callable=check_and_restart_if_needed,
    )
