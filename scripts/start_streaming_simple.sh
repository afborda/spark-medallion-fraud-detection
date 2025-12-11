#!/bin/bash
# ============================================
# STREAMING SIMPLES - APENAS POSTGRES
# ============================================
# 1 job, 2 cores, 2GB RAM

echo "🚀 Iniciando Streaming (simplificado)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Parar tudo
echo "🔄 Parando jobs antigos..."
docker exec fraud_spark_master pkill -9 -f streaming 2>/dev/null || true
sleep 3

# Status do cluster
CORES_USED=$(curl -s http://localhost:8081/json/ | jq -r '.coresused // 0')
echo "📊 Cores em uso: ${CORES_USED}/4"

# Iniciar apenas streaming_to_postgres
echo "🚀 Iniciando streaming_to_postgres (2 cores, 1.5GB RAM)..."
docker exec -d fraud_spark_master spark-submit \
    --master spark://spark-master:7077 \
    --total-executor-cores 2 \
    --executor-memory 1500m \
    --conf spark.streaming.stopGracefullyOnShutdown=true \
    /jobs/streaming/streaming_to_postgres.py

sleep 15

# Verificar
if docker exec fraud_spark_master pgrep -f "streaming_to_postgres" > /dev/null; then
    APPS=$(curl -s http://localhost:8081/json/ | jq -r '.activeapps | length')
    echo "✅ Streaming iniciado! Apps ativos: ${APPS}"
else
    echo "❌ Falhou ao iniciar"
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Pronto! Aguarde 1-2 minutos para processar backlog"
