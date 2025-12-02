#!/usr/bin/env python3
"""
🚀 GERADOR PARALELO DE DADOS BRASILEIROS - 128MB por arquivo
============================================================
Usa multiprocessing para gerar dados em paralelo

Uso:
    python3 scripts/generate_parallel.py --size 50GB --workers 10
"""

import json
import random
import hashlib
import uuid
import os
import sys
import time
import multiprocessing as mp
from datetime import datetime, timedelta
from faker import Faker
from functools import partial

# Configuração
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'raw')
TARGET_FILE_SIZE_MB = 128  # Cada arquivo terá ~128MB
BYTES_PER_TRANSACTION = 1050  # ~1KB por transação JSON (medido)
TRANSACTIONS_PER_FILE = (TARGET_FILE_SIZE_MB * 1024 * 1024) // BYTES_PER_TRANSACTION  # ~128k transações

# Dados estáticos para geração
BANK_CODES = ['001', '033', '104', '237', '341', '260', '077', '336', '290', '380', '323', '403', '212']
MCC_CODES = {
    '5411': ('Supermercados', 'low'), '5541': ('Postos de Combustível', 'low'),
    '5812': ('Restaurantes', 'low'), '5814': ('Fast Food', 'low'),
    '5912': ('Farmácias', 'low'), '5311': ('Lojas de Departamento', 'medium'),
    '5651': ('Vestuário', 'medium'), '5732': ('Eletrônicos', 'high'),
    '5944': ('Joalherias', 'high'), '5999': ('Diversos', 'medium'),
    '7011': ('Hotéis', 'medium'), '4111': ('Transporte', 'low'),
    '6011': ('Caixa Eletrônico', 'medium'), '7995': ('Apostas/Cassino', 'high'),
}
MERCHANTS = [
    'Supermercado Extra', 'Carrefour', 'Pão de Açúcar', 'Posto Shell', 'Posto Ipiranga',
    'iFood', 'Rappi', 'Uber Eats', 'McDonald\'s', 'Burger King', 'Drogasil', 'Droga Raia',
    'Renner', 'C&A', 'Riachuelo', 'Magazine Luiza', 'Casas Bahia', 'Amazon Brasil',
    'Mercado Livre', 'Americanas', 'Hotel Ibis', 'Booking.com', 'Airbnb', '99', 'Uber',
]
TRANSACTION_TYPES = ['PIX', 'PIX', 'PIX', 'PIX', 'CARTAO_CREDITO', 'CARTAO_CREDITO', 
                     'CARTAO_DEBITO', 'TED', 'BOLETO', 'SAQUE']
CHANNELS = ['APP_MOBILE', 'APP_MOBILE', 'APP_MOBILE', 'WEB_BANKING', 'ATM', 'AGENCIA']
FRAUD_TYPES = ['CARTAO_CLONADO', 'CONTA_TOMADA', 'IDENTIDADE_FALSA', 'ENGENHARIA_SOCIAL',
               'LAVAGEM_DINHEIRO', 'AUTOFRAUDE', 'FRAUDE_AMIGAVEL', 'TRIANGULACAO']
PIX_KEY_TYPES = ['CPF', 'EMAIL', 'TELEFONE', 'ALEATORIA', 'CNPJ']
CARD_BRANDS = ['VISA', 'MASTERCARD', 'ELO', 'AMEX', 'HIPERCARD']


def generate_ip_brazil():
    """Gera IP brasileiro"""
    prefix = random.choice(['177.', '187.', '189.', '191.', '200.', '201.'])
    return prefix + '.'.join(str(random.randint(0, 255)) for _ in range(3))


def generate_transaction(tx_id, customer_id, device_id, timestamp, is_fraud, fraud_type, fake):
    """Gera uma transação"""
    tx_type = random.choice(TRANSACTION_TYPES)
    mcc_code = random.choice(list(MCC_CODES.keys()))
    mcc_cat, mcc_risk = MCC_CODES[mcc_code]
    
    # Valor baseado em fraude
    if is_fraud:
        valor = round(random.uniform(500, 15000), 2)
    else:
        valor = round(random.choices(
            [random.uniform(5, 100), random.uniform(100, 500), random.uniform(500, 2000), random.uniform(2000, 10000)],
            weights=[50, 30, 15, 5]
        )[0], 2)
    
    tx = {
        'transaction_id': f'TXN_{tx_id:015d}',
        'customer_id': customer_id,
        'session_id': f'SESS_{tx_id:012d}',
        'device_id': device_id,
        'timestamp': timestamp.isoformat(),
        'tipo': tx_type,
        'valor': valor,
        'moeda': 'BRL',
        'canal': random.choice(CHANNELS),
        'ip_address': generate_ip_brazil(),
        'geolocalizacao_lat': round(random.uniform(-33.75, 5.27), 6),
        'geolocalizacao_lon': round(random.uniform(-73.99, -34.79), 6),
        'merchant_id': f'MERCH_{random.randint(1, 100000):06d}',
        'merchant_name': random.choice(MERCHANTS),
        'merchant_category': mcc_cat,
        'mcc_code': mcc_code,
        'mcc_risk_level': mcc_risk,
    }
    
    # Campos específicos por tipo
    if tx_type in ['CARTAO_CREDITO', 'CARTAO_DEBITO']:
        tx.update({
            'numero_cartao_hash': hashlib.md5(str(random.random()).encode()).hexdigest()[:16],
            'bandeira': random.choice(CARD_BRANDS),
            'tipo_cartao': 'CREDITO' if tx_type == 'CARTAO_CREDITO' else 'DEBITO',
            'parcelas': random.choice([1, 1, 1, 2, 3, 6, 12]) if tx_type == 'CARTAO_CREDITO' else 1,
            'entrada_cartao': random.choice(['CHIP', 'CONTACTLESS', 'DIGITADO', 'MAGNETICO']),
            'cvv_validado': random.choice([True, True, True, False]),
            'autenticacao_3ds': random.choice([True, False]),
            'chave_pix_tipo': None, 'chave_pix_destino': None, 'banco_destino': None,
        })
    elif tx_type == 'PIX':
        tx.update({
            'numero_cartao_hash': None, 'bandeira': None, 'tipo_cartao': None,
            'parcelas': None, 'entrada_cartao': None, 'cvv_validado': None, 'autenticacao_3ds': None,
            'chave_pix_tipo': random.choice(PIX_KEY_TYPES),
            'chave_pix_destino': fake.email() if random.random() > 0.5 else fake.cpf(),
            'banco_destino': random.choice(BANK_CODES),
        })
    else:
        tx.update({
            'numero_cartao_hash': None, 'bandeira': None, 'tipo_cartao': None,
            'parcelas': None, 'entrada_cartao': None, 'cvv_validado': None, 'autenticacao_3ds': None,
            'chave_pix_tipo': None, 'chave_pix_destino': None,
            'banco_destino': random.choice(BANK_CODES) if tx_type in ['TED', 'DOC'] else None,
        })
    
    # Indicadores de risco
    tx.update({
        'distancia_ultima_transacao_km': round(random.uniform(0, 500), 2) if random.random() > 0.7 else None,
        'tempo_desde_ultima_transacao_min': random.randint(1, 1440) if random.random() > 0.5 else None,
        'transacoes_ultimas_24h': random.randint(1, 30),
        'valor_acumulado_24h': round(random.uniform(100, 10000), 2),
        'horario_incomum': random.random() < 0.1,
        'novo_beneficiario': random.random() < 0.2,
        'status': 'APROVADA' if not is_fraud or random.random() > 0.3 else random.choice(['RECUSADA', 'PENDENTE', 'BLOQUEADA']),
        'motivo_recusa': random.choice(['SALDO_INSUFICIENTE', 'SUSPEITA_FRAUDE', 'LIMITE_EXCEDIDO', 'ERRO_COMUNICACAO']) if random.random() < 0.05 else None,
        'fraud_score': round(random.uniform(70, 100), 2) if is_fraud else round(random.uniform(0, 30), 2),
        'is_fraud': is_fraud,
        'fraud_type': fraud_type,
    })
    
    return tx


def worker_generate_batch(args):
    """Worker que gera um arquivo de 128MB"""
    batch_id, num_transactions, customer_ids, device_ids, start_date, end_date, fraud_rate, output_dir = args
    
    # Seed único por worker para dados diferentes
    seed = batch_id * 12345 + int(time.time() * 1000) % 10000
    random.seed(seed)
    fake = Faker('pt_BR')
    Faker.seed(seed)
    
    output_path = os.path.join(output_dir, f'transactions_{batch_id:05d}.json')
    
    start_time = time.time()
    tx_id_start = batch_id * num_transactions
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for i in range(num_transactions):
            tx_id = tx_id_start + i
            customer_id = random.choice(customer_ids)
            device_id = random.choice(device_ids) if device_ids else None
            timestamp = fake.date_time_between(start_date=start_date, end_date=end_date)
            is_fraud = random.random() < fraud_rate
            fraud_type = random.choice(FRAUD_TYPES) if is_fraud else None
            
            tx = generate_transaction(tx_id, customer_id, device_id, timestamp, is_fraud, fraud_type, fake)
            f.write(json.dumps(tx, ensure_ascii=False) + '\n')
    
    elapsed = time.time() - start_time
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    
    return batch_id, num_transactions, file_size_mb, elapsed


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Gerador paralelo de dados brasileiros')
    parser.add_argument('--size', type=str, default='50GB', help='Tamanho alvo (ex: 50GB)')
    parser.add_argument('--workers', type=int, default=mp.cpu_count(), help='Número de workers paralelos')
    parser.add_argument('--output', type=str, default=OUTPUT_DIR, help='Diretório de saída')
    parser.add_argument('--fraud-rate', type=float, default=0.007, help='Taxa de fraude')
    
    args = parser.parse_args()
    
    # Calcular número de arquivos
    target_gb = float(args.size.upper().replace('GB', ''))
    target_mb = target_gb * 1024
    num_files = int(target_mb / TARGET_FILE_SIZE_MB)
    total_transactions = num_files * TRANSACTIONS_PER_FILE
    
    print("=" * 70)
    print("🚀 GERADOR PARALELO DE DADOS BRASILEIROS")
    print("=" * 70)
    print(f"📊 Configuração:")
    print(f"   • Tamanho alvo: {target_gb:.0f} GB")
    print(f"   • Arquivos de 128MB: {num_files:,}")
    print(f"   • Transações por arquivo: {TRANSACTIONS_PER_FILE:,}")
    print(f"   • Total de transações: {total_transactions:,}")
    print(f"   • Workers paralelos: {args.workers}")
    print(f"   • Taxa de fraude: {args.fraud_rate*100:.1f}%")
    print("=" * 70)
    
    os.makedirs(args.output, exist_ok=True)
    
    # Carregar ou gerar IDs de clientes
    customers_path = os.path.join(args.output, 'customers.json')
    if os.path.exists(customers_path):
        print(f"\n📂 Carregando clientes de {customers_path}...")
        with open(customers_path, 'r') as f:
            customer_ids = [json.loads(line)['customer_id'] for line in f]
        print(f"   ✓ {len(customer_ids):,} clientes")
    else:
        print(f"\n🧑 Gerando 100,000 clientes...")
        customer_ids = [f'CUST_{i:08d}' for i in range(1, 100001)]
    
    # Carregar ou gerar IDs de dispositivos
    devices_path = os.path.join(args.output, 'devices.json')
    if os.path.exists(devices_path):
        print(f"📂 Carregando dispositivos de {devices_path}...")
        with open(devices_path, 'r') as f:
            device_ids = [json.loads(line)['device_id'] for line in f]
        print(f"   ✓ {len(device_ids):,} dispositivos")
    else:
        device_ids = [f'DEV_{i:08d}' for i in range(1, 300001)]
    
    # Período de dados
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)
    
    # Verificar arquivos já gerados
    existing_files = [f for f in os.listdir(args.output) if f.startswith('transactions_') and f.endswith('.json')]
    existing_count = len(existing_files)
    
    # Calcular tamanho atual
    current_size_mb = sum(
        os.path.getsize(os.path.join(args.output, f)) / (1024 * 1024) 
        for f in existing_files
    )
    current_size_gb = current_size_mb / 1024
    
    if current_size_gb >= target_gb * 0.99:  # 99% do alvo
        print(f"\n✅ Já temos {current_size_gb:.2f} GB gerados ({existing_count} arquivos)!")
        return
    
    # Calcular quantos arquivos faltam
    remaining_gb = target_gb - current_size_gb
    remaining_files = int((remaining_gb * 1024) / TARGET_FILE_SIZE_MB) + 1
    start_batch = existing_count
    
    print(f"\n🔄 Temos {current_size_gb:.2f} GB ({existing_count} arquivos)")
    print(f"   Faltam {remaining_gb:.2f} GB ({remaining_files} arquivos)")
    
    # Preparar argumentos para workers
    batch_args = [
        (start_batch + i, TRANSACTIONS_PER_FILE, customer_ids, device_ids, 
         start_date, end_date, args.fraud_rate, args.output)
        for i in range(remaining_files)
    ]
    
    print(f"\n💳 Gerando {remaining_files:,} arquivos de 128MB...")
    print(f"   🎯 Total: ~{remaining_files * TARGET_FILE_SIZE_MB / 1024:.1f} GB\n")
    
    # Executar em paralelo
    start_time = time.time()
    completed = 0
    total_mb = 0
    
    with mp.Pool(args.workers) as pool:
        for batch_id, num_tx, file_mb, elapsed in pool.imap_unordered(worker_generate_batch, batch_args):
            completed += 1
            total_mb += file_mb
            
            # Progresso
            pct = (completed / remaining_files) * 100
            elapsed_total = time.time() - start_time
            rate_mb_s = total_mb / elapsed_total if elapsed_total > 0 else 0
            remaining_mb = (remaining_files - completed) * TARGET_FILE_SIZE_MB
            eta_s = remaining_mb / rate_mb_s if rate_mb_s > 0 else 0
            
            bar_width = 40
            filled = int(bar_width * pct / 100)
            bar = '█' * filled + '░' * (bar_width - filled)
            
            print(f"\r  [{bar}] {pct:5.1f}% | {completed}/{remaining_files} | "
                  f"{total_mb/1024:.1f}GB | {rate_mb_s:.1f}MB/s | "
                  f"ETA: {int(eta_s//3600)}h{int((eta_s%3600)//60):02d}m", end='', flush=True)
    
    # Sumário
    total_time = time.time() - start_time
    final_size_gb = current_size_gb + (total_mb / 1024)
    print(f"\n\n{'=' * 70}")
    print("✅ GERAÇÃO CONCLUÍDA!")
    print("=" * 70)
    print(f"📁 Diretório: {args.output}")
    print(f"📊 Arquivos gerados: {remaining_files:,} (total: {existing_count + remaining_files:,})")
    print(f"💾 Tamanho total: {final_size_gb:.2f} GB")
    print(f"⏱️  Tempo total: {int(total_time//3600)}h {int((total_time%3600)//60)}m {int(total_time%60)}s")
    print(f"🚀 Velocidade média: {total_mb/total_time:.1f} MB/s")


if __name__ == '__main__':
    main()
