# 🎲 ShadowTraffic - Gerador de Dados de Fraude

## 📋 Configuração: `transactions_50m_final.json`

### Especificações dos Dados

| Parâmetro | Valor | Descrição |
|-----------|-------|-----------|
| **Total de Eventos** | 50.000.000 | 50 milhões de transações |
| **Pool de Clientes** | 10.000 | `CLIENTE_00001` a `CLIENTE_10000` |
| **Pool de Cartões** | 50.000 | `CARD_000001` a `CARD_050000` |
| **Pool de Devices** | 100.000 | `DEVICE_00000001` a `DEVICE_00100000` |
| **Média tx/cliente** | ~5.000 | 50M / 10K clientes |
| **Taxa de Fraude** | 5% | ~2.5M transações fraudulentas |

### Campos Novos Adicionados

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `customer_age` | int (18-85) | Idade do cliente |
| `card_number_hash` | string | Hash do cartão (pool fixo) |
| `ip_country` | string | País do IP (92% Brasil, 8% outros) |
| `session_id` | string | ID da sessão de navegação |

### Distribuição dos Valores (`amount`)

| Faixa | Peso | Média | Descrição |
|-------|------|-------|-----------|
| Baixo | 60% | R$ 150 | Compras do dia-a-dia |
| Médio | 25% | R$ 500 | Compras normais |
| Alto | 10% | R$ 1.500 | Compras maiores |
| Muito Alto | 3% | R$ 3K-8K | Compras especiais |
| Extremo | 2% | R$ 8K-25K | Compras de luxo |

### Categorias de Alto Risco (para fraude)

- `electronics` (4%) - Eletrônicos
- `jewelry` (2%) - Joias
- `airline_ticket` (5%) - Passagens aéreas

## 🚀 Como Executar

### 1. Iniciar ShadowTraffic

```bash
cd /home/ubuntu/Estudos/1_projeto_bank_Fraud_detection_data_pipeline

# Executar com licença
docker run --rm \
  --network fraud_detection_network \
  -v $(pwd)/shadowtraffic:/shadowtraffic \
  --env-file shadowtraffic/license.env \
  shadowtraffic/shadowtraffic:latest \
  --config /shadowtraffic/transactions_50m_final.json \
  --watch false
```

### 2. Monitorar Progresso

```bash
# Ver mensagens no Kafka
docker exec fraud_kafka kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic transactions \
  --from-beginning \
  --max-messages 10

# Contar mensagens
docker exec fraud_kafka kafka-run-class kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 \
  --topic transactions
```

### 3. Tempo Estimado

| Velocidade | Tempo para 50M |
|------------|----------------|
| 10.000/s | ~1h 23min |
| 50.000/s | ~17min |
| 100.000/s | ~8min |

> O ShadowTraffic sem throttle pode gerar ~50-100K eventos/segundo

## 📊 Comparação: Dados Anteriores vs Novos

| Aspecto | Antes | Agora |
|---------|-------|-------|
| `customer_id` | UUID único | Pool de 10K clientes |
| Tx por cliente | 1 | ~5.000 (média) |
| `card_number_hash` | ❌ Não tinha | ✅ Pool de 50K |
| `customer_age` | ❌ Não tinha | ✅ 18-85 anos |
| `ip_country` | ❌ Não tinha | ✅ Com distribuição |
| `session_id` | ❌ Não tinha | ✅ Pool de 1M |
| Cenários de fraude | Aleatório | 5% controlado |

## 🔍 Por que essas mudanças?

### 1. Pool Fixo de Clientes
```
ANTES: customer_id = UUID (único por transação)
       → Impossível detectar padrões de comportamento

AGORA: customer_id = CLIENTE_00001 a CLIENTE_10000
       → Cada cliente tem ~5000 transações
       → Permite detectar: clonagem, velocidade impossível, etc.
```

### 2. Card Number Hash
```
ANTES: Não existia
       → Não conseguia rastrear uso do mesmo cartão

AGORA: card_number_hash = CARD_000001 a CARD_050000
       → Mesmo cartão usado por múltiplas transações
       → Permite detectar: clonagem de cartão específico
```

### 3. Timestamps Sequenciais
```
O ShadowTraffic usa "_gen": "now" que gera timestamps sequenciais.
Combinado com o pool de clientes, permite:
- Calcular velocidade entre compras do mesmo cliente
- Detectar padrões temporais de fraude
```

## 🎯 Regras de Fraude que Agora Funcionam

| Regra | Antes | Agora | Por quê? |
|-------|-------|-------|----------|
| Clonagem de Cartão | ❌ | ✅ | Mesmo cliente, múltiplas tx |
| Velocidade Impossível | ❌ | ✅ | Timestamps sequenciais por cliente |
| Padrão de Compra | ❌ | ✅ | Histórico por cliente |
| Device Suspeito | ❌ | ✅ | Pool de devices |
| IP Estrangeiro | ❌ | ✅ | Campo ip_country |

## 📁 Arquivos na Pasta

| Arquivo | Descrição | Status |
|---------|-----------|--------|
| `transactions.json` | Config original | ⚠️ Legacy |
| `transactions_50m_final.json` | **Config otimizada** | ✅ Usar este |
| `customers.json` | Dados de clientes | OK |
| `license.env` | Licença ShadowTraffic | Necessário |
