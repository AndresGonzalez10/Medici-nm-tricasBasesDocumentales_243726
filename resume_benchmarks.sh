#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# resume_benchmarks.sh
# Reanuda la corrida desde PostgreSQL Baseline Q2 y perfiles Medium y Severe.
# ─────────────────────────────────────────────────────────────

set -euo pipefail

WARMUP=20
MEASURE=80
COOLDOWN=15
REPS=3

CONCURRENCIES=(1 10 50)
LOG_DIR="entregables/logs"
mkdir -p "$LOG_DIR" entregables

container_name() {
  local engine=$1 profile=$2
  if   [[ "$engine" == "mongo" ]];    then echo "mongo_${profile}"
  elif [[ "$engine" == "postgres" ]]; then echo "postgres_${profile}"
  fi
}

flush_cache() {
  local cname=$1
  echo "  [flush] Limpiando cache en $cname..."
  docker exec "$cname" sh -c "sync; echo 3 > /proc/sys/vm/drop_caches" 2>/dev/null || true
}

echo "═══════════════════════════════════════════════════════"
echo "  Reanudando Benchmark: PostgreSQL Baseline Q2"
echo "═══════════════════════════════════════════════════════"

# 1. Completar PostgreSQL Baseline Q2
for concurrency in "${CONCURRENCIES[@]}"; do
  for rep in $(seq 1 $REPS); do
    logfile="$LOG_DIR/postgres_baseline_q2_c${concurrency}_r${rep}.log"
    echo ""
    echo "─── postgres | profile=baseline | query=q2 | c=$concurrency | r=$rep ───"
    flush_cache "postgres_baseline"

    echo "  [warmup] ${WARMUP}s..."
    python benchmark_runner/runner.py --engine postgres --profile baseline --query q2 --concurrency "$concurrency" --duration "$WARMUP" --run-number 0 >> "$logfile" 2>&1 || true

    echo "  [medicion] ${MEASURE}s..."
    python benchmark_runner/runner.py --engine postgres --profile baseline --query q2 --concurrency "$concurrency" --duration "$MEASURE" --run-number "$rep" 2>&1 | tee -a "$logfile"

    echo "  [cooldown] ${COOLDOWN}s..."
    sleep "$COOLDOWN"
  done
done

echo ""
echo "◀ Bajando contenedores de BD del perfil: baseline"
docker compose --profile baseline down
sleep 5

# 2. Perfiles restantes: Medium y Severe
REMAINING_PROFILES=("medium" "severe")
ENGINES=("mongo" "postgres")
QUERIES=("q1" "q2")

for profile in "${REMAINING_PROFILES[@]}"; do
  echo ""
  echo "▶ Levantando perfil: $profile"
  docker compose --profile "$profile" up -d
  sleep 10

  for engine in "${ENGINES[@]}"; do
    cname=$(container_name "$engine" "$profile")

    for query in "${QUERIES[@]}"; do
      for concurrency in "${CONCURRENCIES[@]}"; do
        for rep in $(seq 1 $REPS); do
          logfile="$LOG_DIR/${engine}_${profile}_${query}_c${concurrency}_r${rep}.log"
          echo ""
          echo "─── $engine | profile=$profile | query=$query | c=$concurrency | r=$rep ───"
          flush_cache "$cname"

          echo "  [warmup] ${WARMUP}s..."
          python benchmark_runner/runner.py --engine "$engine" --profile "$profile" --query "$query" --concurrency "$concurrency" --duration "$WARMUP" --run-number 0 >> "$logfile" 2>&1 || true

          echo "  [medicion] ${MEASURE}s..."
          python benchmark_runner/runner.py --engine "$engine" --profile "$profile" --query "$query" --concurrency "$concurrency" --duration "$MEASURE" --run-number "$rep" 2>&1 | tee -a "$logfile"

          echo "  [cooldown] ${COOLDOWN}s..."
          sleep "$COOLDOWN"
        done
      done
    done
  done

  echo ""
  echo "◀ Bajando contenedores de BD del perfil: $profile"
  docker compose --profile "$profile" down
  sleep 5
done

echo ""
echo "═══════════════════════════════════════════════════════"
echo "  [+] Benchmark reanudado y completado exitosamente!"
echo "  [+] Resultados en: entregables/resultados.csv"
echo "  [+] Logs en:       entregables/logs/"
echo "═══════════════════════════════════════════════════════"

