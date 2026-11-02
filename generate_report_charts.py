"""
generate_report_charts.py
Procesa entregables/resultados.csv y genera graficas de rendimiento para el reporte.
"""

import csv
import os
from collections import defaultdict
import matplotlib.pyplot as plt

CSV_PATH = "entregables/resultados.csv"
OUT_DIR = "entregables/graficas"
os.makedirs(OUT_DIR, exist_ok=True)

# Leer datos
data = defaultdict(lambda: defaultdict(list))
# key: (engine, profile, query_id, concurrency) -> list of records

with open(CSV_PATH, "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if int(row["run_number"]) > 0:  # solo mediciones formales
            engine = row["engine"]
            profile = row["profile"]
            query = row["query_id"]
            conc = int(row["concurrency"])
            qps = float(row["throughput_qps"])
            p50 = float(row["latency_p50_ms"])
            p95 = float(row["latency_p95_ms"])
            p99 = float(row["latency_p99_ms"])
            data[(engine, query, profile)][conc].append({
                "qps": qps, "p50": p50, "p95": p95, "p99": p99
            })

# Promediar
avg_data = {}
for key, conc_dict in data.items():
    avg_data[key] = {}
    for conc, records in conc_dict.items():
        avg_data[key][conc] = {
            "qps": round(sum(r["qps"] for r in records) / len(records), 2),
            "p50": round(sum(r["p50"] for r in records) / len(records), 2),
            "p95": round(sum(r["p95"] for r in records) / len(records), 2),
            "p99": round(sum(r["p99"] for r in records) / len(records), 2),
        }

concurrencies = [1, 10, 50]
profiles = ["baseline", "medium", "severe"]
colors = {
    ("mongo", "baseline"): "#28a745",
    ("mongo", "medium"): "#ffc107",
    ("mongo", "severe"): "#dc3545",
    ("postgres", "baseline"): "#007bff",
    ("postgres", "medium"): "#17a2b8",
    ("postgres", "severe"): "#6f42c1"
}

# ─────────────────────────────────────────────────────────────
# Grafica 1: Latencia P99 vs Concurrencia - Q1 (CPU Bound)
# ─────────────────────────────────────────────────────────────
plt.figure(figsize=(10, 6))
for engine in ["mongo", "postgres"]:
    for profile in profiles:
        k = (engine, "q1", profile)
        if k in avg_data:
            vals = [avg_data[k][c]["p99"] for c in concurrencies if c in avg_data[k]]
            lbl = f"{engine.capitalize()} ({profile.capitalize()})"
            plt.plot(concurrencies, vals, marker="o", linewidth=2, label=lbl, color=colors.get((engine, profile)))

plt.title("Q1: Latencia P99 vs Concurrencia (Saturación de CPU)", fontsize=14, fontweight="bold")
plt.xlabel("Clientes Concurrentes", fontsize=12)
plt.ylabel("Latencia P99 (ms) [Escala Logarítmica]", fontsize=12)
plt.yscale("log")
plt.xticks(concurrencies)
plt.grid(True, which="both", linestyle="--", alpha=0.5)
plt.legend(fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "q1_latencia_p99.png"), dpi=300)
plt.close()

# ─────────────────────────────────────────────────────────────
# Grafica 2: Latencia P99 vs Concurrencia - Q2 (Memory Sort)
# ─────────────────────────────────────────────────────────────
plt.figure(figsize=(10, 6))
for engine in ["mongo", "postgres"]:
    for profile in profiles:
        k = (engine, "q2", profile)
        if k in avg_data:
            vals = [avg_data[k][c]["p99"] for c in concurrencies if c in avg_data[k]]
            lbl = f"{engine.capitalize()} ({profile.capitalize()})"
            plt.plot(concurrencies, vals, marker="s", linewidth=2, label=lbl, color=colors.get((engine, profile)))

plt.title("Q2: Latencia P99 vs Concurrencia (Estrés de Buffer y Ordenamiento)", fontsize=14, fontweight="bold")
plt.xlabel("Clientes Concurrentes", fontsize=12)
plt.ylabel("Latencia P99 (ms) [Escala Logarítmica]", fontsize=12)
plt.yscale("log")
plt.xticks(concurrencies)
plt.grid(True, which="both", linestyle="--", alpha=0.5)
plt.legend(fontsize=10)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "q2_latencia_p99.png"), dpi=300)
plt.close()

# ─────────────────────────────────────────────────────────────
# Grafica 3: Throughput (QPS) vs Nivel de Contencion (50 Clientes)
# ─────────────────────────────────────────────────────────────
plt.figure(figsize=(10, 6))
bar_width = 0.35
indices = [0, 1, 2]

mongo_q1_qps = [avg_data.get(("mongo", "q1", p), {}).get(50, {}).get("qps", 0) for p in profiles]
pg_q1_qps = [avg_data.get(("postgres", "q1", p), {}).get(50, {}).get("qps", 0) for p in profiles]

pos1 = [i - bar_width/2 for i in indices]
pos2 = [i + bar_width/2 for i in indices]

plt.bar(pos1, mongo_q1_qps, width=bar_width, label="MongoDB Q1", color="#28a745")
plt.bar(pos2, pg_q1_qps, width=bar_width, label="PostgreSQL JSONB Q1", color="#007bff")

plt.title("Throughput Q1 (QPS) a 50 Clientes vs Nivel de Contención de CPU", fontsize=14, fontweight="bold")
plt.xlabel("Perfil de Recursos cgroups v2", fontsize=12)
plt.ylabel("Throughput (Queries / Segundo)", fontsize=12)
plt.xticks(indices, ["Baseline (4 CPU)", "Medium (2 CPU)", "Severe (1 CPU)"])
plt.grid(axis="y", linestyle="--", alpha=0.7)
plt.legend(fontsize=11)
plt.tight_layout()
plt.savefig(os.path.join(OUT_DIR, "throughput_qps_contencion.png"), dpi=300)
plt.close()

print("[+] Graficas generadas exitosamente en:", OUT_DIR)

# Imprimir resumen de tabla markdown para incrustar en el reporte
print("\n### TABLA DE RESULTADOS PROMEDIADOS:")
print("| Motor | Perfil | Query | Concurrencia | QPS Promedio | P50 (ms) | P95 (ms) | P99 (ms) |")
print("|---|---|---|---|---|---|---|---|")
for key in sorted(avg_data.keys()):
    eng, qry, prof = key
    for c in concurrencies:
        v = avg_data[key].get(c, {})
        if v:
            print(f"| {eng.capitalize()} | {prof.capitalize()} | {qry.upper()} | {c} clientes | {v['qps']} | {v['p50']:,} | {v['p95']:,} | {v['p99']:,} |")

