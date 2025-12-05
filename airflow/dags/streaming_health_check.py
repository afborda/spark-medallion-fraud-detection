from airflow.decorators import dag, task 
from airflow.operators.bash import BashOperator
from airflow.operators.python import BranchPythonOperator
from datetime import datetime, timedelta
import subprocess
import requests
import os


@dag(
    dag_id='streaming_health_check',
    start_date=datetime(2025, 1, 1),
    schedule='*/5 * * * *',  # A cada 5 minutos
    catchup=False,
    tags=['streaming', 'health_check', 'monitoramento'],
    default_args={
        'owner': 'abner',
        'retries': 1,
        'retry_delay': timedelta(minutes=2),
    }
)
def streaming_health_check():
    """
    DAG de monitoramento de Streaming job.
    Verifica se o job de streaming está rodando e reinicia se necessário.
    """
    
    @task
    def check_spark_process():
        """Verifica se o processo Spark Streaming está rodando."""
        try:
            result = subprocess.run(
                ["docker", "exec", "fraud_spark_master", "ps", "aux"],
                capture_output=True,
                text=True,
                timeout=30
            )

            # Procura por 'spark-submit' ou 'streaming' na lista de processos
            is_running = 'spark-submit' in result.stdout or 'streaming' in result.stdout
            print(f"Spark process running: {is_running}")
            print(f"Process found: {result.stdout[:500]}")
            return {"process_running": is_running}

        except Exception as e:
            print(f"Error checking Spark process: {e}")
            return {"process_running": False, 'error': str(e)}

    @task
    def check_metrics_freshness():
        """Verifica se as métricas estão sendo atualizadas"""
        try:
            result = subprocess.run(
                ['docker', 'exec', 'fraud_postgres', 
                 'psql', '-U', 'fraud_user', '-d', 'fraud_db', '-t', '-c',
                 "SELECT EXTRACT(EPOCH FROM (NOW() - MAX(processed_at)))/60 FROM streaming_metrics;"
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Pega os minutos desde a última atualização
            minutes_since_update = float(result.stdout.strip())
            is_fresh = minutes_since_update < 10  # Menos de 10 min = OK
            
            print(f"Minutes since last update: {minutes_since_update:.1f}")
            print(f"Metrics fresh: {is_fresh}")
            
            return {
                'minutes_since_update': minutes_since_update,
                'metrics_fresh': is_fresh
            }
            
        except Exception as e:
            print(f"Error checking metrics: {e}")
            return {'metrics_fresh': False, 'error': str(e)}

    def decide_action(**context):
        """Decide se precisa reiniciar o streaming job"""
        ti = context['ti']
        
        # Puxa os resultados das tasks anteriores
        process_status = ti.xcom_pull(task_ids='check_spark_process')
        metrics_status = ti.xcom_pull(task_ids='check_metrics_freshness')
        
        process_ok = process_status.get('process_running', False)
        metrics_ok = metrics_status.get('metrics_fresh', False)
        
        print(f"Process OK: {process_ok}")
        print(f"Metrics OK: {metrics_ok}")
        
        # Se processo não está rodando OU métricas estão velhas
        if not process_ok or not metrics_ok:
            print("⚠️ PROBLEMA DETECTADO! Reiniciando...")
            return 'restart_streaming'
        else:
            print("✅ Tudo OK!")
            return 'all_healthy'

    @task
    def all_healthy():
        """Task executada quando tudo está OK"""
        print("✅ Streaming job está saudável!")
        print("Nenhuma ação necessária.")
        return {'status': 'healthy'}

    @task
    def restart_streaming():
        """Reinicia o streaming job"""
        print("🔄 Reiniciando Streaming Job...")
        
        # Comando para reiniciar (mesmo que você rodou manualmente!)
        cmd = """
        docker exec -d fraud_spark_master /opt/spark/bin/spark-submit \
          --master 'local[2]' \
          --jars /opt/spark/jars/spark-sql-kafka-0-10_2.12-3.5.3.jar,/opt/spark/jars/kafka-clients-3.5.1.jar,/opt/spark/jars/spark-token-provider-kafka-0-10_2.12-3.5.3.jar,/opt/spark/jars/postgresql-42.7.4.jar \
          --conf spark.driver.memory=2g \
          --conf spark.executor.memory=2g \
          /jobs/streaming/streaming_realtime_dashboard.py
        """
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        print(f"Restart command executed!")
        print(f"stdout: {result.stdout}")
        print(f"stderr: {result.stderr}")
        
        return {'status': 'restarted', 'return_code': result.returncode}

    @task
    def send_alert(restart_result: dict):
        """Envia alerta quando o streaming é reiniciado"""
        
        # === TELEGRAM (usando variáveis de ambiente) ===
        TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
        TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
        
        message = f"""
🚨 *ALERTA: Streaming Reiniciado*

O job de streaming foi reiniciado automaticamente.

Status: {restart_result.get('status')}
Return Code: {restart_result.get('return_code')}
Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

_Verifique os logs para mais detalhes._
        """
        
        # Envia pro Telegram (se configurado)
        if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
            try:
                url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
                response = requests.post(url, json={
                    'chat_id': TELEGRAM_CHAT_ID,
                    'text': message,
                    'parse_mode': 'Markdown'
                })
                print(f"✅ Alerta enviado para Telegram! Response: {response.status_code}")
            except Exception as e:
                print(f"❌ Erro ao enviar Telegram: {e}")
        else:
            print("⚠️ Telegram não configurado. Configure as variáveis telegram_bot_token e telegram_chat_id")
        
        return {'alert_sent': True}

    # Criar o branch operator
    decide = BranchPythonOperator(
        task_id='decide_action',
        python_callable=decide_action,
    )

    # Executar as tasks
    process_check = check_spark_process()
    metrics_check = check_metrics_freshness()
    healthy = all_healthy()
    restart = restart_streaming()
    alert = send_alert(restart)  # Recebe o resultado do restart!

    # Definir o fluxo
    # 1. Primeiro verifica processo e métricas (em paralelo)
    # 2. Depois decide o que fazer
    # 3. Se reiniciar, envia alerta
    [process_check, metrics_check] >> decide
    decide >> healthy
    decide >> restart >> alert


# Instancia o DAG
streaming_health_check()