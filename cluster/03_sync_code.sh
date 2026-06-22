#!/usr/bin/env bash
# Sync the project directory to the other nodes with rsync.
# Run on node1 (the launcher): bash 03_sync_code.sh
# Re-run it whenever you change code on node1 to update node2/node3/node4.
set -e

NODES=(node2 node3 node4)         # target machines (node1 is the source)
SRC="$HOME/parallel-tsp"          # project directory
USER_NAME=$(whoami)

for n in "${NODES[@]}"; do
    echo "==> Syncing to $n ..."
    rsync -avz --delete \
        --exclude '.git' --exclude 'results/*.png' \
        "$SRC/" "${USER_NAME}@${n}:$SRC/"
done

echo "DONE. All nodes now have identical code."
