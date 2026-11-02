-- ─────────────────────────────────────────────────────────────
-- Q2 — Massive Sort & Top-K  (estrés de buffer / memoria)
-- BDA en la Nube 2026 | PostgreSQL JSONB
-- ─────────────────────────────────────────────────────────────
-- Filtra órdenes completed desde 2026-01-01,
-- ordena DESC por payment.totals.final_total (sin índice),
-- devuelve Top-1000.
-- ─────────────────────────────────────────────────────────────

-- Variante A — Presión alta de memoria (work_mem pequeño)
SET work_mem = '4MB';

SELECT
    data->>'order_id'                              AS order_id,
    data->'customer'->>'id'                        AS customer_id,
    (data->'payment'->>'final_total')::numeric     AS final_total
FROM orders
WHERE
    data->'payment'->>'status' = 'completed'
    AND (data->>'timestamp')::timestamptz >= '2026-01-01 00:00:00Z'
ORDER BY
    (data->'payment'->>'final_total')::numeric DESC
LIMIT 1000;


-- ─────────────────────────────────────────────────────────────
-- Variante B — Más holgura de memoria (work_mem grande)
-- ─────────────────────────────────────────────────────────────
SET work_mem = '64MB';

SELECT
    data->>'order_id'                              AS order_id,
    data->'customer'->>'id'                        AS customer_id,
    (data->'payment'->>'final_total')::numeric     AS final_total
FROM orders
WHERE
    data->'payment'->>'status' = 'completed'
    AND (data->>'timestamp')::timestamptz >= '2026-01-01 00:00:00Z'
ORDER BY
    (data->'payment'->>'final_total')::numeric DESC
LIMIT 1000;


-- ─────────────────────────────────────────────────────────────
-- Plan de ejecución (para el reporte — sección 5):
-- ─────────────────────────────────────────────────────────────
-- SET work_mem = '4MB';
-- EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
-- SELECT ... (misma query de arriba)
--
-- SET work_mem = '64MB';
-- EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
-- SELECT ... (misma query de arriba)

