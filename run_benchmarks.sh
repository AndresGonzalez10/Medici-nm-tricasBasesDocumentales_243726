#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# run_benchmarks.sh
# BDA en la Nube 2026 — IT2iD | Universidad Politécnica de Chiapas
#
# Automatiza la matriz completa de 36 celdas × 3 repeticiones
# = 108 runs totales.
#
# Matriz:
#   2 motores × 3 perfiles × 2 queries × 3 concurrencias × 3 reps
#
# Protocolo por run:
#   1. Levantar perfil Docker
#   2. Flush de caché (dentro del contenedor Linux)
#   3. Warmup 60s
#   4. Medición 300s  → runner.py
#   5. Cooldown 60s
#   6. Bajar contenedores de BD (monitoreo se mantiene)
#
# Uso:
#   bash run_benchmarks.sh
#   bash run_benchmarks.sh --dry-run   (solo imprime los comandos)
# ─────────────────────────────────────────────────────────────

set -euo pipefail

# ── Parámetros del protocolo (Calibrado para ~4.5h totales) ──
WARMUP=20
MEASURE=80
COOLDOWN=15
REPS=3

ENGINES=("mongo" "postgres")
PROFILES=("baseline" "medium" "severe")
QUERIES=("q1" "q2")
CONCURRENCIES=(1 10 50)

DRY_RUN=false
[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=true

LOG_DIR="entregables/logs"
mkdir -p "$LOG_DIR" entregables

TOTAL=$(( ${#ENGINES[@]} * ${#PROFILES[@]} * ${#QUERIES[@]} * ${#CONCURRENCIES[@]} * REPS ))
echo "═══════════════════════════════════════════════════════"
echo "  BDA en la Nube 2026 — Benchmark Completo"
echo "  Total de runs: $TOTAL"
echo "  dry-run: $DRY_RUN"
echo "═══════════════════════════════════════════════════════"

run_count=0

# ── Contenedor por motor y perfil ────────────────────────────
container_name() {
  local engine=$1 profile=$2
  if   [[ "$engine" == "mongo" ]];    then echo "mongo_${profile}"
  elif [[ "$engine" == "postgres" ]]; then echo "postgres_${profile}"
  fi
}

# ── Flush de caché dentro del contenedor ─────────────────────
flush_cache() {
  local cname=$1
  echo "  [flush] Limpiando caché en $cname..."
  if ! $DRY_RUN; then
    docker exec "$cname" sh -c "sync; echo 3 > /proc/sys/vm/drop_caches" 2>/dev/null || true
  fi
}

# ── Loop principal ────────────────────────────────────────────
for profile in "${PROFILES[@]}"; do

  echo ""
  echo "▶ Levantando perfil: $profile"
  if ! $DRY_RUN; then
    docker compose --profile "$profile" up -d
    sleep 10  # esperar a que los motores estén listos
  fi

  for engine in "${ENGINES[@]}"; do
    cname=$(container_name "$engine" "$profile")

    for query in "${QUERIES[@]}"; do
      for concurrency in "${CONCURRENCIES[@]}"; do
        for rep in $(seq 1 $REPS); do

          run_count=$(( run_count + 1 ))
          logfile="$LOG_DIR/${engine}_${profile}_${query}_c${concurrency}_r${rep}.log"

          echo ""
          echo "─── Run $run_count/$TOTAL ─────────────────────────────"
          echo "    engine=$engine | profile=$profile | query=$query"
          echo "    concurrency=$concurrency | rep=$rep"

          if $DRY_RUN; then
            echo "    [DRY] flush_cache $cname"
            echo "    [DRY] warmup ${WARMUP}s"
            echo "    [DRY] python benchmark_runner/runner.py --engine $engine --profile $profile --query $query --concurrency $concurrency --duration $MEASURE --run-number $rep"
            echo "    [DRY] cooldown ${COOLDOWN}s"
            continue
          fi

          # 1. Flush de caché
          flush_cache "$cname"

          # 2. Warmup
          echo "  [warmup] ${WARMUP}s..."
          python benchmark_runner/runner.py \
            --engine "$engine" \
            --profile "$profile" \
            --query "$query" \
            --concurrency "$concurrency" \
            --duration "$WARMUP" \
            --run-number 0 \
            >> "$logfile" 2>&1 || true

          # 3. Medición
          echo "  [medición] ${MEASURE}s..."
          python benchmark_runner/runner.py \
            --engine "$engine" \
            --profile "$profile" \
            --query "$query" \
            --concurrency "$concurrency" \
            --duration "$MEASURE" \
            --run-number "$rep" \
            2>&1 | tee -a "$logfile"

          # 4. Cooldown
          echo "  [cooldown] ${COOLDOWN}s..."
          sleep "$COOLDOWN"

        done  # reps
      done  # concurrencies
    done  # queries
  done  # engines

  echo ""
  echo "◀ Bajando contenedores de BD del perfil: $profile"
  if ! $DRY_RUN; then
    docker compose --profile "$profile" down
    sleep 5
  fi

done  # profiles

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  ✅ Benchmark completo: $run_count runs ejecutados"
echo "  [+] Resultados en: entregables/resultados.csv"
echo "  [+] Logs en:       entregables/logs/"
echo "═══════════════════════════════════════════════════════"

