#!/usr/bin/env bash
# Regenerate ALL report experiments/figures in one command -> results/exp_*.{csv,png}
# Produces: exp_size (find N for 2-3 min), exp_gran (granularity/load-balance),
#           exp_speedup (speedup with & without comm). Matches report §5.
#
# Single machine (this node, procs = cores):
#   bash cluster/run_report_experiments.sh
# On the cluster (distributed, via run_cluster.sh seq mapper):
#   bash cluster/run_report_experiments.sh cluster/hosts.cur
#
# Tunables via env: GENS (default 400), SIZES, SPEEDUP_PROCS, GRAN_N, SPEEDUP_N.
set -u

HF="${1:-}"                                   # optional hostfile -> cluster mode
HFARG=(); [ -n "$HF" ] && HFARG=(--hostfile "$HF")

cd "$(dirname "$0")/.." || exit 1             # repo root

# --- locate OpenMPI 5.0.9 + a python with mpi4py (same logic as run_local.sh) ---
for P in /opt/openmpi-5.0.9 /opt/homebrew /usr/local /usr; do
  [ -x "$P/bin/mpirun" ] && export PATH="$P/bin:$PATH" \
    && export LD_LIBRARY_PATH="$P/lib:${LD_LIBRARY_PATH:-}" \
    && export DYLD_LIBRARY_PATH="$P/lib:${DYLD_LIBRARY_PATH:-}" && break
done
PY=""
for c in /opt/homebrew/bin/python3 python3 /usr/bin/python3; do
  command -v "$c" >/dev/null 2>&1 && "$c" -c "import mpi4py,numpy,matplotlib" >/dev/null 2>&1 && PY="$c" && break
done
[ -n "$PY" ] || { echo "ERROR: need python3 with mpi4py+numpy+matplotlib"; exit 1; }

GENS="${GENS:-400}"
SIZES="${SIZES:-100 200 400 800}"
SPEEDUP_PROCS="${SPEEDUP_PROCS:-1 2 4 8}"
GRAN_N="${GRAN_N:-200}"
SPEEDUP_N="${SPEEDUP_N:-200}"
# procs for size/gran = core count (single machine) or node count (cluster)
if [ -n "$HF" ]; then NPROC=$(grep -cE '^[^#[:space:]]' "$HF"); else NPROC=$(nproc 2>/dev/null || echo 4); fi

echo "=== launcher=$(command -v mpirun)  python=$PY  procs=$NPROC  gens=$GENS  mode=${HF:-single-machine} ==="
echo ">>> [1/3] SIZE sweep (find N for ~2-3 min): N = $SIZES"
"$PY" python/experiments.py size --procs "$NPROC" --sizes $SIZES --gens "$GENS" "${HFARG[@]}"
echo ">>> [2/3] GRANULARITY / load-balance at N=$GRAN_N"
"$PY" python/experiments.py gran --procs "$NPROC" --size "$GRAN_N" --gens "$GENS" "${HFARG[@]}"
echo ">>> [3/3] SPEEDUP (procs $SPEEDUP_PROCS) at N=$SPEEDUP_N"
"$PY" python/experiments.py speedup --procs $SPEEDUP_PROCS --size "$SPEEDUP_N" --gens "$GENS" "${HFARG[@]}"

echo "=== DONE. Figures + CSVs in results/exp_{size,gran,speedup}.{png,csv} ==="
ls -1 results/exp_*.png 2>/dev/null
