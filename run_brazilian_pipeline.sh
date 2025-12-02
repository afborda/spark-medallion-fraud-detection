#!/bin/bash
# ============================================
# 🚀 RUN BRAZILIAN PIPELINE
# Executa pipeline completo com configuração otimizada
# 
# Configuração:
# - 5 Workers (10 cores, 15GB RAM total)
# - Partições: 128MB por lote
# - spark.sql.files.maxPartitionBytes = 128MB
# - Partições = 128MB * 10 cores = ~1.28GB por rodada
# ============================================

set -e

SPARK_MASTER="spark://spark-master:7077"
JARS="/jars/hadoop-aws-3.3.4.jar,/jars/aws-java-sdk-bundle-1.12.262.jar,/jars/postgresql-42.7.4.jar"
CLASSPATH="/jars/hadoop-aws-3.3.4.jar:/jars/aws-java-sdk-bundle-1.12.262.jar:/jars/postgresql-42.7.4.jar"

# Configurações de particionamento otimizado
# 128MB por partição, distribuído entre todos os cores
SPARK_CONF=(
    "--conf" "spark.sql.files.maxPartitionBytes=134217728"
    "--conf" "spark.sql.shuffle.partitions=20"
    "--conf" "spark.default.parallelism=10"
    "--conf" "spark.executor.extraClassPath=$CLASSPATH"
    "--conf" "spark.driver.extraClassPath=$CLASSPATH"
    "--conf" "spark.sql.adaptive.enabled=true"
    "--conf" "spark.sql.adaptive.coalescePartitions.enabled=true"
    "--conf" "spark.sql.adaptive.coalescePartitions.minPartitionSize=67108864"
)

echo "============================================"
echo "🚀 BRAZILIAN FRAUD DETECTION PIPELINE"
echo "============================================"
echo "📊 Configuração:"
echo "   • Workers: 5 (2 cores cada = 10 cores)"
echo "   • Memória: 3GB por executor"
echo "   • Partições: 128MB por lote"
echo "   • Shuffle partitions: 20"
echo "============================================"
echo ""

# Função para executar job
run_job() {
    local job_name=$1
    local job_path=$2
    
    echo "🔄 Executando: $job_name"
    echo "   Arquivo: $job_path"
    
    docker exec fraud_spark_master /opt/spark/bin/spark-submit \
        --master $SPARK_MASTER \
        --deploy-mode client \
        --executor-memory 3g \
        --total-executor-cores 10 \
        --jars $JARS \
        "${SPARK_CONF[@]}" \
        $job_path 2>&1 | grep -vE "^[0-9]{2}/[0-9]{2}/[0-9]{2}|INFO|WARN"
    
    echo ""
}

# Pipeline stages
case "${1:-all}" in
    bronze)
        run_job "🥉 BRONZE LAYER" "/jobs/production/bronze_brazilian.py"
        ;;
    silver)
        run_job "🥈 SILVER LAYER" "/jobs/production/silver_brazilian.py"
        ;;
    gold)
        run_job "🥇 GOLD LAYER" "/jobs/production/gold_brazilian.py"
        ;;
    postgres)
        run_job "📦 LOAD TO POSTGRES" "/jobs/production/load_to_postgres.py"
        ;;
    all)
        echo "🔄 Executando pipeline completo..."
        echo ""
        run_job "🥉 BRONZE LAYER" "/jobs/production/bronze_brazilian.py"
        run_job "🥈 SILVER LAYER" "/jobs/production/silver_brazilian.py"
        run_job "🥇 GOLD LAYER" "/jobs/production/gold_brazilian.py"
        run_job "📦 LOAD TO POSTGRES" "/jobs/production/load_to_postgres.py"
        ;;
    *)
        echo "Uso: $0 {bronze|silver|gold|postgres|all}"
        exit 1
        ;;
esac

echo "============================================"
echo "✅ Pipeline concluído!"
echo "============================================"
