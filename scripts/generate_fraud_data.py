"""
🎯 Gerador de Dados Avançado para Detecção de Fraudes
=====================================================

Este gerador cria dados sintéticos REALISTAS que permitem testar
TODAS as regras de fraude implementadas no pipeline.

DIFERENÇAS DO GERADOR ANTIGO:
1. Pool fixo de clientes (não UUID por transação)
2. Múltiplas transações por cliente (histórico)
3. Timestamps sequenciais realistas
4. Cenários de fraude injetados (~5%)
5. Todos os campos necessários para as regras

REGRAS SUPORTADAS:
- Regra 1: Clonagem de Cartão (mesmo cliente, locais distantes, pouco tempo)
- Regra 2: Velocidade Impossível (> 900 km/h entre compras)
- Regra 7: Categoria Suspeita (electronics, airline_ticket)
- Regra 9: Online Alto Valor (is_online + amount > 1000)
- Regra 10: Muitas Parcelas (installments >= 10 + amount > 500)
- E mais flags: cross_state, night_transaction, high_velocity, etc.

Uso:
    python generate_fraud_data.py --transactions 1000000 --customers 10000
"""

import json
import random
import hashlib
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import math

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

DEFAULT_NUM_CUSTOMERS = 10000      # Pool de clientes
DEFAULT_NUM_TRANSACTIONS = 1000000  # 1 milhão de transações
FRAUD_INJECTION_RATE = 0.05        # 5% de cenários de fraude injetados

OUTPUT_DIR = Path("data/raw")

# =============================================================================
# DADOS DE REFERÊNCIA BRASILEIROS
# =============================================================================

# Estados com coordenadas aproximadas do centro
ESTADOS_BRASIL = {
    "SP": {"nome": "São Paulo", "lat": -23.55, "lon": -46.63, "cidades": ["São Paulo", "Campinas", "Santos", "Ribeirão Preto", "Sorocaba"]},
    "RJ": {"nome": "Rio de Janeiro", "lat": -22.91, "lon": -43.17, "cidades": ["Rio de Janeiro", "Niterói", "Petrópolis", "Volta Redonda"]},
    "MG": {"nome": "Minas Gerais", "lat": -19.92, "lon": -43.94, "cidades": ["Belo Horizonte", "Uberlândia", "Juiz de Fora", "Contagem"]},
    "RS": {"nome": "Rio Grande do Sul", "lat": -30.03, "lon": -51.23, "cidades": ["Porto Alegre", "Caxias do Sul", "Pelotas", "Canoas"]},
    "PR": {"nome": "Paraná", "lat": -25.43, "lon": -49.27, "cidades": ["Curitiba", "Londrina", "Maringá", "Ponta Grossa"]},
    "SC": {"nome": "Santa Catarina", "lat": -27.59, "lon": -48.55, "cidades": ["Florianópolis", "Joinville", "Blumenau", "Chapecó"]},
    "BA": {"nome": "Bahia", "lat": -12.97, "lon": -38.50, "cidades": ["Salvador", "Feira de Santana", "Vitória da Conquista"]},
    "PE": {"nome": "Pernambuco", "lat": -8.05, "lon": -34.88, "cidades": ["Recife", "Olinda", "Jaboatão", "Caruaru"]},
    "CE": {"nome": "Ceará", "lat": -3.72, "lon": -38.52, "cidades": ["Fortaleza", "Caucaia", "Juazeiro do Norte"]},
    "PA": {"nome": "Pará", "lat": -1.46, "lon": -48.50, "cidades": ["Belém", "Ananindeua", "Santarém"]},
    "AM": {"nome": "Amazonas", "lat": -3.10, "lon": -60.02, "cidades": ["Manaus", "Parintins", "Itacoatiara"]},
    "GO": {"nome": "Goiás", "lat": -16.68, "lon": -49.25, "cidades": ["Goiânia", "Aparecida de Goiânia", "Anápolis"]},
    "DF": {"nome": "Distrito Federal", "lat": -15.78, "lon": -47.93, "cidades": ["Brasília", "Taguatinga", "Ceilândia"]},
    "MT": {"nome": "Mato Grosso", "lat": -15.60, "lon": -56.10, "cidades": ["Cuiabá", "Várzea Grande", "Rondonópolis"]},
    "MS": {"nome": "Mato Grosso do Sul", "lat": -20.44, "lon": -54.65, "cidades": ["Campo Grande", "Dourados", "Três Lagoas"]},
}

# Categorias de compra (algumas são de risco)
CATEGORIAS = {
    "normal": ["grocery", "restaurant", "gas_station", "pharmacy", "clothing", "entertainment", "health", "education", "utilities"],
    "risco": ["electronics", "airline_ticket", "jewelry", "luxury_goods"],  # Regra 7
}

# Merchants por categoria
MERCHANTS = {
    "grocery": ["Carrefour", "Pão de Açúcar", "Extra", "Atacadão", "Assaí"],
    "restaurant": ["iFood", "Rappi", "Outback", "McDonalds", "Burger King"],
    "gas_station": ["Shell", "Ipiranga", "BR", "Ale", "Petrobras"],
    "pharmacy": ["Drogasil", "Droga Raia", "Pacheco", "Pague Menos"],
    "clothing": ["Renner", "C&A", "Riachuelo", "Marisa", "Zara"],
    "entertainment": ["Netflix", "Spotify", "Amazon Prime", "Disney+", "HBO Max"],
    "health": ["Unimed", "Amil", "Bradesco Saúde", "SulAmérica"],
    "education": ["Udemy", "Coursera", "Alura", "Descomplica"],
    "utilities": ["Enel", "Sabesp", "Comgás", "Claro", "Vivo"],
    "electronics": ["Magazine Luiza", "Americanas", "Casas Bahia", "Amazon", "Mercado Livre"],  # Risco
    "airline_ticket": ["Gol", "Latam", "Azul", "Decolar", "123Milhas"],  # Risco
    "jewelry": ["Vivara", "Monte Carlo", "HStern", "Pandora"],  # Risco
    "luxury_goods": ["Louis Vuitton", "Gucci", "Prada", "Chanel"],  # Risco
}

CARD_BRANDS = ["Visa", "Mastercard", "Elo", "American Express", "Hipercard"]
PAYMENT_METHODS = ["credit_card", "debit_card", "pix", "boleto"]
DAYS_OF_WEEK = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

FIRST_NAMES = ["Ana", "Bruno", "Carla", "Daniel", "Eduarda", "Felipe", "Gabriela", "Henrique", 
               "Isabela", "João", "Karen", "Lucas", "Maria", "Nicolas", "Olivia", "Pedro",
               "Rafaela", "Samuel", "Tatiana", "Victor", "Yasmin", "Zeca"]
LAST_NAMES = ["Silva", "Santos", "Oliveira", "Souza", "Pereira", "Lima", "Gomes", "Ribeiro", 
              "Almeida", "Costa", "Ferreira", "Rodrigues", "Martins", "Nascimento", "Araújo"]

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def generate_cpf() -> str:
    """Gera CPF fake formatado."""
    return f"{random.randint(100,999)}.{random.randint(100,999)}.{random.randint(100,999)}-{random.randint(10,99)}"

def generate_card_hash(customer_id: str, card_index: int = 0) -> str:
    """Gera hash do cartão (simula número do cartão sem expor)."""
    data = f"{customer_id}-card-{card_index}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]

def generate_device_id() -> str:
    """Gera ID único do dispositivo."""
    return hashlib.md5(str(random.random()).encode()).hexdigest()[:12]

def calculate_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calcula distância aproximada em km entre dois pontos."""
    # Fórmula simplificada (1 grau ≈ 111 km)
    return math.sqrt((lat2 - lat1)**2 + (lon2 - lon1)**2) * 111

def add_noise_to_coords(lat: float, lon: float, radius_km: float = 50) -> tuple:
    """Adiciona variação às coordenadas (simula diferentes locais na cidade)."""
    noise = radius_km / 111  # Converte km para graus
    return (
        lat + random.uniform(-noise, noise),
        lon + random.uniform(-noise, noise)
    )

# =============================================================================
# GERAÇÃO DE CLIENTES
# =============================================================================

def generate_customers(num_customers: int) -> List[Dict[str, Any]]:
    """
    Gera pool de clientes com dados realistas.
    Cada cliente tem um estado "home" e histórico de viagem.
    """
    print(f"   Gerando {num_customers:,} clientes...")
    customers = []
    estados_list = list(ESTADOS_BRASIL.keys())
    
    for i in range(num_customers):
        # Estado de residência
        home_state = random.choice(estados_list)
        estado_data = ESTADOS_BRASIL[home_state]
        home_city = random.choice(estado_data["cidades"])
        
        # Coordenadas do cliente (aproximadas)
        home_lat, home_lon = add_noise_to_coords(estado_data["lat"], estado_data["lon"], radius_km=30)
        
        # Alguns clientes viajam frequentemente
        is_frequent_traveler = random.random() < 0.15  # 15% viajam muito
        
        customer = {
            "customer_id": f"CUST_{i:06d}",  # ID fixo, não UUID!
            "name": f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}",
            "email": f"cliente{i}@email.com",
            "cpf": generate_cpf(),
            "home_state": home_state,
            "home_city": home_city,
            "home_latitude": round(home_lat, 6),
            "home_longitude": round(home_lon, 6),
            "is_frequent_traveler": is_frequent_traveler,
            "risk_score": random.randint(1, 100),  # Score de risco do cliente
            "account_age_days": random.randint(30, 1825),  # 1 mês a 5 anos
            "created_at": (datetime.now() - timedelta(days=random.randint(30, 1825))).isoformat(),
            # Cartões do cliente (1-3 cartões)
            "cards": [
                {
                    "card_hash": generate_card_hash(f"CUST_{i:06d}", j),
                    "brand": random.choice(CARD_BRANDS),
                    "is_international": random.random() < 0.3,
                }
                for j in range(random.randint(1, 3))
            ]
        }
        customers.append(customer)
    
    return customers

# =============================================================================
# GERAÇÃO DE TRANSAÇÕES NORMAIS
# =============================================================================

def generate_normal_transaction(
    customer: Dict, 
    timestamp: datetime,
    tx_index: int,
    prev_transaction: Dict = None
) -> Dict[str, Any]:
    """
    Gera uma transação NORMAL (não fraudulenta).
    """
    # Decide se é online ou presencial
    is_online = random.random() < 0.35  # 35% online
    
    # Categoria (90% normal, 10% categorias de risco)
    if random.random() < 0.10:
        category = random.choice(CATEGORIAS["risco"])
    else:
        category = random.choice(CATEGORIAS["normal"])
    
    merchant = random.choice(MERCHANTS.get(category, ["Loja Genérica"]))
    
    # Local da compra
    if is_online:
        # Compra online: usa localização do cliente
        purchase_state = customer["home_state"]
        purchase_city = customer["home_city"]
        purchase_lat = customer["home_latitude"]
        purchase_lon = customer["home_longitude"]
    else:
        # Compra presencial: geralmente perto de casa, às vezes viagem
        if customer["is_frequent_traveler"] and random.random() < 0.20:
            # 20% das compras de viajantes são em outros estados
            other_states = [s for s in ESTADOS_BRASIL.keys() if s != customer["home_state"]]
            purchase_state = random.choice(other_states)
        else:
            purchase_state = customer["home_state"]
        
        estado_data = ESTADOS_BRASIL[purchase_state]
        purchase_city = random.choice(estado_data["cidades"])
        purchase_lat, purchase_lon = add_noise_to_coords(estado_data["lat"], estado_data["lon"])
    
    # Device location (geralmente próximo à compra, com alguma variação)
    device_lat, device_lon = add_noise_to_coords(purchase_lat, purchase_lon, radius_km=5)
    
    # Valor da transação (distribuição realista)
    if category in CATEGORIAS["risco"]:
        amount = round(random.uniform(200, 3000), 2)  # Categorias de risco = valores maiores
    else:
        # Distribuição log-normal para valores
        amount = round(min(random.lognormvariate(4, 1), 5000), 2)
    
    # Parcelas (mais parcelas em valores altos)
    if amount > 500 and random.random() < 0.40:
        installments = random.choice([2, 3, 4, 5, 6, 8, 10, 12])
    else:
        installments = 1
    
    # Hora da transação
    hour = timestamp.hour + random.uniform(0, 1)
    
    # Seleciona cartão do cliente
    card = random.choice(customer["cards"])
    
    transaction = {
        "transaction_id": f"TX_{tx_index:010d}",
        "customer_id": customer["customer_id"],
        "card_hash": card["card_hash"],
        "amount": amount,
        "merchant": merchant,
        "category": category,
        "transaction_hour": round(hour, 2),
        "day_of_week": DAYS_OF_WEEK[timestamp.weekday()],
        "customer_home_state": customer["home_state"],
        "purchase_state": purchase_state,
        "purchase_city": purchase_city,
        "purchase_latitude": round(purchase_lat, 6),
        "purchase_longitude": round(purchase_lon, 6),
        "device_latitude": round(device_lat, 6),
        "device_longitude": round(device_lon, 6),
        "device_id": generate_device_id(),
        "ip_address": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
        "payment_method": "credit_card" if installments > 1 else random.choice(PAYMENT_METHODS),
        "card_brand": card["brand"],
        "installments": installments,
        "had_travel_purchase_last_12m": customer["is_frequent_traveler"],
        "is_first_purchase_in_state": purchase_state != customer["home_state"] and random.random() < 0.3,
        "transactions_last_24h": random.randint(0, 10),
        "avg_transaction_amount_30d": round(random.uniform(100, 800), 2),
        "is_international": card["is_international"] and random.random() < 0.05,
        "is_online": is_online,
        "is_fraud": False,
        "fraud_type": None,
        "timestamp": int(timestamp.timestamp()),
    }
    
    return transaction

# =============================================================================
# GERAÇÃO DE CENÁRIOS DE FRAUDE
# =============================================================================

def generate_fraud_cloning(
    customer: Dict,
    base_timestamp: datetime,
    tx_index: int
) -> List[Dict[str, Any]]:
    """
    REGRA 1 & 2: Clonagem de Cartão / Velocidade Impossível
    
    Gera 2 transações do MESMO cliente em estados DISTANTES
    com intervalo de tempo CURTO (impossível se deslocar).
    
    Exemplo: SP às 10:00, AM às 10:15 = 2700km em 15min = IMPOSSÍVEL!
    """
    # Escolhe dois estados distantes
    estados_distantes = [
        ("SP", "AM"),  # ~2700 km
        ("RS", "PA"),  # ~3000 km
        ("RJ", "AM"),  # ~2800 km
        ("BA", "RS"),  # ~2200 km
    ]
    state1, state2 = random.choice(estados_distantes)
    
    transactions = []
    card = random.choice(customer["cards"])
    
    # Primeira transação
    estado1_data = ESTADOS_BRASIL[state1]
    lat1, lon1 = add_noise_to_coords(estado1_data["lat"], estado1_data["lon"])
    
    tx1 = {
        "transaction_id": f"TX_{tx_index:010d}",
        "customer_id": customer["customer_id"],
        "card_hash": card["card_hash"],
        "amount": round(random.uniform(500, 2000), 2),
        "merchant": random.choice(MERCHANTS["electronics"]),
        "category": "electronics",
        "transaction_hour": round(base_timestamp.hour + random.uniform(0, 0.5), 2),
        "day_of_week": DAYS_OF_WEEK[base_timestamp.weekday()],
        "customer_home_state": customer["home_state"],
        "purchase_state": state1,
        "purchase_city": random.choice(estado1_data["cidades"]),
        "purchase_latitude": round(lat1, 6),
        "purchase_longitude": round(lon1, 6),
        "device_latitude": round(lat1 + random.uniform(-0.01, 0.01), 6),
        "device_longitude": round(lon1 + random.uniform(-0.01, 0.01), 6),
        "device_id": generate_device_id(),
        "ip_address": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
        "payment_method": "credit_card",
        "card_brand": card["brand"],
        "installments": random.choice([1, 3, 6]),
        "had_travel_purchase_last_12m": customer["is_frequent_traveler"],
        "is_first_purchase_in_state": True,
        "transactions_last_24h": random.randint(5, 15),
        "avg_transaction_amount_30d": round(random.uniform(100, 500), 2),
        "is_international": False,
        "is_online": False,
        "is_fraud": True,
        "fraud_type": "card_cloning",
        "timestamp": int(base_timestamp.timestamp()),
    }
    transactions.append(tx1)
    
    # Segunda transação: 5-30 minutos depois, estado distante
    time_gap_minutes = random.randint(5, 30)
    timestamp2 = base_timestamp + timedelta(minutes=time_gap_minutes)
    
    estado2_data = ESTADOS_BRASIL[state2]
    lat2, lon2 = add_noise_to_coords(estado2_data["lat"], estado2_data["lon"])
    
    tx2 = {
        "transaction_id": f"TX_{tx_index + 1:010d}",
        "customer_id": customer["customer_id"],
        "card_hash": card["card_hash"],
        "amount": round(random.uniform(800, 3000), 2),
        "merchant": random.choice(MERCHANTS["electronics"]),
        "category": "electronics",
        "transaction_hour": round(timestamp2.hour + timestamp2.minute/60, 2),
        "day_of_week": DAYS_OF_WEEK[timestamp2.weekday()],
        "customer_home_state": customer["home_state"],
        "purchase_state": state2,
        "purchase_city": random.choice(estado2_data["cidades"]),
        "purchase_latitude": round(lat2, 6),
        "purchase_longitude": round(lon2, 6),
        "device_latitude": round(lat2 + random.uniform(-0.01, 0.01), 6),
        "device_longitude": round(lon2 + random.uniform(-0.01, 0.01), 6),
        "device_id": generate_device_id(),  # Device diferente!
        "ip_address": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
        "payment_method": "credit_card",
        "card_brand": card["brand"],
        "installments": random.choice([1, 3, 6, 10]),
        "had_travel_purchase_last_12m": customer["is_frequent_traveler"],
        "is_first_purchase_in_state": True,
        "transactions_last_24h": random.randint(5, 15),
        "avg_transaction_amount_30d": round(random.uniform(100, 500), 2),
        "is_international": False,
        "is_online": False,
        "is_fraud": True,
        "fraud_type": "card_cloning",
        "timestamp": int(timestamp2.timestamp()),
    }
    transactions.append(tx2)
    
    return transactions

def generate_fraud_online_high_value(
    customer: Dict,
    timestamp: datetime,
    tx_index: int
) -> Dict[str, Any]:
    """
    REGRA 9: Compra Online de Alto Valor
    
    Compra online > R$ 1000 em categoria de risco,
    geralmente de madrugada.
    """
    # Força horário noturno (2-5am)
    night_hour = random.uniform(2, 5)
    timestamp = timestamp.replace(hour=int(night_hour), minute=random.randint(0, 59))
    
    card = random.choice(customer["cards"])
    category = random.choice(CATEGORIAS["risco"])
    
    return {
        "transaction_id": f"TX_{tx_index:010d}",
        "customer_id": customer["customer_id"],
        "card_hash": card["card_hash"],
        "amount": round(random.uniform(1500, 5000), 2),  # Alto valor
        "merchant": random.choice(MERCHANTS.get(category, ["Loja Online"])),
        "category": category,
        "transaction_hour": round(night_hour, 2),
        "day_of_week": DAYS_OF_WEEK[timestamp.weekday()],
        "customer_home_state": customer["home_state"],
        "purchase_state": customer["home_state"],
        "purchase_city": customer["home_city"],
        "purchase_latitude": customer["home_latitude"],
        "purchase_longitude": customer["home_longitude"],
        "device_latitude": customer["home_latitude"] + random.uniform(-0.1, 0.1),
        "device_longitude": customer["home_longitude"] + random.uniform(-0.1, 0.1),
        "device_id": generate_device_id(),
        "ip_address": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
        "payment_method": "credit_card",
        "card_brand": card["brand"],
        "installments": random.choice([1, 10, 12]),  # Muitas parcelas
        "had_travel_purchase_last_12m": customer["is_frequent_traveler"],
        "is_first_purchase_in_state": False,
        "transactions_last_24h": random.randint(0, 3),
        "avg_transaction_amount_30d": round(random.uniform(50, 200), 2),  # Média baixa
        "is_international": False,
        "is_online": True,  # ONLINE
        "is_fraud": True,
        "fraud_type": "online_high_value",
        "timestamp": int(timestamp.timestamp()),
    }

def generate_fraud_many_installments(
    customer: Dict,
    timestamp: datetime,
    tx_index: int
) -> Dict[str, Any]:
    """
    REGRA 10: Muitas Parcelas em Compra Grande
    
    Fraudadores parcelam ao máximo para diluir detecção.
    """
    card = random.choice(customer["cards"])
    category = random.choice(CATEGORIAS["risco"])
    
    return {
        "transaction_id": f"TX_{tx_index:010d}",
        "customer_id": customer["customer_id"],
        "card_hash": card["card_hash"],
        "amount": round(random.uniform(1000, 4000), 2),
        "merchant": random.choice(MERCHANTS.get(category, ["Loja"])),
        "category": category,
        "transaction_hour": round(random.uniform(10, 20), 2),
        "day_of_week": DAYS_OF_WEEK[timestamp.weekday()],
        "customer_home_state": customer["home_state"],
        "purchase_state": customer["home_state"],
        "purchase_city": customer["home_city"],
        "purchase_latitude": customer["home_latitude"],
        "purchase_longitude": customer["home_longitude"],
        "device_latitude": customer["home_latitude"] + random.uniform(-0.05, 0.05),
        "device_longitude": customer["home_longitude"] + random.uniform(-0.05, 0.05),
        "device_id": generate_device_id(),
        "ip_address": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
        "payment_method": "credit_card",
        "card_brand": card["brand"],
        "installments": random.choice([10, 11, 12]),  # MUITAS parcelas
        "had_travel_purchase_last_12m": customer["is_frequent_traveler"],
        "is_first_purchase_in_state": False,
        "transactions_last_24h": random.randint(3, 10),
        "avg_transaction_amount_30d": round(random.uniform(80, 250), 2),
        "is_international": False,
        "is_online": random.random() < 0.5,
        "is_fraud": True,
        "fraud_type": "installment_abuse",
        "timestamp": int(timestamp.timestamp()),
    }

def generate_fraud_high_velocity(
    customer: Dict,
    base_timestamp: datetime,
    tx_index: int
) -> List[Dict[str, Any]]:
    """
    Padrão de alta velocidade: muitas transações em pouco tempo.
    """
    transactions = []
    card = random.choice(customer["cards"])
    
    # 5-10 transações em 1 hora
    num_tx = random.randint(5, 10)
    
    for i in range(num_tx):
        timestamp = base_timestamp + timedelta(minutes=random.randint(0, 60))
        
        tx = {
            "transaction_id": f"TX_{tx_index + i:010d}",
            "customer_id": customer["customer_id"],
            "card_hash": card["card_hash"],
            "amount": round(random.uniform(100, 800), 2),
            "merchant": random.choice(MERCHANTS[random.choice(list(MERCHANTS.keys()))]),
            "category": random.choice(CATEGORIAS["normal"] + CATEGORIAS["risco"]),
            "transaction_hour": round(timestamp.hour + timestamp.minute/60, 2),
            "day_of_week": DAYS_OF_WEEK[timestamp.weekday()],
            "customer_home_state": customer["home_state"],
            "purchase_state": customer["home_state"],
            "purchase_city": customer["home_city"],
            "purchase_latitude": customer["home_latitude"] + random.uniform(-0.02, 0.02),
            "purchase_longitude": customer["home_longitude"] + random.uniform(-0.02, 0.02),
            "device_latitude": customer["home_latitude"] + random.uniform(-0.02, 0.02),
            "device_longitude": customer["home_longitude"] + random.uniform(-0.02, 0.02),
            "device_id": generate_device_id(),
            "ip_address": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
            "payment_method": "credit_card",
            "card_brand": card["brand"],
            "installments": 1,
            "had_travel_purchase_last_12m": customer["is_frequent_traveler"],
            "is_first_purchase_in_state": False,
            "transactions_last_24h": num_tx + random.randint(0, 5),  # Alta velocidade!
            "avg_transaction_amount_30d": round(random.uniform(100, 300), 2),
            "is_international": False,
            "is_online": random.random() < 0.3,
            "is_fraud": True,
            "fraud_type": "high_velocity",
            "timestamp": int(timestamp.timestamp()),
        }
        transactions.append(tx)
    
    return transactions

# =============================================================================
# GERAÇÃO PRINCIPAL
# =============================================================================

def generate_all_transactions(
    customers: List[Dict],
    num_transactions: int,
    fraud_rate: float = 0.05
) -> List[Dict[str, Any]]:
    """
    Gera todas as transações com mix de normais e fraudulentas.
    """
    print(f"   Gerando {num_transactions:,} transações...")
    
    transactions = []
    tx_index = 0
    
    # Período: últimos 30 dias
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    # Número de fraudes a injetar
    num_frauds = int(num_transactions * fraud_rate)
    num_normal = num_transactions - num_frauds
    
    print(f"   - Transações normais: {num_normal:,}")
    print(f"   - Fraudes injetadas: {num_frauds:,}")
    
    # Gerar transações normais
    print("   Gerando transações normais...")
    for i in range(num_normal):
        if i % 100000 == 0 and i > 0:
            print(f"      {i:,} / {num_normal:,}")
        
        customer = random.choice(customers)
        timestamp = start_date + timedelta(
            seconds=random.randint(0, int((end_date - start_date).total_seconds()))
        )
        
        tx = generate_normal_transaction(customer, timestamp, tx_index)
        transactions.append(tx)
        tx_index += 1
    
    # Gerar fraudes
    print("   Injetando cenários de fraude...")
    fraud_types = ["cloning", "online_high_value", "installments", "high_velocity"]
    
    frauds_generated = 0
    while frauds_generated < num_frauds:
        fraud_type = random.choice(fraud_types)
        customer = random.choice(customers)
        timestamp = start_date + timedelta(
            seconds=random.randint(0, int((end_date - start_date).total_seconds()))
        )
        
        if fraud_type == "cloning":
            fraud_txs = generate_fraud_cloning(customer, timestamp, tx_index)
            transactions.extend(fraud_txs)
            tx_index += len(fraud_txs)
            frauds_generated += len(fraud_txs)
        
        elif fraud_type == "online_high_value":
            tx = generate_fraud_online_high_value(customer, timestamp, tx_index)
            transactions.append(tx)
            tx_index += 1
            frauds_generated += 1
        
        elif fraud_type == "installments":
            tx = generate_fraud_many_installments(customer, timestamp, tx_index)
            transactions.append(tx)
            tx_index += 1
            frauds_generated += 1
        
        elif fraud_type == "high_velocity":
            fraud_txs = generate_fraud_high_velocity(customer, timestamp, tx_index)
            transactions.extend(fraud_txs)
            tx_index += len(fraud_txs)
            frauds_generated += len(fraud_txs)
    
    # Ordenar por timestamp
    print("   Ordenando por timestamp...")
    transactions.sort(key=lambda x: x["timestamp"])
    
    return transactions

# =============================================================================
# SALVAR DADOS
# =============================================================================

def save_to_jsonl(data: List[Dict], filename: str):
    """Salva dados em formato JSON Lines."""
    filepath = OUTPUT_DIR / filename
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"   Salvando {filepath}...")
    with open(filepath, "w", encoding="utf-8") as f:
        for record in data:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    print(f"   ✅ {len(data):,} registros salvos")

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='🎯 Gerador Avançado de Dados para Detecção de Fraudes'
    )
    parser.add_argument('--customers', '-c', type=int, default=DEFAULT_NUM_CUSTOMERS,
                        help=f'Número de clientes (default: {DEFAULT_NUM_CUSTOMERS:,})')
    parser.add_argument('--transactions', '-t', type=int, default=DEFAULT_NUM_TRANSACTIONS,
                        help=f'Número de transações (default: {DEFAULT_NUM_TRANSACTIONS:,})')
    parser.add_argument('--fraud-rate', '-f', type=float, default=FRAUD_INJECTION_RATE,
                        help=f'Taxa de fraude (default: {FRAUD_INJECTION_RATE})')
    args = parser.parse_args()
    
    print("=" * 70)
    print("🎯 GERADOR AVANÇADO DE DADOS PARA DETECÇÃO DE FRAUDES")
    print("=" * 70)
    print(f"\n📊 Configuração:")
    print(f"   Clientes: {args.customers:,}")
    print(f"   Transações: {args.transactions:,}")
    print(f"   Taxa de fraude: {args.fraud_rate * 100}%")
    
    print(f"\n[1/3] Gerando clientes...")
    customers = generate_customers(args.customers)
    
    print(f"\n[2/3] Gerando transações...")
    transactions = generate_all_transactions(customers, args.transactions, args.fraud_rate)
    
    print(f"\n[3/3] Salvando arquivos...")
    save_to_jsonl(customers, "customers.json")
    save_to_jsonl(transactions, "transactions.json")
    
    # Estatísticas finais
    fraud_count = sum(1 for t in transactions if t["is_fraud"])
    fraud_types = {}
    for t in transactions:
        if t["is_fraud"]:
            ft = t.get("fraud_type", "unknown")
            fraud_types[ft] = fraud_types.get(ft, 0) + 1
    
    print("\n" + "=" * 70)
    print("🎉 GERAÇÃO COMPLETA!")
    print("=" * 70)
    print(f"\n📈 Estatísticas:")
    print(f"   Total de clientes: {len(customers):,}")
    print(f"   Total de transações: {len(transactions):,}")
    print(f"   Total de fraudes: {fraud_count:,} ({fraud_count/len(transactions)*100:.2f}%)")
    print(f"\n🚨 Tipos de fraude injetados:")
    for ft, count in sorted(fraud_types.items(), key=lambda x: -x[1]):
        print(f"   - {ft}: {count:,}")
    
    print(f"\n📁 Arquivos salvos em: {OUTPUT_DIR.absolute()}")
    print(f"   - customers.json")
    print(f"   - transactions.json")
