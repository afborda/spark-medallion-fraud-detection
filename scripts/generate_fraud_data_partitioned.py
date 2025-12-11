"""
🎯 Gerador de Dados Particionados para Detecção de Fraudes
===========================================================

Este script gera dados sintéticos e faz upload para o MinIO
no padrão particionado:

    s3://fraud-data/raw/year=YYYY/month=MM/day=DD/transactions_XXXXX.parquet

VANTAGENS DO PARTICIONAMENTO:
1. Leitura seletiva (só processa dias necessários)
2. Paralelismo melhorado (128MB por bloco)
3. Compressão eficiente por partição
4. Fácil reprocessamento de períodos específicos

Uso:
    python generate_fraud_data_partitioned.py --transactions 1000000 --customers 10000
    python generate_fraud_data_partitioned.py -t 100000 -c 1000 --days 7

"""

import json
import random
import hashlib
import argparse
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any
import math

# Importar pandas e pyarrow para Parquet
try:
    import pandas as pd
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    print("❌ Instale as dependências: pip install pandas pyarrow")
    exit(1)

# =============================================================================
# CONFIGURAÇÕES
# =============================================================================

DEFAULT_NUM_CUSTOMERS = 10000       # Pool de clientes
DEFAULT_NUM_TRANSACTIONS = 1000000  # 1 milhão de transações
DEFAULT_DAYS = 30                   # Dias de dados
FRAUD_INJECTION_RATE = 0.05         # 5% de cenários de fraude injetados
RECORDS_PER_FILE = 100000           # 100k registros por arquivo Parquet

OUTPUT_DIR = Path("/tmp/fraud_data_partitioned")
MINIO_BUCKET = "fraud-data"
MINIO_RAW_PATH = "raw"

# =============================================================================
# DADOS DE REFERÊNCIA BRASILEIROS
# =============================================================================

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
}

CATEGORIAS = {
    "normal": ["grocery", "restaurant", "gas_station", "pharmacy", "clothing", "entertainment", "health", "education", "utilities"],
    "risco": ["electronics", "airline_ticket", "jewelry", "luxury_goods"],
}

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
    "electronics": ["Magazine Luiza", "Americanas", "Casas Bahia", "Amazon", "Mercado Livre"],
    "airline_ticket": ["Gol", "Latam", "Azul", "Decolar", "123Milhas"],
    "jewelry": ["Vivara", "Monte Carlo", "HStern", "Pandora"],
    "luxury_goods": ["Louis Vuitton", "Gucci", "Prada", "Chanel"],
}

CARD_BRANDS = ["Visa", "Mastercard", "Elo", "American Express", "Hipercard"]
CHANNELS = ["web", "mobile_app", "pos", "atm"]
TRANSACTION_TYPES = ["purchase", "withdrawal", "transfer", "pix", "payment"]

# =============================================================================
# FUNÇÕES AUXILIARES
# =============================================================================

def generate_cpf() -> str:
    return f"{random.randint(100,999)}.{random.randint(100,999)}.{random.randint(100,999)}-{random.randint(10,99)}"

def generate_card_hash(customer_id: str, card_index: int = 0) -> str:
    data = f"{customer_id}-card-{card_index}"
    return hashlib.sha256(data.encode()).hexdigest()[:16]

def generate_device_id() -> str:
    return hashlib.md5(str(random.random()).encode()).hexdigest()[:12]

def add_noise_to_coords(lat: float, lon: float, radius_km: float = 50) -> tuple:
    noise = radius_km / 111
    return (
        lat + random.uniform(-noise, noise),
        lon + random.uniform(-noise, noise)
    )

# =============================================================================
# GERAÇÃO DE CLIENTES
# =============================================================================

def generate_customers(num_customers: int) -> List[Dict[str, Any]]:
    print(f"   Gerando {num_customers:,} clientes...")
    customers = []
    estados_list = list(ESTADOS_BRASIL.keys())
    
    for i in range(num_customers):
        home_state = random.choice(estados_list)
        estado_data = ESTADOS_BRASIL[home_state]
        home_city = random.choice(estado_data["cidades"])
        home_lat, home_lon = add_noise_to_coords(estado_data["lat"], estado_data["lon"], radius_km=30)
        is_frequent_traveler = random.random() < 0.15
        
        customer = {
            "customer_id": f"CUST_{i:06d}",
            "home_state": home_state,
            "home_city": home_city,
            "home_latitude": round(home_lat, 6),
            "home_longitude": round(home_lon, 6),
            "is_frequent_traveler": is_frequent_traveler,
            "cards": [
                {
                    "card_hash": generate_card_hash(f"CUST_{i:06d}", j),
                    "brand": random.choice(CARD_BRANDS),
                }
                for j in range(random.randint(1, 3))
            ]
        }
        customers.append(customer)
    
    return customers

# =============================================================================
# GERAÇÃO DE TRANSAÇÕES
# =============================================================================

def generate_transaction(
    customer: Dict, 
    timestamp: datetime,
    tx_index: int,
    is_fraud: bool = False,
    fraud_type: str = None
) -> Dict[str, Any]:
    """Gera uma transação no formato do fraud-generator v4-beta (campos em inglês)."""
    
    is_online = random.random() < 0.35
    
    if random.random() < 0.10:
        category = random.choice(CATEGORIAS["risco"])
    else:
        category = random.choice(CATEGORIAS["normal"])
    
    merchant = random.choice(MERCHANTS.get(category, ["Loja Genérica"]))
    
    if is_online:
        purchase_lat = customer["home_latitude"]
        purchase_lon = customer["home_longitude"]
    else:
        if customer["is_frequent_traveler"] and random.random() < 0.20:
            other_states = [s for s in ESTADOS_BRASIL.keys() if s != customer["home_state"]]
            state = random.choice(other_states)
        else:
            state = customer["home_state"]
        estado_data = ESTADOS_BRASIL[state]
        purchase_lat, purchase_lon = add_noise_to_coords(estado_data["lat"], estado_data["lon"])
    
    if category in CATEGORIAS["risco"]:
        amount = round(random.uniform(200, 3000), 2)
    else:
        amount = round(min(random.lognormvariate(4, 1), 5000), 2)
    
    if amount > 500 and random.random() < 0.40:
        installments = random.choice([2, 3, 4, 5, 6, 8, 10, 12])
    else:
        installments = 1
    
    card = random.choice(customer["cards"])
    
    # Campos no padrão fraud-generator v4-beta (inglês)
    return {
        "transaction_id": f"TX_{tx_index:010d}",
        "customer_id": customer["customer_id"],
        "session_id": hashlib.md5(f"{customer['customer_id']}-{timestamp.isoformat()}".encode()).hexdigest()[:16],
        "device_id": generate_device_id(),
        "timestamp": timestamp.isoformat(),
        "type": random.choice(TRANSACTION_TYPES),
        "amount": amount,
        "currency": "BRL",
        "channel": random.choice(CHANNELS),
        "ip_address": f"{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}.{random.randint(1,255)}",
        "geolocation_lat": round(purchase_lat, 6),
        "geolocation_lon": round(purchase_lon, 6),
        "merchant_id": f"MERCH_{random.randint(1, 10000):05d}",
        "merchant_name": merchant,
        "merchant_category": category,
        "mcc_code": str(random.randint(1000, 9999)),
        "mcc_risk_level": "high" if category in CATEGORIAS["risco"] else "low",
        "card_number_hash": card["card_hash"],
        "card_brand": card["brand"],
        "card_type": random.choice(["credit", "debit"]),
        "installments": installments,
        "card_entry": "chip" if not is_online else "online",
        "cvv_validated": True,
        "auth_3ds": is_online and random.random() < 0.7,
        "pix_key_type": None,
        "pix_key_destination": None,
        "destination_bank": None,
        "distance_from_last_txn_km": round(random.uniform(0, 100), 2),
        "time_since_last_txn_min": random.randint(1, 1440),
        "transactions_last_24h": random.randint(0, 15),
        "accumulated_amount_24h": round(random.uniform(0, 5000), 2),
        "unusual_time": timestamp.hour < 6 or timestamp.hour > 23,
        "new_beneficiary": random.random() < 0.1,
        "status": "approved" if not is_fraud else random.choice(["approved", "denied"]),
        "refusal_reason": None if not is_fraud else "fraud_suspicion",
        "fraud_score": round(random.uniform(0.7, 1.0) if is_fraud else random.uniform(0, 0.3), 4),
        "is_fraud": is_fraud,
        "fraud_type": fraud_type
    }

# =============================================================================
# GERAÇÃO PRINCIPAL
# =============================================================================

def generate_all_transactions(
    customers: List[Dict],
    num_transactions: int,
    num_days: int,
    fraud_rate: float = 0.05
) -> Dict[str, List[Dict]]:
    """
    Gera todas as transações agrupadas por data (year/month/day).
    Retorna dict: {(year, month, day): [transactions]}
    """
    print(f"   Gerando {num_transactions:,} transações em {num_days} dias...")
    
    # Dicionário para agrupar por data
    transactions_by_date: Dict[tuple, List[Dict]] = {}
    
    tx_index = 0
    end_date = datetime.now()
    start_date = end_date - timedelta(days=num_days)
    
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
        
        tx = generate_transaction(customer, timestamp, tx_index, is_fraud=False)
        
        # Agrupar por (year, month, day)
        date_key = (timestamp.year, timestamp.month, timestamp.day)
        if date_key not in transactions_by_date:
            transactions_by_date[date_key] = []
        transactions_by_date[date_key].append(tx)
        
        tx_index += 1
    
    # Gerar fraudes
    print("   Injetando cenários de fraude...")
    fraud_types = ["card_cloning", "online_high_value", "installment_abuse", "high_velocity"]
    
    for i in range(num_frauds):
        customer = random.choice(customers)
        timestamp = start_date + timedelta(
            seconds=random.randint(0, int((end_date - start_date).total_seconds()))
        )
        fraud_type = random.choice(fraud_types)
        
        tx = generate_transaction(customer, timestamp, tx_index, is_fraud=True, fraud_type=fraud_type)
        
        date_key = (timestamp.year, timestamp.month, timestamp.day)
        if date_key not in transactions_by_date:
            transactions_by_date[date_key] = []
        transactions_by_date[date_key].append(tx)
        
        tx_index += 1
    
    return transactions_by_date

# =============================================================================
# SALVAR E UPLOAD
# =============================================================================

def save_partitioned_parquet(transactions_by_date: Dict[tuple, List[Dict]]) -> List[Path]:
    """
    Salva os dados particionados em Parquet.
    Estrutura: /tmp/fraud_data_partitioned/year=YYYY/month=MM/day=DD/transactions_XXXXX.parquet
    """
    print("\n📁 Salvando arquivos particionados...")
    
    saved_files = []
    
    for (year, month, day), transactions in sorted(transactions_by_date.items()):
        partition_dir = OUTPUT_DIR / f"year={year}" / f"month={month:02d}" / f"day={day:02d}"
        partition_dir.mkdir(parents=True, exist_ok=True)
        
        # Dividir em arquivos de RECORDS_PER_FILE cada
        for i in range(0, len(transactions), RECORDS_PER_FILE):
            chunk = transactions[i:i + RECORDS_PER_FILE]
            file_index = i // RECORDS_PER_FILE
            
            filepath = partition_dir / f"transactions_{file_index:05d}.parquet"
            
            # Converter para DataFrame e salvar como Parquet
            df = pd.DataFrame(chunk)
            df.to_parquet(filepath, engine='pyarrow', compression='snappy', index=False)
            
            saved_files.append(filepath)
        
        print(f"   ✅ {year}/{month:02d}/{day:02d}: {len(transactions):,} transações")
    
    return saved_files

def upload_to_minio(local_path: Path = OUTPUT_DIR):
    """
    Faz upload dos arquivos particionados para o MinIO.
    """
    print("\n☁️ Fazendo upload para MinIO...")
    
    # Verificar se mc está no PATH
    mc_cmd = "mc"
    result = subprocess.run(["which", "mc"], capture_output=True, text=True)
    if result.returncode != 0:
        # Tentar usar mc do snap ou home
        for path in ["/snap/bin/mc", os.path.expanduser("~/bin/mc"), "/usr/local/bin/mc"]:
            if os.path.exists(path):
                mc_cmd = path
                break
    
    # Verificar se mc está configurado
    try:
        subprocess.run([mc_cmd, "alias", "set", "myminio", "http://localhost:9000", "minioadmin", "minioadmin"], 
                       capture_output=True, check=True)
    except subprocess.CalledProcessError:
        print("❌ Erro ao configurar mc client. Execute manualmente:")
        print(f"   mc cp --recursive {local_path}/ myminio/{MINIO_BUCKET}/{MINIO_RAW_PATH}/")
        return False
    except FileNotFoundError:
        print("❌ mc não encontrado. Execute manualmente:")
        print(f"   mc cp --recursive {local_path}/ myminio/{MINIO_BUCKET}/{MINIO_RAW_PATH}/")
        return False
    
    # Upload recursivo
    src = str(local_path) + "/"
    dst = f"myminio/{MINIO_BUCKET}/{MINIO_RAW_PATH}/"
    
    print(f"   📤 {src} → {dst}")
    
    result = subprocess.run(
        [mc_cmd, "cp", "--recursive", src, dst],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print("   ✅ Upload concluído!")
        return True
    else:
        print(f"   ❌ Erro no upload: {result.stderr}")
        return False

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='🎯 Gerador de Dados Particionados para Detecção de Fraudes'
    )
    parser.add_argument('--customers', '-c', type=int, default=DEFAULT_NUM_CUSTOMERS,
                        help=f'Número de clientes (default: {DEFAULT_NUM_CUSTOMERS:,})')
    parser.add_argument('--transactions', '-t', type=int, default=DEFAULT_NUM_TRANSACTIONS,
                        help=f'Número de transações (default: {DEFAULT_NUM_TRANSACTIONS:,})')
    parser.add_argument('--days', '-d', type=int, default=DEFAULT_DAYS,
                        help=f'Número de dias de dados (default: {DEFAULT_DAYS})')
    parser.add_argument('--fraud-rate', '-f', type=float, default=FRAUD_INJECTION_RATE,
                        help=f'Taxa de fraude (default: {FRAUD_INJECTION_RATE})')
    parser.add_argument('--no-upload', action='store_true',
                        help='Não fazer upload para MinIO')
    args = parser.parse_args()
    
    print("=" * 70)
    print("🎯 GERADOR DE DADOS PARTICIONADOS - FRAUD DETECTION")
    print("=" * 70)
    print(f"\n📊 Configuração:")
    print(f"   Clientes: {args.customers:,}")
    print(f"   Transações: {args.transactions:,}")
    print(f"   Dias de dados: {args.days}")
    print(f"   Taxa de fraude: {args.fraud_rate * 100}%")
    print(f"   Formato: Parquet (Snappy)")
    print(f"   Particionamento: year/month/day")
    
    # Limpar diretório temporário
    if OUTPUT_DIR.exists():
        import shutil
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[1/4] Gerando clientes...")
    customers = generate_customers(args.customers)
    
    print(f"\n[2/4] Gerando transações...")
    transactions_by_date = generate_all_transactions(
        customers, 
        args.transactions, 
        args.days,
        args.fraud_rate
    )
    
    print(f"\n[3/4] Salvando arquivos particionados...")
    saved_files = save_partitioned_parquet(transactions_by_date)
    
    if not args.no_upload:
        print(f"\n[4/4] Upload para MinIO...")
        upload_to_minio()
    else:
        print(f"\n[4/4] Upload para MinIO... PULADO (--no-upload)")
    
    # Estatísticas finais
    total_transactions = sum(len(txs) for txs in transactions_by_date.values())
    total_frauds = sum(
        sum(1 for tx in txs if tx.get("is_fraud")) 
        for txs in transactions_by_date.values()
    )
    
    print("\n" + "=" * 70)
    print("🎉 GERAÇÃO COMPLETA!")
    print("=" * 70)
    print(f"\n📈 Estatísticas:")
    print(f"   Total de clientes: {len(customers):,}")
    print(f"   Total de transações: {total_transactions:,}")
    print(f"   Total de fraudes: {total_frauds:,} ({total_frauds/total_transactions*100:.2f}%)")
    print(f"   Dias particionados: {len(transactions_by_date)}")
    print(f"   Arquivos Parquet: {len(saved_files)}")
    
    # Calcular tamanho total
    total_size = sum(f.stat().st_size for f in saved_files)
    print(f"   Tamanho total: {total_size / (1024*1024):.1f} MB")
    
    print(f"\n📁 Estrutura no MinIO:")
    print(f"   s3://fraud-data/raw/year=YYYY/month=MM/day=DD/transactions_XXXXX.parquet")
    print("=" * 70)
