#!/usr/bin/env bash
# Install everything OTHER than OpenMPI on every Ubuntu node.
# Run AFTER cluster/00_build_openmpi.sh (which builds the pinned OpenMPI into /opt).
# Run on each machine: bash 01_install.sh
set -e

echo "==> Updating package lists..."
sudo apt update

echo "==> Installing the C/C++ toolchain, SSH, rsync, and the Python plotting libraries..."
# OpenMPI is NOT installed here on purpose: it is pinned/source-built by 00_build_openmpi.sh
# so every node has the exact same version (apt versions differ across releases -> PMIx
# mismatch). The solver is C++ (needs build-essential + make). Python is only for plotting,
# so it just needs numpy + matplotlib (NO mpi4py).
sudo apt install -y \
    build-essential make \
    python3-pip python3-numpy python3-matplotlib \
    openssh-server rsync

echo "==> Checking the pinned OpenMPI from 00_build_openmpi.sh..."
if [ -x /opt/openmpi-5.0.9/bin/mpirun ]; then
    /opt/openmpi-5.0.9/bin/mpirun --version | head -n 1
    /opt/openmpi-5.0.9/bin/mpicxx --version | head -n 1
else
    echo "WARNING: /opt/openmpi-5.0.9 not found. Run cluster/00_build_openmpi.sh first."
fi

echo ""
echo "DONE. Next: build the solver -> cd cpp && make    (see README.md)."
