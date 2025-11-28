"""
Gerador de dados sintéticos para detecção de fraudes
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

# Configurações
NUM_CUSTOMERS = 100 # Número de clientes
NUM_TRANSACTIONS = 500 # Número de transações
FRAUD_PROBABILITY = 0.05 # Probabilidade de uma transação ser fraudulenta

# DIRETÓRIO DE SAÍDA
OUTPUT_DIR = Path("data/raw")

print("=== Gerador de Dados Sintéticos para Detecção de Fraudes ===")
print(f"Número de Clientes: {NUM_CUSTOMERS}")
print(f"Número de Transações: {NUM_TRANSACTIONS}")
print(f"Taxa de Fraude: {FRAUD_PROBABILITY * 100}%")

# Lista de dados fakes
FIRST_NAMES = ["Ana", "Bruno", "Carla", "Daniel", "Eduarda", "Felipe", "Gabriela", "Henrique", "Isabela", "João"]
LAST_NAMES = ["Silva", "Santos", "Oliveira", "Souza", "Pereira", "Lima", "Gomes", "Ribeiro", "Almeida", "Costa"]
CITIES = ["São Paulo", "Rio de Janeiro", "Belo Horizonte", "Curitiba", "Porto Alegre", "Salvador", "Fortaleza", "Recife", "Brasília", "Manaus"]


def generate_customers(num_customers):
	""" Gera lista de clientes fake."""
	customers = []
	for i in range(num_customers):
		customer = {
			"customer_id": str(uuid.uuid4()),
			"name": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
			"email": f"cliente{i}@email.com",
			"cpf": f"{random.randint(100,999)}.{random.randint(100,999)}.{random.randint(100,999)}-{random.randint(10,99)}",
			"city": random.choice(CITIES),
			"created_at": (datetime.now() - timedelta(days=random.randint(30, 365))).isoformat()

		}
		customers.append(customer)
	return customers

# Tipos de estabelecimentos
MERCHANTS = ["Supermercado ABC", "Posto Shell", "Farmacia Popular", "Restaurante XYZ", "Loja Online", "Shopping Center"]

def generate_transactions(customers, num_transactions, fraud_ratio):
	"""
	Gera lista de transações fake.
	"""
	transactions = []

	for i in range(num_transactions):
		# Seleciona cliente aleatório
		customer = random.choice(customers)
		# Define se é fraude
		is_fraud  = random.random() < fraud_ratio
		# Fraudes tendem a ter valores maiores
		if is_fraud:
			amount = round(random.uniform(1000, 5000), 2)
		else:
			amount = round(random.uniform(10, 500), 2)
		
		transaction = {
			"transaction_id": str(uuid.uuid4()),
			"customer_id": customer["customer_id"],
			"amount": amount,
			"merchant": random.choice(MERCHANTS),
			"timestamp": (datetime.now() - timedelta(hours=random.randint(1, 720))).isoformat(),
			"is_fraud": is_fraud
		}
		transactions.append(transaction)
	return transactions




def save_to_json(data, filename):
	"""
	Salvar dados em formato JSON Lines (um JSON por linha).
	Formato ideal para processamento distribuído com Spark.
	"""
	filepath = OUTPUT_DIR / filename
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

	with open(filepath, "w", encoding="utf-8") as f:
		for record in data:
			# Cada registro em uma linha separada
			f.write(json.dumps(record, ensure_ascii=False) + "\n")
	
	print(f"✅ Dados salvos em {filepath} ({len(data)} registros)")


# Teste: gerar 3 clientes e mostrar
if __name__ == "__main__":
    # 1. Gerar clientes
    print("\n[1/3] Gerando clientes...")
    customers = generate_customers(NUM_CUSTOMERS)
    
    # 2. Gerar transações
    print("[2/3] Gerando transações...")
    transactions = generate_transactions(customers, NUM_TRANSACTIONS, FRAUD_PROBABILITY)
    
    # 3. Salvar arquivos
    print("[3/3] Salvando arquivos...")
    save_to_json(customers, "customers.json")
    save_to_json(transactions, "transactions.json")
    
    # Resumo
    frauds = [t for t in transactions if t["is_fraud"]]
    print(f"\n🎉 Geração completa!")
    print(f"   Clientes: {len(customers)}")
    print(f"   Transações: {len(transactions)}")
    print(f"   Fraudes: {len(frauds)} ({len(frauds)/len(transactions)*100:.1f}%)")
	

