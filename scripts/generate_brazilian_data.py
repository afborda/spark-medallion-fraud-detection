"""
🇧🇷 GERADOR DE DADOS BRASILEIROS PARA DETECÇÃO DE FRAUDE
=======================================================
Gera dados realistas de banco/fintech brasileiro usando Faker pt_BR

Estrutura de Dados:
- customers.json: 100k clientes com dados completos
- transactions.json: ~230M transações (~50GB)
- devices.json: 500k dispositivos vinculados a clientes
- sessions.json: Histórico de sessões/logins

Campos baseados em análise de sistemas reais de:
- Bancos digitais (Nubank, Inter, C6)
- Fintechs de crédito
- Gateways de pagamento (PagSeguro, Stone)
- Sistemas antifraude (ClearSale, Konduto)

Autor: Data Engineering Project
Data: 2024
"""

import json
import random
import uuid
import hashlib
import gzip
import os
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Generator, List, Dict, Any, Tuple
from dataclasses import dataclass, asdict
from faker import Faker
from faker.providers import BaseProvider
import multiprocessing as mp
from functools import partial

# ============================================
# CONFIGURAÇÃO
# ============================================

fake = Faker('pt_BR')
Faker.seed(42)
random.seed(42)

# Diretório de saída
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'raw')

# ============================================
# PROVIDER CUSTOMIZADO PARA DADOS BRASILEIROS
# ============================================

class BrazilianBankingProvider(BaseProvider):
    """Provider customizado para dados bancários brasileiros"""
    
    # Códigos de banco brasileiros reais
    BANK_CODES = {
        '001': 'Banco do Brasil',
        '033': 'Santander',
        '104': 'Caixa Econômica',
        '237': 'Bradesco',
        '341': 'Itaú',
        '260': 'Nubank',
        '077': 'Inter',
        '336': 'C6 Bank',
        '290': 'PagSeguro',
        '380': 'PicPay',
        '323': 'Mercado Pago',
        '403': 'Cora',
        '212': 'Original',
    }
    
    # MCC (Merchant Category Codes) comuns
    MCC_CODES = {
        '5411': ('Supermercados', 'low'),
        '5541': ('Postos de Combustível', 'low'),
        '5812': ('Restaurantes', 'low'),
        '5814': ('Fast Food', 'low'),
        '5912': ('Farmácias', 'low'),
        '5311': ('Lojas de Departamento', 'medium'),
        '5651': ('Vestuário', 'medium'),
        '5732': ('Eletrônicos', 'high'),
        '5944': ('Joalherias', 'high'),
        '5999': ('Diversos', 'medium'),
        '7011': ('Hotéis', 'medium'),
        '4111': ('Transporte', 'low'),
        '4121': ('Táxi/Uber', 'low'),
        '5172': ('Petróleo', 'low'),
        '6011': ('Caixa Eletrônico', 'medium'),
        '6012': ('Instituição Financeira', 'high'),
        '7995': ('Apostas/Cassino', 'high'),
        '4829': ('Transferência Internacional', 'high'),
        '5967': ('Marketing Direto', 'high'),
        '7273': ('Serviços de Namoro', 'medium'),
        '5661': ('Calçados', 'low'),
        '5942': ('Livrarias', 'low'),
        '7832': ('Cinema', 'low'),
        '7841': ('Streaming/Vídeo', 'low'),
        '4816': ('Internet/Telefonia', 'low'),
        '5462': ('Padarias', 'low'),
        '5813': ('Bares', 'medium'),
    }
    
    # Tipos de transação
    TRANSACTION_TYPES = [
        ('PIX', 45),           # 45% das transações
        ('CARTAO_CREDITO', 25),
        ('CARTAO_DEBITO', 15),
        ('TED', 5),
        ('DOC', 2),
        ('BOLETO', 5),
        ('SAQUE', 3),
    ]
    
    # Canais de origem
    CHANNELS = [
        ('APP_MOBILE', 60),
        ('WEB_BANKING', 20),
        ('ATM', 10),
        ('AGENCIA', 5),
        ('API_PARCEIRO', 5),
    ]
    
    # Tipos de conta
    ACCOUNT_TYPES = ['CORRENTE', 'POUPANCA', 'SALARIO', 'PAGAMENTO', 'DIGITAL']
    
    # Estados brasileiros com peso populacional
    ESTADOS = {
        'SP': 45.0, 'MG': 15.0, 'RJ': 12.0, 'BA': 6.0, 'RS': 5.0,
        'PR': 5.0, 'PE': 3.0, 'CE': 2.0, 'PA': 1.5, 'SC': 1.5,
        'GO': 1.0, 'MA': 0.8, 'PB': 0.5, 'ES': 0.5, 'AM': 0.5,
        'RN': 0.3, 'MT': 0.3, 'MS': 0.2, 'DF': 0.4, 'AL': 0.2,
        'PI': 0.2, 'SE': 0.1, 'RO': 0.1, 'TO': 0.1, 'AC': 0.05,
        'AP': 0.05, 'RR': 0.05,
    }
    
    # Fabricantes de dispositivos
    DEVICE_MANUFACTURERS = {
        'Samsung': 35, 'Apple': 25, 'Motorola': 20, 'Xiaomi': 10,
        'LG': 5, 'Asus': 3, 'Huawei': 2,
    }
    
    # Sistemas operacionais
    OPERATING_SYSTEMS = {
        'Android': {'versions': ['10', '11', '12', '13', '14'], 'weight': 70},
        'iOS': {'versions': ['15.0', '16.0', '17.0', '17.1'], 'weight': 30},
    }

    def bank_code(self) -> Tuple[str, str]:
        """Retorna código e nome do banco"""
        code = random.choice(list(self.BANK_CODES.keys()))
        return code, self.BANK_CODES[code]
    
    def account_number(self) -> str:
        """Gera número de conta realista"""
        return f"{random.randint(10000, 999999)}-{random.randint(0, 9)}"
    
    def agency_number(self) -> str:
        """Gera número de agência"""
        return f"{random.randint(1, 9999):04d}"
    
    def mcc_code(self) -> Tuple[str, str, str]:
        """Retorna MCC, descrição e nível de risco"""
        code = random.choice(list(self.MCC_CODES.keys()))
        desc, risk = self.MCC_CODES[code]
        return code, desc, risk
    
    def transaction_type(self) -> str:
        """Retorna tipo de transação baseado em probabilidade"""
        types, weights = zip(*self.TRANSACTION_TYPES)
        return random.choices(types, weights=weights)[0]
    
    def channel(self) -> str:
        """Retorna canal de origem"""
        channels, weights = zip(*self.CHANNELS)
        return random.choices(channels, weights=weights)[0]
    
    def estado(self) -> str:
        """Retorna estado baseado em população"""
        estados, weights = zip(*self.ESTADOS.items())
        return random.choices(list(estados), weights=list(weights))[0]
    
    def pix_key_type(self) -> str:
        """Tipo de chave PIX"""
        return random.choice(['CPF', 'EMAIL', 'TELEFONE', 'ALEATORIA', 'CNPJ'])
    
    def device_fingerprint(self) -> str:
        """Gera fingerprint único de dispositivo"""
        return hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:32]
    
    def ip_address_brazil(self) -> str:
        """Gera IP brasileiro (ranges mais comuns)"""
        # Ranges de IPs brasileiros comuns
        prefixes = ['177.', '187.', '189.', '191.', '200.', '201.']
        prefix = random.choice(prefixes)
        return prefix + '.'.join(str(random.randint(0, 255)) for _ in range(3))
    
    def device_info(self) -> Dict:
        """Gera informações completas de dispositivo"""
        manufacturer = random.choices(
            list(self.DEVICE_MANUFACTURERS.keys()),
            weights=list(self.DEVICE_MANUFACTURERS.values())
        )[0]
        
        os_name = random.choices(
            list(self.OPERATING_SYSTEMS.keys()),
            weights=[v['weight'] for v in self.OPERATING_SYSTEMS.values()]
        )[0]
        os_version = random.choice(self.OPERATING_SYSTEMS[os_name]['versions'])
        
        return {
            'manufacturer': manufacturer,
            'os_name': os_name,
            'os_version': os_version,
        }


fake.add_provider(BrazilianBankingProvider)


# ============================================
# DATACLASSES PARA ESTRUTURA DOS DADOS
# ============================================

@dataclass
class Customer:
    """Estrutura completa de cliente"""
    # Identificação
    customer_id: str
    cpf: str
    rg: str
    nome_completo: str
    nome_social: str = None  # Para inclusão
    data_nascimento: str = None
    sexo: str = None
    estado_civil: str = None
    
    # Contato
    email: str = None
    telefone_celular: str = None
    telefone_fixo: str = None
    
    # Endereço
    cep: str = None
    logradouro: str = None
    numero: str = None
    complemento: str = None
    bairro: str = None
    cidade: str = None
    estado: str = None
    
    # Dados bancários
    banco_codigo: str = None
    banco_nome: str = None
    agencia: str = None
    conta: str = None
    tipo_conta: str = None
    
    # Profissional/Financeiro
    profissao: str = None
    renda_mensal: float = None
    score_credito: int = None
    limite_credito: float = None
    limite_pix_diario: float = None
    
    # Perfil de risco
    perfil_investidor: str = None
    pep: bool = False  # Pessoa Politicamente Exposta
    data_cadastro: str = None
    status: str = 'ATIVO'
    nivel_verificacao: str = None  # KYC level
    
    # Flags de comportamento
    is_premium: bool = False
    aceita_marketing: bool = True
    biometria_facial: bool = False
    token_ativo: bool = False


@dataclass
class Device:
    """Dispositivo vinculado ao cliente"""
    device_id: str
    customer_id: str
    device_fingerprint: str
    manufacturer: str
    model: str
    os_name: str
    os_version: str
    app_version: str
    screen_resolution: str
    is_rooted: bool
    is_emulator: bool
    first_seen: str
    last_seen: str
    is_trusted: bool
    risk_score: int


@dataclass
class Session:
    """Sessão/Login do usuário"""
    session_id: str
    customer_id: str
    device_id: str
    ip_address: str
    ip_country: str
    ip_city: str
    ip_isp: str
    user_agent: str
    login_timestamp: str
    logout_timestamp: str = None
    session_duration_seconds: int = None
    login_method: str = None  # SENHA, BIOMETRIA, TOKEN
    login_success: bool = True
    failed_attempts_before: int = 0
    is_vpn: bool = False
    is_tor: bool = False
    risk_flags: List[str] = None


@dataclass
class Transaction:
    """Transação financeira completa"""
    # Identificação
    transaction_id: str
    customer_id: str
    session_id: str = None
    device_id: str = None
    
    # Dados da transação
    timestamp: str = None
    tipo: str = None  # PIX, CARTAO_CREDITO, etc
    valor: float = None
    moeda: str = 'BRL'
    
    # Origem
    canal: str = None
    ip_address: str = None
    geolocalizacao_lat: float = None
    geolocalizacao_lon: float = None
    
    # Comerciante/Destino
    merchant_id: str = None
    merchant_name: str = None
    merchant_category: str = None
    mcc_code: str = None
    mcc_risk_level: str = None
    
    # Dados específicos de cartão
    numero_cartao_hash: str = None
    bandeira: str = None
    tipo_cartao: str = None  # CREDITO, DEBITO
    parcelas: int = None
    entrada_cartao: str = None  # CHIP, CONTACTLESS, DIGITADO, ECOMMERCE
    cvv_validado: bool = None
    autenticacao_3ds: bool = None
    
    # Dados PIX
    chave_pix_tipo: str = None
    chave_pix_destino: str = None
    banco_destino: str = None
    
    # Contexto de risco
    distancia_ultima_transacao_km: float = None
    tempo_desde_ultima_transacao_min: int = None
    transacoes_ultimas_24h: int = None
    valor_acumulado_24h: float = None
    horario_incomum: bool = False
    novo_beneficiario: bool = False
    
    # Resultado
    status: str = 'APROVADA'
    motivo_recusa: str = None
    fraud_score: float = None
    is_fraud: bool = False
    fraud_type: str = None


# ============================================
# GERADORES
# ============================================

def generate_customer(customer_id: int) -> Customer:
    """Gera um cliente brasileiro completo"""
    
    # Dados básicos
    sexo = random.choice(['M', 'F'])
    if sexo == 'M':
        nome = fake.name_male()
    else:
        nome = fake.name_female()
    
    # Renda baseada em distribuição realista brasileira
    renda_base = random.choices(
        [1500, 3000, 5000, 10000, 20000, 50000],
        weights=[40, 30, 15, 10, 4, 1]
    )[0]
    renda = renda_base * random.uniform(0.8, 1.5)
    
    # Score de crédito (300-850)
    score = int(random.gauss(650, 100))
    score = max(300, min(850, score))
    
    # Limite de crédito baseado na renda
    limite_credito = renda * random.uniform(2, 8)
    
    # Data de nascimento (18-80 anos)
    idade = random.randint(18, 80)
    data_nasc = fake.date_of_birth(minimum_age=idade, maximum_age=idade)
    
    # Endereço
    estado = fake.estado()
    
    # Verificação KYC
    nivel_kyc = random.choices(
        ['BASICO', 'INTERMEDIARIO', 'COMPLETO'],
        weights=[20, 50, 30]
    )[0]
    
    # Banco
    banco_codigo, banco_nome = fake.bank_code()
    
    return Customer(
        customer_id=f"CUST_{customer_id:08d}",
        cpf=fake.cpf(),
        rg=f"{random.randint(10, 99)}.{random.randint(100, 999)}.{random.randint(100, 999)}-{random.randint(0, 9)}",
        nome_completo=nome,
        nome_social=nome.split()[0] if random.random() < 0.1 else None,
        data_nascimento=str(data_nasc),
        sexo=sexo,
        estado_civil=random.choice(['SOLTEIRO', 'CASADO', 'DIVORCIADO', 'VIUVO', 'UNIAO_ESTAVEL']),
        email=fake.email(),
        telefone_celular=fake.cellphone_number(),
        telefone_fixo=fake.phone_number() if random.random() < 0.3 else None,
        cep=fake.postcode(),
        logradouro=fake.street_name(),
        numero=str(random.randint(1, 9999)),
        complemento=random.choice(['', 'Apto 101', 'Bloco A', 'Casa 2', 'Sala 305']) if random.random() < 0.4 else None,
        bairro=fake.bairro(),
        cidade=fake.city(),
        estado=estado,
        banco_codigo=banco_codigo,
        banco_nome=banco_nome,
        agencia=fake.agency_number(),
        conta=fake.account_number(),
        tipo_conta=random.choice(['CORRENTE', 'POUPANCA', 'SALARIO', 'DIGITAL']),
        profissao=fake.job(),
        renda_mensal=round(renda, 2),
        score_credito=score,
        limite_credito=round(limite_credito, 2),
        limite_pix_diario=round(random.uniform(1000, 20000), 2),
        perfil_investidor=random.choice(['CONSERVADOR', 'MODERADO', 'ARROJADO', 'AGRESSIVO']),
        pep=random.random() < 0.005,  # 0.5% são PEP
        data_cadastro=str(fake.date_between(start_date='-5y', end_date='today')),
        status=random.choices(['ATIVO', 'INATIVO', 'BLOQUEADO', 'SUSPENSO'], weights=[90, 5, 3, 2])[0],
        nivel_verificacao=nivel_kyc,
        is_premium=random.random() < 0.15,
        aceita_marketing=random.random() < 0.7,
        biometria_facial=random.random() < 0.4,
        token_ativo=random.random() < 0.6,
    )


def generate_device(device_id: int, customer_id: str) -> Device:
    """Gera um dispositivo vinculado ao cliente"""
    
    device_info = fake.device_info()
    
    # Modelos por fabricante
    models = {
        'Samsung': ['Galaxy S23', 'Galaxy S22', 'Galaxy A54', 'Galaxy A34', 'Galaxy M54'],
        'Apple': ['iPhone 15', 'iPhone 14', 'iPhone 13', 'iPhone 12', 'iPhone SE'],
        'Motorola': ['Moto G84', 'Moto G54', 'Edge 40', 'Moto G73', 'Razr 40'],
        'Xiaomi': ['Redmi Note 12', 'Poco X5', 'Redmi 12', 'Mi 13', 'Poco F5'],
        'LG': ['K62', 'K52', 'K42', 'Velvet', 'Wing'],
        'Asus': ['ROG Phone 7', 'Zenfone 10', 'ROG Phone 6', 'Zenfone 9'],
        'Huawei': ['P60', 'Mate 50', 'Nova 11', 'P50', 'Nova 10'],
    }
    
    first_seen = fake.date_time_between(start_date='-2y', end_date='-30d')
    last_seen = fake.date_time_between(start_date=first_seen, end_date='now')
    
    return Device(
        device_id=f"DEV_{device_id:08d}",
        customer_id=customer_id,
        device_fingerprint=fake.device_fingerprint(),
        manufacturer=device_info['manufacturer'],
        model=random.choice(models.get(device_info['manufacturer'], ['Unknown'])),
        os_name=device_info['os_name'],
        os_version=device_info['os_version'],
        app_version=f"{random.randint(1, 5)}.{random.randint(0, 99)}.{random.randint(0, 999)}",
        screen_resolution=random.choice(['1080x1920', '1440x2560', '1080x2400', '1284x2778']),
        is_rooted=random.random() < 0.02,  # 2% rootados
        is_emulator=random.random() < 0.01,  # 1% emuladores
        first_seen=first_seen.isoformat(),
        last_seen=last_seen.isoformat(),
        is_trusted=random.random() < 0.8,
        risk_score=random.randint(0, 100),
    )


def generate_session(
    session_id: int, 
    customer_id: str, 
    device_id: str,
    timestamp: datetime
) -> Session:
    """Gera uma sessão de login"""
    
    login_ts = timestamp
    duration = random.randint(60, 7200)  # 1min a 2h
    logout_ts = login_ts + timedelta(seconds=duration)
    
    # IP brasileiro
    ip = fake.ip_address_brazil()
    
    # Detecção de VPN/TOR (raro em usuários legítimos)
    is_vpn = random.random() < 0.05
    is_tor = random.random() < 0.01
    
    # Método de login
    login_method = random.choices(
        ['SENHA', 'BIOMETRIA', 'TOKEN', 'FACE_ID'],
        weights=[40, 35, 15, 10]
    )[0]
    
    # Falhas antes do sucesso
    failed_attempts = 0 if random.random() < 0.9 else random.randint(1, 3)
    
    risk_flags = []
    if is_vpn:
        risk_flags.append('VPN_DETECTED')
    if is_tor:
        risk_flags.append('TOR_DETECTED')
    if failed_attempts > 2:
        risk_flags.append('MULTIPLE_FAILED_ATTEMPTS')
    
    return Session(
        session_id=f"SESS_{session_id:012d}",
        customer_id=customer_id,
        device_id=device_id,
        ip_address=ip,
        ip_country='BR',
        ip_city=fake.city(),
        ip_isp=random.choice(['Vivo', 'Claro', 'TIM', 'Oi', 'NET', 'Brisanet', 'Algar']),
        user_agent=fake.user_agent(),
        login_timestamp=login_ts.isoformat(),
        logout_timestamp=logout_ts.isoformat(),
        session_duration_seconds=duration,
        login_method=login_method,
        login_success=True,
        failed_attempts_before=failed_attempts,
        is_vpn=is_vpn,
        is_tor=is_tor,
        risk_flags=risk_flags if risk_flags else None,
    )


def generate_transaction(
    tx_id: int,
    customer: Customer,
    device_id: str,
    session_id: str,
    timestamp: datetime,
    last_tx_timestamp: datetime = None,
    last_tx_lat: float = None,
    last_tx_lon: float = None,
    tx_count_24h: int = 0,
    valor_acumulado_24h: float = 0.0,
    is_fraud: bool = False,
    fraud_type: str = None,
) -> Transaction:
    """Gera uma transação financeira completa"""
    
    # Tipo e canal
    tipo = fake.transaction_type()
    canal = fake.channel()
    
    # MCC
    mcc_code, mcc_desc, mcc_risk = fake.mcc_code()
    
    # Valor baseado no tipo e perfil do cliente
    if tipo == 'PIX':
        valor_base = random.choices([50, 200, 500, 1000, 5000], weights=[40, 30, 15, 10, 5])[0]
    elif tipo in ['CARTAO_CREDITO', 'CARTAO_DEBITO']:
        valor_base = random.choices([30, 100, 300, 800, 2000], weights=[35, 30, 20, 10, 5])[0]
    elif tipo == 'TED':
        valor_base = random.choices([500, 2000, 5000, 15000, 50000], weights=[30, 30, 20, 15, 5])[0]
    else:
        valor_base = random.choices([100, 500, 1000, 3000], weights=[40, 30, 20, 10])[0]
    
    valor = valor_base * random.uniform(0.5, 2.0)
    
    # Fraude aumenta valor
    if is_fraud:
        valor = valor * random.uniform(2, 10)
    
    # Geolocalização brasileira
    lat = random.uniform(-33.75, 5.27)
    lon = random.uniform(-73.99, -34.79)
    
    # Distância da última transação
    distancia_km = None
    tempo_min = None
    if last_tx_timestamp and last_tx_lat and last_tx_lon:
        # Cálculo simplificado de distância
        distancia_km = ((lat - last_tx_lat)**2 + (lon - last_tx_lon)**2)**0.5 * 111
        tempo_min = int((timestamp - last_tx_timestamp).total_seconds() / 60)
    
    # Horário incomum (23h - 5h)
    hora = timestamp.hour
    horario_incomum = hora >= 23 or hora <= 5
    
    # Novo beneficiário (30% das transações PIX)
    novo_beneficiario = tipo == 'PIX' and random.random() < 0.3
    
    # Dados específicos de cartão
    numero_cartao_hash = None
    bandeira = None
    tipo_cartao = None
    parcelas = None
    entrada_cartao = None
    cvv_validado = None
    autenticacao_3ds = None
    
    if tipo in ['CARTAO_CREDITO', 'CARTAO_DEBITO']:
        numero_cartao_hash = hashlib.sha256(f"{customer.customer_id}_{random.randint(1,3)}".encode()).hexdigest()[:16]
        bandeira = random.choice(['VISA', 'MASTERCARD', 'ELO', 'AMEX', 'HIPERCARD'])
        tipo_cartao = 'CREDITO' if tipo == 'CARTAO_CREDITO' else 'DEBITO'
        parcelas = random.choices([1, 2, 3, 6, 10, 12], weights=[50, 15, 15, 10, 5, 5])[0] if tipo == 'CARTAO_CREDITO' else 1
        entrada_cartao = random.choices(
            ['CHIP', 'CONTACTLESS', 'DIGITADO', 'ECOMMERCE'],
            weights=[30, 25, 15, 30]
        )[0]
        cvv_validado = entrada_cartao in ['DIGITADO', 'ECOMMERCE']
        autenticacao_3ds = entrada_cartao == 'ECOMMERCE' and random.random() < 0.6
    
    # Dados PIX
    chave_pix_tipo = None
    chave_pix_destino = None
    banco_destino = None
    
    # Lista de códigos de banco
    bank_codes = ['001', '033', '104', '237', '341', '260', '077', '336', '290', '380', '323', '403', '212']
    
    if tipo == 'PIX':
        chave_pix_tipo = fake.pix_key_type()
        if chave_pix_tipo == 'CPF':
            chave_pix_destino = fake.cpf()
        elif chave_pix_tipo == 'EMAIL':
            chave_pix_destino = fake.email()
        elif chave_pix_tipo == 'TELEFONE':
            chave_pix_destino = fake.cellphone_number()
        else:
            chave_pix_destino = str(uuid.uuid4())
        banco_destino = random.choice(bank_codes)
    
    # Fraud score (0-100)
    fraud_score = random.uniform(0, 30)
    if is_fraud:
        fraud_score = random.uniform(70, 100)
    elif horario_incomum:
        fraud_score += 10
    elif mcc_risk == 'high':
        fraud_score += 15
    elif novo_beneficiario:
        fraud_score += 5
    
    # Status
    if is_fraud and random.random() < 0.3:  # 30% das fraudes são detectadas
        status = 'BLOQUEADA'
        motivo = 'SUSPEITA_FRAUDE'
    elif valor > customer.limite_credito and tipo == 'CARTAO_CREDITO':
        status = 'RECUSADA'
        motivo = 'LIMITE_EXCEDIDO'
    elif random.random() < 0.02:  # 2% de recusas aleatórias
        status = 'RECUSADA'
        motivo = random.choice(['SALDO_INSUFICIENTE', 'CARTAO_BLOQUEADO', 'ERRO_COMUNICACAO'])
    else:
        status = 'APROVADA'
        motivo = None
    
    # Merchant
    merchant_names = [
        'Supermercado Extra', 'Carrefour', 'Magazine Luiza', 'Americanas',
        'iFood', 'Uber', '99', 'Shell', 'BR Distribuidora', 'Riachuelo',
        'Renner', 'C&A', 'Drogasil', 'Pague Menos', 'Netflix', 'Spotify',
        'Amazon', 'Mercado Livre', 'Shopee', 'AliExpress', 'Shein',
        'Restaurante Popular', 'Padaria Central', 'Bar do Zé', 'Hotel Ibis',
        'Posto Ipiranga', 'Posto BR', 'Lojas Americanas', 'Casas Bahia',
    ]
    
    return Transaction(
        transaction_id=f"TXN_{tx_id:015d}",
        customer_id=customer.customer_id,
        session_id=session_id,
        device_id=device_id,
        timestamp=timestamp.isoformat(),
        tipo=tipo,
        valor=round(valor, 2),
        moeda='BRL',
        canal=canal,
        ip_address=fake.ip_address_brazil(),
        geolocalizacao_lat=round(lat, 6),
        geolocalizacao_lon=round(lon, 6),
        merchant_id=f"MERCH_{random.randint(1, 100000):06d}",
        merchant_name=random.choice(merchant_names),
        merchant_category=mcc_desc,
        mcc_code=mcc_code,
        mcc_risk_level=mcc_risk,
        numero_cartao_hash=numero_cartao_hash,
        bandeira=bandeira,
        tipo_cartao=tipo_cartao,
        parcelas=parcelas,
        entrada_cartao=entrada_cartao,
        cvv_validado=cvv_validado,
        autenticacao_3ds=autenticacao_3ds,
        chave_pix_tipo=chave_pix_tipo,
        chave_pix_destino=chave_pix_destino,
        banco_destino=banco_destino,
        distancia_ultima_transacao_km=round(distancia_km, 2) if distancia_km else None,
        tempo_desde_ultima_transacao_min=tempo_min,
        transacoes_ultimas_24h=tx_count_24h,
        valor_acumulado_24h=round(valor_acumulado_24h, 2),
        horario_incomum=horario_incomum,
        novo_beneficiario=novo_beneficiario,
        status=status,
        motivo_recusa=motivo,
        fraud_score=round(fraud_score, 2),
        is_fraud=is_fraud,
        fraud_type=fraud_type,
    )


# ============================================
# GERAÇÃO EM LOTE
# ============================================

def generate_and_save_customers(num_customers: int, output_path: str) -> List[Customer]:
    """Gera e salva clientes"""
    print(f"🧑 Gerando {num_customers:,} clientes...")
    
    customers = []
    with open(output_path, 'w', encoding='utf-8') as f:
        for i in range(1, num_customers + 1):
            customer = generate_customer(i)
            customers.append(customer)
            json_line = json.dumps(asdict(customer), ensure_ascii=False)
            f.write(json_line + '\n')
            
            if i % 10000 == 0:
                print(f"  ✓ {i:,} clientes gerados")
    
    print(f"  ✅ {num_customers:,} clientes salvos em {output_path}")
    return customers


def generate_and_save_devices(customers: List[Customer], devices_per_customer: int, output_path: str) -> Dict[str, List[Device]]:
    """Gera e salva dispositivos"""
    print(f"📱 Gerando dispositivos ({devices_per_customer}-{devices_per_customer+2} por cliente)...")
    
    customer_devices = {}
    device_id = 1
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for customer in customers:
            num_devices = random.randint(devices_per_customer, devices_per_customer + 2)
            devices = []
            
            for _ in range(num_devices):
                device = generate_device(device_id, customer.customer_id)
                devices.append(device)
                json_line = json.dumps(asdict(device), ensure_ascii=False)
                f.write(json_line + '\n')
                device_id += 1
            
            customer_devices[customer.customer_id] = devices
            
            if device_id % 50000 == 0:
                print(f"  ✓ {device_id:,} dispositivos gerados")
    
    print(f"  ✅ {device_id-1:,} dispositivos salvos em {output_path}")
    return customer_devices


def generate_transactions_batch(
    batch_num: int,
    customers: List[Customer],
    customer_devices: Dict[str, List[Device]],
    transactions_per_batch: int,
    start_date: datetime,
    end_date: datetime,
    fraud_rate: float = 0.007,  # 0.7% de fraude
) -> str:
    """Gera um lote de transações e retorna o caminho do arquivo"""
    
    output_path = os.path.join(OUTPUT_DIR, f'transactions_batch_{batch_num:04d}.json')
    
    fraud_types = [
        'CARTAO_CLONADO', 'CONTA_TOMADA', 'IDENTIDADE_FALSA',
        'ENGENHARIA_SOCIAL', 'LAVAGEM_DINHEIRO', 'AUTOTRAUDE',
        'FRAUDE_AMIGAVEL', 'TRIANGULACAO',
    ]
    
    session_id = batch_num * 1000000
    tx_id_start = batch_num * transactions_per_batch
    
    with open(output_path, 'w', encoding='utf-8') as f:
        for i in range(transactions_per_batch):
            tx_id = tx_id_start + i + 1
            
            # Seleciona cliente aleatório
            customer = random.choice(customers)
            
            # Seleciona dispositivo do cliente
            devices = customer_devices.get(customer.customer_id, [])
            device = random.choice(devices) if devices else None
            # Suporta tanto objeto Device quanto dict
            if device:
                device_id = device.device_id if hasattr(device, 'device_id') else device.get('device_id')
            else:
                device_id = None
            
            # Timestamp aleatório no período
            timestamp = fake.date_time_between(start_date=start_date, end_date=end_date)
            
            # Determina se é fraude
            is_fraud = random.random() < fraud_rate
            fraud_type = random.choice(fraud_types) if is_fraud else None
            
            # Gera transação
            tx = generate_transaction(
                tx_id=tx_id,
                customer=customer,
                device_id=device_id,
                session_id=f"SESS_{session_id + i:012d}",
                timestamp=timestamp,
                tx_count_24h=random.randint(0, 20),
                valor_acumulado_24h=random.uniform(0, 5000),
                is_fraud=is_fraud,
                fraud_type=fraud_type,
            )
            
            json_line = json.dumps(asdict(tx), ensure_ascii=False)
            f.write(json_line + '\n')
    
    return output_path


def estimate_size_gb(num_transactions: int) -> float:
    """Estima tamanho em GB baseado no número de transações"""
    # Cada transação JSON tem aproximadamente 1.5KB
    bytes_per_tx = 1500
    return (num_transactions * bytes_per_tx) / (1024**3)


def transactions_for_size_gb(target_gb: float) -> int:
    """Calcula quantas transações para atingir o tamanho"""
    bytes_per_tx = 1500
    return int((target_gb * (1024**3)) / bytes_per_tx)


# ============================================
# FUNÇÃO PRINCIPAL
# ============================================

def main():
    """Função principal de geração"""
    import argparse
    import glob
    
    parser = argparse.ArgumentParser(description='Gerador de dados brasileiros para detecção de fraude')
    parser.add_argument('--size', type=str, default='1GB', 
                       help='Tamanho alvo: 1GB, 10GB, 50GB ou número de transações')
    parser.add_argument('--customers', type=int, default=100000,
                       help='Número de clientes (padrão: 100000)')
    parser.add_argument('--output', type=str, default=OUTPUT_DIR,
                       help='Diretório de saída')
    parser.add_argument('--fraud-rate', type=float, default=0.007,
                       help='Taxa de fraude (padrão: 0.7%%)')
    parser.add_argument('--batch-size', type=int, default=1000000,
                       help='Transações por arquivo (padrão: 1M)')
    parser.add_argument('--resume', action='store_true',
                       help='Continuar geração de onde parou')
    
    args = parser.parse_args()
    
    # Parse tamanho
    size_str = args.size.upper()
    if 'GB' in size_str:
        target_gb = float(size_str.replace('GB', ''))
        num_transactions = transactions_for_size_gb(target_gb)
    else:
        num_transactions = int(args.size)
        target_gb = estimate_size_gb(num_transactions)
    
    print("=" * 60)
    print("🇧🇷 GERADOR DE DADOS BRASILEIROS PARA FRAUDE")
    print("=" * 60)
    print(f"📊 Configuração:")
    print(f"   • Clientes: {args.customers:,}")
    print(f"   • Transações: {num_transactions:,}")
    print(f"   • Tamanho estimado: {target_gb:.1f} GB")
    print(f"   • Taxa de fraude: {args.fraud_rate*100:.1f}%")
    print(f"   • Diretório: {args.output}")
    print("=" * 60)
    
    # Criar diretório
    os.makedirs(args.output, exist_ok=True)
    
    # Período de dados (últimos 2 anos)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=730)
    
    # Verificar se deve continuar de onde parou
    start_batch = 0
    if args.resume:
        # Encontrar batches existentes
        existing_batches = sorted(glob.glob(os.path.join(args.output, 'transactions_batch_*.json')))
        if existing_batches:
            # Verificar último batch e remover se incompleto
            last_batch_file = existing_batches[-1]
            last_batch_num = int(last_batch_file.split('_')[-1].replace('.json', ''))
            
            # Verificar se último batch está completo (tamanho esperado ~2GB para 1M transações)
            last_size = os.path.getsize(last_batch_file) / (1024**3)
            expected_size = (args.batch_size / 1000000) * 2  # ~2GB por 1M transações
            
            if last_size < expected_size * 0.9:  # Se menor que 90% do esperado, está incompleto
                print(f"⚠️  Removendo batch incompleto: {last_batch_file} ({last_size:.2f}GB < {expected_size:.2f}GB)")
                os.remove(last_batch_file)
                start_batch = last_batch_num
            else:
                start_batch = last_batch_num + 1
                
            print(f"🔄 Continuando do batch {start_batch}...")
    
    # 1. Gerar ou carregar clientes
    customers_path = os.path.join(args.output, 'customers.json')
    if args.resume and os.path.exists(customers_path):
        print(f"📂 Carregando clientes existentes de {customers_path}...")
        with open(customers_path, 'r') as f:
            customers_data = [json.loads(line) for line in f]
        # Converter para objetos Customer (lista, não dict)
        customers = []
        for c in customers_data:
            cust = Customer(
                customer_id=c['customer_id'],
                cpf=c['cpf'],
                rg=c.get('rg', ''),
                nome_completo=c['nome_completo'],
                nome_social=c.get('nome_social'),
                data_nascimento=c.get('data_nascimento'),
                sexo=c.get('sexo', 'M'),
                estado_civil=c.get('estado_civil'),
                email=c.get('email'),
                telefone_celular=c.get('telefone_celular'),
                telefone_fixo=c.get('telefone_fixo'),
                cep=c.get('cep'),
                logradouro=c.get('logradouro'),
                numero=c.get('numero'),
                complemento=c.get('complemento'),
                bairro=c.get('bairro'),
                cidade=c.get('cidade'),
                estado=c.get('estado'),
                banco_codigo=c.get('banco_codigo'),
                banco_nome=c.get('banco_nome'),
                agencia=c.get('agencia'),
                conta=c.get('conta'),
                tipo_conta=c.get('tipo_conta'),
                profissao=c.get('profissao'),
                renda_mensal=c.get('renda_mensal', 0),
                score_credito=c.get('score_credito', 500),
                limite_credito=c.get('limite_credito', 0),
                limite_pix_diario=c.get('limite_pix_diario', 0),
                perfil_investidor=c.get('perfil_investidor'),
                pep=c.get('pep', False),
                data_cadastro=c.get('data_cadastro'),
                status=c.get('status', 'ATIVO'),
                nivel_verificacao=c.get('nivel_verificacao'),
                is_premium=c.get('is_premium', False),
                aceita_marketing=c.get('aceita_marketing', True),
                biometria_facial=c.get('biometria_facial', False),
                token_ativo=c.get('token_ativo', False),
            )
            customers.append(cust)
        print(f"   ✓ {len(customers):,} clientes carregados")
    else:
        customers = generate_and_save_customers(args.customers, customers_path)
    
    # 2. Gerar ou carregar dispositivos
    devices_path = os.path.join(args.output, 'devices.json')
    if args.resume and os.path.exists(devices_path):
        print(f"📂 Carregando dispositivos existentes de {devices_path}...")
        with open(devices_path, 'r') as f:
            devices_data = [json.loads(line) for line in f]
        customer_devices = {}
        for d in devices_data:
            cust_id = d['customer_id']
            if cust_id not in customer_devices:
                customer_devices[cust_id] = []
            customer_devices[cust_id].append(d)
        print(f"   ✓ {len(devices_data):,} dispositivos carregados")
    else:
        customer_devices = generate_and_save_devices(customers, devices_per_customer=2, output_path=devices_path)
    
    # 3. Gerar transações em lotes
    print(f"\n💳 Gerando {num_transactions:,} transações...")
    
    num_batches = (num_transactions + args.batch_size - 1) // args.batch_size
    transactions_remaining = num_transactions - (start_batch * args.batch_size)
    
    if start_batch > 0:
        print(f"   ⏭️  Pulando {start_batch} batches já gerados ({start_batch * args.batch_size:,} transações)")
    
    # Tracking de tempo para estimativa
    import time
    batch_times = []
    generation_start = time.time()
    
    for batch_num in range(start_batch, num_batches):
        batch_start = time.time()
        batch_size = min(args.batch_size, transactions_remaining)
        
        # Calcular progresso
        batches_done = batch_num - start_batch
        total_batches_to_do = num_batches - start_batch
        progress_pct = (batches_done / total_batches_to_do) * 100 if total_batches_to_do > 0 else 0
        
        # Calcular tempo estimado
        if batch_times:
            avg_time_per_batch = sum(batch_times) / len(batch_times)
            batches_remaining = num_batches - batch_num
            eta_seconds = avg_time_per_batch * batches_remaining
            eta_str = f"ETA: {int(eta_seconds // 3600)}h {int((eta_seconds % 3600) // 60)}m"
        else:
            eta_str = "ETA: calculando..."
        
        # Barra de progresso visual
        bar_width = 30
        filled = int(bar_width * progress_pct / 100)
        bar = '█' * filled + '░' * (bar_width - filled)
        
        print(f"\n  [{bar}] {progress_pct:5.1f}% | Lote {batch_num + 1}/{num_batches} | {eta_str}")
        print(f"  📦 Gerando {batch_size:,} transações...")
        
        output_file = generate_transactions_batch(
            batch_num=batch_num,
            customers=customers,
            customer_devices=customer_devices,
            transactions_per_batch=batch_size,
            start_date=start_date,
            end_date=end_date,
            fraud_rate=args.fraud_rate,
        )
        
        transactions_remaining -= batch_size
        
        # Registrar tempo do batch
        batch_elapsed = time.time() - batch_start
        batch_times.append(batch_elapsed)
        
        # Mostra tamanho do arquivo e velocidade
        file_size = os.path.getsize(output_file) / (1024**3)
        speed = batch_size / batch_elapsed if batch_elapsed > 0 else 0
        print(f"     ✅ Salvo: {os.path.basename(output_file)} ({file_size:.2f} GB) em {batch_elapsed:.1f}s ({speed:,.0f} tx/s)")
    
    # Tempo total
    total_elapsed = time.time() - generation_start
    print(f"\n  ⏱️  Tempo total de geração: {int(total_elapsed // 3600)}h {int((total_elapsed % 3600) // 60)}m {int(total_elapsed % 60)}s")
    
    # Sumário final
    print("\n" + "=" * 60)
    print("✅ GERAÇÃO CONCLUÍDA!")
    print("=" * 60)
    
    # Calcula tamanho total
    total_size = 0
    for f in os.listdir(args.output):
        if f.endswith('.json'):
            total_size += os.path.getsize(os.path.join(args.output, f))
    
    print(f"📁 Arquivos gerados em: {args.output}")
    print(f"📊 Tamanho total: {total_size / (1024**3):.2f} GB")
    print(f"🧑 Clientes: {len(customers):,}")
    print(f"📱 Dispositivos: {sum(len(d) for d in customer_devices.values()):,}")
    print(f"💳 Transações: {num_transactions:,}")
    print(f"🚨 Fraudes estimadas: {int(num_transactions * args.fraud_rate):,}")


if __name__ == '__main__':
    main()
