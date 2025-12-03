# 🏦 Sistema de Detecção de Fraudes
## Resumo Executivo para Stakeholders

---

## 📊 Visão Geral

| Métrica | Valor |
|---------|-------|
| **Volume Processado** | 30 milhões de transações |
| **Dados Analisados** | 19.2 GB |
| **Tempo de Processamento** | ~15 minutos |
| **Alertas Gerados** | 2.088.839 (6.9%) |
| **Fraudes Detectadas** | 842.997 (40.36% precisão) |

---

## 🎯 As 12 Regras de Detecção

### 🔴 Regras Críticas (Alta Severidade)

| # | Regra | O que Detecta | Por que é Importante |
|---|-------|---------------|---------------------|
| 1 | **Clonagem de Cartão** | Mesmo cartão usado em 2 cidades distantes (>555km) em menos de 1 hora | Fisicamente impossível estar em 2 lugares - indica cartão clonado |
| 2 | **Velocidade Impossível** | Deslocamento entre compras >900 km/h | Mais rápido que um avião comercial - fraude certa |

### 🟠 Regras de Alto Risco

| # | Regra | O que Detecta | Por que é Importante |
|---|-------|---------------|---------------------|
| 3 | **Gasto Anormal** | Valor da compra >5x a média do cliente nos últimos 30 dias | Padrão de gasto fora do normal pode indicar uso não autorizado |
| 4 | **GPS Divergente** | Celular do cliente em local diferente da compra (>2.200km) | Se o celular está em SP e a compra é em Manaus, algo está errado |
| 5 | **Horário Suspeito** | Compras entre 2h-5h da manhã | Horário atípico para transações legítimas |
| 6 | **Categoria de Risco** | Compras de eletrônicos ou passagens aéreas | Categorias preferidas por fraudadores (fácil revenda/fuga) |

### 🟡 Regras de Risco Médio

| # | Regra | O que Detecta | Por que é Importante |
|---|-------|---------------|---------------------|
| 7 | **Online Alto Valor** | Compras online >R$ 1.000 | E-commerce não exige cartão físico - mais vulnerável |
| 8 | **Parcelamento Excessivo** | 10+ parcelas em compras >R$ 500 | Fraudadores parcelam para diluir detecção |
| 9 | **Compra Interestadual** | Compra em estado diferente sem histórico de viagem | Primeira compra fora do estado pode ser fraude |
| 10 | **Alta Frequência** | >15 transações em 24 horas | Padrão de "corrida" para usar cartão antes do bloqueio |

---

## 📈 Sistema de Pontuação (Scoring)

Cada transação recebe uma pontuação baseada nas regras acionadas:

### Pontos por Regra

| Severidade | Regras | Pontos |
|------------|--------|--------|
| 🔴 Crítica | Clonagem, Velocidade Impossível | 25-40 pontos |
| 🟠 Alta | GPS, Gasto Anormal, Horário, Categoria | 3-5 pontos |
| 🟡 Média | Online, Parcelas, Interestadual, Frequência | 2-3 pontos |

### Pontos por Combinação

| Combinação | Exemplo | Pontos Extras |
|------------|---------|---------------|
| 2 fatores | GPS mismatch + Alto valor | +8 a 15 pontos |
| 3+ fatores | GPS + Alto valor + Noite | +20 a 40 pontos |

---

## 🚦 Classificação de Risco

| Nível | Score | Ação Recomendada | % das Transações |
|-------|-------|------------------|------------------|
| ✅ **NORMAL** | < 10 | Aprovar automaticamente | 90.26% |
| 🟢 **BAIXO** | 10-17 | Aprovar com monitoramento | 0.46% |
| 🟠 **MÉDIO** | 18-29 | Verificação adicional | 2.32% |
| 🟡 **ALTO** | 30-49 | Autenticação extra (SMS/Token) | 2.07% |
| 🔴 **CRÍTICO** | 50+ | Bloquear e contactar cliente | 4.89% |

---

## 💰 Impacto Financeiro

### Cenário: Base de 30 Milhões de Transações

| Métrica | Valor |
|---------|-------|
| Fraudes injetadas (5%) | 1.500.000 |
| Alertas gerados | 2.088.839 |
| Fraudes detectadas | 842.997 |
| Taxa de detecção | **56.2%** |
| Precisão | **40.36%** |

### Por que 40% de Precisão é Aceitável?

#### 🎯 Entendendo as Métricas

```
De cada 100 alertas gerados:
├── 40 são FRAUDES REAIS ✅ (evitamos prejuízo)
└── 60 são FALSOS POSITIVOS ⚠️ (incomodamos cliente legítimo)
```

#### 💰 Análise de Custo-Benefício

| Cenário | Custo Médio | Frequência | Impacto |
|---------|-------------|------------|---------|
| **Fraude não detectada** | R$ 5.000 | Cada fraude | 💸 Prejuízo direto + chargeback |
| **Falso positivo** | R$ 50 | Cada bloqueio errado | 😤 Atendimento + insatisfação |

**Relação de custo: 100:1**

#### 📊 Simulação com Números Reais

```
Nosso sistema gerou 2.088.839 alertas:

Se NÃO tivéssemos o sistema:
├── 1.500.000 fraudes passariam despercebidas
├── Prejuízo potencial: R$ 7,5 BILHÕES
└── (1.5M × R$ 5.000)

Com o sistema (40% precisão):
├── 842.997 fraudes detectadas e BLOQUEADAS
├── Prejuízo EVITADO: R$ 4,2 BILHÕES ✅
├── 1.245.842 falsos positivos
├── Custo de atendimento: R$ 62,3 milhões
└── (1.2M × R$ 50)

SALDO POSITIVO: R$ 4,15 BILHÕES economizados 🎉
```

#### 🎚️ O Trade-off Precisão vs Detecção

```
                    MAIS RIGOROSO                    MENOS RIGOROSO
                    (menos alertas)                  (mais alertas)
                         │                               │
    ┌────────────────────┼───────────────────────────────┼────────────────────┐
    │                    │                               │                    │
    │   Precisão: 80%    │      Precisão: 40%           │   Precisão: 20%    │
    │   Detecção: 20%    │      Detecção: 56%           │   Detecção: 80%    │
    │                    │            ▲                  │                    │
    │   ❌ Muitas fraudes │      NOSSO SISTEMA          │   ❌ Muito bloqueio │
    │      passam        │      ✅ Equilíbrio           │      de legítimos  │
    │                    │                               │                    │
    └────────────────────┴───────────────────────────────┴────────────────────┘
```

#### 🏦 Benchmark da Indústria

| Sistema | Precisão | Detecção | Observação |
|---------|----------|----------|------------|
| Bancos tradicionais | 30-50% | 40-60% | Regras baseadas |
| Fintechs com ML | 50-70% | 60-80% | Machine Learning |
| **Nosso sistema** | **40%** | **56%** | Regras + Scoring |

> **Conclusão:** Nossa precisão está dentro do padrão da indústria para sistemas baseados em regras. A implementação de Machine Learning no futuro pode elevar para 60-70%.

---

## 🚀 Como Melhorar a Precisão de 40% para 70%+

### 📊 Diagnóstico Atual

```
Precisão atual: 40.36%
├── Fraudes detectadas: 842.997 ✅
├── Falsos positivos: 1.245.842 ❌
└── Fraudes não detectadas: 657.003 (44%)
```

**Problema principal:** Muitos falsos positivos porque as regras são "estáticas" - não consideram o histórico individual de cada cliente.

### 🎯 Estratégias de Melhoria

#### 1. **Feedback Loop** (Curto Prazo - 2 semanas)
> Impacto esperado: +5-10% precisão

```
HOJE:
Alerta → Bloqueio → Fim

PROPOSTA:
Alerta → Bloqueio → Cliente confirma → Sistema APRENDE
                           │
                    ┌──────┴──────┐
                    │             │
              "Foi fraude"   "Não foi"
                    │             │
                    ▼             ▼
              Peso +1        Peso -1
              na regra       na regra
```

**Implementação:**
- Adicionar tabela `fraud_feedback` no PostgreSQL
- Atualizar pesos das regras baseado em confirmações
- Regras com muitos falsos positivos → reduzir pontuação

#### 2. **Perfil Comportamental por Cliente** (Médio Prazo - 1 mês)
> Impacto esperado: +10-15% precisão

```python
# HOJE: Threshold fixo para todos
is_high_value = amount > avg_30d * 5  # 5x média

# PROPOSTA: Threshold dinâmico por cliente
cliente_conservador:  threshold = avg_30d * 3   # Mais sensível
cliente_viajante:     threshold = avg_30d * 8   # Menos sensível
cliente_empresarial:  threshold = avg_30d * 10  # Muito menos sensível
```

**Implementação:**
- Clusterizar clientes por comportamento (K-Means)
- Criar perfis: conservador, moderado, arrojado, viajante, empresarial
- Ajustar thresholds por perfil

#### 3. **Machine Learning** (Longo Prazo - 2-3 meses)
> Impacto esperado: +15-25% precisão

| Modelo | Precisão Esperada | Complexidade |
|--------|-------------------|--------------|
| Logistic Regression | 55-60% | Baixa |
| Random Forest | 60-70% | Média |
| XGBoost | 65-75% | Média |
| Neural Network | 70-80% | Alta |

**Abordagem Híbrida Recomendada:**

```
┌─────────────────────────────────────────────────────────────┐
│                    SISTEMA HÍBRIDO                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Transação → [Regras Atuais] → Score Inicial (0-100)       │
│                     │                                       │
│                     ▼                                       │
│              [Modelo ML] → Ajuste de Score (+/- 20 pts)    │
│                     │                                       │
│                     ▼                                       │
│              Score Final → Classificação de Risco          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Por que híbrido?**
- Regras: explicáveis, auditáveis (compliance bancário)
- ML: captura padrões complexos que regras não pegam

#### 4. **Análise de Sequência** (Médio Prazo - 1 mês)
> Impacto esperado: +5-10% precisão

```
PADRÃO SUSPEITO (fraude real):
├── 09:00 - Compra pequena (teste) - R$ 50
├── 09:05 - Compra média - R$ 500
├── 09:10 - Compra grande - R$ 2.000
└── 09:15 - Compra máxima - R$ 5.000

PADRÃO NORMAL (viagem):
├── 08:00 - Café aeroporto - R$ 30
├── 12:00 - Almoço destino - R$ 80
├── 18:00 - Hotel - R$ 400
└── 20:00 - Jantar - R$ 150
```

**Implementação:**
- Usar Window Functions para analisar sequência de 5 últimas transações
- Detectar padrão de "escada" (valores crescentes rápidos)
- Flag: `is_escalating_pattern`

#### 5. **Enriquecimento de Dados** (Curto Prazo - 2 semanas)
> Impacto esperado: +5-8% precisão

| Dado Adicional | Fonte | Impacto |
|----------------|-------|---------|
| Reputação do merchant | Lista interna | Reduz falsos positivos |
| Histórico de chargebacks | PostgreSQL | Identifica reincidentes |
| Device fingerprint | SDK mobile | Detecta devices suspeitos |
| Geolocalização precisa | GPS real-time | Melhora regra GPS mismatch |

---

### 📈 Roadmap de Melhoria de Precisão

```
                    PRECISÃO
                       │
    80% ───────────────┼─────────────────────────── 🎯 META
                       │                        ╱
    70% ───────────────┼───────────────────────╱── ML + Híbrido
                       │                    ╱
    60% ───────────────┼───────────────────╱───── Perfil + Sequência
                       │                ╱
    50% ───────────────┼───────────────╱────────── Feedback Loop
                       │            ╱
    40% ───────────────┼───────────●─────────────── HOJE
                       │
        ───────────────┼─────┬─────┬─────┬─────┬───────►
                       │   Dez   Jan   Fev   Mar   TEMPO
                           2025  2026  2026  2026
```

### 💰 ROI das Melhorias

| Melhoria | Investimento | Precisão | Economia Adicional/Ano |
|----------|--------------|----------|------------------------|
| Feedback Loop | 40h dev | 45% | R$ 200M |
| Perfil Cliente | 80h dev | 55% | R$ 500M |
| ML Básico | 160h dev | 65% | R$ 1B |
| ML Avançado | 320h dev | 75% | R$ 1.5B |

> **Nota:** Valores estimados baseados em 30M transações/mês com ticket médio de fraude R$ 5.000

---

## 🔧 Tecnologia Utilizada

| Componente | Função |
|------------|--------|
| **Apache Spark** | Processamento distribuído de 30M registros |
| **Window Functions** | Análise temporal (transação atual vs anterior) |
| **Arquitetura Medallion** | Bronze → Silver → Gold (qualidade crescente) |
| **PostgreSQL** | Armazenamento de alertas para análise |
| **MinIO** | Data Lake para histórico |

---

## 📋 Próximos Passos Recomendados

### ✅ Concluído
- [x] Dashboard de monitoramento em tempo real (Metabase com auto-refresh)
- [x] Detecção de fraude em tempo real (streaming via Kafka → Spark → PostgreSQL)
- [x] Escalar para 50GB+ de dados (51GB processados com sucesso!)

### Curto Prazo
- [ ] Criar API para consulta de score por transação
- [ ] Adicionar notificações automáticas para risco CRÍTICO

### Médio Prazo
- [ ] Integrar com modelo de Machine Learning para refinamento
- [ ] Implementar feedback loop (confirmação de fraudes)

### Longo Prazo
- [ ] Análise de padrões comportamentais por cliente
- [ ] Integração com sistemas antifraude de terceiros

---

## 📞 Contato

**Projeto:** Fraud Detection Data Pipeline  
**GitHub:** [spark-medallion-fraud-detection](https://github.com/afborda/spark-medallion-fraud-detection)

---

*Documento gerado em: 01/12/2025*
