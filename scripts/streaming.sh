#!/bin/bash
# ============================================
# 🚀 STREAMING MANAGER - Start/Stop/Status
# ============================================
# Uso:
#   ./scripts/streaming.sh start   # Inicia streaming
#   ./scripts/streaming.sh stop    # Para streaming (gracioso)
#   ./scripts/streaming.sh status  # Verifica status
#   ./scripts/streaming.sh restart # Reinicia streaming
#
# CONFIGURAÇÃO FIXA (2 workers × 2 cores = 4 cores total):
#   Streaming: 2 cores, 4g executor memory (50% do cluster)
#   Batch:     4 cores, 4g executor memory (100% do cluster)
# ============================================

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configurações fixas (não alterar)
STREAMING_CORES=2
STREAMING_MEMORY="4g"
GRACEFUL_TIMEOUT=60

# ============================================
# FUNÇÕES
# ============================================

check_master() {
    if ! docker ps | grep -q fraud_spark_master; then
        echo -e "${RED}❌ Spark Master não está rodando!${NC}"
        echo "   Execute: docker compose up -d"
        exit 1
    fi
}

get_cluster_status() {
    curl -s http://localhost:8081/json/ 2>/dev/null || echo "{}"
}

show_status() {
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}📊 STATUS DO CLUSTER SPARK${NC}"
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
    
    local STATUS=$(get_cluster_status)
    local WORKERS=$(echo "$STATUS" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('workers',[])))" 2>/dev/null || echo "0")
    local CORES=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cores',0))" 2>/dev/null || echo "0")
    local CORES_USED=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('coresused',0))" 2>/dev/null || echo "0")
    local APPS=$(echo "$STATUS" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('activeapps',[])))" 2>/dev/null || echo "0")
    
    echo -e "   Workers:     ${GREEN}$WORKERS${NC}"
    echo -e "   Cores:       ${GREEN}$CORES_USED/$CORES${NC}"
    echo -e "   Apps ativas: ${GREEN}$APPS${NC}"
    
    # Verificar processos de streaming
    local STREAMING_PROCS=$(docker exec fraud_spark_master pgrep -f "streaming_to_postgres" 2>/dev/null | wc -l)
    
    if [ "$STREAMING_PROCS" -gt 0 ]; then
        echo -e "   Streaming:   ${GREEN}✅ RODANDO${NC}"
    else
        echo -e "   Streaming:   ${YELLOW}⏹️  PARADO${NC}"
    fi
    
    echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
}

stop_streaming() {
    echo -e "${YELLOW}════════════════════════════════════════════════════════════${NC}"
    echo -e "${YELLOW}🛑 PARANDO STREAMING (gracioso, timeout ${GRACEFUL_TIMEOUT}s)${NC}"
    echo -e "${YELLOW}════════════════════════════════════════════════════════════${NC}"
    
    # Verificar se há processos rodando
    local PIDS=$(docker exec fraud_spark_master pgrep -f "streaming_to_postgres" 2>/dev/null || true)
    
    if [ -z "$PIDS" ]; then
        echo -e "${GREEN}✅ Nenhum processo de streaming rodando${NC}"
        return 0
    fi
    
    echo -e "   PIDs encontrados: $PIDS"
    
    # Enviar SIGTERM (gracioso)
    echo -e "${BLUE}📤 Enviando SIGTERM...${NC}"
    docker exec fraud_spark_master pkill -TERM -f "streaming_to_postgres" 2>/dev/null || true
    
    # Aguardar com verificação a cada 5 segundos
    local WAITED=0
    while [ $WAITED -lt $GRACEFUL_TIMEOUT ]; do
        sleep 5
        WAITED=$((WAITED + 5))
        
        PIDS=$(docker exec fraud_spark_master pgrep -f "streaming_to_postgres" 2>/dev/null || true)
        if [ -z "$PIDS" ]; then
            echo -e "${GREEN}✅ Streaming parado graciosamente após ${WAITED}s${NC}"
            return 0
        fi
        
        echo -e "   ⏳ Aguardando... ${WAITED}s/${GRACEFUL_TIMEOUT}s"
    done
    
    # Se ainda está rodando, forçar com SIGKILL
    echo -e "${RED}⚠️ Timeout! Forçando parada com SIGKILL...${NC}"
    docker exec fraud_spark_master pkill -9 -f "streaming_to_postgres" 2>/dev/null || true
    docker exec fraud_spark_master pkill -9 -f "SparkSubmit.*streaming" 2>/dev/null || true
    
    sleep 3
    
    PIDS=$(docker exec fraud_spark_master pgrep -f "streaming_to_postgres" 2>/dev/null || true)
    if [ -z "$PIDS" ]; then
        echo -e "${GREEN}✅ Streaming parado (forçado)${NC}"
    else
        echo -e "${RED}❌ Falha ao parar streaming!${NC}"
        return 1
    fi
}

start_streaming() {
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}🚀 INICIANDO STREAMING${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "   Cores:  ${STREAMING_CORES}"
    echo -e "   Memory: ${STREAMING_MEMORY}"
    echo ""
    
    # Verificar se já está rodando
    local PIDS=$(docker exec fraud_spark_master pgrep -f "streaming_to_postgres" 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo -e "${YELLOW}⚠️ Streaming já está rodando (PIDs: $PIDS)${NC}"
        echo -e "   Use: ./scripts/streaming.sh restart"
        return 0
    fi
    
    # Verificar workers disponíveis
    local STATUS=$(get_cluster_status)
    local WORKERS=$(echo "$STATUS" | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('workers',[])))" 2>/dev/null || echo "0")
    
    if [ "$WORKERS" -lt 1 ]; then
        echo -e "${RED}❌ Nenhum worker disponível!${NC}"
        echo "   Aguarde os workers iniciarem ou execute: docker compose up -d"
        exit 1
    fi
    
    echo -e "${BLUE}📤 Submetendo job...${NC}"
    
    # Iniciar streaming em background
    docker exec -d fraud_spark_master /opt/spark/bin/spark-submit \
        --master spark://spark-master:7077 \
        --total-executor-cores $STREAMING_CORES \
        --executor-memory $STREAMING_MEMORY \
        --conf spark.streaming.stopGracefullyOnShutdown=true \
        --conf spark.sql.adaptive.enabled=true \
        --conf spark.dynamicAllocation.enabled=false \
        /jobs/streaming/streaming_to_postgres.py
    
    # Aguardar inicialização
    echo -e "${BLUE}⏳ Aguardando inicialização...${NC}"
    sleep 15
    
    # Verificar se iniciou
    PIDS=$(docker exec fraud_spark_master pgrep -f "streaming_to_postgres" 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
        echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
        echo -e "${GREEN}✅ STREAMING INICIADO COM SUCESSO!${NC}"
        echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
        show_status
    else
        echo -e "${RED}❌ Falha ao iniciar streaming!${NC}"
        echo "   Verifique os logs: docker logs fraud_spark_master"
        exit 1
    fi
}

# ============================================
# MAIN
# ============================================

ACTION=${1:-status}

check_master

case $ACTION in
    start)
        start_streaming
        ;;
    stop)
        stop_streaming
        ;;
    restart)
        stop_streaming
        sleep 5
        start_streaming
        ;;
    status)
        show_status
        ;;
    *)
        echo "Uso: $0 {start|stop|restart|status}"
        exit 1
        ;;
esac
