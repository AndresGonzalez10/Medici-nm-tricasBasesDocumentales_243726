-- ─────────────────────────────────────────────────────────────
-- Q1 — Unwind, Filter & Grouping  (saturación de CPU)
-- BDA en la Nube 2026 | PostgreSQL JSONB
-- ─────────────────────────────────────────────────────────────
-- Desanida el arreglo items con jsonb_array_elements,
-- filtra price > 50, calcula subtotal (qty * price) y
-- agrupa suma + promedio por país y categoría.
-- ─────────────────────────────────────────────────────────────

SELECT
    data->'customer'->'geo'->>'country'           AS country,
    item->>'category'                             AS category,
    SUM((item->>'qty')::numeric
      * (item->>'price')::numeric)                AS total_revenue,
    AVG((item->>'qty')::numeric
      * (item->>'price')::numeric)                AS avg_revenue,
    COUNT(*)                                      AS count
FROM
    orders,
    jsonb_array_elements(data->'items') AS item
WHERE
    (item->>'price')::numeric > 50
GROUP BY 1, 2
ORDER BY total_revenue DESC;

-- ─────────────────────────────────────────────────────────────
-- Plan de ejecución (para el reporte — sección 5):
-- ─────────────────────────────────────────────────────────────
-- EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
-- SELECT ... (misma query de arriba)

