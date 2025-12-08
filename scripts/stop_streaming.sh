#!/bin/bash
# ============================================
# SCRIPT PARA PARAR JOBS DE STREAMING
# ============================================
# Uso: ./scripts/stop_streaming.sh
# ============================================

echo "════════════════════════════════════════════════════════════"
echo "🛑 PARANDO JOBS DE STREAMING"
echo "════════════════════════════════════════════════════════════"
echo "📅 $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Parar streaming_to_postgres
echo "🔄 Parando streaming_to_postgres..."
docker exec fraud_spark_master pkill -f "streaming_to_postgres" 2>/dev/null || true

# Parar streaming_realtime_dashboard
echo "🔄 Parando streaming_realtime_dashboard..."
docker exec fraud_spark_master pkill -f "streaming_realtime_dashboard" 2>/dev/null || true

sleep 5

# Verificar
STREAMING_COUNT=$(docker exec fraud_spark_master pgrep -f "streaming" 2>/dev/null | wc -l)

if [ "$STREAMING_COUNT" -eq 0 ]; then
    echo ""
    echo "✅ Todos os jobs de streaming foram parados!"
else
    echo ""
    echo "⚠️ Ainda há $STREAMING_COUNT processos de streaming rodando"
    echo "   Forçando parada..."
    docker exec fraud_spark_master pkill -9 -f "streaming" 2>/dev/null || true
fi

# Status final
echo ""
CORES_INFO=$(curl -s http://localhost:8081/json/ 2>/dev/null)
CORES_USED=$(echo $CORES_INFO | python3 -c "import sys,json; print(json.load(sys.stdin).get('coresused',0))" 2>/dev/null || echo "?")
echo "📊 Cores em uso: $CORES_USED"
echo ""
echo "════════════════════════════════════════════════════════════"
