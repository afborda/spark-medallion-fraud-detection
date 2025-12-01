#!/usr/bin/env python3
"""
🚀 Gerador de Dados RÁPIDO para Detecção de Fraudes (20M+)
==========================================================

Versão otimizada com:
- Barra de progresso em tempo real
- Estimativa de tempo restante
- Multiprocessing para velocidade
- Escrita em chunks para memória eficiente

Uso:
    python generate_fraud_data_fast.py --transactions 20000000
"""

import json
import random
import hashlib
import argparse
import time
import sys
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Tuple
from multiprocessing import Pool, cpu_count
import math

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

DEFAULT_NUM_CUSTOMERS = 50000       # Pool maior para 20M
DEFAULT_NUM_TRANSACTIONS = 20000000  # 20 milhões
FRAUD_INJECTION_RATE = 0.05         # 5% fraudes
CHUNK_SIZE = 100000                  # Gerar em chunks de 100k
OUTPUT_DIR = Path("data/raw")

# =============================================================================
# DADOS DE REFERÊNCIA BRASILEIROS
# =============================================================================

ESTADOS_BRASIL = {
    "SP": {"lat": -23.55, "lon": -46.63, "cidades": ["São Paulo", "Campinas", "Santos", "Ribeirão Preto", "Sorocaba", "Guarulhos"]},
    "RJ": {"lat": -22.91, "lon": -43.17, "cidades": ["Rio de Janeiro", "Niterói", "Petrópolis", "Volta Redonda", "Duque de Caxias"]},
    "MG": {"lat": -19.92, "lon": -43.94, "cidades": ["Belo Horizonte", "Uberlândia", "Juiz de Fora", "Contagem", "Betim"]},
    "RS": {"lat": -30.03, "lon": -51.23, "cidades": ["Porto Alegre", "Caxias do Sul", "Pelotas", "Canoas", "Santa Maria"]},
    "PR": {"lat": -25.43, "lon": -49.27, "cidades": ["Curitiba", "Londrina", "Maringá", "Ponta Grossa", "Cascavel"]},
    "SC": {"lat": -27.59, "lon": -48.55, "cidades": ["Florianópolis", "Joinville", "Blumenau", "Chapecó", "Itajaí"]},
    "BA": {"lat": -12.97, "lon": -38.50, "cidades": ["Salvador", "Feira de Santana", "Vitória da Conquista", "Camaçari"]},
    "PE": {"lat": -8.05, "lon": -34.88, "cidades": ["Recife", "Olinda", "Jaboatão", "Caruaru", "Petrolina"]},
    "CE": {"lat": -3.72, "lon": -38.52, "cidades": ["Fortaleza", "Caucaia", "Juazeiro do Norte", "Maracanaú"]},
    "PA": {"lat": -1.46, "lon": -48.50, "cidades": ["Belém", "Ananindeua", "Santarém", "Marabá"]},
    "AM": {"lat": -3.10, "lon": -60.02, "cidades": ["Manaus", "Parintins", "Itacoatiara", "Manacapuru"]},
    "GO": {"lat": -16.68, "lon": -49.25, "cidades": ["Goiânia", "Aparecida de Goiânia", "Anápolis", "Rio Verde"]},
    "DF": {"lat": -15.78, "lon": -47.93, "cidades": ["Brasília", "Taguatinga", "Ceilândia", "Samambaia"]},
}

CATEGORIAS_NORMAL = ["grocery", "restaurant", "gas_station", "pharmacy", "clothing", "entertainment", "streaming", "utilities"]
CATEGORIAS_RISCO = ["electronics", "airline_ticket", "jewelry", "luxury_goods"]

MERCHANTS = {
    "grocery": ["Carrefour", "Pão de Açúcar", "Extra", "Atacadão", "Assaí"],
    "restaurant": ["iFood", "Rappi", "Outback", "McDonalds", "Burger King", "Starbucks"],
    "gas_station": ["Shell", "Ipiranga", "BR", "Ale"],
    "pharmacy": ["Drogasil", "Droga Raia", "Pacheco", "Pague Menos"],
    "clothing": ["Renner", "C&A", "Riachuelo", "Zara", "Marisa"],
    "entertainment": ["Cinema", "Teatro", "Show", "Parque"],
    "streaming": ["Netflix", "Spotify", "Amazon Prime", "Disney+", "HBO Max"],
    "utilities": ["Enel", "Sabesp", "Comgás", "Claro", "Vivo", "Tim"],
    "electronics": ["Magazine Luiza", "Americanas", "Casas Bahia", "Amazon", "Mercado Livre", "Kabum"],
    "airline_ticket": ["Gol", "Latam", "Azul", "Decolar", "123Milhas"],
    "jewelry": ["Vivara", "Monte Carlo", "HStern", "Pandora", "Swarovski"],
    "luxury_goods": ["Louis Vuitton", "Gucci", "Prada", "Chanel", "Dior"],
}

CARD_BRANDS = ["Visa", "Mastercard", "Elo", "Amex", "Hipercard"]
PAYMENT_METHODS = ["credit_card", "debit_card", "pix"]
DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

ESTADOS_LIST = list(ESTADOS_BRASIL.keys())
ESTADOS_DISTANTES = [("SP", "AM"), ("RS", "PA"), ("RJ", "AM"), ("BA", "RS"), ("SC", "CE"), ("PR", "PA")]

# =============================================================================
# BARRA DE PROGRESSO
# =============================================================================

class ProgressBar:
    def __init__(self, total: int, prefix: str = ""):
        self.total = total
        self.prefix = prefix
        self.start_time = time.time()
        self.current = 0
        self.last_print = 0
        
    def update(self, current: int):
        self.current = current
        
        # Só atualiza a cada 0.5 segundo para não sobrecarregar o terminal
        now = time.time()
        if now - self.last_print < 0.5 and current < self.total:
            return
        self.last_print = now
        
        elapsed = now - self.start_time
        percent = current / self.total * 100
        
        if current > 0:
            rate = current / elapsed
            remaining = (self.total - current) / rate if rate > 0 else 0
            eta_str = self._format_time(remaining)
            rate_str = f"{rate:,.0f}/s"
        else:
            eta_str = "calculando..."
            rate_str = "-"
        
        # Barra visual
        bar_length = 40
        filled = int(bar_length * current / self.total)
        bar = "█" * filled + "░" * (bar_length - filled)
        
        # Formata números
        current_str = f"{current:,}"
        total_str = f"{self.total:,}"
        
        sys.stdout.write(f"\r{self.prefix} [{bar}] {percent:5.1f}% | {current_str}/{total_str} | {rate_str} | ETA: {eta_str}   ")
        sys.stdout.flush()
        
        if current >= self.total:
            elapsed_str = self._format_time(elapsed)
            print(f"\n   ✅ Concluído em {elapsed_str}")
    
    def _format_time(self, seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            m, s = divmod(int(seconds), 60)
            return f"{m}m {s}s"
        else:
            h, rem = divmod(int(seconds), 3600)
            m, s = divmod(rem, 60)
            return f"{h}h {m}m"

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def add_noise(lat: float, lon: float, radius_km: float = 30) -> Tuple[float, float]:
    noise = radius_km / 111
    return (lat + random.uniform(-noise, noise), lon + random.uniform(-noise, noise))

# =============================================================================
# GERAÇÃO DE CLIENTES (PRÉ-COMPUTADO)
# =============================================================================

def generate_customers(num_customers: int) -> List[Dict]:
    """Gera pool de clientes."""
    print(f"   Gerando {num_customers:,} clientes...")
    customers = []
    
    progress = ProgressBar(num_customers, "   Clientes")
    
    for i in range(num_customers):
        home_state = random.choice(ESTADOS_LIST)
        estado = ESTADOS_BRASIL[home_state]
        home_lat, home_lon = add_noise(estado["lat"], estado["lon"])
        
        customer = {
            "id": f"CUST_{i:06d}",
            "state": home_state,
            "city": random.choice(estado["cidades"]),
            "lat": round(home_lat, 6),
            "lon": round(home_lon, 6),
            "traveler": random.random() < 0.15,
            "cards": [
                {"hash": hashlib.md5(f"CUST_{i:06d}-{j}".encode()).hexdigest()[:16], "brand": random.choice(CARD_BRANDS)}
                for j in range(random.randint(1, 3))
            ]
        }
        customers.append(customer)
        
        if i % 5000 == 0:
            progress.update(i)
    
    progress.update(num_customers)
    return customers

# =============================================================================
# GERAÇÃO DE TRANSAÇÕES
# =============================================================================

def generate_transaction(customer: Dict, timestamp: datetime, tx_id: int, is_fraud: bool = False, fraud_type: str = None) -> Dict:
    """Gera uma transação."""
    
    is_online = random.random() < 0.35
    
    # Categoria
    if is_fraud and fraud_type in ["online_high_value", "installments"]:
        category = random.choice(CATEGORIAS_RISCO)
    elif random.random() < 0.10:
        category = random.choice(CATEGORIAS_RISCO)
    else:
        category = random.choice(CATEGORIAS_NORMAL)
    
    # Local da compra
    if is_online or random.random() > 0.15 or not customer["traveler"]:
        purchase_state = customer["state"]
        estado = ESTADOS_BRASIL[purchase_state]
        p_lat, p_lon = add_noise(customer["lat"], customer["lon"], 10)
    else:
        purchase_state = random.choice([s for s in ESTADOS_LIST if s != customer["state"]])
        estado = ESTADOS_BRASIL[purchase_state]
        p_lat, p_lon = add_noise(estado["lat"], estado["lon"])
    
    # Valor
    if is_fraud:
        amount = round(random.uniform(800, 5000), 2)
    elif category in CATEGORIAS_RISCO:
        amount = round(random.uniform(200, 3000), 2)
    else:
        amount = round(min(abs(random.gauss(150, 200)), 2000), 2)
    
    # Parcelas
    if is_fraud and fraud_type == "installments":
        installments = random.choice([10, 11, 12])
    elif amount > 500 and random.random() < 0.40:
        installments = random.choice([2, 3, 4, 6, 10, 12])
    else:
        installments = 1
    
    card = random.choice(customer["cards"])
    hour = timestamp.hour + random.uniform(0, 1)
    
    # Forçar madrugada para fraude online
    if is_fraud and fraud_type == "online_high_value":
        hour = random.uniform(1, 5)
        is_online = True
    
    d_lat, d_lon = add_noise(p_lat, p_lon, 3)
    
    return {
        "transaction_id": f"TX_{tx_id:010d}",
        "customer_id": customer["id"],
        "card_hash": card["hash"],
        "amount": amount,
        "merchant": random.choice(MERCHANTS.get(category, ["Loja"])),
        "category": category,
        "transaction_hour": round(hour, 2),
        "day_of_week": DAYS_OF_WEEK[timestamp.weekday()],
        "customer_home_state": customer["state"],
        "purchase_state": purchase_state,
        "purchase_city": random.choice(estado["cidades"]),
        "purchase_latitude": round(p_lat, 6),
        "purchase_longitude": round(p_lon, 6),
        "device_latitude": round(d_lat, 6),
        "device_longitude": round(d_lon, 6),
        "device_id": hashlib.md5(str(random.random()).encode()).hexdigest()[:12],
        "ip_address": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
        "ip_country": "Brazil" if random.random() > 0.02 else random.choice(["USA", "Russia", "China", "Nigeria"]),
        "payment_method": "credit_card" if installments > 1 else random.choice(PAYMENT_METHODS),
        "card_brand": card["brand"],
        "installments": installments,
        "is_online": is_online,
        "is_fraud": is_fraud,
        "fraud_type": fraud_type,
        "timestamp": int(timestamp.timestamp()),
    }

def generate_fraud_cloning(customer: Dict, base_ts: datetime, tx_id: int) -> List[Dict]:
    """Gera fraude de clonagem: 2 transações em estados distantes em minutos."""
    state1, state2 = random.choice(ESTADOS_DISTANTES)
    
    card = random.choice(customer["cards"])
    e1, e2 = ESTADOS_BRASIL[state1], ESTADOS_BRASIL[state2]
    
    tx1 = {
        "transaction_id": f"TX_{tx_id:010d}",
        "customer_id": customer["id"],
        "card_hash": card["hash"],
        "amount": round(random.uniform(500, 2500), 2),
        "merchant": random.choice(MERCHANTS["electronics"]),
        "category": "electronics",
        "transaction_hour": round(base_ts.hour + random.uniform(0, 0.3), 2),
        "day_of_week": DAYS_OF_WEEK[base_ts.weekday()],
        "customer_home_state": customer["state"],
        "purchase_state": state1,
        "purchase_city": random.choice(e1["cidades"]),
        "purchase_latitude": round(e1["lat"] + random.uniform(-0.5, 0.5), 6),
        "purchase_longitude": round(e1["lon"] + random.uniform(-0.5, 0.5), 6),
        "device_latitude": round(e1["lat"] + random.uniform(-0.02, 0.02), 6),
        "device_longitude": round(e1["lon"] + random.uniform(-0.02, 0.02), 6),
        "device_id": hashlib.md5(str(random.random()).encode()).hexdigest()[:12],
        "ip_address": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
        "ip_country": "Brazil",
        "payment_method": "credit_card",
        "card_brand": card["brand"],
        "installments": random.choice([1, 3, 6]),
        "is_online": False,
        "is_fraud": True,
        "fraud_type": "card_cloning",
        "timestamp": int(base_ts.timestamp()),
    }
    
    ts2 = base_ts + timedelta(minutes=random.randint(5, 30))
    
    tx2 = {
        "transaction_id": f"TX_{tx_id+1:010d}",
        "customer_id": customer["id"],
        "card_hash": card["hash"],
        "amount": round(random.uniform(800, 4000), 2),
        "merchant": random.choice(MERCHANTS["electronics"]),
        "category": "electronics",
        "transaction_hour": round(ts2.hour + ts2.minute/60, 2),
        "day_of_week": DAYS_OF_WEEK[ts2.weekday()],
        "customer_home_state": customer["state"],
        "purchase_state": state2,
        "purchase_city": random.choice(e2["cidades"]),
        "purchase_latitude": round(e2["lat"] + random.uniform(-0.5, 0.5), 6),
        "purchase_longitude": round(e2["lon"] + random.uniform(-0.5, 0.5), 6),
        "device_latitude": round(e2["lat"] + random.uniform(-0.02, 0.02), 6),
        "device_longitude": round(e2["lon"] + random.uniform(-0.02, 0.02), 6),
        "device_id": hashlib.md5(str(random.random()).encode()).hexdigest()[:12],
        "ip_address": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
        "ip_country": "Brazil",
        "payment_method": "credit_card",
        "card_brand": card["brand"],
        "installments": random.choice([1, 6, 10]),
        "is_online": False,
        "is_fraud": True,
        "fraud_type": "card_cloning",
        "timestamp": int(ts2.timestamp()),
    }
    
    return [tx1, tx2]

# =============================================================================
# GERAÇÃO PRINCIPAL
# =============================================================================

def generate_all_transactions(customers: List[Dict], num_transactions: int, fraud_rate: float) -> None:
    """Gera transações e salva em arquivo incrementalmente."""
    
    print(f"\n   Gerando {num_transactions:,} transações...")
    
    num_frauds = int(num_transactions * fraud_rate)
    num_normal = num_transactions - num_frauds
    
    print(f"   - Normais: {num_normal:,} ({100-fraud_rate*100:.1f}%)")
    print(f"   - Fraudes: {num_frauds:,} ({fraud_rate*100:.1f}%)")
    
    # Período: últimos 30 dias
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    total_seconds = int((end_date - start_date).total_seconds())
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / "transactions.json"
    
    progress = ProgressBar(num_transactions, "   Transações")
    
    tx_id = 0
    fraud_count = 0
    fraud_types_count = {"card_cloning": 0, "online_high_value": 0, "installments": 0}
    
    with open(filepath, "w", encoding="utf-8") as f:
        while tx_id < num_transactions:
            customer = random.choice(customers)
            timestamp = start_date + timedelta(seconds=random.randint(0, total_seconds))
            
            # Decide se gera fraude
            should_fraud = fraud_count < num_frauds and random.random() < (fraud_rate * 1.5)
            
            if should_fraud:
                fraud_type = random.choice(["cloning", "online_high_value", "installments"])
                
                if fraud_type == "cloning":
                    txs = generate_fraud_cloning(customer, timestamp, tx_id)
                    for tx in txs:
                        f.write(json.dumps(tx, ensure_ascii=False) + "\n")
                    tx_id += len(txs)
                    fraud_count += len(txs)
                    fraud_types_count["card_cloning"] += len(txs)
                else:
                    tx = generate_transaction(customer, timestamp, tx_id, is_fraud=True, fraud_type=fraud_type)
                    f.write(json.dumps(tx, ensure_ascii=False) + "\n")
                    tx_id += 1
                    fraud_count += 1
                    fraud_types_count[fraud_type] += 1
            else:
                tx = generate_transaction(customer, timestamp, tx_id)
                f.write(json.dumps(tx, ensure_ascii=False) + "\n")
                tx_id += 1
            
            if tx_id % 10000 == 0:
                progress.update(tx_id)
    
    progress.update(tx_id)
    
    return tx_id, fraud_count, fraud_types_count

# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description='🚀 Gerador Rápido de Dados de Fraude')
    parser.add_argument('--customers', '-c', type=int, default=DEFAULT_NUM_CUSTOMERS)
    parser.add_argument('--transactions', '-t', type=int, default=DEFAULT_NUM_TRANSACTIONS)
    parser.add_argument('--fraud-rate', '-f', type=float, default=FRAUD_INJECTION_RATE)
    args = parser.parse_args()
    
    print()
    print("=" * 70)
    print("🚀 GERADOR RÁPIDO DE DADOS PARA DETECÇÃO DE FRAUDES")
    print("=" * 70)
    print(f"\n📊 Configuração:")
    print(f"   Clientes:    {args.customers:>15,}")
    print(f"   Transações:  {args.transactions:>15,}")
    print(f"   Taxa fraude: {args.fraud_rate*100:>14.1f}%")
    
    start_total = time.time()
    
    # Gerar clientes
    print(f"\n[1/2] Gerando clientes...")
    customers = generate_customers(args.customers)
    
    # Salvar clientes
    customers_file = OUTPUT_DIR / "customers.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(customers_file, "w", encoding="utf-8") as f:
        for c in customers:
            # Formato simplificado para arquivo
            customer_record = {
                "customer_id": c["id"],
                "home_state": c["state"],
                "home_city": c["city"],
                "home_latitude": c["lat"],
                "home_longitude": c["lon"],
                "is_frequent_traveler": c["traveler"],
                "cards": c["cards"]
            }
            f.write(json.dumps(customer_record, ensure_ascii=False) + "\n")
    print(f"   ✅ Salvo em {customers_file}")
    
    # Gerar transações
    print(f"\n[2/2] Gerando transações...")
    total_tx, fraud_count, fraud_types = generate_all_transactions(customers, args.transactions, args.fraud_rate)
    
    elapsed_total = time.time() - start_total
    
    # Estatísticas finais
    print("\n" + "=" * 70)
    print("🎉 GERAÇÃO COMPLETA!")
    print("=" * 70)
    print(f"\n📈 Estatísticas:")
    print(f"   Total de clientes:    {len(customers):>15,}")
    print(f"   Total de transações:  {total_tx:>15,}")
    print(f"   Total de fraudes:     {fraud_count:>15,} ({fraud_count/total_tx*100:.2f}%)")
    print(f"\n🚨 Tipos de fraude:")
    for ft, count in sorted(fraud_types.items(), key=lambda x: -x[1]):
        print(f"   - {ft:20s}: {count:>10,}")
    
    print(f"\n⏱️  Tempo total: {elapsed_total/60:.1f} minutos ({total_tx/elapsed_total:,.0f} tx/seg)")
    print(f"\n📁 Arquivos salvos em: {OUTPUT_DIR.absolute()}")
    print(f"   - customers.json    ({os.path.getsize(customers_file)/1024/1024:.1f} MB)")
    print(f"   - transactions.json ({os.path.getsize(OUTPUT_DIR / 'transactions.json')/1024/1024:.1f} MB)")

if __name__ == "__main__":
    main()
