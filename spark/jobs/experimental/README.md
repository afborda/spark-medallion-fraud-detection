# 🧪 Experimental - Scripts em Teste

## ⚠️ AVISO

**Estes scripts são EXPERIMENTAIS e não testados completamente.**
Use com cautela e apenas em ambiente de desenvolvimento.

## 📋 Visão Geral

Scripts que testam novas abordagens ou funcionalidades que ainda não foram
validadas para uso em produção.

## 📁 Arquivos

| Arquivo | Descrição | Status |
|---------|-----------|--------|
| `batch_silver_gold.py` | Executa Silver + Gold em um único job | 🧪 Testando |
| `kafka_to_postgres_batch.py` | Pipeline direto Kafka → PostgreSQL | 🧪 Testando |

## 🎯 Detalhes dos Scripts

### batch_silver_gold.py

**Objetivo**: Combinar Silver e Gold em uma única execução para reduzir overhead.

**Hipótese**: Executar Silver → Gold em sequência sem sair do Spark pode ser mais eficiente.

**Status**: 
- ✅ Funciona
- ⚠️ Não validado em escala
- ❓ Comparar performance com execução separada

**Riscos**:
- Debugging mais difícil
- Se falhar no Gold, refaz Silver também
- Mais memória necessária

### kafka_to_postgres_batch.py

**Objetivo**: Pipeline simplificado direto do Kafka para PostgreSQL.

**Hipótese**: Para casos simples, pode-se pular a camada de armazenamento intermediário.

**Status**:
- ✅ Funciona para volumes pequenos
- ⚠️ Não mantém histórico
- ❌ Perde benefícios do Medallion

**Riscos**:
- Sem camada Bronze (perde raw data)
- Sem replay capability
- Acoplamento direto Kafka-Postgres

## 🖥️ Como Executar

### batch_silver_gold.py

```bash
docker exec -it spark-master bash

spark-submit \
  --master spark://spark-master:7077 \
  --jars /jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar,/jars/postgresql-42.7.4.jar \
  /spark/jobs/experimental/batch_silver_gold.py
```

### kafka_to_postgres_batch.py

```bash
docker exec -it spark-master bash

spark-submit \
  --master spark://spark-master:7077 \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.3 \
  --jars /jars/postgresql-42.7.4.jar \
  /spark/jobs/experimental/kafka_to_postgres_batch.py
```

## 📊 Comparação com Produção

| Aspecto | Production | batch_silver_gold | kafka_to_postgres |
|---------|------------|-------------------|-------------------|
| Histórico | ✅ Completo | ✅ Completo | ❌ Não |
| Replay | ✅ Sim | ✅ Sim | ❌ Não |
| Debug | ✅ Fácil | ⚠️ Médio | ⚠️ Médio |
| Performance | Baseline | ❓ A testar | ❓ A testar |
| Complexidade | Média | Menor | Menor |

## 🧪 Como Validar

### Checklist antes de promover para produção:

1. [ ] Testar com 1M+ de registros
2. [ ] Comparar tempo de execução
3. [ ] Verificar uso de memória
4. [ ] Validar resultados (diff com produção)
5. [ ] Testar cenários de falha
6. [ ] Documentar trade-offs
7. [ ] Code review

## 💡 Ideias para Experimentação

- [ ] `medallion_all_in_one.py` - Bronze + Silver + Gold em um job
- [ ] `streaming_with_ml.py` - ML em tempo real
- [ ] `delta_lake_migration.py` - Migrar para Delta Lake
- [ ] `iceberg_test.py` - Testar Apache Iceberg
- [ ] `spark_connect_test.py` - Testar Spark Connect

## 📝 Como Contribuir

1. Crie seu script experimental
2. Documente a hipótese
3. Defina métricas de sucesso
4. Teste em ambiente isolado
5. Documente resultados
6. Se aprovado, mova para `production/`

## 🗑️ Limpeza

Scripts que não forem validados após 30 dias devem ser:
- Arquivados em branch separado
- Ou removidos com documentação do motivo
