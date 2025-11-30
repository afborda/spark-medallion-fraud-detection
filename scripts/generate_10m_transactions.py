#!/usr/bin/env python3
"""
Gerador de 10 Milhões de Transações com Progresso
- Gera dados fake realistas
- Mostra progresso em %
- Salva em arquivo JSON para reutilização
- Opcionalmente envia para Kafka
"""

import json
import random
import uuid
import sys
import os
from datetime import datetime

# Configurações
TOTAL_RECORDS = 10_000_000
BATCH_SIZE = 100_000  # Salvar a cada 100k registros
OUTPUT_DIR = "/home/ubuntu/Estudos/1_projeto_bank_Fraud_detection_data_pipeline/data/generated"

# Dados para geração
MERCHANTS = [
    "Amazon", "Mercado Livre", "Magazine Luiza", "Casas Bahia", "Americanas",
    "Shopee", "AliExpress", "Carrefour", "Extra", "Pão de Açúcar",
    "iFood", "Rappi", "Uber", "99", "Netflix", "Spotify", "Disney+",
    "Steam", "PlayStation Store", "Zara", "Renner", "C&A", "Riachuelo",
    "Drogasil", "Droga Raia", "Farmácia São Paulo", "Shell", "Ipiranga", "BR"
]

CATEGORIES = [
    "Eletrônicos", "Roupas", "Supermercado", "Restaurante", "Transporte",
    "Streaming", "Games", "Farmácia", "Combustível", "Viagem", "Educação"
]

STATES = ["SP", "RJ", "MG", "RS", "PR", "SC", "BA", "PE", "CE", "GO", "DF", "PA", "AM", "MT", "MS"]

PAYMENT_METHODS = ["credit_card", "debit_card", "pix", "boleto"]
CARD_BRANDS = ["Visa", "Mastercard", "Elo", "Amex", "Hipercard"]
DAYS_OF_WEEK = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]

def generate_transaction():
    """Gera uma transação fake realista"""
    
    # Dados básicos
    customer_home_state = random.choice(STATES)
    
    # 70% das compras são no mesmo estado
    if random.random() < 0.7:
        purchase_state = customer_home_state
    else:
        purchase_state = random.choice(STATES)
    
    # Coordenadas base por estado (aproximadas)
    state_coords = {
        "SP": (-23.55, -46.63), "RJ": (-22.90, -43.17), "MG": (-19.92, -43.94),
        "RS": (-30.03, -51.23), "PR": (-25.43, -49.27), "SC": (-27.59, -48.55),
        "BA": (-12.97, -38.50), "PE": (-8.05, -34.88), "CE": (-3.72, -38.52),
        "GO": (-16.68, -49.25), "DF": (-15.78, -47.93), "PA": (-1.46, -48.50),
        "AM": (-3.10, -60.02), "MT": (-15.60, -56.10), "MS": (-20.47, -54.62)
    }
    
    home_lat, home_lon = state_coords.get(customer_home_state, (-23.55, -46.63))
    purchase_lat, purchase_lon = state_coords.get(purchase_state, (-23.55, -46.63))
    
    # Adicionar variação nas coordenadas
    purchase_lat += random.uniform(-2, 2)
    purchase_lon += random.uniform(-2, 2)
    
    # Device pode estar em local diferente (indicador de fraude)
    if random.random() < 0.15:  # 15% com GPS suspeito
        device_lat = purchase_lat + random.uniform(-10, 10)
        device_lon = purchase_lon + random.uniform(-10, 10)
    else:
        device_lat = purchase_lat + random.uniform(-0.5, 0.5)
        device_lon = purchase_lon + random.uniform(-0.5, 0.5)
    
    # Valor da transação (distribuição realista)
    if random.random() < 0.6:  # 60% valores baixos
        amount = round(random.uniform(10, 200), 2)
    elif random.random() < 0.9:  # 30% valores médios
        amount = round(random.uniform(200, 1000), 2)
    else:  # 10% valores altos
        amount = round(random.uniform(1000, 5000), 2)
    
    # Média histórica do cliente
    avg_amount = round(random.uniform(100, 500), 2)
    
    # Hora da transação (mais transações em horário comercial)
    if random.random() < 0.7:
        transaction_hour = random.randint(8, 22)
    else:
        transaction_hour = random.randint(0, 7)  # Madrugada (suspeito)
    
    # Transações nas últimas 24h
    if random.random() < 0.85:
        transactions_last_24h = random.randint(0, 5)
    else:
        transactions_last_24h = random.randint(6, 20)  # Alta velocidade (suspeito)
    
    # Flag de fraude real (para validação do modelo)
    # Regra simplificada: combinação de fatores suspeitos
    fraud_indicators = 0
    if customer_home_state != purchase_state:
        fraud_indicators += 1
    if transaction_hour < 6:
        fraud_indicators += 1
    if amount > avg_amount * 3:
        fraud_indicators += 1
    if transactions_last_24h > 5:
        fraud_indicators += 1
    if abs(device_lat - purchase_lat) > 5 or abs(device_lon - purchase_lon) > 5:
        fraud_indicators += 2
    
    is_fraud = fraud_indicators >= 3 or (fraud_indicators >= 2 and random.random() < 0.3)
    
    return {
        "transaction_id": str(uuid.uuid4()),
        "customer_id": str(uuid.uuid4()),
        "amount": amount,
        "merchant": random.choice(MERCHANTS),
        "category": random.choice(CATEGORIES),
        "transaction_hour": transaction_hour,
        "day_of_week": random.choice(DAYS_OF_WEEK),
        "customer_home_state": customer_home_state,
        "purchase_state": purchase_state,
        "purchase_city": f"Cidade_{random.randint(1, 100)}",
        "purchase_latitude": round(purchase_lat, 6),
        "purchase_longitude": round(purchase_lon, 6),
        "device_latitude": round(device_lat, 6),
        "device_longitude": round(device_lon, 6),
        "device_id": str(uuid.uuid4())[:8],
        "ip_address": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
        "payment_method": random.choice(PAYMENT_METHODS),
        "card_brand": random.choice(CARD_BRANDS),
        "installments": random.choice([1, 1, 1, 2, 3, 6, 12]),
        "had_travel_purchase_last_12m": random.random() < 0.3,
        "is_first_purchase_in_state": random.random() < 0.1,
        "transactions_last_24h": transactions_last_24h,
        "avg_transaction_amount_30d": avg_amount,
        "is_international": random.random() < 0.05,
        "is_online": random.random() < 0.6,
        "is_fraud": is_fraud,
        "timestamp": int(datetime.now().timestamp() * 1000)
    }


def main():
    print("=" * 60)
    print("🚀 GERADOR DE 10 MILHÕES DE TRANSAÇÕES")
    print("=" * 60)
    print(f"📁 Salvando em: {OUTPUT_DIR}")
    print(f"📊 Total: {TOTAL_RECORDS:,} registros")
    print(f"📦 Batch size: {BATCH_SIZE:,} registros por arquivo")
    print("=" * 60)
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    start_time = datetime.now()
    batch_num = 0
    current_batch = []
    
    for i in range(1, TOTAL_RECORDS + 1):
        transaction = generate_transaction()
        current_batch.append(transaction)
        
        # Salvar batch
        if len(current_batch) >= BATCH_SIZE:
            batch_num += 1
            filename = f"{OUTPUT_DIR}/transactions_batch_{batch_num:04d}.json"
            
            with open(filename, 'w') as f:
                for tx in current_batch:
                    f.write(json.dumps(tx) + '\n')
            
            current_batch = []
            
            # Calcular progresso
            progress = (i / TOTAL_RECORDS) * 100
            elapsed = (datetime.now() - start_time).total_seconds()
            rate = i / elapsed if elapsed > 0 else 0
            eta_seconds = (TOTAL_RECORDS - i) / rate if rate > 0 else 0
            eta_minutes = eta_seconds / 60
            
            print(f"\r[{'█' * int(progress // 2)}{' ' * (50 - int(progress // 2))}] "
                  f"{progress:6.2f}% | {i:,}/{TOTAL_RECORDS:,} | "
                  f"{rate:,.0f}/s | ETA: {eta_minutes:.1f}min", end='', flush=True)
    
    # Salvar último batch se houver
    if current_batch:
        batch_num += 1
        filename = f"{OUTPUT_DIR}/transactions_batch_{batch_num:04d}.json"
        with open(filename, 'w') as f:
            for tx in current_batch:
                f.write(json.dumps(tx) + '\n')
    
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print("\n" + "=" * 60)
    print(f"✅ CONCLUÍDO!")
    print(f"📁 {batch_num} arquivos gerados")
    print(f"⏱️  Tempo total: {elapsed/60:.1f} minutos")
    print(f"📊 Taxa média: {TOTAL_RECORDS/elapsed:,.0f} registros/segundo")
    print("=" * 60)
    
    # Listar arquivos gerados
    files = os.listdir(OUTPUT_DIR)
    total_size = sum(os.path.getsize(f"{OUTPUT_DIR}/{f}") for f in files if f.endswith('.json'))
    print(f"💾 Tamanho total: {total_size / (1024**3):.2f} GB")


if __name__ == "__main__":
    main()
