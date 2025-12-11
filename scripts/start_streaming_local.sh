#!/bin/bash
# ============================================
# STREAMING EM LOCAL MODE (SEM CLUSTER)
# FUNCIONA GARANTIDO!
# ============================================

echo "🚀 Streaming em LOCAL MODE (mais simples)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Parar tudo
docker exec fraud_spark_master pkill -9 -f streaming 2>/dev/null || true
sleep 3

# Rodar em LOCAL MODE (dentro do próprio driver, sem executors)
echo "🚀 Iniciando em modo local..."
docker exec -d fraud_spark_master spark-submit \
    --master local[2] \
    --driver-memory 2g \
    /jobs/streaming/streaming_to_postgres.py

sleep 15

if docker exec fraud_spark_master pgrep -f "streaming_to_postgres" > /dev/null; then
    echo "✅ Streaming rodando em LOCAL MODE!"
else
    echo "❌ Falhou"
    exit 1
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Pronto! Dados devem aparecer no banco em ~30s"
