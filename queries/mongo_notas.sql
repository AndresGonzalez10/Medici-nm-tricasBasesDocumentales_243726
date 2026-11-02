-- ─────────────────────────────────────────────────────────────
-- Q1 — Unwind, Filter & Grouping  (saturación de CPU)
-- BDA en la Nube 2026 | MongoDB Aggregation Pipeline
-- ─────────────────────────────────────────────────────────────
-- Desanida el arreglo items, filtra price > 50,
-- calcula subtotal (qty * price) y agrupa suma + promedio
-- por país y categoría.
--
-- Variantes de estrés de memoria:
--   allowDiskUse: false  → falla si no cabe en RAM
--   allowDiskUse: true   → vuelca a disco si es necesario
-- ─────────────────────────────────────────────────────────────

-- Ejecutar desde Python (ver benchmark_runner/):
--
-- pipeline = json.load(open("queries/mongo_q1.json"))
-- result = db.orders.aggregate(pipeline, allowDiskUse=False)
-- result = db.orders.aggregate(pipeline, allowDiskUse=True)

-- Plan de ejecución (para el reporte):
-- db.orders.explain("executionStats").aggregate(pipeline)


-- ─────────────────────────────────────────────────────────────
-- Q2 — Massive Sort & Top-K  (estrés de buffer / memoria)
-- ─────────────────────────────────────────────────────────────
-- Filtra órdenes completed desde 2026-01-01,
-- ordena DESC por payment.totals.final_total (sin índice),
-- devuelve Top-1000.
--
-- Variantes:
--   allowDiskUse: false  → OOM si sort no cabe en RAM
--   allowDiskUse: true   → spill a disco temporal
-- ─────────────────────────────────────────────────────────────

-- Ejecutar desde Python:
--
-- pipeline = json.load(open("queries/mongo_q2.json"))
-- result = db.orders.aggregate(pipeline, allowDiskUse=False)
-- result = db.orders.aggregate(pipeline, allowDiskUse=True)

-- Plan de ejecución:
-- db.orders.explain("executionStats").aggregate(pipeline)

