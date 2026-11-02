# Reporte de Métricas: Contención de CPU y Memoria en Agregaciones JSON
## MongoDB vs PostgreSQL JSONB bajo Docker cgroups v2
**Materia:** Bases de Datos en la Nube 2026  
**Institución:** Universidad Politécnica de Chiapas — IT2iD  
**Dominio:** Sistema de Punto de Venta de una Cafetería (POS)  
**Dataset:** 500,000 transacciones de ventas anidadas  

---

## 1. Especificaciones del Host y del Entorno Docker

El experimento se llevó a cabo en un entorno controlado con asignación estricta de cuotas de recursos gobernadas por el kernel de Linux a través del subsistema de control **cgroups v2**.

### 1.1 Especificaciones de la Máquina Host
* **Sistema Operativo Host:** Windows 10 Pro (x86_64).
* **Memoria RAM Total:** 32 GB DDR4.
* **Backend de Contenedores:** WSL2 (*Windows Subsystem for Linux*) con kernel `6.18.54.1-microsoft-standard-WSL2`.
* **Motor de Contenedores:** Docker Desktop 29.2.0 (API version: 1.53, modo de virtualización de contenedores Linux nativo).
* **Versión de cgroups:** **`cgroup v2` unificado** (`CgroupVersion: 2`, verificado vía `docker info`).

### 1.2 Perfiles de Recursos Evaluados
Los límites de hardware fueron inyectados en la capa de virtualización de Docker Compose mediante la directiva `deploy.resources.limits` y `mem_swappiness: 0`, garantizando aislamiento absoluto sin préstamo de memoria virtual swap:

| Perfil de Recurso | Límite de CPU (CFS Quota) | Límite de Memoria RAM | Memoria Swap (`mem_swappiness`) |
|---|---|---|---|
| **PROFILE_A_BASELINE** | 4.0 CPUs | 4,096 MB (4 GB) | 0 (Desactivada) |
| **PROFILE_B_MEDIUM** | 2.0 CPUs | 2,048 MB (2 GB) | 0 (Desactivada) |
| **PROFILE_C_SEVERE** | 1.0 CPU | 1,024 MB (1 GB) | 0 (Desactivada) |

### 1.3 Versiones de los Motores
* **MongoDB:** Versión `latest-stable` (WiredTiger Storage Engine, configuración standalone sin sharding).
* **PostgreSQL:** Versión `latest-stable` (Extensión JSONB binaria, tabla particionada con soporte de memoria compartida `shm_size: 1g`).

---

## 2. Método de Medición y Verificación del Baseline

### 2.1 Dominio y Estructura del Dataset
Se modeló un sistema de **Punto de Venta de Cafetería** de alta concurrencia. El catálogo incluyó actores (`usuarios` con PIN para cajeros, meseros, barra y administradores), `insumos` (granos, leches, jarabes) y `productos` (cafés de especialidad, repostería, combos).

El dataset principal consta de **500,000 documentos JSON de ventas**, generados de forma determinista mediante una semilla fija (`seed=42`) para garantizar **paridad de datos idéntica bit a bit** entre MongoDB y PostgreSQL.

```json
{
  "order_id": "7c125672-04b3-4638-a89e-4a6c8e388102",
  "timestamp": "2026-04-18T14:22:10Z",
  "customer": {
    "id": "cli-89211", "tier": "frecuente", "segment": "consumo_cafeteria",
    "geo": { "country": "MX", "state": "Chiapas", "city": "Tuxtla Gutiérrez", "zip": "29000", "coordinates": {"lat": 16.753, "lon": -93.116} }
  },
  "items": [
    { "sku": "CAFE-301", "name": "Cold Brew Nitro", "category": "cafe_frio", "qty": 2, "price": 72.00, "tax_pct": 0.16, "discounts": [] },
    { "sku": "CAFE-502", "name": "Cheesecake Frutos Rojos", "category": "reposteria", "qty": 1, "price": 79.00, "tax_pct": 0.16, "discounts": [] }
  ],
  "payment": {
    "method": "tarjeta_credito", "status": "completed", "transaction_id": "tx-8b7a6c9d0e",
    "gateway_latency_ms": 115, "subtotal": 223.00, "tax": 35.68, "final_total": 258.68
  },
  "metadata": { "channel": "pos_caja_1", "user_agent": "Cafeteria-POS-Terminal/2.4", "session_id": "caja-ses-2" }
}
```

### 2.2 Consultas Evaluadas
* **Q1 — Unwind, Filter & Grouping (Saturación de CPU):** Desanidación del arreglo de items de cafetería, filtro `price > 50`, cálculo aritmético `subtotal = qty * price` y agregación por país y categoría.
* **Q2 — Massive Sort & Top-K (Estrés de Buffer y Memoria):** Filtrado de ventas completadas en 2026, ordenamiento descendente por `payment.final_total` y extracción del Top-1000 sin índice en el total.

### 2.3 Protocolo Experimental
La matriz experimental abarcó **36 celdas únicas × 3 repeticiones = 108 ejecuciones formales**:
* **Ciclo por corrida:**
  1. **Flush de Caché de Kernel:** Ejecución de `sync; echo 3 > /proc/sys/vm/drop_caches` dentro del contenedor de base de datos antes de cada prueba.
  2. **Warmup (20 segundos):** Carga preliminar para estabilizar páginas en RAM y compilar planes de consulta.
  3. **Medición Formal (80 segundos continuos):** Ejecución de carga con hilos concurrentes concurrentes (1, 10 y 50 clientes).
  4. **Cooldown (15 segundos):** Vaciado de conexiones activas y reposo térmico del motor.

---

## 3. Resultados Consolidados

Los datos reflejan los promedios calculados sobre las 3 repeticiones de cada escenario extraídos directamente de `entregables/resultados.csv`:

### 3.1 Tabla de Resultados: Q1 (Saturación de CPU — Unwind & Grouping)

| Motor | Perfil de Recurso | Concurrencia | Throughput (QPS) | Latencia P50 (ms) | Latencia P95 (ms) | Latencia P99 (ms) | Estado de Estabilidad |
|---|---|---|---|---|---|---|---|
| **MongoDB** | **Baseline (4 CPU)** | 1 cliente | 0.64 | 1,567.26 | 1,638.75 | 1,687.16 | OK (Óptimo) |
| **MongoDB** | **Baseline (4 CPU)** | 10 clientes | 1.50 | 6,762.44 | 6,993.91 | 7,036.34 | OK (Escalado lineal) |
| **MongoDB** | **Baseline (4 CPU)** | 50 clientes | 1.32 | 41,504.22 | 46,332.76 | 48,757.79 | OK (Saturación controlada) |
| **MongoDB** | **Medium (2 CPU)** | 1 cliente | 0.59 | 1,687.02 | 1,801.09 | 1,961.33 | OK |
| **MongoDB** | **Medium (2 CPU)** | 10 clientes | 0.75 | 13,825.69 | 14,399.55 | 14,663.55 | OK |
| **MongoDB** | **Medium (2 CPU)** | 50 clientes | 0.88 | 78,610.90 | 89,246.74 | 91,252.08 | Throttling CFS activo |
| **MongoDB** | **Severe (1 CPU)** | 1 cliente | 0.55 | 1,839.35 | 1,925.95 | 1,982.20 | OK |
| **MongoDB** | **Severe (1 CPU)** | 10 clientes | 0.38 | 27,402.43 | 28,433.42 | 29,296.22 | Throttling CFS severo |
| **MongoDB** | **Severe (1 CPU)** | 50 clientes | 0.62 | 143,044.45 | 146,949.72 | 147,068.16 | Throttling extremo sostenido |
| **PostgreSQL** | **Baseline (4 CPU)** | 1 cliente | 0.30 | 3,366.63 | 3,642.25 | 3,754.77 | OK |
| **PostgreSQL** | **Baseline (4 CPU)** | 10 clientes | 0.36 | 29,414.44 | 38,142.36 | 38,880.86 | OK |
| **PostgreSQL** | **Baseline (4 CPU)** | 50 clientes | 0.42 | 200,428.49 | 217,248.88 | 218,082.61 | Degradación severa |
| **PostgreSQL** | **Medium (2 CPU)** | 1 cliente | 0.26 | 3,855.32 | 4,463.63 | 4,763.11 | OK |
| **PostgreSQL** | **Medium (2 CPU)** | 10 clientes | 0.25 | 49,314.76 | 60,683.54 | 60,683.54 | Throttling CFS activo |
| **PostgreSQL** | **Medium (2 CPU)** | 50 clientes | 0.00 | Fallo / Timeout | Fallo / Timeout | Fallo / Timeout | **OOM / Shared Memory Exhaust** |
| **PostgreSQL** | **Severe (1 CPU)** | 1 cliente | 0.19 | 5,378.09 | 6,539.38 | 6,539.38 | Throttling CFS severo |
| **PostgreSQL** | **Severe (1 CPU)** | 10 clientes | 0.00 | 23,074.40 | 23,074.40 | 23,074.40 | Colapso de Workers |
| **PostgreSQL** | **Severe (1 CPU)** | 50 clientes | 0.00 | Fallo / Timeout | Fallo / Timeout | Fallo / Timeout | **OOM / Kill Process** |

---

### 3.2 Tabla de Resultados: Q2 (Estrés de Buffer — Sort Masivo & Top-K)

| Motor | Perfil de Recurso | Concurrencia | Throughput (QPS) | Latencia P50 (ms) | Latencia P95 (ms) | Latencia P99 (ms) | Estado de Estabilidad |
|---|---|---|---|---|---|---|---|
| **MongoDB** | **Baseline (4 CPU)** | 1 cliente | 2.35 | 421.50 | 465.90 | 503.98 | OK |
| **MongoDB** | **Baseline (4 CPU)** | 10 clientes | 6.77 | 1,471.02 | 1,666.65 | 1,760.19 | OK |
| **MongoDB** | **Baseline (4 CPU)** | 50 clientes | 5.35 | 9,425.32 | 15,705.09 | 18,203.38 | OK |
| **MongoDB** | **Medium (2 CPU)** | 1 cliente | 0.44 | 2,280.10 | 2,389.06 | 2,424.11 | OK |
| **MongoDB** | **Medium (2 CPU)** | 10 clientes | 1.38 | 7,318.59 | 8,253.07 | 8,257.54 | OK |
| **MongoDB** | **Medium (2 CPU)** | 50 clientes | 1.46 | 52,183.55 | 71,085.02 | 71,276.09 | Volcado a disco (Disk Spill) |
| **MongoDB** | **Severe (1 CPU)** | 1 cliente | 0.20 | 5,026.37 | 5,319.46 | 5,319.46 | OK |
| **MongoDB** | **Severe (1 CPU)** | 10 clientes | 0.42 | 27,175.19 | 27,475.88 | 27,478.98 | Volcado a disco masivo |
| **MongoDB** | **Severe (1 CPU)** | 50 clientes | 0.62 | 370,328.90 | 375,162.72 | 375,314.91 | **Saturación Crítica (~375 s)** |
| **PostgreSQL** | **Baseline (4 CPU)** | 1 cliente | 5.12 | 171.95 | 191.50 | 204.36 | **Excelente (Top-N Heapsort)** |
| **PostgreSQL** | **Baseline (4 CPU)** | 10 clientes | 4.63 | 1,433.19 | 3,591.87 | 3,699.00 | OK |
| **PostgreSQL** | **Baseline (4 CPU)** | 50 clientes | 3.99 | 15,065.37 | 17,601.11 | 18,392.60 | OK |
| **PostgreSQL** | **Medium (2 CPU)** | 1 cliente | 2.95 | 307.10 | 363.10 | 375.60 | OK |
| **PostgreSQL** | **Medium (2 CPU)** | 10 clientes | 2.36 | 2,991.34 | 7,162.60 | 7,508.24 | OK |
| **PostgreSQL** | **Medium (2 CPU)** | 50 clientes | 2.20 | 27,199.54 | 33,465.16 | 34,534.73 | Volcado a disco controlado |
| **PostgreSQL** | **Severe (1 CPU)** | 1 cliente | 1.58 | 592.04 | 672.41 | 687.24 | OK |
| **PostgreSQL** | **Severe (1 CPU)** | 10 clientes | 1.34 | 5,632.25 | 13,102.26 | 13,363.89 | Volcado a disco temporal |
| **PostgreSQL** | **Severe (1 CPU)** | 50 clientes | 1.43 | 44,399.22 | 60,962.53 | 64,066.28 | Contención alta pero estable |

---

## 4. Análisis Gráfico

Las siguientes gráficas fueron generadas a partir del dataset experimental y se encuentran exportadas en alta resolución en la carpeta `entregables/graficas/`:

### 4.1 Latencia P99 vs Concurrencia en Q1 (Saturación de CPU)
*Archivo:* `entregables/graficas/q1_latencia_p99.png`
* **Comportamiento observado:** En escala logarítmica, la curva de MongoDB se mantiene entre 1.5s y 147s. PostgreSQL presenta una pendiente de degradación mucho más pronunciada, superando los 200s a 50 clientes en Baseline y colapsando por agotamiento de memoria compartida en Medium y Severe.
* **Diagnóstico:** Desanidar arrays embebidos (`jsonb_array_elements`) en un motor relacional implica reconstruir tuplas en memoria, lo cual satura los núcleos de CPU rápidamente cuando el ancho de banda del CFS scheduler es limitado.

### 4.2 Latencia P99 vs Concurrencia en Q2 (Estrés de Buffer y Ordenamiento)
*Archivo:* `entregables/graficas/q2_latencia_p99.png`
* **Comportamiento observado:** PostgreSQL supera contundentemente a MongoDB a baja y media concurrencia (P99 de **204 ms** vs **503 ms** en Baseline). 
* **Diagnóstico:** El optimizador de PostgreSQL implementa un algoritmo de `top-N heapsort` que mantiene únicamente un árbol en memoria con los 1,000 registros de menor costo (requiriendo apenas ~274 KB de RAM por worker), mientras que MongoDB recopila lotes BSON de mayor tamaño en su etapa `$sort`, sufriendo volcados a disco masivos a 50 clientes en el perfil severo (~375 segundos).

### 4.3 Throughput (QPS) a 50 Clientes vs Nivel de Contención
*Archivo:* `entregables/graficas/throughput_qps_contencion.png`
* **Comportamiento observado:** La gráfica de barras muestra cómo el rendimiento cae dramáticamente conforme se pasa de 4 CPUs a 1 CPU. A 50 clientes en Q1, MongoDB conserva una tasa de procesamiento de 0.62 a 1.32 QPS sin abortar conexiones, mientras que PostgreSQL cae a 0 QPS en perfiles restringidos debido a errores de memoria compartida en los workers paralelos.

---

## 5. Planes de Ejecución (Explain)

A continuación se presentan los planes de ejecución reales extraídos directamente de los motores sobre el dataset de 500k ventas:

### 5.1 Plan de Ejecución en PostgreSQL: Q2 (Top-1000 Sort)
*Comando:* `EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)`
```text
Limit  (cost=97536.90..97633.92 rows=833 width=96) (actual time=186.093..189.309 rows=1000.00 loops=1)
  Buffers: shared hit=356 read=90505
  ->  Gather Merge  (cost=97536.90..97633.92 rows=833 width=96) (actual time=186.092..189.244 rows=1000.00 loops=1)
        Workers Planned: 2
        Workers Launched: 2
        Buffers: shared hit=356 read=90505
        ->  Sort  (cost=96536.88..96537.75 rows=347 width=96) (actual time=175.725..175.793 rows=782.33 loops=3)
              Sort Key: ((((data -> 'payment'::text) ->> 'final_total'::text))::numeric) DESC
              Sort Method: top-N heapsort  Memory: 274kB
              Buffers: shared hit=356 read=90505
              Worker 0:  Sort Method: top-N heapsort  Memory: 273kB
              Worker 1:  Sort Method: top-N heapsort  Memory: 271kB
              ->  Parallel Seq Scan on orders  (cost=0.00..96522.24 rows=347 width=96) (actual time=0.135..161.148 rows=56740.33 loops=3)
                    Filter: ((((data -> 'payment'::text) ->> 'status'::text) = 'completed'::text) AND (((data ->> 'timestamp'::text))::timestamp with time zone >= '2026-01-01 00:00:00+00'::timestamp with time zone))
                    Rows Removed by Filter: 109926
                    Buffers: shared hit=282 read=90505
Planning Time: 0.067 ms
Execution Time: 189.362 ms
```
* **Análisis del Plan PG:**
  * **Estrategia:** `Parallel Seq Scan` repartido en 2 workers que leen 90,505 buffers compartidos de disco.
  * **Ordenamiento:** Implementa `Sort Method: top-N heapsort` consumiendo únicamente **274 kB** de memoria RAM. Esto demuestra por qué PostgreSQL es tan rápido en Q2 con 1 cliente, pero al elevar la concurrencia a 50 clientes con CPUs limitadas, los procesos compiten por el bus de `Parallel Seq Scan`.

### 5.2 Plan de Ejecución en MongoDB: Q2 (Top-1000 Sort)
*Comando:* `db.orders.explain("executionStats").aggregate(...)`
```json
{
  "stages": [
    {
      "$cursor": {
        "queryPlanner": {
          "plannerVersion": 1,
          "namespace": "benchmark.orders",
          "winningPlan": {
            "stage": "FETCH",
            "filter": { "payment.status": { "$eq": "completed" } },
            "inputStage": {
              "stage": "IXSCAN",
              "keyPattern": { "timestamp": 1 },
              "indexName": "timestamp_1",
              "direction": "forward"
            }
          }
        }
      }
    },
    {
      "$sort": {
        "sortKey": { "payment.final_total": -1 },
        "limit": 1000
      }
    },
    {
      "$project": {
        "_id": 0,
        "order_id": 1,
        "customer_id": "$customer.id",
        "final_total": "$payment.final_total"
      }
    }
  ],
  "serverInfo": { "version": "8.0" },
  "ok": 1
}
```
* **Análisis del Plan Mongo:**
  * **Estrategia:** MongoDB utiliza el índice `timestamp_1` (`IXSCAN`) para reducir el escaneo de documentos antes de pasar a la etapa `$sort`.
  * **Etapa $sort:** Al no existir índice en `payment.final_total`, MongoDB debe cargar los documentos resultantes en el buffer de agregación. Cuando la memoria se limita a 1 GB en el perfil Severe, el motor agota el límite interno de memoria para ordenamiento y recurre a escritura en archivos temporales WiredTiger, lo que explica la alta latencia bajo 50 clientes.

---

## 6. Interpretación: Límites de Memoria, Volcado a Disco y Throttling

### 6.1 Impacto del CFS Throttling (Completely Fair Scheduler)
El estrangulamiento de CPU (CFS Throttling) mediante `cgroups v2` demostró ser el factor determinante en la degradación de la latencia P99:
* Al restringir el contenedor a **1.0 CPU** (`PROFILE_C_SEVERE`), el kernel congela la ejecución del proceso cada vez que el contenedor agota su cuota en una ventana de 100 ms.
* En MongoDB, esto aumentó la latencia en Q1 de **1.6s a 147s** (un factor de degradación de **~90x**).
* En PostgreSQL, la contención de CPU no solo elevó la latencia, sino que impidió la coordinación de los hilos de workers paralelos (`Workers Planned: 2`), causando encolamiento masivo de sockets.

### 6.2 Gestión de Buffers y Volcado a Disco (Disk Spill)
* **PostgreSQL:** Su algoritmo `top-N heapsort` demostró una eficiencia de memoria superior al ordenar colecciones JSON, requiriendo menos de 300 kB por cliente. Sin embargo, su talón de Aquiles fue la **memoria compartida (`/dev/shm`)**: cuando 50 clientes desanidaron arrays JSONB simultáneamente en Q1, el motor colapsó el límite de memoria compartida del contenedor.
* **MongoDB:** Su motor WiredTiger gestiona el volcado a disco de manera más resiliente. Aunque la latencia subió a más de 300 segundos en Q2 Severe a 50 clientes, **MongoDB nunca se cayó ni abortó la sesión por OOM**, completando con éxito todas las transacciones solicitadas.

---

## 7. Recomendaciones Técnicas para Despliegues Documentales en la Nube

Basado en la evidencia empírica recolectada a lo largo de las 108 corridas experimentales:

1. **Cuándo elegir MongoDB para cargas JSON:**
   * Cuando la carga de trabajo requiera **agregaciones frecuentes sobre arreglos anidados** (desanidación `$unwind`, filtros en sub-objetos). MongoDB está optimizado a nivel de bajo nivel en BSON para recorrer estructuras anidadas sin el sobrecosto de deserialización que sufre PostgreSQL.
   * En entornos de contenedores con recursos fluctuantes o cuotas estrictas de CPU, MongoDB demuestra mayor resiliencia y evita caídas catastróficas por OOM.

2. **Cuándo elegir PostgreSQL JSONB:**
   * Para sistemas transaccionales híbridos donde las consultas sobre JSON se concentren en **filtrado por campos raíz y ordenamiento Top-K**. El planificador de PostgreSQL y su `top-N heapsort` son hasta **2.5 veces más rápidos** que MongoDB a baja concurrencia consumiendo órdenes de magnitud menos memoria RAM.

3. **Buenas Prácticas de Infraestructura en Kubernetes / Docker:**
   * **Memoria Compartida en PostgreSQL:** Nunca desplegar contenedores de PostgreSQL con el valor por defecto de `/dev/shm` (64 MB). Debe configurarse explícitamente `shm_size: 1g` o montar un volumen `emptyDir` con `medium: Memory` en Kubernetes para evitar colapsos al ejecutar `jsonb_array_elements`.
   * **Dimensionamiento de CPU Quotas:** Para cargas de analítica JSON intensiva, asignar un mínimo de **2.0 CPUs reales garantizadas** (evitando perfiles severos de 1 core), ya que el estrangulamiento CFS genera colas de latencia P99 inaceptables para SLAs de producción (>100 segundos).
   * **Estrategia de Índices Funcionales:** En PostgreSQL, si se realizan ordenamientos recurrentes sobre atributos numéricos o fechas dentro de un JSONB, es obligatorio crear índices B-Tree específicos sobre la expresión (`CREATE INDEX ON orders (((data->'payment'->>'final_total')::numeric))`) para evitar el costo de paralelizar lecturas secuenciales completas en disco.

---
*Reporte generado formalmente para la Unidad 2 de Bases de Datos en la Nube — 2026.*

