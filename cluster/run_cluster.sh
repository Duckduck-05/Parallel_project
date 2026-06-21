#!/usr/bin/env bash
# Launch MPI across the Tailscale cluster from node1 (the launcher).
# Usage:
#   ./run_cluster.sh <hostfile> <np> <command...>
#   ./run_cluster.sh cluster/hosts.cur 2 hostname
#   ./run_cluster.sh cluster/hosts.cur 2 python3 python/tsp_island.py data/cities_50.txt --gens 500 --migrate 20
#
# Why these flags (discovered the hard way, 2026-06-21):
#  - node1 + node4 both run OpenMPI 5.0.9 in /opt/openmpi-5.0.9 (must MATCH across nodes,
#    else PMIx "version mismatch"). node1 was apt 5.0.10 -> rebuilt 5.0.9 from source.
#  - prte_launch_agent: node4's 5.0.9 isn't in non-interactive ssh PATH, so give prted's
#    absolute path. Same path exists on node1 (real build).
#  - oob_tcp/btl_tcp if_include tailscale0: force PRRTE + MPI traffic onto the tailnet
#    interface, else daemons can't connect back over WAN/NAT and mpirun hangs.
#
# NOTE: assumes every remote node has OpenMPI 5.0.9 at /opt/openmpi-5.0.9 and a
# tailscale0 interface. node3 (macOS) differs (brew path, utun* iface) — adjust
# LAUNCH_AGENT / IFACE per platform when node3 joins.
set -euo pipefail

export PATH="/opt/openmpi-5.0.9/bin:$PATH"
export LD_LIBRARY_PATH="/opt/openmpi-5.0.9/lib:${LD_LIBRARY_PATH:-}"

LAUNCH_AGENT="/opt/openmpi-5.0.9/bin/prted"

HOSTFILE="${1:-cluster/hosts.cur}"
NP="${2:-2}"
shift 2 2>/dev/null || true
[ "$#" -gt 0 ] || { echo "usage: $0 <hostfile> <np> <command...>"; exit 1; }

# Each rank cd's to its OWN ~/parallel-tsp first ($HOME expands per-node/per-user),
# because mpirun starts remote ranks in $HOME, and homes differ across machines.
# No interface pin: tailscale0 (Linux) vs utunN (mac) differ per node and OpenMPI's
# default selection reaches the tailnet fine. Re-add --mca btl_tcp_if_include if a
# node with multiple NICs picks the wrong route.
exec mpirun \
  --prtemca prte_launch_agent "$LAUNCH_AGENT" \
  --hostfile "$HOSTFILE" -np "$NP" \
  bash -c 'cd "$HOME/parallel-tsp" && exec "$@"' _ "$@"
