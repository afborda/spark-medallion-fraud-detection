#!/bin/bash
# ============================================
# SCRIPT DE INICIALIZAÇÃO DOS JOBS DE STREAMING
# ============================================
# Uso: ./scripts/start_streaming.sh
# 
# VPS: 8 vCores, 24 GB RAM
# Cluster: 4 workers x 1 core = 4 cores total
# Streaming usa 100% quando batch não está rodando
# ============================================

set -e

# Configurações de recursos (VPS atualizada)
STREAMING_POSTGRES_CORES=2    # 50% do cluster
STREAMING_DASHBOARD_CORES=2   # 50% do cluster
TOTAL_STREAMING_CORES=4       # 100% do cluster para streaming

echo "════════════════════════════════════════════════════════════"
echo "🚀 INICIANDO JOBS DE STREAMING"
echo "════════════════════════════════════════════════════════════"
echo "📅 $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Verificar se o Spark Master está rodando
if ! docker ps | grep -q fraud_spark_master; then
    echo "❌ ERRO: Spark Master não está rodando!"
    echo "   Execute: docker compose up -d"
    exit 1
fi

# Verificar recursos disponíveis
echo "📊 Verificando recursos do cluster..."
CORES_INFO=$(curl -s http://localhost:8081/json/ 2>/dev/null)
TOTAL_CORES=$(echo $CORES_INFO | python3 -c "import sys,json; print(json.load(sys.stdin).get('cores',0))")
CORES_USED=$(echo $CORES_INFO | python3 -c "import sys,json; print(json.load(sys.stdin).get('coresused',0))")

echo "   Total de cores: $TOTAL_CORES"
echo "   Cores em uso:   $CORES_USED"
echo ""

# Parar jobs existentes (se houver)
echo "🔄 Parando jobs de streaming existentes..."
docker exec fraud_spark_master pkill -f "streaming_to_postgres" 2>/dev/null || true
docker exec fraud_spark_master pkill -f "streaming_realtime_dashboard" 2>/dev/null || true
sleep 5

# Limpar checkpoints antigos (opcional - descomente se quiser resetar)
# echo "🧹 Limpando checkpoints antigos..."
# docker exec fraud_spark_master rm -rf /data/checkpoints/streaming_postgres 2>/dev/null || true
# docker exec fraud_spark_master rm -rf /data/checkpoints/streaming_dashboard 2>/dev/null || true

# Criar diretório de checkpoints persistente
echo "📁 Configurando diretórios de checkpoint..."
docker exec fraud_spark_master mkdir -p /data/checkpoints/streaming_postgres
docker exec fraud_spark_master mkdir -p /data/checkpoints/streaming_dashboard

# Iniciar streaming_to_postgres (principal)
echo ""
echo "🚀 Iniciando streaming_to_postgres com $STREAMING_POSTGRES_CORES cores..."
docker exec -d fraud_spark_master \
    /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --total-executor-cores $STREAMING_POSTGRES_CORES \
    --executor-memory 1g \
    --conf spark.streaming.stopGracefullyOnShutdown=true \
    --conf spark.sql.adaptive.enabled=true \
    /jobs/streaming/streaming_to_postgres.py

sleep 10

# Verificar se iniciou
if docker exec fraud_spark_master pgrep -f "streaming_to_postgres" > /dev/null; then
    echo "   ✅ streaming_to_postgres iniciado!"
else
    echo "   ❌ ERRO: streaming_to_postgres não iniciou!"
    exit 1
fi

# Iniciar streaming_realtime_dashboard
echo ""
echo "🚀 Iniciando streaming_realtime_dashboard com $STREAMING_DASHBOARD_CORES cores..."
docker exec -d fraud_spark_master \
    /opt/spark/bin/spark-submit \
    --master spark://spark-master:7077 \
    --total-executor-cores $STREAMING_DASHBOARD_CORES \
    --executor-memory 1g \
    --conf spark.streaming.stopGracefullyOnShutdown=true \
    --conf spark.sql.adaptive.enabled=true \
    /jobs/streaming/streaming_realtime_dashboard.py

sleep 10

# Verificar se iniciou
if docker exec fraud_spark_master pgrep -f "streaming_realtime_dashboard" > /dev/null; then
    echo "   ✅ streaming_realtime_dashboard iniciado!"
else
    echo "   ⚠️ AVISO: streaming_realtime_dashboard pode não ter iniciado"
fi

# Status final
echo ""
echo "════════════════════════════════════════════════════════════"
echo "📊 STATUS FINAL"
echo "════════════════════════════════════════════════════════════"

CORES_INFO=$(curl -s http://localhost:8081/json/ 2>/dev/null)
CORES_USED=$(echo $CORES_INFO | python3 -c "import sys,json; print(json.load(sys.stdin).get('coresused',0))")
APPS_COUNT=$(echo $CORES_INFO | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('activeapps',[])))")

echo "   Cores em uso:     $CORES_USED/$TOTAL_CORES ($(( CORES_USED * 100 / TOTAL_CORES ))%)"
echo "   Apps ativos:      $APPS_COUNT"
echo "   Reserva (batch):  $(( TOTAL_CORES - CORES_USED )) cores"
echo ""
echo "   📊 streaming_to_postgres      → $STREAMING_POSTGRES_CORES cores"
echo "   📈 streaming_realtime_dashboard → $STREAMING_DASHBOARD_CORES cores"
echo ""
echo "════════════════════════════════════════════════════════════"
echo "✅ Streaming iniciado com sucesso!"
echo "════════════════════════════════════════════════════════════"
