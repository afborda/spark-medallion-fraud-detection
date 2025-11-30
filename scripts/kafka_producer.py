"""
Kafka Producer - Simula transações em tempo real
Envia transações para o topic 'transactions' do Kafka

Uso:
    python scripts/kafka_producer.py --rate 100  # 100 transações por segundo
    python scripts/kafka_producer.py --rate 1000 # 1000 transações por segundo
"""

import json
import time
import random
import argparse
from datetime import datetime
from kafka import KafkaProducer

# ============================================================
# CONFIGURAÇÃO
# ============================================================

KAFKA_BOOTSTRAP_SERVERS = ['localhost:9092']
KAFKA_TOPIC = 'transactions'

# Dados para geração
CATEGORIES = ['electronics', 'food', 'travel', 'clothing', 'entertainment', 'health', 'gas_station']
CITIES = ['São Paulo', 'Rio de Janeiro', 'Belo Horizonte', 'Salvador', 'Curitiba', 'Fortaleza', 'Brasília']
HIGH_RISK_CATEGORIES = ['electronics', 'jewelry', 'gambling', 'crypto']

# ============================================================
# GERADOR DE TRANSAÇÕES
# ============================================================

def generate_transaction(transaction_id: int, fraud_rate: float = 0.05) -> dict:
    """
    Gera uma transação sintética.
    
    Por que esses campos?
    - customer_id: para agrupar transações por cliente
    - amount: valor da transação (fraudes tendem a ter valores maiores)
    - category: tipo de compra (algumas categorias são mais arriscadas)
    - city: localização (fraudes podem ter padrões geográficos)
    - timestamp: quando aconteceu (fraudes podem ter padrões de horário)
    - is_fraud: flag de fraude (5% por padrão)
    """
    
    # Decidir se é fraude ANTES de gerar os dados
    # (fraudes têm características diferentes)
    is_fraud = random.random() < fraud_rate
    
    # Transações fraudulentas tendem a:
    # - Ter valores maiores
    # - Ocorrer em categorias de alto risco
    # - Acontecer em horários incomuns (madrugada)
    
    if is_fraud:
        amount = round(random.uniform(500, 10000), 2)  # Valores altos
        category = random.choice(HIGH_RISK_CATEGORIES + CATEGORIES)
        hour = random.choice([2, 3, 4, 5, 14, 15])  # Madrugada ou tarde
    else:
        amount = round(random.uniform(10, 500), 2)  # Valores normais
        category = random.choice(CATEGORIES)
        hour = random.randint(8, 22)  # Horário comercial
    
    transaction = {
        'transaction_id': f'TXN_{transaction_id:010d}',
        'customer_id': f'CUST_{random.randint(1, 100000):06d}',
        'amount': amount,
        'category': category,
        'city': random.choice(CITIES),
        'timestamp': datetime.now().replace(hour=hour).isoformat(),
        'is_fraud': is_fraud
    }
    
    return transaction

# ============================================================
# KAFKA PRODUCER
# ============================================================

def create_producer() -> KafkaProducer:
    """
    Cria conexão com o Kafka.
    
    value_serializer: converte dict Python → bytes JSON
    (Kafka só transporta bytes, não objetos Python)
    """
    return KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda v: json.dumps(v).encode('utf-8'),
        # Configurações de performance
        batch_size=16384,      # Agrupa mensagens em lotes de 16KB
        linger_ms=10,          # Espera até 10ms para formar lote
        compression_type='gzip'  # Comprime para economizar rede
    )

def send_transactions(producer: KafkaProducer, rate: int, duration: int, fraud_rate: float):
    """
    Envia transações para o Kafka em uma taxa específica.
    
    Args:
        producer: conexão Kafka
        rate: transações por segundo
        duration: duração em segundos (0 = infinito)
        fraud_rate: percentual de fraudes (0.05 = 5%)
    """
    print(f"\n🚀 Iniciando Producer")
    print(f"   📊 Taxa: {rate} transações/segundo")
    print(f"   ⏱️  Duração: {'infinito' if duration == 0 else f'{duration}s'}")
    print(f"   🎯 Taxa de fraude: {fraud_rate*100}%")
    print(f"   📬 Topic: {KAFKA_TOPIC}")
    print(f"\n{'='*50}")
    print("Pressione Ctrl+C para parar\n")
    
    transaction_id = 0
    start_time = time.time()
    interval = 1.0 / rate  # Tempo entre cada transação
    
    sent_count = 0
    fraud_count = 0
    
    try:
        while True:
            # Verificar duração
            if duration > 0 and (time.time() - start_time) >= duration:
                break
            
            # Gerar e enviar transação
            transaction = generate_transaction(transaction_id, fraud_rate)
            producer.send(KAFKA_TOPIC, value=transaction)
            
            transaction_id += 1
            sent_count += 1
            if transaction['is_fraud']:
                fraud_count += 1
            
            # Log a cada 1000 transações
            if sent_count % 1000 == 0:
                elapsed = time.time() - start_time
                actual_rate = sent_count / elapsed
                print(f"📤 Enviadas: {sent_count:,} | Fraudes: {fraud_count:,} ({fraud_count/sent_count*100:.1f}%) | Taxa real: {actual_rate:.0f}/s")
            
            # Controlar taxa
            time.sleep(interval)
            
    except KeyboardInterrupt:
        print(f"\n\n⏹️  Interrompido pelo usuário")
    finally:
        producer.flush()  # Garantir que todas mensagens foram enviadas
        producer.close()
        
        elapsed = time.time() - start_time
        print(f"\n{'='*50}")
        print(f"📊 RESUMO")
        print(f"   Transações enviadas: {sent_count:,}")
        print(f"   Fraudes: {fraud_count:,} ({fraud_count/max(sent_count,1)*100:.1f}%)")
        print(f"   Tempo: {elapsed:.1f}s")
        print(f"   Taxa média: {sent_count/max(elapsed,1):.0f} transações/s")
        print(f"{'='*50}\n")

# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Kafka Producer - Simula transações em tempo real')
    parser.add_argument('--rate', type=int, default=100, help='Transações por segundo (default: 100)')
    parser.add_argument('--duration', type=int, default=0, help='Duração em segundos (0 = infinito)')
    parser.add_argument('--fraud-rate', type=float, default=0.05, help='Taxa de fraude (default: 0.05 = 5%%)')
    
    args = parser.parse_args()
    
    print("="*50)
    print("🏦 KAFKA PRODUCER - Simulador de Transações")
    print("="*50)
    
    # Criar producer
    print("\n📡 Conectando ao Kafka...")
    try:
        producer = create_producer()
        print("✅ Conectado!")
    except Exception as e:
        print(f"❌ Erro ao conectar: {e}")
        print("\nVerifique se o Kafka está rodando:")
        print("  docker ps | grep kafka")
        exit(1)
    
    # Enviar transações
    send_transactions(producer, args.rate, args.duration, args.fraud_rate)
