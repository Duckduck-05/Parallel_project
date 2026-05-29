#!/usr/bin/env bash
# Task 3 - Thiet lap SSH khong can mat khau giua cac node.
# Chay tren TUNG may (node1, node2, node3): bash 02_ssh_setup.sh
# Yeu cau: da lam xong Task 2 (cac may ping duoc nhau theo ten node1/2/3).
set -e

NODES=(node1 node2 node3)
USER_NAME=$(whoami)

echo "==> Bao dam co OpenSSH server..."
sudo apt install -y openssh-server
sudo systemctl enable --now ssh

# 1) Tao khoa SSH neu chua co (khong dat passphrase de MPI tu dong dang nhap).
if [ ! -f "$HOME/.ssh/id_rsa" ]; then
    echo "==> Tao cap khoa SSH..."
    ssh-keygen -t rsa -b 4096 -N "" -f "$HOME/.ssh/id_rsa"
else
    echo "==> Da co khoa SSH, bo qua buoc tao."
fi

# 2) Chep khoa cong khai sang TAT CA node (ke ca chinh no de mpirun chay local qua SSH).
echo "==> Chep khoa cong khai sang cac node (se hoi mat khau LAN DAU)..."
for n in "${NODES[@]}"; do
    ssh-copy-id -o StrictHostKeyChecking=no "${USER_NAME}@${n}" || \
        echo "   (Bo qua $n neu chua bat hoac la chinh may nay)"
done

echo ""
echo "==> DEMO kiem tra: dang nhap khong mat khau"
for n in "${NODES[@]}"; do
    echo -n "ssh $n => "
    ssh -o BatchMode=yes -o StrictHostKeyChecking=no "${USER_NAME}@${n}" hostname || \
        echo "CHUA OK (chay lai script tren $n)"
done

echo ""
echo "Neu moi dong in ra dung ten node ma KHONG hoi mat khau => Task 3 HOAN TAT."
