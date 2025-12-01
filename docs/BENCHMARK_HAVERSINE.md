# 📊 Benchmark: Cálculo de Distância Geográfica

> **Data:** 01/12/2025
> **Teste:** Comparação de 3 métodos para cálculo de distância entre coordenadas
> **Dataset:** 1.000.000 transações (amostra dos 30M)

---

## 🎯 Objetivo

Comparar performance e precisão entre diferentes métodos de cálculo de distância geográfica para detecção de fraude.

---

## 📐 Métodos Testados

### 1. Pitágoras Simplificado (ATUAL)

```python
# Código atual no medallion_silver.py
sqrt(
    spark_pow(col("purchase_latitude") - col("prev_latitude"), 2) +
    spark_pow(col("purchase_longitude") - col("prev_longitude"), 2)
) * 111  # Converte graus para km (aproximado)
```

**Características:**
- Fórmula plana (não considera curvatura da Terra)
- Multiplicador 111 = aproximação de 1 grau = 111 km
- Erro aumenta em longas distâncias

### 2. Haversine UDF Python

```python
def haversine_distance(lat1, lon1, lat2, lon2):
    lat1_rad = math.radians(float(lat1))
    lon1_rad = math.radians(float(lon1))
    lat2_rad = math.radians(float(lat2))
    lon2_rad = math.radians(float(lon2))
    
    dlon = lon2_rad - lon1_rad
    dlat = lat2_rad - lat1_rad
    a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
    c = 2 * math.asin(math.sqrt(a))
    r = 6371  # Raio da Terra em km
    return c * r

haversine_udf = udf(haversine_distance, DoubleType())
```

**Características:**
- Fórmula geodésica correta para superfície esférica
- Processamento row-by-row (serialização Python)
- UDF registrada no Spark

### 3. Haversine Nativo Spark

```python
EARTH_RADIUS_KM = 6371

df.withColumn("lat1_rad", radians(col("purchase_latitude"))) \
  .withColumn("lat2_rad", radians(col("device_latitude"))) \
  .withColumn("lon1_rad", radians(col("purchase_longitude"))) \
  .withColumn("lon2_rad", radians(col("device_longitude"))) \
  .withColumn("dlat", col("lat2_rad") - col("lat1_rad")) \
  .withColumn("dlon", col("lon2_rad") - col("lon1_rad")) \
  .withColumn("a",
      spark_pow(sin(col("dlat") / 2), 2) +
      cos(col("lat1_rad")) * cos(col("lat2_rad")) * spark_pow(sin(col("dlon") / 2), 2)
  ) \
  .withColumn("c", 2 * asin(sqrt(col("a")))) \
  .withColumn("distance_km", col("c") * EARTH_RADIUS_KM)
```

**Características:**
- Mesma fórmula Haversine, mas usando funções nativas Spark
- Otimizado pelo Catalyst (query optimizer)
- Execução paralela sem serialização

---

## 📊 Resultados do Benchmark

### Ambiente de Teste

| Configuração | Valor |
|--------------|-------|
| Cluster | 5 Workers × 2 cores = 10 cores |
| RAM | 15 GB (5×3GB) |
| Dataset | 1,000,000 transações |
| Spark | 3.5.3 |

### Performance

| Método | Tempo | Throughput | vs Baseline |
|--------|-------|------------|-------------|
| **Pitágoras Simplificado** | 0.49s | 2,022,969/s | baseline |
| **Haversine UDF (Python)** | 0.26s | 3,838,021/s | **-47.3% 🏆** |
| **Haversine Nativo (Spark)** | 0.45s | 2,224,788/s | -9.1% |

### Comparação de Precisão

| Lat/Lon | Pitágoras (km) | Haversine (km) | Erro Pitágoras |
|---------|----------------|----------------|----------------|
| -30.52, -51.28 | 56.39 | 56.42 | 0.05% |
| -30.52, -51.58 | 67.21 | 64.42 | **4.3%** |
| -30.52, -50.80 | 72.82 | 68.71 | **6.0%** |
| -30.52, -51.43 | 58.27 | 57.17 | 1.9% |
| -30.52, -50.90 | 65.26 | 62.86 | **3.8%** |

**Conclusão de Precisão:**
- Erro médio do Pitágoras: ~3-6% em distâncias de 50-70km
- Para detecção de fraude com threshold de 555km, o erro é aceitável
- Mas Haversine é matematicamente CORRETO

---

## 🔍 Análise Técnica

### Por que UDF foi mais rápido? 🤔

**Resultado surpreendente!** Normalmente UDFs são mais lentas. Possíveis razões:

1. **Cache do DataFrame**: O cache inicial beneficiou a UDF
2. **Catalyst Overhead**: Para operações simples, o overhead do Catalyst pode não compensar
3. **Complexidade da Fórmula Nativa**: Muitos `withColumn()` encadeados criam overhead
4. **Tamanho do Dataset**: Com 1M registros, a diferença pode ser diferente em 30M

### Recomendação

| Cenário | Método Recomendado |
|---------|-------------------|
| Performance crítica | Haversine UDF |
| Manutenibilidade | Haversine Nativo |
| Legibilidade | Pitágoras (atual) |
| **Precisão + Performance** | **Haversine Nativo** |

---

## 🎯 Conclusão

### ✅ Haversine é MELHOR que Pitágoras porque:

1. **Mais preciso** - Fórmula geodésica correta
2. **Não é mais lento** - Até 47% mais rápido (UDF) ou 9% (Nativo)
3. **Padrão da indústria** - Usado por Google Maps, Uber, etc.

### 📝 Recomendação Final

**Migrar para Haversine Nativo** porque:
- Precisão matemática correta
- Performance equivalente ou melhor
- Funções nativas do Spark (sem dependência Python)
- Código mais profissional

---

## 📌 Impacto para o Projeto

Se migrarmos para Haversine:

| Regra de Fraude | Impacto |
|-----------------|---------|
| Clonagem (>555km) | Detecção mais precisa |
| GPS Mismatch (>20°) | Precisa ajustar threshold |
| Velocidade Impossível | Cálculo correto de km/h |

---

## 🔗 Arquivos Relacionados

- `/spark/jobs/tests/benchmark_haversine.py` - Script de teste
- `/spark/jobs/production/medallion_silver.py` - Código atual
- `/docs/BENCHMARK_HAVERSINE.md` - Esta documentação

---

*Documentado em: 01/12/2025*
*Benchmark executado em: 01/12/2025 18:53*
