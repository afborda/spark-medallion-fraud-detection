from airflow.decorators import dag, task
from datetime import datetime


@dag(
    dag_id='hello_taskflow',
    start_date=datetime(2025, 1, 1),
    schedule=None,
    catchup=False,
    tags=['exemplo', 'taskflow']
)
def meu_primeiro_taskflow():
    """DAG usando TaskFlow API - forma moderna do Airflow"""
    
    @task
    def extrair():
        """Simula extração de dados"""
        dados = {'valores': [1, 2, 3, 4, 5]}
        print(f"Extraído: {dados}")
        return dados
    
    @task
    def transformar(dados: dict):
        """Simula transformação - dobra os valores"""
        resultado = {'valores': [x * 2 for x in dados['valores']]}
        print(f"Transformado: {resultado}")
        return resultado
    
    @task
    def carregar(dados: dict):
        """Simula carga no destino"""
        soma = sum(dados['valores'])
        print(f"Carregado! Soma total: {soma}")

    # Executa o pipeline ETL
    dados_brutos = extrair()
    dados_transformados = transformar(dados_brutos)
    carregar(dados_transformados)


# Instancia o DAG
meu_primeiro_taskflow()