# 🎓 PROGRESSO DE APRENDIZADO - Fraud Detection Pipeline

> **IMPORTANTE PARA A IA:** Este arquivo contém o contexto completo do projeto de aprendizado.
> O aluno está aprendendo passo a passo (baby steps). NÃO faça código automaticamente.
> Siga a metodologia: explicar → aluno pergunta → aluno digita → executar juntos.

---

## 👤 PERFIL DO ALUNO

- Nível: Iniciante/Intermediário em Data Engineering
- Objetivo: Aprender construindo, não copiando
- Preferência: Explicações em português, passo a passo
- Frase-chave: "eu nunca fiz um projeto desses do 0, quero bb steps passo a passo, sentir que eu fiz, não que foi tudo automático"

---

## 📍 STATUS ATUAL

**Último checkpoint completado:** 8 - Bronze Layer ✅
**Próximo checkpoint:** 9 - Silver Layer
**Data da última sessão:** 2025-11-28

---

## ✅ CHECKPOINTS COMPLETADOS

### Checkpoint 1-5: Infraestrutura Docker ✅
- [x] docker-compose.yml criado com 6 serviços
- [x] PostgreSQL 16 (porta 5432)
- [x] MinIO (portas 9002/9003) - bucket "fraud-data" criado via UI
- [x] Zookeeper 7.5.0 + Kafka 7.5.0 (porta 9092) - topic "transactions" criado
- [x] Spark Master + Worker apache/spark:3.5.3 (UI porta 8081)
- [x] Todos containers rodando

### Checkpoint 6-7: Geração de Dados ✅
- [x] scripts/generate_data.py criado
- [x] Funções: generate_customers(), generate_transactions(), save_to_json()
- [x] Formato: JSON Lines (um registro por linha) - corrigido durante a sessão
- [x] Dados gerados: 100 clientes + 500 transações (~5% fraude = ~25 fraudes)

### Checkpoint 8: Bronze Layer ✅
- [x] spark/jobs/bronze_layer.py criado
- [x] PySpark 4.0.1 instalado no venv (compatível com Spark 4.0.1 do sistema)
- [x] Conversão JSON → Parquet funcionando
- [x] Metadados adicionados: _ingestion_time, _process_date
- [x] Output: data/bronze/customers/ e data/bronze/transactions/

---

## 🔜 CHECKPOINTS PENDENTES

### Checkpoint 9: Silver Layer (PRÓXIMO!)
**Objetivo:** Limpar e validar dados
**Arquivo a criar:** spark/jobs/silver_layer.py

O que fazer:
1. Ler Parquet do Bronze
2. Remover duplicados
3. Tratar valores nulos
4. Validar formatos (CPF, email)
5. Padronizar campos (lowercase, trim)
6. Salvar em data/silver/

Conceitos a ensinar:
- dropDuplicates()
- fillna() / dropna()
- regexp_extract() para validações
- withColumn() para transformações

### Checkpoint 10: Gold Layer
**Objetivo:** Agregações e métricas para análise
**Arquivo a criar:** spark/jobs/gold_layer.py

O que fazer:
1. Métricas por cliente (total gasto, qtd transações)
2. Métricas por merchant
3. Métricas de fraude
4. Salvar em data/gold/

### Checkpoint 11: Regras de Fraude
**Objetivo:** Implementar detecção de fraudes
**Arquivo a criar:** spark/jobs/fraud_detection.py

Regras a implementar:
- Transação > R$1000 (flag)
- Múltiplas transações em < 1 hora (mesmo cliente)
- Transações em horários suspeitos (2h-5h)
- Cliente novo + valor alto

### Checkpoint 12: Kafka Streaming
**Objetivo:** Processar transações em tempo real
**Arquivo a criar:** spark/jobs/streaming_processor.py

### Checkpoint 13: Dashboard/Alertas
**Objetivo:** Visualização e alertas

---

## 🛠️ AMBIENTE TÉCNICO

```yaml
Sistema: Ubuntu 25.04 (plucky) - VPS
IP: 54.36.100.35
Shell: zsh

Python: 3.13
PySpark: 4.0.1
Spark: 4.0.1 (SPARK_HOME=/home/ubuntu/Estudos/apache-spark/spark-4.0.1-bin-hadoop3)
Java: OpenJDK 17

Docker: docker.io (não docker-ce - incompatível com Ubuntu 25.04)
```

### Comandos para iniciar sessão:
```bash
cd ~/Estudos/1_projeto_bank_Fraud_detection_data_pipeline
source venv/bin/activate
docker compose ps  # verificar containers
```

---

## 📁 ESTRUTURA DO PROJETO

```
1_projeto_bank_Fraud_detection_data_pipeline/
├── LEARNING_PROGRESS.md    ← Este arquivo (contexto para IA)
├── docker-compose.yml      ← Infraestrutura (6 serviços)
├── venv/                   ← Virtual environment Python
├── scripts/
│   └── generate_data.py    ← Gerador de dados sintéticos
├── spark/
│   └── jobs/
│       ├── bronze_layer.py ← JSON → Parquet ✅
│       ├── silver_layer.py ← (A CRIAR)
│       ├── gold_layer.py   ← (A CRIAR)
│       └── fraud_detection.py ← (A CRIAR)
└── data/
    ├── raw/                ← JSON Lines (origem)
    │   ├── customers.json
    │   └── transactions.json
    ├── bronze/             ← Parquet bruto ✅
    │   ├── customers/
    │   └── transactions/
    ├── silver/             ← (A CRIAR) Parquet limpo
    └── gold/               ← (A CRIAR) Parquet agregado
```

---

## 📝 METODOLOGIA DE ENSINO

### Regras para a IA:

1. **NÃO escreva código automaticamente** - guie o aluno
2. **Explique o conceito primeiro** (teoria breve)
3. **Mostre o código a digitar** em blocos pequenos
4. **Espere o aluno confirmar** que digitou
5. **Execute junto** e analise o resultado
6. **Se der erro**, explique o porquê antes de corrigir

### Formato de aula:
```
## 📝 AULA X.Y: [Nome do Conceito]

[Explicação teórica em 2-3 parágrafos]

---

Agora digita no arquivo [nome]:

```python
# código aqui
```

Me avisa quando terminar!
```

---

## 🐛 PROBLEMAS RESOLVIDOS (para referência)

| Problema | Causa | Solução |
|----------|-------|---------|
| docker-ce não instala | Ubuntu 25.04 incompatível | Usar docker.io nativo |
| Porta 9000 ocupada | Portainer usando | MinIO mudou para 9002/9003 |
| Porta 8080 ocupada | Open-WebUI usando | Spark UI mudou para 8081 |
| Bitnami Spark não funciona | Imagens pagas agora | Usar apache/spark oficial |
| pip não funciona | PEP 668 (externally-managed) | Criar venv |
| PySpark 3.5.3 erro | SPARK_HOME aponta p/ 4.0.1 | Instalar PySpark 4.0.1 |
| JSON corrupt record | Formato array [...] | Mudar para JSON Lines |

---

## 🚀 COMO CONTINUAR

Quando o aluno voltar, dizer:

> "Bem-vindo de volta! Vi no LEARNING_PROGRESS.md que completaste o Bronze Layer.
> Pronto para começar a Silver Layer? Vamos limpar e validar os dados!"

Primeiro passo da próxima sessão:
1. Verificar se containers estão rodando: `docker compose ps`
2. Ativar venv: `source venv/bin/activate`
3. Verificar dados bronze existem: `ls data/bronze/`
4. Começar explicação da Silver Layer

---

*Última atualização: 2025-11-28 04:45*
