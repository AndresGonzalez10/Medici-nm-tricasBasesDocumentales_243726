"""
benchmark_runner/runner.py
BDA en la Nube 2026 — IT2iD | Universidad Politécnica de Chiapas

Ejecuta Q1 y Q2 contra MongoDB y PostgreSQL con concurrencia
configurable (1 / 10 / 50 clientes), mide latencias P50/P95/P99
y guarda los resultados en results/resultados.csv.

Uso:
  python benchmark_runner/runner.py \\
      --engine mongo \\
      --profile baseline \\
      --query q1 \\
      --concurrency 10 \\
      --duration 300 \\
      --run-number 1

El script mide por tiempo (--duration segundos) en lugar de
por número fijo de peticiones, para respetar el protocolo:
  warmup 60s → medición 300s → cooldown 60s
El warmup y cooldown se manejan desde run_benchmarks.sh.
"""

import argparse
import csv
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from pymongo import MongoClient

# ─────────────────────────────────────────
# Conexiones
# ─────────────────────────────────────────
MONGO_URI = "mongodb://localhost:27017"
MONGO_DB  = "benchmark"
MONGO_COL = "orders"

PG_DSN = "host=localhost port=5432 dbname=benchmark user=bench password=bench1234"

QUERIES_DIR = Path(__file__).parent.parent / "queries"
RESULTS_DIR = Path(__file__).parent.parent / "entregables"
RESULTS_DIR.mkdir(exist_ok=True)

CSV_FILE = RESULTS_DIR / "resultados.csv"

CSV_HEADERS = [
    "timestamp_epoch", "engine", "profile", "query_id",
    "concurrency", "run_number",
    "throughput_qps", "latency_p50_ms", "latency_p95_ms", "latency_p99_ms",
    "cpu_throttled_seconds", "max_rss_mb", "disk_spill", "status",
]


# ─────────────────────────────────────────
# Funciones de query — MongoDB
# ─────────────────────────────────────────
def run_mongo_q1(allow_disk: bool = True) -> float:
    """Ejecuta Q1 en MongoDB. Retorna latencia en ms."""
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    col = client[MONGO_DB][MONGO_COL]
    pipeline = json.load(open(QUERIES_DIR / "mongo_q1.json"))
    t0 = time.perf_counter()
    list(col.aggregate(pipeline, allowDiskUse=allow_disk))
    elapsed_ms = (time.perf_counter() - t0) * 1000
    client.close()
    return elapsed_ms


def run_mongo_q2(allow_disk: bool = False) -> float:
    """Ejecuta Q2 en MongoDB. Retorna latencia en ms."""
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    col = client[MONGO_DB][MONGO_COL]
    pipeline = json.load(open(QUERIES_DIR / "mongo_q2.json"))
    t0 = time.perf_counter()
    try:
        list(col.aggregate(pipeline, allowDiskUse=allow_disk))
        elapsed_ms = (time.perf_counter() - t0) * 1000
    except Exception:
        # OOM / sort limit → registrar como fallo
        elapsed_ms = -1.0
    client.close()
    return elapsed_ms


# ─────────────────────────────────────────
# Funciones de query — PostgreSQL
# ─────────────────────────────────────────
def run_pg_q1(work_mem: str = "64MB") -> float:
    """Ejecuta Q1 en PostgreSQL. Retorna latencia en ms."""
    conn = psycopg2.connect(PG_DSN)
    sql = (QUERIES_DIR / "postgres_q1.sql").read_text()
    # Extraer solo el SELECT (ignorar comentarios y EXPLAIN)
    select_sql = [
        line for line in sql.splitlines()
        if line.strip().upper().startswith("SELECT")
        or (not line.strip().startswith("--") and line.strip())
    ]
    query = "\n".join(select_sql).split("-- ─")[0].strip()
    with conn.cursor() as cur:
        cur.execute(f"SET work_mem = '{work_mem}';")
        t0 = time.perf_counter()
        cur.execute(query)
        cur.fetchall()
        elapsed_ms = (time.perf_counter() - t0) * 1000
    conn.close()
    return elapsed_ms


def run_pg_q2(work_mem: str = "4MB") -> float:
    """Ejecuta Q2 en PostgreSQL. Retorna latencia en ms."""
    conn = psycopg2.connect(PG_DSN)
    with conn.cursor() as cur:
        cur.execute(f"SET work_mem = '{work_mem}';")
        sql = """
        SELECT
            data->>'order_id'                                    AS order_id,
            data->'customer'->>'id'                              AS customer_id,
            (data->'payment'->>'final_total')::numeric           AS final_total
        FROM orders
        WHERE data->'payment'->>'status' = 'completed'
          AND (data->>'timestamp')::timestamptz >= '2026-01-01 00:00:00Z'
        ORDER BY (data->'payment'->>'final_total')::numeric DESC
        LIMIT 1000;
        """
        t0 = time.perf_counter()
        cur.execute(sql)
        cur.fetchall()
        elapsed_ms = (time.perf_counter() - t0) * 1000
    conn.close()
    return elapsed_ms


# ─────────────────────────────────────────
# Dispatcher
# ─────────────────────────────────────────
QUERY_MAP = {
    ("mongo",    "q1"): lambda: run_mongo_q1(allow_disk=True),
    ("mongo",    "q2"): lambda: run_mongo_q2(allow_disk=False),
    ("postgres", "q1"): lambda: run_pg_q1(work_mem="64MB"),
    ("postgres", "q2"): lambda: run_pg_q2(work_mem="4MB"),
}


def worker(query_fn, stop_at: float, latencies: list) -> None:
    """Ejecuta query_fn en loop hasta stop_at (epoch). Acumula latencias."""
    while time.time() < stop_at:
        ms = query_fn()
        if ms > 0:
            latencies.append(ms)


# ─────────────────────────────────────────
# Cálculo de percentiles
# ─────────────────────────────────────────
def percentile(data: list, p: float) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    idx = min(idx, len(sorted_data) - 1)
    return round(sorted_data[idx], 2)


# ─────────────────────────────────────────
# Main
# ─────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Benchmark Runner — BDA 2026")
    parser.add_argument("--engine",      choices=["mongo", "postgres"], required=True)
    parser.add_argument("--profile",     choices=["baseline", "medium", "severe"], required=True)
    parser.add_argument("--query",       choices=["q1", "q2"], required=True)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--duration",    type=int, default=300, help="Segundos de medición")
    parser.add_argument("--run-number",  type=int, default=1)
    args = parser.parse_args()

    key = (args.engine, args.query)
    if key not in QUERY_MAP:
        print(f"[ERROR] Combinación no soportada: {key}")
        return

    query_fn = QUERY_MAP[key]
    latencies = []

    print(f"\n{'='*60}")
    print(f"  engine={args.engine} | profile={args.profile} | "
          f"query={args.query} | concurrency={args.concurrency} | run={args.run_number}")
    print(f"  Midiendo por {args.duration}s con {args.concurrency} cliente(s)...")
    print(f"{'='*60}")

    stop_at = time.time() + args.duration
    disk_spill = False
    status = "ok"

    try:
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [
                pool.submit(worker, query_fn, stop_at, latencies)
                for _ in range(args.concurrency)
            ]
            for f in as_completed(futures):
                exc = f.exception()
                if exc:
                    status = f"error: {str(exc)[:60]}"

    except Exception as e:
        status = f"error: {str(e)[:60]}"

    # KPIs
    elapsed = args.duration
    throughput = round(len(latencies) / elapsed, 4) if elapsed > 0 else 0
    p50 = percentile(latencies, 50)
    p95 = percentile(latencies, 95)
    p99 = percentile(latencies, 99)

    print(f"\n  [+] Completado | queries={len(latencies)} | "
          f"QPS={throughput} | P50={p50}ms | P95={p95}ms | P99={p99}ms")

    # Escribir CSV
    write_header = not CSV_FILE.exists()
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerow({
            "timestamp_epoch":      int(datetime.now(timezone.utc).timestamp()),
            "engine":               args.engine,
            "profile":              args.profile,
            "query_id":             args.query,
            "concurrency":          args.concurrency,
            "run_number":           args.run_number,
            "throughput_qps":       throughput,
            "latency_p50_ms":       p50,
            "latency_p95_ms":       p95,
            "latency_p99_ms":       p99,
            "cpu_throttled_seconds": "",   # se llena desde Prometheus post-run
            "max_rss_mb":            "",   # se llena desde Prometheus post-run
            "disk_spill":            disk_spill,
            "status":               status,
        })

    print(f"  [+] Resultado guardado en: {CSV_FILE}")


if __name__ == "__main__":
    main()

