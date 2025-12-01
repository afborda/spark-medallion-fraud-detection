"""
🥈 SILVER LAYER - Bronze → Silver (MinIO)
Limpeza e enriquecimento dos dados
"""

from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    from_json, col, when, abs as spark_abs, sqrt, pow as spark_pow,
    current_timestamp, round as spark_round,
    # NOVOS IMPORTS para Window Functions:
    lag      # Pegar valor da linha anterior (como explicado!)
)
from pyspark.sql.window import Window  # Para criar janelas de análise
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    BooleanType, LongType, IntegerType
)

print("=" * 60)
print("🥈 SILVER LAYER - Bronze → Silver")
print("=" * 60)

# Schema das transações
transaction_schema = StructType([
    StructField("transaction_id", StringType(), True),
    StructField("customer_id", StringType(), True),
    StructField("amount", DoubleType(), True),
    StructField("merchant", StringType(), True),
    StructField("category", StringType(), True),
    StructField("transaction_hour", DoubleType(), True),
    StructField("day_of_week", StringType(), True),
    StructField("customer_home_state", StringType(), True),
    StructField("purchase_state", StringType(), True),
    StructField("purchase_city", StringType(), True),
    StructField("purchase_latitude", DoubleType(), True),
    StructField("purchase_longitude", DoubleType(), True),
    StructField("device_latitude", DoubleType(), True),
    StructField("device_longitude", DoubleType(), True),
    StructField("device_id", StringType(), True),
    StructField("ip_address", StringType(), True),
    StructField("payment_method", StringType(), True),
    StructField("card_brand", StringType(), True),
    StructField("installments", IntegerType(), True),
    StructField("had_travel_purchase_last_12m", BooleanType(), True),
    StructField("is_first_purchase_in_state", BooleanType(), True),
    StructField("transactions_last_24h", DoubleType(), True),
    StructField("avg_transaction_amount_30d", DoubleType(), True),
    StructField("is_international", BooleanType(), True),
    StructField("is_online", BooleanType(), True),
    StructField("is_fraud", BooleanType(), True),
    StructField("timestamp", LongType(), True)
])

# JARs
JARS_PATH = "/jars"
HADOOP_AWS = f"{JARS_PATH}/hadoop-aws-3.3.4.jar"
AWS_SDK = f"{JARS_PATH}/aws-java-sdk-bundle-1.12.262.jar"
JARS = f"{HADOOP_AWS},{AWS_SDK}"
CLASSPATH = f"{HADOOP_AWS}:{AWS_SDK}"

spark = SparkSession.builder \
    .appName("Silver_Bronze_to_Silver") \
    .config("spark.jars", JARS) \
    .config("spark.driver.extraClassPath", CLASSPATH) \
    .config("spark.executor.extraClassPath", CLASSPATH) \
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio:9000") \
    .config("spark.hadoop.fs.s3a.access.key", "minioadmin") \
    .config("spark.hadoop.fs.s3a.secret.key", "minioadmin123@@!!_2") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false") \
    .getOrCreate()

spark.sparkContext.setLogLevel("WARN")

# Ler Bronze
bronze_path = "s3a://fraud-data/medallion/bronze/transactions"
print(f"📂 Lendo Bronze: {bronze_path}")

df_bronze = spark.read.parquet(bronze_path)
total_bronze = df_bronze.count()
print(f"✅ {total_bronze:,} registros no Bronze")

# Parsear JSON
print("🔄 Parseando JSON e limpando dados...")


df_parsed = df_bronze \
    .select(from_json(col("raw_json"), transaction_schema).alias("data")) \
    .select("data.*") \
    .filter(col("transaction_id").isNotNull())

# ============================================================
# REGRA 1: CLONAGEM DE CARTÃO (Window Function)
# ============================================================
# 
# CONCEITO: Detectar quando o MESMO cartão é usado em locais
# geograficamente distantes em um curto período de tempo.
# Isso é IMPOSSÍVEL fisicamente - indica clonagem!
#
# PASSO 1: Criar a "janela" - agrupa por cliente, ordena por tempo
# É como criar uma pasta para cada cliente com suas transações em ordem
#
print("🔍 Aplicando Window Functions para detectar clonagem...")

window_por_cliente = Window.partitionBy("customer_id").orderBy("timestamp")
#                          ↑                            ↑
#                          │                            └─ Ordena por tempo (mais antiga primeiro)
#                          └─ Cada cliente é uma "pasta" separada

# PASSO 2: Usar lag() para pegar dados da transação ANTERIOR
# É como perguntar: "Qual foi a compra anterior deste cliente?"
df_with_prev = df_parsed \
    .withColumn("prev_timestamp", lag("timestamp", 1).over(window_por_cliente)) \
    .withColumn("prev_latitude", lag("purchase_latitude", 1).over(window_por_cliente)) \
    .withColumn("prev_longitude", lag("purchase_longitude", 1).over(window_por_cliente)) \
    .withColumn("prev_state", lag("purchase_state", 1).over(window_por_cliente))
#               ↑              ↑                    ↑        ↑
#               │              │                    │        └─ Aplica na janela que criamos
#               │              │                    └─ 1 = uma linha para trás
#               │              └─ Coluna que quero da linha anterior
#               └─ Nome da nova coluna

# PASSO 3: Calcular diferença de tempo (em minutos)
# timestamp está em segundos, então dividimos por 60
df_with_time_diff = df_with_prev \
    .withColumn("time_since_last_tx",
        when(col("prev_timestamp").isNotNull(),
            (col("timestamp") - col("prev_timestamp")) / 60  # Converte para minutos
        ).otherwise(None)  # Se não tem transação anterior, é NULL
    )

# PASSO 4: Calcular distância geográfica da transação anterior
# Usamos Pitágoras: distância = √((lat2-lat1)² + (lon2-lon1)²)
# NOTA: 1 grau de latitude ≈ 111 km, então multiplicamos por 111
df_with_distance = df_with_time_diff \
    .withColumn("distance_km_from_prev",
        when(col("prev_latitude").isNotNull(),
            sqrt(
                spark_pow(col("purchase_latitude") - col("prev_latitude"), 2) +
                spark_pow(col("purchase_longitude") - col("prev_longitude"), 2)
            ) * 111  # Converte graus para km (aproximado)
        ).otherwise(None)
    )

# ============================================================
# REGRA 2: VELOCIDADE IMPOSSÍVEL
# ============================================================
#
# CONCEITO: Se calculamos distância e tempo entre duas compras,
# podemos calcular a VELOCIDADE necessária para se deslocar.
#
# FÍSICA BÁSICA:
#   velocidade = distância / tempo
#   
# Se a velocidade for maior que um avião (~900 km/h),
# é FISICAMENTE IMPOSSÍVEL - forte indício de fraude!
#
# Exemplo:
#   - Compra 1: São Paulo às 10:00
#   - Compra 2: Manaus às 10:30 (30 minutos depois)
#   - Distância: ~2.700 km
#   - Velocidade necessária: 2700 / 0.5 = 5.400 km/h 
#   - Isso é 6x a velocidade de um avião! IMPOSSÍVEL!
#
print("🚀 Calculando velocidade entre transações...")

df_with_velocity = df_with_distance \
    .withColumn("velocity_kmh",
        when(
            (col("distance_km_from_prev").isNotNull()) & 
            (col("time_since_last_tx") > 0),  # Evita divisão por zero
            # Velocidade = distância(km) / tempo(horas)
            # time_since_last_tx está em minutos, então dividimos por 60
            col("distance_km_from_prev") / (col("time_since_last_tx") / 60)
        ).otherwise(None)
    ) \
    .withColumn("is_impossible_velocity",
        # Se velocidade > 900 km/h (velocidade de avião), é impossível!
        when(col("velocity_kmh") > 900, True).otherwise(False)
    )

# PASSO 5: Criar a FLAG de clonagem
# Suspeito se: tempo < 60 min E distância > 555km (~5 graus) E estados diferentes
df_with_cloning = df_with_velocity \
    .withColumn("is_cloning_suspect",
        when(
            (col("time_since_last_tx") < 60) &                # Menos de 1 hora
            (col("distance_km_from_prev") > 555) &            # Mais de 555km de distância
            (col("prev_state") != col("purchase_state"))      # Estados diferentes
        , True).otherwise(False)
    )

# Transformações Silver - Limpeza e Enriquecimento
# THRESHOLDS REALISTAS para evitar excesso de flags
df_silver = df_with_cloning \
    .withColumn("amount_clean", 
        when(col("amount") < 0, spark_abs(col("amount")))
        .otherwise(col("amount"))) \
    .withColumn("distance_gps",
        spark_round(sqrt(
            spark_pow(col("device_latitude") - col("purchase_latitude"), 2) +
            spark_pow(col("device_longitude") - col("purchase_longitude"), 2)
        ), 4)) \
    .withColumn("is_cross_state",
        # Cross-state só é relevante SE não houver histórico de viagem
        when((col("customer_home_state") != col("purchase_state")) & 
             (col("had_travel_purchase_last_12m") == False), True)
        .otherwise(False)) \
    .withColumn("is_night_transaction",
        # Horário suspeito: 2-5am 
        when((col("transaction_hour") >= 2) & (col("transaction_hour") < 5), True)
        .otherwise(False)) \
    .withColumn("is_high_value",
        # Valor alto: 5x a média 
        when(col("amount") > col("avg_transaction_amount_30d") * 5, True)
        .otherwise(False)) \
    .withColumn("is_high_velocity",
        # Alta velocidade: mais de 15 transações em 24h (não 5)
        when(col("transactions_last_24h") > 15, True)
        .otherwise(False)) \
    .withColumn("is_gps_mismatch",
        # GPS mismatch: distância > 20 graus (~2222km) é suspeito
        # Dados ShadowTraffic têm mediana de 10 graus, p95=21 graus
        # Threshold alto para pegar apenas ~5% dos casos extremos
        when(col("distance_gps") > 20.0, True)
        .otherwise(False)) \
    .withColumn("is_risky_category",
        # REGRA 7: Categoria de Alto Risco
        # Categorias onde fraudes são mais comuns: eletrônicos (alta revenda),
        # passagens aéreas (alto valor, difícil cancelar)
        when(col("category").isin("electronics", "airline_ticket"), True)
        .otherwise(False)) \
    .withColumn("is_online_high_value",
        # REGRA 9: Compra Online de Alto Valor
        # Compras online > R$ 1000 são mais arriscadas porque:
        # 1) Não precisa do cartão físico
        # 2) Endereço de entrega pode ser diferente
        # 3) Mais fácil para fraudadores
        when((col("is_online") == True) & (col("amount") > 1000), True)
        .otherwise(False)) \
    .withColumn("is_many_installments",
        # REGRA 10: Muitas Parcelas em Compra Grande
        # Fraudadores parcelam ao máximo para:
        # 1) Aumentar tempo antes da detecção
        # 2) Diluir o valor por fatura
        # 3) Dificultar rastreamento
        # 10+ parcelas com valor > R$ 500 é suspeito
        when((col("installments") >= 10) & (col("amount") > 500), True)
        .otherwise(False)) \
    .withColumn("silver_timestamp", current_timestamp())

# Salvar Silver
silver_path = "s3a://fraud-data/medallion/silver/transactions"
print(f"💾 Salvando em: {silver_path}")

df_silver.write \
    .mode("overwrite") \
    .parquet(silver_path)

# Verificar
df_check = spark.read.parquet(silver_path)
print(f"✅ SILVER CONCLUÍDO: {df_check.count():,} registros limpos")

# Mostrar estatísticas
print("\n📊 Estatísticas Silver:")
print(f"   - Transações cross-state: {df_check.filter(col('is_cross_state')).count():,}")
print(f"   - Transações noturnas: {df_check.filter(col('is_night_transaction')).count():,}")
print(f"   - Alto valor: {df_check.filter(col('is_high_value')).count():,}")
print(f"   - GPS suspeito: {df_check.filter(col('is_gps_mismatch')).count():,}")
print(f"   - Categoria de risco: {df_check.filter(col('is_risky_category')).count():,}")
print(f"   - Online alto valor: {df_check.filter(col('is_online_high_value')).count():,}")
print(f"   - Muitas parcelas: {df_check.filter(col('is_many_installments')).count():,}")
print(f"   - 🚨 Suspeita clonagem: {df_check.filter(col('is_cloning_suspect')).count():,}")
print(f"   - 🚀 Velocidade impossível: {df_check.filter(col('is_impossible_velocity')).count():,}")
print("=" * 60)

spark.stop()
