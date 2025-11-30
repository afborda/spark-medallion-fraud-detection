# 📋 Documentação de Regras de Detecção de Fraude

> **Projeto:** Bank Fraud Detection Data Pipeline  
> **Versão:** 1.0  
> **Última Atualização:** Novembro 2025

---

## 📑 Índice

1. [Visão Geral](#visão-geral)
2. [Regras de Limpeza (Silver Layer)](#regras-de-limpeza-silver-layer)
3. [Flags de Comportamento Suspeito](#flags-de-comportamento-suspeito)
4. [Regras de Scoring de Fraude](#regras-de-scoring-de-fraude)
5. [Classificação de Nível de Risco](#classificação-de-nível-de-risco)
6. [Combinações Críticas](#combinações-críticas)
7. [Resumo das Regras por Camada](#resumo-das-regras-por-camada)

---

## Visão Geral

O sistema de detecção de fraudes utiliza uma arquitetura **Medallion** (Bronze → Silver → Gold) onde cada camada aplica regras específicas para identificar transações suspeitas.

### Fluxo de Processamento

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│    BRONZE       │ ──▶ │    SILVER       │ ──▶ │     GOLD        │
│  Dados Brutos   │     │ Limpeza + Flags │     │ Score + Risco   │
└─────────────────┘     └─────────────────┘     └─────────────────┘
```

---

## Regras de Limpeza (Silver Layer)

### 🧹 REGRA CLN-001: Remoção de Duplicatas por Transaction ID

| Atributo | Valor |
|----------|-------|
| **Nome da Regra** | Deduplicação de Transações |
| **Código** | `CLN-001` |
| **Camada** | Silver |
| **Campo Aplicado** | `transaction_id` |
| **Lógica** | `dropDuplicates(["transaction_id"])` |

**Por que essa regra existe?**

Transações duplicadas podem ocorrer por:
- **Falhas de comunicação**: Retry automático de sistemas que não receberam confirmação
- **Erro de integração**: Mensagens duplicadas no Kafka/filas
- **Reprocessamento**: Jobs Spark que são reexecutados sem tratamento idempotente

**Impacto se não aplicada:**
- Métricas financeiras inflacionadas (soma de valores duplicada)
- Contagem incorreta de transações por cliente
- Distorção da taxa de fraude

---

### 🧹 REGRA CLN-002: Validação de Campos Obrigatórios

| Atributo | Valor |
|----------|-------|
| **Nome da Regra** | Integridade de Dados Essenciais |
| **Código** | `CLN-002` |
| **Camada** | Silver |
| **Campos Aplicados** | `transaction_id`, `customer_id`, `amount` |
| **Lógica** | `dropna(subset=["transaction_id", "customer_id", "amount"])` |

**Por que essa regra existe?**

Uma transação sem esses campos é **inutilizável** para análise:
- **Sem `transaction_id`**: Impossível rastrear ou deduzir a transação
- **Sem `customer_id`**: Impossível identificar comportamento do cliente
- **Sem `amount`**: Impossível calcular métricas financeiras ou detectar valores anômalos

**Base em dados reais:**
- Segundo a indústria bancária, ~0.1-0.5% das transações chegam com campos nulos devido a timeouts ou erros de serialização

---

### 🧹 REGRA CLN-003: Correção de Valores Negativos

| Atributo | Valor |
|----------|-------|
| **Nome da Regra** | Normalização de Valores Monetários |
| **Código** | `CLN-003` |
| **Camada** | Silver |
| **Campo Aplicado** | `amount` |
| **Lógica** | `when(col("amount") < 0, spark_abs(col("amount"))).otherwise(col("amount"))` |

**Por que essa regra existe?**

Valores negativos em transações de compra indicam:
- **Erro de sinal**: Sistemas legados que usam convenção diferente (débito = negativo)
- **Estornos classificados errado**: Estornos que entraram como compra
- **Bug no gerador de dados**: Distribuição normal pode gerar valores negativos

**Tratamento:**
Convertemos para valor absoluto porque o contexto (transação de compra) implica que é uma saída de dinheiro, então o sinal não é relevante.

---

### 🧹 REGRA CLN-004: Filtro de Transações com Valor Zero

| Atributo | Valor |
|----------|-------|
| **Nome da Regra** | Exclusão de Transações Vazias |
| **Código** | `CLN-004` |
| **Camada** | Silver |
| **Campo Aplicado** | `amount` |
| **Lógica** | `filter(col("amount") > 0)` |

**Por que essa regra existe?**

Transações com valor zero não têm significado financeiro:
- **Testes de cartão**: Fraudadores testam se o cartão está ativo com R$ 0
- **Autorização de reserva**: Hotels/locadoras que apenas reservam limite
- **Erro de sistema**: Transações que falharam parcialmente

**Nota de segurança:** Embora transações de R$ 0 possam indicar teste de cartão por fraudadores, decidimos excluí-las pois não representam perda financeira direta.

---

### 🧹 REGRA CLN-005: Padronização de Texto

| Atributo | Valor |
|----------|-------|
| **Nome da Regra** | Normalização de Campos de Texto |
| **Código** | `CLN-005` |
| **Camada** | Silver |
| **Campos Aplicados** | `email`, `name`, `merchant`, `city` |
| **Lógica** | `trim()`, `lower()` para email |

**Por que essa regra existe?**

Dados textuais inconsistentes causam problemas de agregação:
- `"  Loja ABC  "` vs `"Loja ABC"` seriam tratados como merchants diferentes
- `"JOAO@EMAIL.COM"` vs `"joao@email.com"` seriam clientes diferentes

**Padronização aplicada:**
- **Email**: lowercase + trim (padrão universal)
- **Nome/Merchant/City**: trim (preserva capitalização original)

---

### 🧹 REGRA CLN-006: Remoção de Duplicatas de Cliente

| Atributo | Valor |
|----------|-------|
| **Nome da Regra** | Deduplicação de Clientes |
| **Código** | `CLN-006` |
| **Camada** | Silver |
| **Campo Aplicado** | `customer_id` |
| **Lógica** | `dropDuplicates(["customer_id"])` |

**Por que essa regra existe?**

Cadastros duplicados de clientes podem ocorrer por:
- Reprocessamento de eventos de cadastro
- Falha de idempotência no sistema de origem
- Merge de bases de dados com overlaps

---

## Flags de Comportamento Suspeito

As flags são criadas na camada **Silver** e representam indicadores individuais de comportamento potencialmente fraudulento.

### 🚩 FLAG FLG-001: Transação Cross-State

| Atributo | Valor |
|----------|-------|
| **Nome da Flag** | Compra em Estado Diferente do Domicílio |
| **Código** | `FLG-001` |
| **Campo Gerado** | `is_cross_state` |
| **Condição (Batch)** | `customer_home_state != purchase_state` AND `had_travel_purchase_last_12m == False` |
| **Condição (Streaming)** | `customer_home_state != purchase_state` |

**Por que essa flag existe?**

Estatísticas do setor bancário mostram que:
- **70-80% das fraudes** de cartão envolvem uso fora da região habitual do cliente
- Fraudadores tendem a usar cartões roubados em estados/cidades diferentes para dificultar rastreamento

**Refinamento:**
Na versão batch, consideramos também se o cliente tem histórico de viagens nos últimos 12 meses. Se ele costuma viajar, compras em outros estados são **esperadas** e não devem levantar flag.

**Percentual esperado:** ~15-25% das transações (dependendo do perfil da base)

---

### 🚩 FLAG FLG-002: Transação Noturna/Madrugada

| Atributo | Valor |
|----------|-------|
| **Nome da Flag** | Compra em Horário de Risco |
| **Código** | `FLG-002` |
| **Campo Gerado** | `is_night_transaction` |
| **Condição (Conservadora)** | `transaction_hour >= 2 AND transaction_hour < 5` |
| **Condição (Ampla)** | `transaction_hour >= 0 AND transaction_hour < 6` |

**Por que essa flag existe?**

Dados históricos de fraudes bancárias indicam:
- **Pico de fraudes entre 2h-5h da manhã**: período com menor monitoramento humano
- Fraudadores preferem horários onde alertas demoram mais para serem tratados
- Comportamento de compra legítima é **muito raro** nesse horário

**Estatísticas de referência:**
- Apenas ~3-5% das transações legítimas ocorrem entre 2h-5h
- ~15-20% das fraudes ocorrem neste período

**Percentual esperado da flag:** ~12-15% das transações (usando range 2-5h)

---

### 🚩 FLAG FLG-003: Valor Alto (Acima da Média)

| Atributo | Valor |
|----------|-------|
| **Nome da Flag** | Transação de Valor Atípico |
| **Código** | `FLG-003` |
| **Campo Gerado** | `is_high_value` |
| **Condição (Conservadora)** | `amount > avg_transaction_amount_30d * 5` |
| **Condição (Streaming)** | `amount > avg_transaction_amount_30d * 3` |

**Por que essa flag existe?**

O comportamento de gasto de um cliente é relativamente estável:
- **Desvios significativos** (3x a 5x a média) indicam possível comprometimento do cartão
- Fraudadores tendem a "maximizar o valor" antes que o cartão seja bloqueado
- Estudos mostram que **transações fraudulentas têm valor médio 4-6x maior** que transações legítimas

**Por que usamos multiplicador da média pessoal:**
Um cliente que gasta em média R$ 5.000/mês é diferente de um que gasta R$ 500/mês. Usar valor fixo (ex: R$ 1.000) geraria muitos falsos positivos.

**Threshold justificado:**
- **3x**: mais sensível, captura mais fraudes mas gera mais falsos positivos
- **5x**: mais conservador, usado no batch para reduzir alertas

---

### 🚩 FLAG FLG-004: Alta Velocidade de Transações

| Atributo | Valor |
|----------|-------|
| **Nome da Flag** | Padrão de Gasto Acelerado |
| **Código** | `FLG-004` |
| **Campo Gerado** | `is_high_velocity` |
| **Condição (Conservadora)** | `transactions_last_24h > 15` |
| **Condição (Streaming)** | `transactions_last_24h > 5` |

**Por que essa flag existe?**

Fraudadores, ao obter acesso a um cartão, tentam:
- Fazer o **máximo de compras possível** antes do bloqueio
- Compras pequenas consecutivas para "testar" o cartão
- Múltiplas compras em diferentes merchants para diversificar

**Base estatística:**
- Cliente médio faz 2-3 transações por dia
- Mais de 5 transações/24h já é incomum para pessoa física
- Mais de 15 transações/24h é altamente suspeito (exceto em contextos específicos como viagens)

**Percentual esperado:** ~5-10% das transações

---

### 🚩 FLAG FLG-005: Discrepância GPS Dispositivo/Compra

| Atributo | Valor |
|----------|-------|
| **Nome da Flag** | Inconsistência Geográfica |
| **Código** | `FLG-005` |
| **Campo Gerado** | `is_gps_mismatch` |
| **Campo Auxiliar** | `distance_gps` ou `distance_device_purchase` |
| **Condição (Conservadora - Batch)** | `distance_gps > 20.0` graus (~2.222 km) |
| **Condição (Streaming)** | `distance_device_purchase > 5` graus (~555 km) |

**Por que essa flag existe?**

Esta é uma das **flags mais fortes** para detecção de fraude:
- Se o dispositivo do cliente está em São Paulo mas a compra é em Recife, há inconsistência
- Fraudadores não têm acesso ao dispositivo real do cliente
- Clonagem de cartão permite uso físico longe do proprietário

**Cálculo da distância:**
```
distance = sqrt((device_lat - purchase_lat)² + (device_long - purchase_long)²)
```
Nota: Fórmula simplificada em graus. 1 grau ≈ 111km no equador.

**Thresholds:**
- **5 graus (~555km)**: Captura compras em estados adjacentes com dispositivo em local diferente
- **20 graus (~2.222km)**: Ultra conservador, captura apenas casos extremos (ex: dispositivo no Sul, compra no Nordeste)

**Percentual esperado:** ~3-5% com threshold de 20 graus

---

### 🚩 FLAG FLG-006: Cross-State sem Histórico de Viagem

| Atributo | Valor |
|----------|-------|
| **Nome da Flag** | Compra Interestadual Atípica |
| **Código** | `FLG-006` |
| **Campo Gerado** | `is_cross_state_no_travel` |
| **Condição** | `is_cross_state == True AND had_travel_purchase_last_12m == False` |

**Por que essa flag existe?**

Combina duas informações para reduzir falsos positivos:
- Cliente que **nunca viajou** nos últimos 12 meses
- Repentinamente faz compra em outro estado

Isso é mais suspeito do que um viajante frequente fazendo compra em outro estado.

**Contexto:**
- Clientes com histórico de viagem: compras cross-state são normais
- Clientes sem histórico: compras cross-state merecem atenção

---

### 🚩 FLAG FLG-007: Primeira Compra no Estado

| Atributo | Valor |
|----------|-------|
| **Nome da Flag** | Novo Comportamento Geográfico |
| **Código** | `FLG-007` |
| **Campo** | `is_first_purchase_in_state` |
| **Origem** | Dado de entrada (pré-calculado) |

**Por que essa flag existe?**

A primeira vez que um cliente faz uma compra em um novo estado é estatisticamente mais arriscada:
- Pode indicar início de uso fraudulento
- Representa mudança de padrão comportamental
- Sem histórico no estado, é difícil validar a legitimidade

---

### 🚩 FLAG FLG-008: Transação Internacional

| Atributo | Valor |
|----------|-------|
| **Nome da Flag** | Compra em Território Estrangeiro |
| **Código** | `FLG-008` |
| **Campo** | `is_international` |
| **Origem** | Dado de entrada (pré-calculado) |

**Por que essa flag existe?**

Transações internacionais têm risco elevado:
- **Clonagem de cartão**: dados vendidos na dark web são usados globalmente
- **Teste de cartão**: fraudadores testam em países com menos rastreamento
- Dificuldade de contestação/estorno em compras internacionais

**Estatística de referência:**
- ~2-3% das transações são internacionais
- ~10-15% das fraudes envolvem uso internacional

---

## Regras de Scoring de Fraude

O **Fraud Score** é calculado na camada **Gold** somando pesos de cada indicador.

### 📊 Tabela de Pesos (Batch - Conservador)

| Indicador | Peso Individual | Justificativa |
|-----------|-----------------|---------------|
| `is_cross_state` | 2 | Baixo isoladamente, comum em viajantes |
| `is_night_transaction` | 3 | Moderado, horário de risco |
| `is_high_value` | 3 | Moderado, pode ser compra legítima grande |
| `is_high_velocity` | 5 | Significativo, padrão de ataque |
| `is_gps_mismatch` | 5 | Significativo, indica clonagem |
| `is_first_purchase_in_state` | 2 | Baixo, pode ser viagem legítima |
| `is_international` | 4 | Moderado, risco aumentado |

### 📊 Tabela de Pesos (Streaming - Sensível)

| Indicador | Peso Individual | Justificativa |
|-----------|-----------------|---------------|
| `is_cross_state` | 15 | Mais peso para ação rápida |
| `is_night_transaction` | 10 | Atenção em tempo real |
| `is_high_value` | 20 | Proteger grandes valores |
| `is_high_velocity` | 15 | Detectar ataques em andamento |
| `is_gps_mismatch` | 25 | Forte indicador de clonagem |
| `is_cross_state_no_travel` | 30 | Combinação forte |
| `is_first_purchase_in_state` | 10 | Novo comportamento |
| `is_international` | 15 | Risco internacional |

---

## Combinações Críticas

As combinações de flags têm **peso adicional** porque a probabilidade de fraude aumenta exponencialmente quando múltiplos fatores coincidem.

### ⚠️ COMBO-001: GPS Mismatch + Alto Valor + Noturna

| Atributo | Valor |
|----------|-------|
| **Nome** | Tríade de Risco Máximo |
| **Código** | `COMBO-001` |
| **Peso Adicional** | +25 pontos |
| **Condição** | `is_gps_mismatch AND is_high_value AND is_night_transaction` |

**Por que essa combinação é crítica?**

Representa o cenário clássico de fraude:
1. **Dispositivo do cliente em local A** (dormindo à noite)
2. **Compra de alto valor** (maximizar ganho)
3. **Horário de madrugada** (menos monitoramento)

**Taxa de fraude esperada:** >70% quando os três fatores coincidem

---

### ⚠️ COMBO-002: GPS Mismatch + Cross-State + Sem Histórico de Viagem

| Atributo | Valor |
|----------|-------|
| **Nome** | Compra Impossível |
| **Código** | `COMBO-002` |
| **Peso Adicional** | +30 pontos |
| **Condição** | `is_gps_mismatch AND is_cross_state AND had_travel_purchase_last_12m == False` |

**Por que essa combinação é crítica?**

Indica uso de cartão clonado com alta probabilidade:
1. Cliente **nunca viaja** (baseado em histórico)
2. Compra em **outro estado** (não faz sentido)
3. **Dispositivo em local diferente** (não está presente)

Praticamente impossível ser transação legítima sem explicação.

---

### ⚠️ COMBO-003: Alta Velocidade + GPS Mismatch + Alto Valor

| Atributo | Valor |
|----------|-------|
| **Nome** | Ataque Coordenado |
| **Código** | `COMBO-003` |
| **Peso Adicional** | +35 pontos |
| **Condição** | `is_high_velocity AND is_gps_mismatch AND is_high_value` |

**Por que essa combinação é crítica?**

Padrão típico de fraude organizada:
1. **Múltiplas transações rápidas** (antes do bloqueio)
2. **Local inconsistente** (cartão clonado)
3. **Valores altos** (maximizar prejuízo)

Indica ataque em andamento que requer ação imediata.

---

### ⚠️ COMBO-004: Noturna + Alta Velocidade + Cross-State sem Histórico

| Atributo | Valor |
|----------|-------|
| **Nome** | Fraude Noturna Coordenada |
| **Código** | `COMBO-004` |
| **Peso Adicional** | +40 pontos |
| **Condição** | `is_night_transaction AND is_high_velocity AND is_cross_state AND had_travel_purchase_last_12m == False` |

**Por que essa combinação é crítica?**

Cenário de maior risco:
1. **Madrugada** (cliente provavelmente dormindo)
2. **Múltiplas compras** (ataque ativo)
3. **Estado diferente** (não está lá)
4. **Nunca viajou** (não faz sentido estar lá)

**Recomendação:** Bloqueio imediato do cartão.

---

## Classificação de Nível de Risco

### Batch Processing (Conservador)

| Nível | Score Mínimo | Percentual Esperado | Ação Recomendada |
|-------|--------------|---------------------|------------------|
| **CRÍTICO** | ≥ 50 | ~0.5% | Bloqueio imediato + contato |
| **ALTO** | ≥ 30 | ~2-3% | Análise manual urgente |
| **MÉDIO** | ≥ 18 | ~5-10% | Monitoramento ativo |
| **BAIXO** | ≥ 10 | ~10-15% | Registro para histórico |
| **NORMAL** | < 10 | ~70-85% | Nenhuma ação |

### Streaming Processing (Sensível)

| Nível | Score Mínimo | Percentual Esperado | Ação Recomendada |
|-------|--------------|---------------------|------------------|
| **CRÍTICO** | ≥ 70 | ~1-2% | Bloqueio automático |
| **ALTO** | ≥ 50 | ~3-5% | Alerta + revisão imediata |
| **MÉDIO** | ≥ 30 | ~8-12% | Fila de análise |
| **BAIXO** | ≥ 15 | ~15-20% | Monitoramento |
| **NORMAL** | < 15 | ~60-70% | Aprovado |

### Regra Simples (fraud_detection.py)

| Nível | Condição | Descrição |
|-------|----------|-----------|
| **Alto Risco** | `amount > 1000 AND hour BETWEEN 2-5` | Valor alto + madrugada |
| **Risco Médio** | `amount > 1000 OR hour BETWEEN 2-5` | Um dos fatores |
| **Baixo Risco** | Outros casos | Transação normal |

---

## Resumo das Regras por Camada

### Bronze Layer
- Ingestão de dados brutos sem transformação
- Preservação do JSON original

### Silver Layer
| Código | Nome | Tipo |
|--------|------|------|
| CLN-001 | Deduplicação de Transações | Limpeza |
| CLN-002 | Integridade de Dados Essenciais | Limpeza |
| CLN-003 | Normalização de Valores Monetários | Limpeza |
| CLN-004 | Exclusão de Transações Vazias | Limpeza |
| CLN-005 | Normalização de Campos de Texto | Limpeza |
| CLN-006 | Deduplicação de Clientes | Limpeza |
| FLG-001 | Compra em Estado Diferente | Flag |
| FLG-002 | Compra em Horário de Risco | Flag |
| FLG-003 | Transação de Valor Atípico | Flag |
| FLG-004 | Padrão de Gasto Acelerado | Flag |
| FLG-005 | Inconsistência Geográfica | Flag |
| FLG-006 | Compra Interestadual Atípica | Flag |
| FLG-007 | Novo Comportamento Geográfico | Flag |
| FLG-008 | Compra em Território Estrangeiro | Flag |

### Gold Layer
| Código | Nome | Tipo |
|--------|------|------|
| COMBO-001 | Tríade de Risco Máximo | Combinação |
| COMBO-002 | Compra Impossível | Combinação |
| COMBO-003 | Ataque Coordenado | Combinação |
| COMBO-004 | Fraude Noturna Coordenada | Combinação |
| SCORE | Fraud Score | Cálculo |
| RISK | Classificação de Risco | Classificação |

---

## Referências

1. **Nilson Report** - Estatísticas globais de fraude em cartões
2. **FEBRABAN** - Federação Brasileira de Bancos - Dados de fraude no Brasil
3. **PCI DSS** - Payment Card Industry Data Security Standard
4. **Estudos de Machine Learning em Fraude** - IEEE/ACM

---

> 📝 **Nota:** Esta documentação deve ser atualizada sempre que novas regras forem adicionadas ou thresholds forem ajustados.
