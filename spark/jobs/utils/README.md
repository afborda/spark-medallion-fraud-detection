# 🔧 Utils - Scripts Utilitários

## 📋 Visão Geral

Scripts auxiliares para **verificação, debug e análise** dos dados.
Não fazem parte do pipeline principal, mas são úteis para desenvolvimento.

## 📁 Arquivos

| Arquivo | Descrição | Uso |
|---------|-----------|-----|
| `check_flags.py` | Verifica flags de fraude no Silver | Debug/Análise |
| `check_gps.py` | Verifica coordenadas GPS dos customers | Validação |

## 🎯 Detalhes dos Scripts

### check_flags.py

**Propósito**: Verificar se as flags de fraude estão sendo calculadas corretamente.

**O que faz**:
- Lê dados da camada Silver
- Mostra estatísticas das flags
- Identifica transações suspeitas

**Quando usar**:
- Após rodar `medallion_silver.py`
- Para validar novas regras de fraude
- Debug quando alertas parecem incorretos

```python
# Exemplo de output:
+-------------------+-------+
| flag              | count |
+-------------------+-------+
| is_high_amount    |  1234 |
| is_unusual_hour   |   567 |
| is_foreign        |   890 |
| is_cloning_suspect|     0 |
+-------------------+-------+
```

### check_gps.py

**Propósito**: Validar coordenadas GPS dos clientes.

**O que faz**:
- Lê dados de customers
- Verifica latitude/longitude válidas
- Identifica coordenadas fora do Brasil

**Quando usar**:
- Validar dados de entrada
- Antes de implementar regra de distância
- Debug de problemas geográficos

## 🖥️ Como Executar

### No Cluster Spark

```bash
docker exec -it spark-master bash

# Check Flags
spark-submit \
  --master spark://spark-master:7077 \
  --jars /jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar \
  /spark/jobs/utils/check_flags.py

# Check GPS
spark-submit \
  --master spark://spark-master:7077 \
  --jars /jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar \
  /spark/jobs/utils/check_gps.py
```

### Execução Local

```bash
spark-submit \
  --master local[*] \
  --jars /path/to/jars/hadoop-aws-3.3.4.jar,/path/to/jars/aws-java-sdk-bundle-1.12.262.jar \
  check_flags.py
```

## 🔍 Interpretando os Resultados

### check_flags.py

| Flag | Significado | Esperado |
|------|-------------|----------|
| `is_high_amount` | Valor > R$5.000 | 5-15% |
| `is_unusual_hour` | 00:00 - 06:00 | 10-20% |
| `is_foreign` | País != Brasil | 1-5% |
| `is_cloning_suspect` | Transação após < 5min | ~0% (dados teste) |
| `is_suspicious_category` | Eletrônicos/Passagens | 10-15% |
| `is_online_high_value` | Online + > R$1.000 | 3-8% |

### check_gps.py

```
✅ GPS válido: latitude entre -33.75 e 5.27 (Brasil)
✅ GPS válido: longitude entre -73.99 e -34.79 (Brasil)
⚠️ GPS suspeito: coordenadas fora do Brasil
❌ GPS inválido: valores nulos ou zerados
```

## 🛠️ Criando Novos Utils

Template para criar um novo script de verificação:

```python
from pyspark.sql import SparkSession

def main():
    spark = SparkSession.builder \
        .appName("CheckNomeDoCheck") \
        .getOrCreate()
    
    # Configurar MinIO
    spark.sparkContext._jsc.hadoopConfiguration().set("fs.s3a.endpoint", "http://minio:9000")
    spark.sparkContext._jsc.hadoopConfiguration().set("fs.s3a.access.key", "minioadmin")
    spark.sparkContext._jsc.hadoopConfiguration().set("fs.s3a.secret.key", "minioadmin")
    spark.sparkContext._jsc.hadoopConfiguration().set("fs.s3a.path.style.access", "true")
    
    # Ler dados
    df = spark.read.parquet("s3a://lakehouse/silver/transactions")
    
    # Suas verificações aqui
    print("=== Verificação XYZ ===")
    df.groupBy("coluna").count().show()
    
    spark.stop()

if __name__ == "__main__":
    main()
```

## 📝 Sugestões de Novos Utils

- [ ] `check_duplicates.py` - Encontrar transações duplicadas
- [ ] `check_schema.py` - Validar schema dos dados
- [ ] `check_nulls.py` - Identificar campos com muitos nulls
- [ ] `check_outliers.py` - Detectar valores discrepantes
- [ ] `compare_layers.py` - Comparar contagens Bronze/Silver/Gold
