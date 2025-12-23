#!/bin/bash
# ============================================
# 🔄 BATCH PIPELINE - Geração de Dados + Medallion
# ============================================
# Uso:
#   ./scripts/batch.sh              # Executa pipeline completo (5GB default)
#   ./scripts/batch.sh generate     # Apenas gera dados
#   ./scripts/batch.sh medallion    # Apenas executa medallion
#   ./scripts/batch.sh clean        # Limpa bronze/silver/gold (mantém raw)
#   SIZE=10GB ./scripts/batch.sh    # Pipeline com 10GB de dados
#   CLEAN=1 ./scripts/batch.sh      # Limpa dados antigos antes de rodar
#
# FLUXO AUTOMÁTICO:
#   1. Para streaming graciosamente
#   2. Gera dados batch para MinIO (fraud-generator)
#   3. Executa pipeline medallion (Bronze → Silver → Gold → Postgres)
#   4. Reinicia streaming
#
# CONFIGURAÇÃO FIXA (2 workers × 2 cores = 4 cores total):
#   Batch: 4 cores, 4g executor memory (100% do cluster)
# ============================================

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Configurações fixas (não alterar)
BATCH_CORES=4
BATCH_MEMORY="4g"
DEFAULT_SIZE="5GB"

# Diretório base
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# ============================================
# FUNÇÕES
# ============================================

log_step() {
    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${CYAN}📌 $1${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════════${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️ $1${NC}"
}

clean_medallion_data() {
    log_step "Limpando dados do Medallion (bronze/silver/gold)..."
    
    echo "   ⚠️  Isso removerá todos os dados de bronze, silver e gold"
    echo "   📁 Raw será preservado"
    
    # Limpar via container MinIO
    docker exec fraud_minio sh -c "rm -rf /data/fraud-data/bronze/* /data/fraud-data/silver/* /data/fraud-data/gold/*" 2>/dev/null || true
    
    log_success "Dados limpos!"
}

check_infrastructure() {
    log_step "Verificando infraestrutura..."
    
    # Verificar Spark Master
    if ! docker ps | grep -q fraud_spark_master; then
        log_error "Spark Master não está rodando!"
        echo "   Execute: docker compose up -d"
        exit 1
    fi
    
    # Verificar MinIO
    if ! docker ps | grep -q fraud_minio; then
        log_error "MinIO não está rodando!"
        echo "   Execute: docker compose up -d"
        exit 1
    fi
    
    # Verificar workers
    local WORKERS=$(curl -s http://localhost:8081/json/ 2>/dev/null | python3 -c "import sys,json; print(len(json.load(sys.stdin).get('workers',[])))" 2>/dev/null || echo "0")
    
    if [ "$WORKERS" -lt 1 ]; then
        log_error "Nenhum worker disponível!"
        echo "   Aguarde os workers iniciarem..."
        exit 1
    fi
    
    log_success "Infraestrutura OK ($WORKERS workers)"
}

stop_streaming() {
    log_step "Parando streaming..."
    
    # Usar script de streaming se existir
    if [ -x "$SCRIPT_DIR/streaming.sh" ]; then
        "$SCRIPT_DIR/streaming.sh" stop
    else
        # Fallback
        docker exec fraud_spark_master pkill -TERM -f "streaming_to_postgres" 2>/dev/null || true
        sleep 10
        docker exec fraud_spark_master pkill -9 -f "streaming_to_postgres" 2>/dev/null || true
    fi
    
    sleep 5
    log_success "Streaming parado"
}

start_streaming() {
    log_step "Reiniciando streaming..."
    
    # Usar script de streaming se existir
    if [ -x "$SCRIPT_DIR/streaming.sh" ]; then
        "$SCRIPT_DIR/streaming.sh" start
    else
        # Fallback
        docker exec -d fraud_spark_master /opt/spark/bin/spark-submit \
            --master spark://spark-master:7077 \
            --total-executor-cores 2 \
            --executor-memory 4g \
            --conf spark.streaming.stopGracefullyOnShutdown=true \
            /jobs/streaming/streaming_to_postgres.py
        sleep 15
    fi
    
    log_success "Streaming reiniciado"
}

generate_data() {
    local SIZE=${SIZE:-$DEFAULT_SIZE}
    
    log_step "Gerando dados batch ($SIZE)..."
    echo "   Destino: minio://fraud-data/raw/batch"
    echo "   Formato: parquet"
    echo ""
    
    # Executar fraud-generator-batch
    cd "$PROJECT_DIR"
    
    # Usar docker compose run para garantir que o container termine
    docker compose run --rm \
        -e SIZE="$SIZE" \
        fraud-generator-batch
    
    local EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        log_success "Dados gerados com sucesso!"
    else
        log_error "Falha ao gerar dados (exit code: $EXIT_CODE)"
        return 1
    fi
}

run_medallion_job() {
    local JOB_NAME=$1
    local JOB_PATH=$2
    
    echo -e "${BLUE}   🔄 Executando: $JOB_NAME${NC}"
    
    docker exec fraud_spark_master /opt/spark/bin/spark-submit \
        --master spark://spark-master:7077 \
        --total-executor-cores $BATCH_CORES \
        --executor-memory $BATCH_MEMORY \
        --conf spark.sql.adaptive.enabled=true \
        --conf spark.sql.adaptive.coalescePartitions.enabled=true \
        "$JOB_PATH" 2>&1 | grep -E "(^=|🥉|🥈|🥇|📂|🔍|✅|⚠️|❌|📊|🔄|💾|registros|Lidos|CONCLU|records|count|Error|Exception)" || true
    
    local EXIT_CODE=${PIPESTATUS[0]}
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo -e "${GREEN}   ✅ $JOB_NAME concluído${NC}"
    else
        echo -e "${RED}   ❌ $JOB_NAME falhou (exit code: $EXIT_CODE)${NC}"
        return 1
    fi
}

run_medallion_pipeline() {
    log_step "Executando Pipeline Medallion..."
    echo "   Bronze → Silver → Gold → PostgreSQL"
    echo "   Cores: $BATCH_CORES | Memory: $BATCH_MEMORY"
    echo ""
    
    local START_TIME=$(date +%s)
    
    # Bronze
    run_medallion_job "BRONZE (Raw → Bronze)" "/jobs/production/batch_bronze_from_raw.py"
    
    # Silver
    run_medallion_job "SILVER (Bronze → Silver)" "/jobs/production/batch_silver_from_bronze.py"
    
    # Gold
    run_medallion_job "GOLD (Silver → Gold)" "/jobs/production/batch_gold_from_silver.py"
    
    # PostgreSQL
    run_medallion_job "POSTGRES (Gold → PostgreSQL)" "/jobs/production/batch_postgres_from_gold.py"
    
    local END_TIME=$(date +%s)
    local DURATION=$((END_TIME - START_TIME))
    local MINUTES=$((DURATION / 60))
    local SECONDS=$((DURATION % 60))
    
    log_success "Pipeline Medallion concluído em ${MINUTES}m ${SECONDS}s"
}

show_summary() {
    echo ""
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}🎉 BATCH PIPELINE CONCLUÍDO!${NC}"
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
    
    # Status do cluster
    local STATUS=$(curl -s http://localhost:8081/json/ 2>/dev/null)
    local CORES_USED=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('coresused',0))" 2>/dev/null || echo "?")
    local CORES=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('cores',0))" 2>/dev/null || echo "?")
    
    echo "   📊 Cluster: $CORES_USED/$CORES cores em uso"
    
    # Verificar streaming
    local STREAMING_PROCS=$(docker exec fraud_spark_master pgrep -f "streaming_to_postgres" 2>/dev/null | wc -l)
    if [ "$STREAMING_PROCS" -gt 0 ]; then
        echo -e "   🚀 Streaming: ${GREEN}RODANDO${NC}"
    else
        echo -e "   🚀 Streaming: ${YELLOW}PARADO${NC}"
    fi
    
    echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
}

# ============================================
# MAIN
# ============================================

ACTION=${1:-full}
SIZE=${SIZE:-$DEFAULT_SIZE}
CLEAN=${CLEAN:-0}

echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}🔄 BATCH PIPELINE${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════${NC}"
echo "   📅 $(date '+%Y-%m-%d %H:%M:%S')"
echo "   📦 Tamanho: $SIZE"
echo "   ⚙️  Modo: $ACTION"
if [ "$CLEAN" = "1" ]; then
    echo "   🧹 Limpeza: Ativada"
fi
echo ""

check_infrastructure

# Limpar dados se solicitado
if [ "$CLEAN" = "1" ]; then
    clean_medallion_data
fi

case $ACTION in
    full)
        stop_streaming
        generate_data
        run_medallion_pipeline
        start_streaming
        show_summary
        ;;
    generate)
        stop_streaming
        generate_data
        start_streaming
        show_summary
        ;;
    medallion)
        stop_streaming
        run_medallion_pipeline
        start_streaming
        show_summary
        ;;
    clean)
        clean_medallion_data
        ;;
    *)
        echo "Uso: $0 {full|generate|medallion|clean}"
        echo ""
        echo "  full      - Pipeline completo (gera dados + medallion)"
        echo "  generate  - Apenas gera dados batch"
        echo "  medallion - Apenas executa pipeline medallion"
        echo "  clean     - Limpa dados bronze/silver/gold (preserva raw)"
        echo ""
        echo "Variáveis de ambiente:"
        echo "  SIZE=10GB $0     - Define tamanho dos dados (default: 5GB)"
        echo "  CLEAN=1 $0 full  - Limpa dados antes de executar"
        exit 1
        ;;
esac
