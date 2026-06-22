#!/usr/bin/env bash
# Launch an MPI job across the cluster from node1 (the launcher).
# Usage:
#   ./run_cluster.sh <hostfile> <np> <command...>
#   ./run_cluster.sh cluster/hosts 4 hostname
#   ./run_cluster.sh cluster/hosts 4 ./cpp/tsp_island data/cities_50.txt --gens 500 --sync 20
#
# Why these flags (learned the hard way):
#  - Every node must run the SAME OpenMPI build (here 5.0.9 in /opt/openmpi-5.0.9), otherwise
#    PMIx reports a "version mismatch". If a node was installed from apt with a different
#    version, rebuild 5.0.9 from source so the launcher and all nodes match.
#  - prte_launch_agent: a node's /opt OpenMPI may not be on its non-interactive ssh PATH, so
#    we pass prted's absolute path explicitly (the same path exists on every node).
#  - --map-by seq + --bind-to none: assign ranks to hostfile nodes sequentially WITHOUT
#    requiring each node's hwloc topology. Essential for HETEROGENEOUS nodes (different core
#    counts) -- the default topology-aware mapper drops any node whose topology differs from
#    the launcher's. --bind-to none also avoids core binding (which needs topology).
set -euo pipefail

export PATH="/opt/openmpi-5.0.9/bin:$PATH"
export LD_LIBRARY_PATH="/opt/openmpi-5.0.9/lib:${LD_LIBRARY_PATH:-}"

LAUNCH_AGENT="/opt/openmpi-5.0.9/bin/prted"

HOSTFILE="${1:-cluster/hosts}"
NP="${2:-4}"
shift 2 2>/dev/null || true
[ "$#" -gt 0 ] || { echo "usage: $0 <hostfile> <np> <command...>"; exit 1; }

# Each rank cd's into its OWN ~/parallel-tsp first ($HOME expands per node/user), because
# mpirun starts remote ranks in $HOME and home directories differ across machines.
exec mpirun \
  --prtemca prte_launch_agent "$LAUNCH_AGENT" \
  --map-by seq --bind-to none \
  --hostfile "$HOSTFILE" -np "$NP" \
  bash -c 'cd "$HOME/parallel-tsp" && exec "$@"' _ "$@"
