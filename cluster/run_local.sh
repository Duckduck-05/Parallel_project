#!/usr/bin/env bash
# Run the Island-GA TSP solver on THIS machine alone (single node, oversubscribed cores).
# Builds the C++ binary if needed, then launches it with mpirun. No cluster / ssh needed.
#
# Usage:
#   bash cluster/run_local.sh                 # 4 islands, cities_50, 300 gens
#   bash cluster/run_local.sh 4
#   bash cluster/run_local.sh 4 data/cities_50.txt --gens 500 --sync 20
set -u

NP="${1:-4}"; shift 2>/dev/null || true

# --- locate OpenMPI (a source build in /opt first, then system / Homebrew) ---
MPIROOT=""
for P in /opt/openmpi-5.0.9 /opt/homebrew /usr/local /usr; do
  [ -x "$P/bin/mpirun" ] && MPIROOT="$P" && break
done
[ -n "$MPIROOT" ] || { echo "ERROR: mpirun (OpenMPI) not found"; exit 1; }
export PATH="$MPIROOT/bin:$PATH"
export LD_LIBRARY_PATH="$MPIROOT/lib:${LD_LIBRARY_PATH:-}"
export DYLD_LIBRARY_PATH="$MPIROOT/lib:${DYLD_LIBRARY_PATH:-}"   # macOS

cd "$(dirname "$0")/.." || exit 1     # repo root (cluster/.. )

# --- build the solver if it is missing or older than its source ---
if [ ! -x cpp/tsp_island ] || [ cpp/tsp_island.cpp -nt cpp/tsp_island ]; then
  echo "Building cpp/tsp_island ..."
  ( cd cpp && make tsp_island ) || { echo "ERROR: build failed"; exit 1; }
fi

echo "host=$(hostname)  mpirun=$MPIROOT/bin/mpirun  np=$NP"
if [ "$#" -gt 0 ]; then
  exec mpirun --oversubscribe -np "$NP" ./cpp/tsp_island "$@"
else
  exec mpirun --oversubscribe -np "$NP" ./cpp/tsp_island data/cities_50.txt --gens 300 --sync 20
fi
