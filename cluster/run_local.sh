#!/usr/bin/env bash
# Run the Island-GA TSP on THIS machine alone (single node, oversubscribed cores).
# Portable across the team: auto-detects OpenMPI 5.0.9 + a python that has mpi4py,
# on Linux (WSL/native) and macOS. No cluster / ssh / Tailscale needed.
#
# Usage:
#   bash cluster/run_local.sh                 # 2 islands, cities_50, 300 gens
#   bash cluster/run_local.sh 4               # 4 islands
#   bash cluster/run_local.sh 4 data/cities_50.txt --gens 500 --migrate 20
set -u

NP="${1:-2}"; shift 2>/dev/null || true

# --- locate OpenMPI 5.0.9 (source /opt on Linux+mac, or brew on mac) ---
MPIROOT=""
for P in /opt/openmpi-5.0.9 /opt/homebrew /usr/local /usr; do
  [ -x "$P/bin/mpirun" ] && MPIROOT="$P" && break
done
[ -n "$MPIROOT" ] || { echo "ERROR: mpirun (OpenMPI) not found"; exit 1; }
export PATH="$MPIROOT/bin:$PATH"
export LD_LIBRARY_PATH="$MPIROOT/lib:${LD_LIBRARY_PATH:-}"
export DYLD_LIBRARY_PATH="$MPIROOT/lib:${DYLD_LIBRARY_PATH:-}"   # macOS

# --- pick a python3 that actually has mpi4py (mac: brew python, not /usr/bin) ---
PY=""
for cand in /opt/homebrew/bin/python3 /usr/local/bin/python3 python3 /usr/bin/python3; do
  command -v "$cand" >/dev/null 2>&1 || continue
  if "$cand" -c "import mpi4py, numpy" >/dev/null 2>&1; then PY="$cand"; break; fi
done
[ -n "$PY" ] || { echo "ERROR: no python3 with mpi4py+numpy found. Install: pip install --user mpi4py numpy (build mpi4py against this OpenMPI)"; exit 1; }

cd "$(dirname "$0")/.." || exit 1     # repo root (cluster/.. )

echo "host=$(hostname)  mpirun=$MPIROOT/bin/mpirun  python=$PY  np=$NP"
if [ "$#" -gt 0 ]; then
  exec mpirun --oversubscribe -np "$NP" "$PY" python/tsp_island.py "$@"
else
  exec mpirun --oversubscribe -np "$NP" "$PY" python/tsp_island.py data/cities_50.txt --gens 300 --migrate 20
fi
