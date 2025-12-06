#!/bin/bash
# ============================================================
# Script para executar o Streaming Kafka → PostgreSQL
# 
# Este script configura corretamente a comunicação bidirecional
# entre o Driver (no spark-master) e os Executores (workers).
#
# Uso:
#   ./run_streaming.sh              # Inicia em foreground
#   ./run_streaming.sh --background # Inicia em background
# ============================================================

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Carregar variáveis de ambiente
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Verificar se MINIO_ROOT_PASSWORD está definido
if [ -z "$MINIO_ROOT_PASSWORD" ]; then
    echo -e "${RED}❌ Erro: MINIO_ROOT_PASSWORD não definido${NC}"
    echo "   Execute: source .env"
    exit 1
fi

echo -e "${GREEN}============================================================${NC}"
echo -e "${GREEN}🚀 Iniciando Streaming: Kafka → PostgreSQL${NC}"
echo -e "${GREEN}============================================================${NC}"
echo ""
echo -e "${BLUE}📊 Configurações:${NC}"
echo "   - Driver Host:  spark-master"
echo "   - Driver Port:  5555"
echo "   - UI Port:      4050"
echo "   - Checkpoint:   s3a://fraud-data/streaming/checkpoints/postgres"
echo ""

# Verificar se já existe um processo rodando
if pgrep -f "streaming_to_postgres" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Streaming já está rodando!${NC}"
    echo "   PIDs: $(pgrep -f 'streaming_to_postgres' | tr '\n' ' ')"
    echo ""
    read -p "Deseja parar e reiniciar? (s/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Ss]$ ]]; then
        echo -e "${YELLOW}Parando processos existentes...${NC}"
        pkill -f "streaming_to_postgres" 2>/dev/null || true
        sleep 2
    else
        echo -e "${BLUE}Mantendo processo existente.${NC}"
        exit 0
    fi
fi

# Construir comando spark-submit
SPARK_SUBMIT_CMD="docker exec fraud_spark_master /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --deploy-mode client \
    --conf spark.driver.host=spark-master \
    --conf spark.driver.port=5555 \
    --conf spark.driver.bindAddress=0.0.0.0 \
    --conf spark.ui.port=4050 \
    --conf spark.driver.extraClassPath=/jars/hadoop-aws-3.3.4.jar:/jars/aws-java-sdk-bundle-1.12.262.jar \
    --conf spark.executor.extraClassPath=/jars/hadoop-aws-3.3.4.jar:/jars/aws-java-sdk-bundle-1.12.262.jar \
    --conf spark.hadoop.fs.s3a.endpoint=http://minio:9000 \
    --conf spark.hadoop.fs.s3a.access.key=minioadmin \
    --conf spark.hadoop.fs.s3a.secret.key=${MINIO_ROOT_PASSWORD} \
    --conf spark.hadoop.fs.s3a.path.style.access=true \
    --conf spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem \
    --conf spark.hadoop.fs.s3a.connection.ssl.enabled=false \
    /jobs/streaming/streaming_to_postgres.py"

# Executar em background ou foreground
if [ "$1" == "--background" ] || [ "$1" == "-b" ]; then
    echo -e "${GREEN}▶️  Iniciando em BACKGROUND...${NC}"
    eval "$SPARK_SUBMIT_CMD" > /tmp/streaming_to_postgres.log 2>&1 &
    sleep 5
    
    if pgrep -f "streaming_to_postgres" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Streaming iniciado com sucesso!${NC}"
        echo ""
        echo -e "${BLUE}📝 Para ver os logs:${NC}"
        echo "   tail -f /tmp/streaming_to_postgres.log"
        echo ""
        echo -e "${BLUE}🛑 Para parar:${NC}"
        echo "   pkill -f streaming_to_postgres"
    else
        echo -e "${RED}❌ Falha ao iniciar streaming${NC}"
        echo "   Verifique: tail -50 /tmp/streaming_to_postgres.log"
        exit 1
    fi
else
    echo -e "${GREEN}▶️  Iniciando em FOREGROUND (Ctrl+C para parar)...${NC}"
    echo ""
    eval "$SPARK_SUBMIT_CMD"
fi
