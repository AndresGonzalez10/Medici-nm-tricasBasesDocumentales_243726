# Explicación Detallada del Proyecto
## Medición de Métricas en Bases Documentales — Bases de Datos en la Nube 2026
**Universidad Politécnica de Chiapas | IT2iD**

---

## 1. Contexto Académico

Este proyecto corresponde a la **Unidad 2** de la materia *Bases de Datos en la Nube* del programa de Ingeniería en Tecnologías de la Información e Innovación Digital (IT2iD). Su propósito es que el estudiante experimente de forma empírica las diferencias de comportamiento entre dos paradigmas de almacenamiento de datos JSON bajo condiciones realistas de restricción de recursos computacionales.

En entornos de nube modernos, los contenedores raramente tienen acceso irrestricto a la CPU y la memoria del host. Los orquestadores (Kubernetes, ECS, etc.) aplican **límites de recursos** (CPU quotas vía CFS, límites de memoria vía cgroups) que producen efectos medibles en el rendimiento de las bases de datos. Este proyecto reproduce esas condiciones de forma controlada y sistemática.

---

## 2. Objetivo General

> Medir la **latencia**, el **rendimiento** (throughput) y la **huella de recursos** al ejecutar agregaciones JSON anidadas bajo límites estrictos de CPU (CFS throttling) y memoria con Docker cgroups v2, comparando un motor documental nativo (**MongoDB**) con un motor relacional que almacena documentos en formato **JSONB** (**PostgreSQL**).

---

## 3. Justificación del Experimento

### ¿Por qué comparar MongoDB vs PostgreSQL JSONB?
Ambos motores pueden almacenar y consultar datos semi-estructurados en formato JSON, pero sus arquitecturas internas difieren radicalmente:

- **MongoDB** fue diseñado desde cero para documentos: su motor WiredTiger almacena BSON nativamente, y las agregaciones pipeline están optimizadas para recorrer arrays anidados.
- **PostgreSQL con JSONB** es un motor relacional que *extiende* su modelo para soportar JSON binario. Sus operadores JSONB permiten consultas similares, pero el planificador de consultas y la gestión de memoria están orientados al modelo tabular.

Esta diferencia arquitectónica hace que ambos motores respondan de manera distinta cuando los recursos son escasos: uno puede priorizar índices especializados, el otro puede manejar mejor el trabajo en memoria bajo presión.

---

## 4. Preguntas de Investigación

### M1 — Latencia bajo contención
**¿Cómo cambian la latencia P95 y P99 de las agregaciones sobre documentos anidados cuando se limita de forma estricta la CPU y la memoria?**

Esta pregunta busca cuantificar la *cola de distribución de latencia* (percentil 95 y 99), que representa los peores casos experimentados por los usuarios finales. P99 es especialmente relevante en SLAs de producción.

### M2 — Eficiencia de buffers
**¿Qué motor usa de forma más eficiente los buffers de ordenamiento y agrupamiento antes de volcar a disco temporal o fallar por OOM?**

Cuando la memoria disponible es insuficiente para completar una operación de sort o group en RAM, los motores tienen dos opciones: volcar datos a disco (spill) o abortar la operación (OOM kill). Esta pregunta mide cuándo y cómo ocurre cada caso.

### M3 — Huella de recursos por documento
**¿Cuál es la huella de CPU y memoria por cada 1,000 documentos procesados en el motor documental frente al motor con JSONB?**

Normalizar el consumo de recursos por volumen de datos permite comparar la *eficiencia intrínseca* de cada motor independientemente del tamaño del dataset.

---

## 5. Diseño Experimental

### 5.1 Motores Objetivo

| Motor | Versión | Modelo | Configuración |
|-------|---------|--------|---------------|
| **MongoDB** | latest-stable | Colección `orders` sin sharding | WiredTiger; índice simple en `timestamp` y `order_id` |
| **PostgreSQL** | latest-stable | Tabla `orders(id UUID PRIMARY KEY, data JSONB)` | PK en `id`; B-Tree sobre `timestamp` extraído del JSONB |

### 5.2 Perfiles de Recursos (Docker / cgroups v2)

Los contenedores se configuran con `--cpus` y `--memory` para simular distintos niveles de contención:

| Perfil | Nombre | CPUs | Memoria | Efecto esperado |
|--------|--------|------|---------|-----------------|
| `PROFILE_A_BASELINE` | Sin contención | 4.0 | 4 096 MB | Rendimiento máximo; referencia |
| `PROFILE_B_MEDIUM` | Contención media | 2.0 | 2 048 MB | Throttling ocasional; presión de memoria moderada |
| `PROFILE_C_SEVERE` | Contención severa | 1.0 | 1 024 MB | Throttling activo y constante; riesgo de OOM |

El parámetro `mem_swappiness=0` desactiva el uso de swap, forzando que los fallos de memoria sean reales y medibles.

---

## 6. Dataset Sintético

### Especificaciones
- **Volumen:** 500,000 registros
- **Formato:** JSON con 3 niveles de anidamiento promedio
- **Ítems por registro:** ~3 (en el arreglo `items`)
- **Generador:** `synthetic_data_generator.py`

### Estructura de cada documento

```json
{
  "order_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2026-03-15T14:32:10Z",
  "customer": {
    "id": "cust-001",
    "tier": "gold",
    "segment": "b2c",
    "geo": {
      "country": "MX",
      "state": "Chiapas",
      "city": "Tuxtla Gutiérrez",
      "zip": "29000",
      "coordinates": { "lat": 16.75, "lon": -93.11 }
    }
  },
  "items": [
    {
      "sku": "SKU-42",
      "category": "electronics",
      "brand": "BrandX",
      "qty": 2,
      "price": 149.99,
      "tax_pct": 0.16,
      "discounts": ["PROMO10"]
    }
  ],
  "payment": {
    "method": "credit_card",
    "status": "completed",
    "transaction_id": "txn-abc123",
    "gateway_latency_ms": 230,
    "totals": {
      "subtotal": 299.98,
      "tax": 47.99,
      "final_total": 347.97
    }
  },
  "metadata": {
    "channel": "web",
    "user_agent": "Mozilla/5.0",
    "session_id": "sess-xyz",
    "flags": { "is_returned": false, "is_flagged": false }
  }
}
```

---

## 7. Cargas de Trabajo (Queries)

### Q1 — Unwind, Filter & Grouping *(saturación de CPU)*

**Descripción:** Esta query es intensiva en CPU. Desanida el arreglo `items` (multiplicando el número de filas/documentos por ~3), filtra los ítems con `price > 50`, calcula el subtotal (`qty × price`) y agrupa por país y categoría para obtener suma y promedio. En MongoDB genera una etapa `$unwind` que es costosa; en PostgreSQL usa `jsonb_array_elements` que tiene un comportamiento similar.

**MongoDB pipeline:**
```json
[
  { "$unwind": "$items" },
  { "$match": { "items.price": { "$gt": 50 } } },
  {
    "$group": {
      "_id": {
        "country": "$customer.geo.country",
        "category": "$items.category"
      },
      "total_revenue": { "$sum": { "$multiply": ["$items.qty", "$items.price"] } },
      "avg_revenue":   { "$avg": { "$multiply": ["$items.qty", "$items.price"] } },
      "count": { "$sum": 1 }
    }
  }
]
```

**PostgreSQL:**
```sql
SELECT
  data->'customer'->'geo'->>'country' AS country,
  item->>'category' AS category,
  SUM((item->>'qty')::numeric * (item->>'price')::numeric) AS total_revenue,
  AVG((item->>'qty')::numeric * (item->>'price')::numeric) AS avg_revenue,
  COUNT(*) AS count
FROM orders, jsonb_array_elements(data->'items') AS item
WHERE (item->>'price')::numeric > 50
GROUP BY 1, 2;
```

---

### Q2 — Massive Sort & Top-K *(estrés de buffer)*

**Descripción:** Esta query estresa la memoria de ordenamiento. Filtra órdenes completadas desde `2026-01-01`, ordena por `payment.final_total` descendente (campo sin índice, forzando un sort completo) y devuelve solo los Top-1,000. Se prueba con y sin acceso a disco para aislar el comportamiento del buffer de ordenamiento.

**Variantes de estrés:**
- **MongoDB:** `allowDiskUse: false` (falla si no cabe en RAM) vs `allowDiskUse: true` (vuelca a disco)
- **PostgreSQL:** `SET work_mem = '4MB'` (presión alta) vs `SET work_mem = '64MB'` (más holgura)

**MongoDB pipeline:**
```json
[
  { "$match": {
      "payment.status": "completed",
      "timestamp": { "$gte": "2026-01-01T00:00:00Z" }
  }},
  { "$sort": { "payment.final_total": -1 } },
  { "$limit": 1000 },
  { "$project": {
      "order_id": 1,
      "customer.id": 1,
      "payment.final_total": 1
  }}
]
```

**PostgreSQL:**
```sql
SELECT
  data->>'order_id' AS order_id,
  data->'customer'->>'id' AS customer_id,
  (data->'payment'->>'final_total')::numeric AS final_total
FROM orders
WHERE data->'payment'->>'status' = 'completed'
  AND (data->>'timestamp')::timestamptz >= '2026-01-01 00:00:00Z'
ORDER BY (data->'payment'->>'final_total')::numeric DESC
LIMIT 1000;
```

---

## 8. Protocolo de Ejecución

### Dimensiones del experimento

| Dimensión | Valores |
|-----------|---------|
| Motores | MongoDB, PostgreSQL |
| Perfiles de recursos | A (baseline), B (medium), C (severe) |
| Queries | Q1 (CPU-bound), Q2 (memory-bound) |
| Concurrencia | 1, 10, 50 clientes simultáneos |
| Repeticiones | 3 por cada combinación |
| **Total de runs** | **2 × 3 × 2 × 3 × 3 = 108 ejecuciones** |

### Ciclo de vida de cada escenario
```
[Flush caché]  →  [Warmup 60s]  →  [Medición 300s]  →  [Cooldown 60s]
```

El flush de caché se realiza con:
```bash
sync; echo 3 > /proc/sys/vm/drop_caches
```
> ⚠️ En WSL2/Windows, este comando debe ejecutarse **dentro del contenedor Linux**, no en PowerShell.

---

## 9. Telemetría y KPIs

### Stack de monitoreo
- **cAdvisor** → métricas de contenedor via cgroups v2
- **Node Exporter** → métricas del host (I/O, disco, swap)
- **Prometheus** → recolección con `scrape_interval: 1s`

### Indicadores clave

| KPI | Unidad | Categoría | Descripción |
|-----|--------|-----------|-------------|
| `throughput_qps` | queries/s | Performance | Consultas completadas por segundo |
| `latency_p50_ms` | ms | Performance | Latencia mediana |
| `latency_p95_ms` | ms | Performance | Latencia percentil 95 |
| `latency_p99_ms` | ms | Performance | Latencia percentil 99 (cola) |
| `container_cpu_cfs_throttled_seconds_total` | s | OS/Contention | Tiempo total de throttling CFS |
| `container_memory_rss_bytes` | bytes | OS/Memory | Memoria residente en uso |
| `disk_spill_detected` | boolean | Engine/Internal | Si el motor volcó datos a disco |
| `oom_killed` | boolean | Stability | Si el contenedor fue terminado por OOM |

---

## 10. Entregables

### Repositorio de código
```
📁 proyecto/
├── 📄 docker-compose.yml               ← Perfiles A/B/C parametrizados
├── 🐍 synthetic_data_generator.py      ← Genera 500k documentos JSON
├── 📁 benchmark_runner/
│   ├── k6_script.js                    ← Script de carga con k6
│   └── runner.py                       ← Alternativa Python multiproceso
├── 📁 queries/
│   ├── mongo_q1.json                   ← Pipeline Q1 MongoDB
│   ├── mongo_q2.json                   ← Pipeline Q2 MongoDB
│   ├── postgres_q1.sql                 ← Query Q1 PostgreSQL
│   └── postgres_q2.sql                 ← Query Q2 PostgreSQL
└── 📜 run_benchmarks.sh                ← Automatiza la matriz de 36 celdas
```

### Esquema CSV de resultados
```csv
timestamp_epoch, engine, profile, query_id, concurrency, run_number,
throughput_qps, latency_p50_ms, latency_p95_ms, latency_p99_ms,
cpu_throttled_seconds, max_rss_mb, disk_spill, status
```

### Reporte final (secciones)
1. Especificaciones del host y entorno Docker
2. Método de medición y verificación del baseline
3. Resultados consolidados (throughput, P95/P99, throttling)
4. Análisis gráfico (P99 vs concurrencia, throttling vs QPS, curva RSS)
5. Planes de ejecución (`explain executionStats` vs `EXPLAIN ANALYZE BUFFERS`)
6. Interpretación: límites de memoria, volcado a disco y throttling de cgroups
7. Recomendaciones técnicas para despliegues documentales en la nube

---

## 11. Entorno del Desarrollador

| Elemento | Detalle |
|----------|---------|
| **Sistema Operativo** | Windows 10 |
| **RAM total** | 32 GB |
| **Docker backend** | WSL2 (probable) |
| **Capacidad de perfiles** | Todos los perfiles son ejecutables cómodamente |

> **Nota:** Con 32 GB de RAM, todos los contenedores (máximo 4 GB) se ejecutan sin afectar el host. El mayor riesgo es la fidelidad de las métricas de cgroups v2 dentro de WSL2, que pueden diferir levemente de Linux bare-metal.
