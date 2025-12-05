"""
🏅 MEDALLION PIPELINE - Orquestrado pelo Airflow
Pipeline completo: Bronze → Silver → Gold → Postgres
"""

from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'abner',
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
    'email': ['abner.borda@gmail.com'],
    'email_on_failure': True,
}

# Comando base para executar spark-submit via docker exec
SPARK_SUBMIT = """
docker exec fraud_spark_master \
    /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    /jobs/production/{script}
"""

with DAG(
    dag_id='medallion_pipeline',
    default_args=default_args,
    description='Pipeline Medallion: Bronze → Silver → Gold → Postgres',
    start_date=datetime(2025, 12, 1),
    schedule_interval='@daily',
    catchup=False,
    tags=['medallion', 'spark', 'producao'],
) as dag:

    # ==========================================
    # TASK 1: BRONZE - Ingestão de dados brutos
    # ==========================================
    bronze = BashOperator(
        task_id='bronze_ingestion',
        bash_command=SPARK_SUBMIT.format(script='bronze_brazilian.py'),
    )

    # ==========================================
    # TASK 2: SILVER - Limpeza e transformação
    # ==========================================
    silver = BashOperator(
        task_id='silver_transformation',
        bash_command=SPARK_SUBMIT.format(script='silver_brazilian.py'),
    )

    # ==========================================
    # TASK 3: GOLD - Agregações e métricas
    # ==========================================
    gold = BashOperator(
        task_id='gold_aggregation',
        bash_command=SPARK_SUBMIT.format(script='gold_brazilian.py'),
    )

    # ==========================================
    # TASK 4: POSTGRES - Carregar para BI
    # ==========================================
    postgres = BashOperator(
        task_id='load_to_postgres',
        bash_command=SPARK_SUBMIT.format(script='load_to_postgres.py'),
    )

    # ==========================================
    # DEPENDÊNCIAS - Define a ordem de execução
    # ==========================================
    bronze >> silver >> gold >> postgres