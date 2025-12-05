from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta


default_args ={
	'owner': 'abner',
	'retries': 3,
	'retry_delay': timedelta(minutes=5),
	'email': ['abner.borda@gmail.com'], # Email pra notificações
	'email_on_failure': True,           # Manda email se falhar
	'email_on_retry': False,            # Não manda email em retry
	'depends_on_past': False,           # Não depende de execuções anteriores
}

def tarefa_inicio():
	print("Olá, mundo! Esta é a minha primeira DAG no Airflow.")
def tarefa_hello():
	print("Hello, World! Esta é a minha tarefa de saudação.")
def tarefa_fim():
	print("DAG concluída com sucesso! Até a próxima.")

with DAG(
	dag_id='hello_world',
	default_args=default_args,
	description='Um DAG simples de Hello World',
	start_date=datetime(2025, 12, 1),
	schedule_interval='@daily',
	catchup=False,
	tags=['exemplo', 'hello_world', 'tutorial'],

)as dag:

	task_inicio = PythonOperator(
		task_id='inicio',
		python_callable=tarefa_inicio
	)
	task_hello = PythonOperator(
		task_id='hello',
		python_callable=tarefa_hello
	)
	task_fim = PythonOperator(
		task_id='fim',
		python_callable=tarefa_fim
	)
	task_inicio >> task_hello >> task_fim




