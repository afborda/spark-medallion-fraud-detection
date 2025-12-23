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
    schedule=None,  # DESABILITADO - Usar streaming_supervisor em vez disso
    catchup=False,
    tags=['streaming', 'health_check', 'monitoramento', 'DEPRECATED'],
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
        """Verifica se as transações estão sendo processadas pelo streaming"""
        try:
            # Verifica a tabela transactions (atualizada pelo streaming principal)
            # Usa event_time que é o timestamp da transação processada
            result = subprocess.run(
                ['docker', 'exec', 'fraud_postgres', 
                 'psql', '-U', 'fraud_user', '-d', 'fraud_db', '-t', '-c',
                 "SELECT EXTRACT(EPOCH FROM (NOW() - MAX(event_time)))/60 FROM transactions;"
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            # Pega os minutos desde a última transação
            minutes_since_update = float(result.stdout.strip())
            is_fresh = minutes_since_update < 10  # Menos de 10 min = OK
            
            print(f"Minutes since last transaction: {minutes_since_update:.1f}")
            print(f"Streaming active: {is_fresh}")
            
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
        """Reinicia o streaming job (APENAS streaming_to_postgres)"""
        print("🔄 Reiniciando Streaming Job (streaming_to_postgres)...")
        
        # ATUALIZADO: Usa streaming_to_postgres no cluster mode (workers 1-2 dedicados)
        # streaming_realtime_dashboard foi REMOVIDO para evitar competição
        cmd = """
        docker exec -d fraud_spark_master /opt/spark/bin/spark-submit \
          --master spark://fraud_spark_master:7077 \
          --deploy-mode client \
          --total-executor-cores 2 \
          --executor-memory 2g \
          --driver-memory 1g \
          --conf spark.sql.shuffle.partitions=4 \
          --conf spark.app.name=Streaming_Kafka_to_PostgreSQL \
          /jobs/streaming/streaming_to_postgres.py
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
        
        # === DISCORD (usando variáveis de ambiente) ===
        DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
        
        message = f"""
🚨 *ALERTA: Streaming Reiniciado*

O job de streaming foi reiniciado automaticamente.

Status: {restart_result.get('status')}
Return Code: {restart_result.get('return_code')}
Horário: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

_Verifique os logs para mais detalhes._
        """
        
        # Envia pro Discord (se configurado)
        if DISCORD_WEBHOOK_URL:
            try:
                embed = {
                    "title": "🚨 ALERTA: Streaming Reiniciado",
                    "description": "O job de streaming foi reiniciado automaticamente.",
                    "color": 15158332,  # Vermelho
                    "fields": [
                        {"name": "Status", "value": str(restart_result.get('status')), "inline": True},
                        {"name": "Return Code", "value": str(restart_result.get('return_code')), "inline": True},
                        {"name": "Horário", "value": datetime.now().strftime('%Y-%m-%d %H:%M:%S'), "inline": False}
                    ],
                    "footer": {"text": "Verifique os logs para mais detalhes."}
                }
                response = requests.post(
                    DISCORD_WEBHOOK_URL,
                    json={"username": "🤖 Streaming Health Check", "embeds": [embed]},
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
                print(f"✅ Alerta enviado para Discord! Response: {response.status_code}")
            except Exception as e:
                print(f"❌ Erro ao enviar Discord: {e}")
        else:
            print("⚠️ Discord não configurado. Configure a variável DISCORD_WEBHOOK_URL")
        
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
            print("⚠️ Telegram não configurado. Configure as variáveis TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID")
        
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