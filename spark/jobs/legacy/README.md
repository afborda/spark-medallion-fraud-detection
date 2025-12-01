# 📦 Legacy - Scripts Antigos/Descontinuados

## ⚠️ AVISO IMPORTANTE

**Estes scripts são versões ANTIGAS ou experimentais.**
Foram substituídos pelos scripts na pasta `production/`.

**NÃO USE EM PRODUÇÃO** - mantidos apenas para referência histórica.

## 📋 Visão Geral

Scripts desenvolvidos durante as fases iniciais do projeto, antes da consolidação
na arquitetura Medallion atual. Alguns têm funcionalidades fragmentadas ou
abordagens diferentes.

## 📁 Arquivos

| Arquivo | Status | Substituído Por |
|---------|--------|-----------------|
| `bronze_layer.py` | 🔴 Obsoleto | `production/medallion_bronze.py` |
| `silver_layer.py` | 🔴 Obsoleto | `production/medallion_silver.py` |
| `gold_layer.py` | 🔴 Obsoleto | `production/medallion_gold.py` |
| `bronze_to_minio.py` | 🟡 Parcial | Integrado em `medallion_bronze.py` |
| `silver_to_minio.py` | 🟡 Parcial | Integrado em `medallion_silver.py` |
| `gold_to_minio.py` | 🟡 Parcial | Integrado em `medallion_gold.py` |
| `fraud_detection.py` | 🔴 Obsoleto | Regras em `medallion_silver.py` |
| `load_to_postgres.py` | 🟡 Parcial | Integrado em `medallion_gold.py` |

## 🔍 Descrição dos Scripts

### bronze_layer.py
- Versão inicial da camada Bronze
- Sem conexão com Kafka, usa arquivos locais
- Não usa MinIO

### silver_layer.py
- Versão inicial da camada Silver
- Limpeza básica sem flags de fraude
- Estrutura simplificada

### gold_layer.py
- Versão inicial da camada Gold
- Agregações simples sem scoring de fraude

### *_to_minio.py
- Scripts separados para upload ao MinIO
- Funcionalidade agora incorporada nos scripts medallion_*

### fraud_detection.py
- Implementação inicial de detecção de fraude
- Regras básicas, sem Window Functions
- Substituído pelas regras em `medallion_silver.py`

### load_to_postgres.py
- Script isolado para carga no PostgreSQL
- Funcionalidade agora em `medallion_gold.py`

## 📜 Histórico

Estes scripts representam a evolução do projeto:

```
Fase 1: Scripts separados (bronze_layer, silver_layer, gold_layer)
    │
    ▼
Fase 2: Adição de MinIO (*_to_minio.py)
    │
    ▼
Fase 3: Consolidação (medallion_*.py) ← ATUAL
```

## 🎓 Valor Educacional

Estes scripts são úteis para:

1. **Entender a evolução** da arquitetura
2. **Comparar abordagens** simples vs otimizadas
3. **Aprender** conceitos básicos antes dos avançados
4. **Debug** - testar partes isoladas do pipeline

## 🖥️ Como Executar (se necessário)

```bash
# APENAS PARA REFERÊNCIA - NÃO USE EM PRODUÇÃO

docker exec -it spark-master bash

spark-submit \
  --master spark://spark-master:7077 \
  --jars /jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar \
  /spark/jobs/legacy/bronze_layer.py
```

## 🗑️ Possível Remoção

Estes scripts podem ser removidos no futuro quando:
- Documentação estiver completa
- Todos os conceitos estiverem em `production/`
- Testes estiverem validados

**Recomendação**: Manter por mais 2-3 sprints para referência, depois arquivar.
