"""
Fraud Detection - Regras de Negócio
Aplica regras para identificar transações suspeitas
"""


from pyspark.sql import SparkSession
from pyspark.sql.functions import col, when, hour, to_timestamp
from datetime import date


# caminhos

SILVER_PATH = "data/silver"
FRAUD_PATH = "data/gold/fraud_detection"
PROCESS_DATE = date.today().isoformat()

print("=" * 50)
print("🚨 FRAUD DETECTION - Regras de Negócio")
print("=" * 50)
print(f"📂 Origem: {SILVER_PATH}")
print(f"📂 Destino: {FRAUD_PATH}")
print(f"📅 Data: {PROCESS_DATE}")
print("=" * 50)



print ("🚀 Iniciando Spark Session...")
spark = SparkSession.builder \
	.appName("Fraud Detection - Business Rules") \
	.getOrCreate()

	
def apply_fraud_rules(df):
	"""
	Aplicar regras de detecção de fraude 
	regras:
	Valor alto: transçoes > R$ 1000
	horario suspeito: entre 2h e 5h
	Combinação: valor alto + horario suspeito = Alto Risco
	"""

	print("\n🚨 Aplicando regras de detecção de fraude...")

	#Converter timestamp para extrair hora
	df_wirh_hour = df.withColumn("transaction_hour", hour(to_timestamp(col("timestamp"))))

	#Regra 1: Valor alto
	df_rules = df_wirh_hour.withColumn(
		"high_value",
		when(col("amount") > 1000, True).otherwise(False)
	)

	#Regra 2 : Horário suspeito (2h - 5H)
	df_rules = df_rules.withColumn(
		"suspicious_hour",
		when((col("transaction_hour") >= 2) &
			(col("transaction_hour") <= 5), True
			).otherwise(False)
		)
	#Regra 3: Combnacão de ambas as regras
	df_rules = df_rules.withColumn(
		"risk_level",
		when((col("high_value") == True) & (col("suspicious_hour") ==True),
		"Alto Risco"
		).when((col("high_value") == True) | (col("suspicious_hour") == True),
		"Risco Médio"
		).otherwise("Baixo Risco")
	)

	return df_rules 

# 1 Ler dados do silver
print ("🚨 Carregando dados de transações do Silver Layer...")
df_transactions = spark.read.parquet(f"{SILVER_PATH}/transactions")
print(f"✅ Dados carregados. Registros: {df_transactions.count()}")

# 2 Aplicar regras de fraude
df_flagged  = apply_fraud_rules(df_transactions)

# 3 mostrar estatísticas
print("\n📊 Estatísticas de risco de fraude:")
df_flagged.groupBy("risk_level").count().show()

# 4 Mostrar  exemplo de cada nivel
print("\n🔴 Exemplos ALTO RISCO:")
df_flagged.filter(col("risk_level") == "Alto Risco") \
	.select("transaction_id", "amount", "transaction_hour", "risk_level") \
	.show(5)

print("\n🟠 Exemplos RISCO MÉDIO:")
df_flagged.filter(col("risk_level") == "Risco Médio") \
	.select("transaction_id", "amount", "transaction_hour", "risk_level") \
	.show(5)
	
# 5 Salvar resultados 

print(f"\n🚨 Salvando em {FRAUD_PATH}... ")
df_flagged.write \
	.mode("overwrite") \
	.partitionBy("risk_level") \
	.parquet(FRAUD_PATH)

print("\n ✅ Fraudes detectados com sucesso!")
print(f"   📁 Dados salvos em: {FRAUD_PATH}")

spark.stop()
print("\n🚀 Spark Session finalizada.")