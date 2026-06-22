#!/usr/bin/env bash
# Install OpenMPI + the tools needed on EVERY Ubuntu node.
# Run on each machine: bash 01_install.sh
set -e

echo "==> Updating package lists..."
sudo apt update

echo "==> Installing OpenMPI, the C/C++ toolchain, and the Python plotting libraries..."
# The solver is C++ (needs libopenmpi-dev + build-essential). Python is only used for
# plotting / the live demo, so it just needs numpy + matplotlib (NO mpi4py).
sudo apt install -y \
    openmpi-bin libopenmpi-dev build-essential make \
    python3-pip python3-numpy python3-matplotlib \
    openssh-server rsync

echo "==> Versions:"
mpirun --version | head -n 1
mpicxx --version | head -n 1

echo ""
echo "DONE. Next: build the solver -> cd cpp && make    (see README.md)."
