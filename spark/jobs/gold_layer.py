"""
Gold Layer - Agregações e Métricas
Dados prontos para análise e dashboards
"""


from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum , count, avg, round as spark_round
from datetime import date 


#CAMINHOS
SILVER_PATH = "data/silver"
GOLD_PATH = "data/gold"
PROCESS_DATE = date.today().isoformat()		


print("=" * 50)
print("🥇 GOLD LAYER - Agregações e Métricas")
print("=" * 50)
print(f"📂 Origem: {SILVER_PATH}")
print(f"📂 Destino: {GOLD_PATH}")
print(f"📅 Data: {PROCESS_DATE}")
print("=" * 50)


# INICILAIZAR SPARK SESSION
print ("🚀 Iniciando Spark Session...")
spark = SparkSession.builder \
	.appName("Gold Layer - Aggregations and Metrics") \
	.getOrCreate()
print(f"✅ Spark Session iniciada. Versão: {spark.version}")	


def  create_customer_summary():
	""" Cria resumo agregado por cliente"""
	print("\n 📊 Criando: customer_summary")

	# 1 . ler transações do silver
	df = spark.read.parquet(f"{SILVER_PATH}/transactions")
	print(f"✅ Dados de transações carregados. Registros: {df.count()}")	


	# 2. agrupar por cliente e calcular metricas 
	summary = df.groupBy("customer_id").agg(
		spark_round(sum("amount"), 2).alias("total_gasto"),
		count("*").alias("qtd_transacoes"),
		spark_round(avg("amount"), 2).alias("media_gasto"),
		sum (col("is_fraud").cast("int")).alias("qtd_fraudes")
	)

	# 3. salvar no gold
	output_path = f"{GOLD_PATH}/customer_summary"
	summary.write.mode("overwrite").parquet(output_path)


	count_records = summary.count()
	print(f"✅ Resumo de clientes salvo. Registros: {count_records}")
	return count_records

def create_fraud_summary():
	"""Criar estatisticas de fraudes"""
	print("\n📊 Criando: fraud_summary")
	
	#1 Ler transações do silver
	df = spark.read.parquet(f"{SILVER_PATH}/transactions")

	#2 Calcular metricas gerais
	total_transacoes = df.count()

	#3 Filtrar só fraudes e calcular
	fraud_df = df.filter(col("is_fraud") == True)
	total_fraude = fraud_df.count()
	valor_fraudado = fraud_df.agg(spark_round(sum("amount"), 2).alias("valor_fraudado")).collect()[0][0]

	#4 Calcula porcentagem
	percentual_fraude = round((total_fraude/total_transacoes)*100,2)


	#5 Criar DataFrame com o resumo

	summary_data = [(
		total_transacoes,
		total_fraude,
		valor_fraudado,
		percentual_fraude,
	)] 

	summary_df = spark.createDataFrame(summary_data, [
		"total_transacoes",
		"total_fraude",
		"valor_fraudado",
		"percentual_fraude",
	])

	#6 Salvar no gold
	output_path = f"{GOLD_PATH}/fraud_summary"
	summary_df.write.mode("overwrite").parquet(output_path)
	print(f"   📈 Total transações: {total_transacoes}")
	print(f"   🚨 Total fraudes: {total_fraude}")
	print(f"   💰 Valor fraudado: R$ {valor_fraudado}")
	print(f"   📊 Percentual: {percentual_fraude}%")

	return 1 


if __name__ == "__main__":

	create_customer_summary()
	create_fraud_summary()

	print("\n" + "=" * 50)
	print("🎉 Gold Layer completo!")
	print("=" * 50)
	spark.stop()