# 🍞 Baking Dependencies - Imutabilidade de Infraestrutura

> **Data:** 2025-12-04  
> **Padrão:** Baking Dependencies / Immutable Infrastructure  
> **Contexto:** Refatoração para eliminar configurações manuais de JARs e credenciais hardcoded

---

## 📋 Índice

1. [O Problema (Antes)](#o-problema-antes)
2. [A Solução (Depois)](#a-solução-depois)
3. [Arquivos Criados/Modificados](#arquivos-criadosmodificados)
4. [Benefícios](#benefícios)
5. [Como Funciona](#como-funciona)
6. [Comandos para Aplicar](#comandos-para-aplicar)

---

## 🔴 O Problema (Antes)

### Configuração de JARs Repetida em Cada Script

Cada script Spark precisava especificar manualmente os JARs necessários:

```python
# ❌ ANTES: Repetido em TODOS os scripts
spark = SparkSession.builder \
    .appName("BronzeLayer") \
    .config("spark.jars", "/jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar,/jars/postgresql-42.7.4.jar") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123@@!!_2") \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .getOrCreate()
```

### Problemas Identificados

| Problema | Impacto |
|----------|---------|
| 🔁 **Duplicação** | Mesma configuração copiada em 10+ scripts |
| 🔓 **Segurança** | Credenciais hardcoded no código fonte |
| 🐛 **Manutenção** | Mudar versão do JAR = alterar todos os scripts |
| 🚫 **Inconsistência** | Fácil esquecer um JAR em um script novo |
| 📦 **Portabilidade** | Dependência de caminhos específicos |

---

## 🟢 A Solução (Depois)

### Baking Dependencies: JARs na Imagem Docker

```dockerfile
# Dockerfile.spark
FROM apache/spark:3.5.3

# JARs "assados" na imagem - sempre disponíveis
COPY jars/*.jar /opt/spark/jars/

# Configurações globais (sem secrets!)
COPY spark/conf/spark-defaults.conf /opt/spark/conf/
```

### Credenciais via Environment Variables

```yaml
# docker-compose.yml
spark-master:
  build:
    context: .
    dockerfile: Dockerfile.spark
  environment:
    - MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
    - MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
```

### Scripts Limpos e Focados

```python
# ✅ DEPOIS: Script limpo e seguro
from config import get_spark_session, apply_s3a_configs

spark = get_spark_session("BronzeLayer")
spark = apply_s3a_configs(spark)

# Agora só a lógica de negócio!
```

---

## 📁 Arquivos Criados/Modificados

### Novos Arquivos

| Arquivo | Propósito |
|---------|-----------|
| `Dockerfile.spark` | Imagem customizada com JARs embutidos |
| `spark/conf/spark-defaults.conf` | Configurações S3A globais (sem secrets) |

### Arquivos Modificados

| Arquivo | Mudança |
|---------|---------|
| `docker-compose.yml` | Todos os serviços Spark usam `build:` ao invés de `image:` |
| `.env.example` | Adicionadas variáveis MINIO_ACCESS_KEY e MINIO_SECRET_KEY |
| `spark/jobs/config.py` | Função `apply_s3a_configs()` lê credenciais de env vars |
| `spark/jobs/production/*.py` | Removidas configs duplicadas, usam `apply_s3a_configs()` |
| `spark/jobs/streaming/*.py` | Removidas configs duplicadas, usam `apply_s3a_configs()` |

---

## ✅ Benefícios

### Comparativo Antes × Depois

| Aspecto | ❌ Antes | ✅ Depois |
|---------|----------|----------|
| **Segurança** | Senhas no código Git | Env vars (nunca versionadas) |
| **Manutenção** | Alterar 10+ arquivos | Alterar 1 Dockerfile |
| **Consistência** | JARs podem divergir | Mesma imagem = mesmos JARs |
| **Código** | ~15 linhas de config por script | ~2 linhas |
| **Deploy** | "Works on my machine" | Imagem idêntica em qualquer lugar |
| **Debug** | "Qual JAR está faltando?" | Sempre completo |

### Por Que "Baking" (Assar)?

A analogia é com assar um bolo:
- **Frying (Fritar):** Configurar em runtime = adicionar ingredientes na hora
- **Baking (Assar):** Tudo já está na imagem = bolo pronto para servir

> **Regra de Ouro:** Se algo não muda entre deploys, deve estar NA imagem, não configurado em runtime.

---

## ⚙️ Como Funciona

### 1. Build da Imagem (Uma vez)

```bash
docker compose build
```

Isso cria uma imagem `fraud-spark` com:
- Apache Spark 3.5.3
- hadoop-aws-3.3.4.jar
- aws-java-sdk-bundle-1.12.262.jar  
- postgresql-42.7.4.jar
- spark-defaults.conf configurado

### 2. Runtime (Cada execução)

O `docker-compose.yml` injeta as credenciais:

```yaml
environment:
  - MINIO_ACCESS_KEY=${MINIO_ACCESS_KEY}
  - MINIO_SECRET_KEY=${MINIO_SECRET_KEY}
```

### 3. Código Python lê do ambiente

```python
# config.py
def apply_s3a_configs(spark):
    return spark.builder \
        .config("spark.hadoop.fs.s3a.access.key", os.getenv("MINIO_ACCESS_KEY")) \
        .config("spark.hadoop.fs.s3a.secret.key", os.getenv("MINIO_SECRET_KEY")) \
        .getOrCreate()
```

### Fluxo Visual

```
┌─────────────────────────────────────────────────────────────┐
│                     BUILD TIME                               │
│  Dockerfile.spark                                            │
│  ├── COPY jars/*.jar → /opt/spark/jars/                     │
│  └── COPY spark-defaults.conf → /opt/spark/conf/            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     RUN TIME                                 │
│  docker-compose.yml                                          │
│  ├── environment: MINIO_ACCESS_KEY, MINIO_SECRET_KEY        │
│  └── .env file (gitignored)                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     PYTHON CODE                              │
│  config.py → apply_s3a_configs(spark)                       │
│  ├── os.getenv("MINIO_ACCESS_KEY")                          │
│  └── Retorna SparkSession configurado                        │
└─────────────────────────────────────────────────────────────┘
```

---

## 🚀 Comandos para Aplicar

### Primeira vez (ou após mudanças no Dockerfile)

```bash
# Rebuild todas as imagens Spark
docker compose build

# Subir o cluster com as novas imagens
docker compose up -d
```

### Verificar se os JARs estão na imagem

```bash
# Listar JARs no container
docker exec fraud_spark_master ls /opt/spark/jars/ | grep -E "hadoop|aws|postgresql"
```

**Saída esperada:**
```
aws-java-sdk-bundle-1.12.262.jar
hadoop-aws-3.3.4.jar
postgresql-42.7.4.jar
```

### Testar se as env vars estão funcionando

```bash
# Verificar variáveis no container
docker exec fraud_spark_master env | grep MINIO
```

**Saída esperada:**
```
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin123@@!!_2
```

---

## 📚 Referências

- [12 Factor App - Config](https://12factor.net/config) - Configuração via ambiente
- [Docker Best Practices](https://docs.docker.com/develop/develop-images/dockerfile_best-practices/) - Baking dependencies
- [Spark Configuration](https://spark.apache.org/docs/latest/configuration.html) - spark-defaults.conf

---

## 🔗 Arquivos Relacionados

- [`Dockerfile.spark`](../Dockerfile.spark)
- [`spark/conf/spark-defaults.conf`](../spark/conf/spark-defaults.conf)
- [`docker-compose.yml`](../docker-compose.yml)
- [`spark/jobs/config.py`](../spark/jobs/config.py)
- [`.env.example`](../.env.example)
