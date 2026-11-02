# Resumen Ejecutivo — BDA en la Nube 2026
**IT2iD | Universidad Politécnica de Chiapas**

---

## ¿Qué se hace?
Comparar **MongoDB** vs **PostgreSQL (JSONB)** midiendo rendimiento y consumo de recursos al ejecutar consultas JSON complejas dentro de **contenedores Docker con CPU y memoria limitadas**.

---

## ¿Por qué?
En producción, las bases de datos corren con recursos restringidos. Se quiere saber cuál motor aguanta mejor la presión.

---

## Preguntas clave

| # | Pregunta |
|---|----------|
| M1 | ¿Cómo sube la latencia (P95/P99) al reducir CPU y RAM? |
| M2 | ¿Cuál maneja mejor los buffers antes de fallar o volcar a disco? |
| M3 | ¿Cuánta CPU/RAM consume cada motor por 1,000 docs procesados? |

---

## Setup

| Elemento | Detalle |
|----------|---------|
| Dataset | 500,000 órdenes JSON anidadas |
| Perfiles Docker | Baseline (4 CPU/4GB) · Medium (2/2GB) · Severe (1/1GB) |
| Queries | Q1: Unwind+Group (CPU) · Q2: Sort+Top-K (memoria) |
| Concurrencia | 1 · 10 · 50 clientes |
| Repeticiones | 3 por escenario → **108 runs totales** |

---

## Qué se mide
`throughput_qps` · `latency_p95_ms` · `latency_p99_ms` · `cpu_throttled_s` · `max_rss_mb` · `disk_spill` · `oom_killed`

---

## Entregables
- `docker-compose.yml` con perfiles
- Generador de datos Python (500k docs)
- Scripts de benchmark (k6 / Python)
- Queries MongoDB + PostgreSQL
- CSV con resultados + Reporte de métricas

---

## Tu entorno
**Windows 10 · 32 GB RAM · Docker + WSL2** — recursos suficientes para todos los perfiles.
