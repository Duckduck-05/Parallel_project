#!/usr/bin/env bash
# Generate a --map-by seq hostfile with N ranks per node, for a given list of nodes.
# Avoids hand-writing/hardcoding a separate static hostfile for every island count.
#
# Usage: bash make_hostfile.sh <ranks_per_node> <node1> [node2 ...] > cluster/hosts.generated
#   bash cluster/make_hostfile.sh 2 node1 node2 node3 node4 > /tmp/hosts_8
#   bash cluster/make_hostfile.sh 1 node1 node2 node4        > /tmp/hosts_3node
#
# Why repeated literal lines instead of "slots=N": --map-by seq (required for this
# heterogeneous-CPU cluster, see CLAUDE.md) ignores hostfile "slots=" and needs one
# literal line per rank.
set -euo pipefail

RANKS_PER_NODE="${1:?usage: make_hostfile.sh <ranks_per_node> <node...>}"
shift
[ "$#" -gt 0 ] || { echo "usage: make_hostfile.sh <ranks_per_node> <node...>" >&2; exit 1; }

for node in "$@"; do
    for ((r = 0; r < RANKS_PER_NODE; r++)); do
        echo "$node"
    done
done
