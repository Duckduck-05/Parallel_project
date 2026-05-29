#!/usr/bin/env bash
# Task 4 - Dong bo thu muc code sang cac node khac bang rsync.
# Chay tren node1 (may chu): bash 03_sync_code.sh
# Moi lan sua code tren node1, chay lai script nay de cap nhat node2/node3.
set -e

NODES=(node2 node3)              # cac may dich (khong gom node1)
SRC="$HOME/parallel-tsp"          # thu muc du an
USER_NAME=$(whoami)

for n in "${NODES[@]}"; do
    echo "==> Dong bo sang $n ..."
    rsync -avz --delete \
        --exclude '.git' --exclude 'results/*.png' \
        "$SRC/" "${USER_NAME}@${n}:$SRC/"
done

echo "HOAN TAT. Code tren ca 3 may da giong nhau."
