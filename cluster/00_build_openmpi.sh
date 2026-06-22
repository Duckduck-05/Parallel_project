#!/usr/bin/env bash
# Build a PINNED OpenMPI version from source into /opt so EVERY node ends up with the EXACT
# same MPI runtime. This is the deterministic part of the setup: `apt install openmpi-bin`
# gives whatever version each Ubuntu release ships (e.g. 4.1.x vs 5.0.x), and a version
# mismatch between nodes causes PMIx errors / mpirun refusing to run. Run this on EVERY node.
#
#   bash cluster/00_build_openmpi.sh            # builds the default pinned version
#   OPENMPI_VERSION=5.0.9 bash cluster/00_build_openmpi.sh
set -euo pipefail

VER="${OPENMPI_VERSION:-5.0.9}"
SERIES="${VER%.*}"                 # e.g. 5.0
PREFIX="/opt/openmpi-$VER"

if [ -x "$PREFIX/bin/mpirun" ]; then
    echo "OpenMPI already installed at $PREFIX:"
    "$PREFIX/bin/mpirun" --version | head -n 1
    exit 0
fi

echo "==> Installing build dependencies..."
sudo apt update
sudo apt install -y build-essential gfortran wget

TARBALL="openmpi-$VER.tar.bz2"
URL="https://download.open-mpi.org/release/open-mpi/v$SERIES/$TARBALL"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
cd "$TMP"

echo "==> Downloading $URL"
wget -q "$URL"
tar xf "$TARBALL"
cd "openmpi-$VER"

echo "==> ./configure --prefix=$PREFIX  (log: /tmp/ompi_configure.log)"
./configure --prefix="$PREFIX" > /tmp/ompi_configure.log 2>&1
echo "==> make -j$(nproc)  (this takes several minutes; log: /tmp/ompi_make.log)"
make -j"$(nproc)" > /tmp/ompi_make.log 2>&1
echo "==> sudo make install  (log: /tmp/ompi_install.log)"
sudo make install > /tmp/ompi_install.log 2>&1

# Put the pinned OpenMPI on PATH for interactive shells (idempotent).
BRC="$HOME/.bashrc"
if ! grep -q "openmpi-$VER/bin" "$BRC" 2>/dev/null; then
    {
        echo ""
        echo "# pinned OpenMPI for the parallel-tsp project"
        echo "export PATH=$PREFIX/bin:\$PATH"
        echo "export LD_LIBRARY_PATH=$PREFIX/lib:\${LD_LIBRARY_PATH:-}"
    } >> "$BRC"
    echo "==> Added $PREFIX to PATH in $BRC (open a new shell to pick it up)."
fi

echo "==> Done:"
"$PREFIX/bin/mpirun" --version | head -n 1
echo "All nodes that run this script get an identical $PREFIX runtime."
