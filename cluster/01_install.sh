#!/usr/bin/env bash
# Task 1 - Cai dat OpenMPI + cong cu can thiet tren MOI may Ubuntu.
# Chay tren CA 3 may: bash 01_install.sh
set -e

echo "==> Cap nhat danh sach goi..."
sudo apt update

echo "==> Cai OpenMPI, trinh bien dich C/C++, va thu vien Python..."
sudo apt install -y \
    openmpi-bin libopenmpi-dev build-essential \
    python3-pip python3-mpi4py python3-numpy python3-matplotlib \
    openssh-server rsync

echo "==> Kiem tra phien ban:"
mpirun --version
mpicc --version | head -n 1
python3 -c "import mpi4py; print('mpi4py OK', mpi4py.__version__)"

echo ""
echo "HOAN TAT. Buoc tiep theo: chay thu hello (xem README cluster)."
