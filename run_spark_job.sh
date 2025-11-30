#!/bin/bash
# ============================================================
# Script único para executar jobs Spark no cluster
# Uso: ./run_spark_job.sh <nome_do_job>
#
# Exemplos:
#   ./run_spark_job.sh bronze_to_minio
#   ./run_spark_job.sh silver_to_minio
#   ./run_spark_job.sh gold_to_minio
#   ./run_spark_job.sh bronze_layer
#   ./run_spark_job.sh silver_layer
#   ./run_spark_job.sh gold_layer
#
# Por que este script é necessário?
# ---------------------------------
# Quando usamos spark-submit, os JARs devem ser passados via linha
# de comando porque a JVM do Spark é criada ANTES de ler o código
# Python. Configurações como spark.jars no Python são ignoradas
# quando já existe um SparkContext ativo.
#
# Em execução local (python script.py), o spark.jars funciona
# porque a JVM é criada pelo próprio código Python.
# ============================================================

set -e  # Para em caso de erro

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verificar argumento
if [ -z "$1" ]; then
    echo -e "${RED}❌ Erro: Informe o nome do job${NC}"
    echo ""
    echo "Uso: $0 <nome_do_job>"
    echo ""
    echo "Jobs disponíveis:"
    echo "  - bronze_to_minio  : RAW (JSON) → Bronze (Parquet) no MinIO"
    echo "  - silver_to_minio  : Silver local → MinIO"
    echo "  - gold_to_minio    : Gold local → MinIO"
    echo "  - bronze_layer     : RAW → Bronze local"
    echo "  - silver_layer     : Bronze → Silver local"
    echo "  - gold_layer       : Silver → Gold local"
    echo "  - fraud_detection  : Análise de fraude"
    echo "  - load_to_postgres : Gold → PostgreSQL"
    exit 1
fi

JOB_NAME=$1
JOB_FILE="/jobs/${JOB_NAME}.py"

# Verificar se o job existe
if ! docker exec fraud_spark_master test -f "$JOB_FILE"; then
    echo -e "${RED}❌ Erro: Job não encontrado: ${JOB_FILE}${NC}"
    echo ""
    echo "Jobs disponíveis:"
    docker exec fraud_spark_master ls /jobs/*.py 2>/dev/null | xargs -n1 basename | sed 's/.py$//'
    exit 1
fi

echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}🚀 Executando: ${JOB_NAME}${NC}"
echo -e "${GREEN}============================================================${NC}"

# Configuração dos JARs
# ---------------------
# hadoop-aws-3.3.4 + aws-sdk-bundle-1.12.262 = AWS SDK v1
# Esta combinação funciona com MinIO via HTTP
# NÃO usar hadoop-aws-3.4.x que usa AWS SDK v2 (bug com MinIO)
JARS="/jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar"
CLASSPATH="/jars/hadoop-aws-3.3.4.jar:/jars/aws-java-sdk-bundle-1.12.262.jar"

# Configurações S3A para MinIO
# ----------------------------
# endpoint: usar 'minio' (service name), NÃO 'fraud_minio' (container_name)
#           hostnames com underscore causam erro no AWS SDK
# path.style.access: MinIO usa path-style (bucket no path da URL)
# connection.ssl.enabled: false porque usamos HTTP, não HTTPS

docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --jars "$JARS" \
    --conf "spark.driver.extraClassPath=$CLASSPATH" \
    --conf "spark.executor.extraClassPath=$CLASSPATH" \
    --conf "spark.hadoop.fs.s3a.endpoint=http://minio:9000" \
    --conf "spark.hadoop.fs.s3a.access.key=minioadmin" \
    --conf "spark.hadoop.fs.s3a.secret.key=minioadmin123@@!!_2" \
    --conf "spark.hadoop.fs.s3a.path.style.access=true" \
    --conf "spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem" \
    --conf "spark.hadoop.fs.s3a.connection.ssl.enabled=false" \
    "$JOB_FILE"

echo ""
echo -e "${GREEN}✅ Job ${JOB_NAME} concluído!${NC}"
