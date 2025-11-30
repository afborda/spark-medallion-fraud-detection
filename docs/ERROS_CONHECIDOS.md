# 🚨 Erros Conhecidos e Soluções

Este documento registra erros importantes encontrados durante o desenvolvimento do projeto, para referência futura.

---

## 1. `hostname cannot be null` / `URISyntaxException`

### Erro Completo
```
java.lang.IllegalArgumentException: hostname cannot be null
WARN FileSystem: Failed to initialize fileystem s3a://fraud-data/...
```

ou

```
java.net.URISyntaxException: Expected scheme-specific part at index 5: http:
```

### Causa Raiz

**Duas causas combinadas:**

#### A) AWS SDK v2 Bug (Spark 4.x + Hadoop 3.4.x)

O Spark 4.x usa Hadoop 3.4.x que por sua vez usa AWS SDK **v2**. Este SDK tem um bug conhecido ao parsear endpoints HTTP customizados para storages S3-compatíveis como MinIO.

```
Spark 4.0.x → Hadoop 3.4.x → AWS SDK v2 → ❌ BUG
Spark 3.5.x → Hadoop 3.3.x → AWS SDK v1 → ✅ OK
```

**Referências:**
- [StackOverflow: Spark 4 writing to MinIO fails](https://stackoverflow.com/questions/79293356/spark-4-writing-to-minio-fails-with-expected-scheme-specific-part-at-index-5-h)
- [Apache Jira HADOOP-19027](https://issues.apache.org/jira/browse/HADOOP-19027)

#### B) Hostname com Underscore

Nomes de host com underscore (`_`) **não são válidos** segundo RFC 952/1123. O AWS SDK falha ao resolver esses hostnames.

```python
# ❌ ERRADO - underscore no hostname
MINIO_ENDPOINT = "http://fraud_minio:9000"

# ✅ CORRETO - usar nome do serviço Docker Compose (sem underscore)
MINIO_ENDPOINT = "http://minio:9000"
```

**Por que `fraud_minio` existe?**
- `fraud_minio` é o `container_name` no docker-compose.yml
- `minio` é o nome do **serviço** no docker-compose.yml
- Ambos resolvem para o mesmo IP, mas o AWS SDK só aceita hostnames válidos

### Solução

1. **Usar Spark 3.5.x** (não 4.x) com os JARs corretos:
   - `hadoop-aws-3.3.4.jar`
   - `aws-java-sdk-bundle-1.12.262.jar`

2. **Usar hostname sem underscore**:
   - `minio` ao invés de `fraud_minio`

3. **Configurações S3A obrigatórias**:
```python
.config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000")
.config("spark.hadoop.fs.s3a.access.key", "minioadmin")
.config("spark.hadoop.fs.s3a.secret.key", "sua_senha")
.config("spark.hadoop.fs.s3a.path.style.access", "true")  # IMPORTANTE para MinIO
.config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
.config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")  # HTTP, não HTTPS
```

---

## 2. `403 Forbidden` ao acessar MinIO

### Erro
```
com.amazonaws.services.s3.model.AmazonS3Exception: Forbidden (Status Code: 403)
```

### Causa
Credenciais incorretas (access key ou secret key).

### Solução
Verificar se as credenciais no código Python batem com as do `docker-compose.yml`:
```yaml
environment:
  MINIO_ROOT_USER: minioadmin
  MINIO_ROOT_PASSWORD: sua_senha_aqui
```

---

## 3. JARs não encontrados ou conflito de versões

### Erro
```
java.lang.ClassNotFoundException: org.apache.hadoop.fs.s3a.S3AFileSystem
```

### Causa
JARs do Hadoop AWS não estão no classpath ou há conflito de versões.

### Solução

**JARs necessários (apenas estes 3):**
```
jars/
├── hadoop-aws-3.3.4.jar          # Conector S3A
├── aws-java-sdk-bundle-1.12.262.jar  # AWS SDK v1 (NÃO v2!)
└── postgresql-42.7.4.jar         # JDBC PostgreSQL (se usar)
```

**No código Python:**
```python
JARS_PATH = "/jars"
spark = SparkSession.builder \
    .config("spark.jars", f"{JARS_PATH}/hadoop-aws-3.3.4.jar,{JARS_PATH}/aws-java-sdk-bundle-1.12.262.jar") \
    ...
```

**No spark-submit (se usar):**
```bash
--jars /jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar
--conf "spark.driver.extraClassPath=/jars/hadoop-aws-3.3.4.jar:/jars/aws-java-sdk-bundle-1.12.262.jar"
--conf "spark.executor.extraClassPath=/jars/hadoop-aws-3.3.4.jar:/jars/aws-java-sdk-bundle-1.12.262.jar"
```

---

## Resumo: Stack Compatível com MinIO

| Componente | Versão | Motivo |
|------------|--------|--------|
| Spark | 3.5.3 | Usa Hadoop 3.3.x com AWS SDK v1 |
| hadoop-aws | 3.3.4 | Compatível com Spark 3.5.x |
| aws-java-sdk-bundle | 1.12.262 | SDK v1 (v2 tem bug) |
| MinIO Endpoint | `http://minio:9000` | Sem underscore no hostname |

---

*Documento criado em: Novembro 2025*
*Tempo perdido debugando: ~3 horas* 😅
