# Parallel TSP - Island-model Genetic Algorithm on an MPI cluster

Solve the Travelling Salesman Problem with an **island-model Genetic Algorithm**,
parallelized with **MPI (OpenMPI)** across a cluster of up to **4 nodes**.

The whole solver - the GA and all parallelization - is written in **C++**.
**Python is used only for visualization, the live demo, and plotting the report figures.**

## Repository layout

```
cpp/        C++ source: GA core, local search, MPI island solver, sequential baseline, tests
python/     visualization & plotting only (no algorithm): live_view, visualize, benchmark, experiments
data/       city coordinates + a small generator
cluster/    install / ssh / sync scripts, hostfiles, and the MPI launchers
results/    generated figures (PNG) and CSVs
report/     report.docx + source archive
```

## Parallel design

Each MPI process is an independent **island** running its own GA with its own seed, so the
islands explore different regions of the search space in parallel. They share results
periodically:

1. **Partial global-best migration (every `--sync` generations).** `MPI_Allreduce(MINLOC)`
   finds the single best tour across all islands; its owner `MPI_Bcast`s it. Rather than
   cloning that whole tour into every island (which collapses diversity), each other island
   splices only a random contiguous **segment** of it into `--migrants` of its individuals via
   OX crossover (segment from the best, the rest from a random local individual). Good
   sub-routes spread, but random cut points + different local mates keep every island distinct
   so diversity is preserved.
2. **Convergence stop.** Because the global best is identical on every rank at each sync, all
   ranks can agree to **stop together** once it has not improved for `--patience` generations -
   no extra communication, no deadlock.
3. **Baseline.** `--sync 0` disables sharing entirely (embarrassingly parallel; also disables
   the early stop) - useful as the "no communication" comparison in the report.

The final global best is gathered with `MPI_Allreduce(MINLOC)` and sent to rank 0.

## Build

Requires OpenMPI (`mpicxx`) and a C++17 compiler.

```bash
cd cpp
make            # builds tsp_island (MPI) + tsp_sequential (baseline)
make test       # builds and runs the unit tests (no MPI needed)
```

If `mpicxx` is not on your PATH (e.g. a source build under /opt):

```bash
make CXX=/opt/openmpi-5.0.9/bin/mpicxx
```

## Run

```bash
# one machine, 4 islands, sharing every 20 generations
mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_50.txt --gens 500 --sync 20

# stop early once the global best stalls for 200 generations
mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_50.txt --gens 5000 --sync 20 --patience 200

# baseline: no result sharing
mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_50.txt --gens 500 --sync 0

# convenience wrapper (builds if needed, single machine)
bash cluster/run_local.sh 4 data/cities_50.txt --gens 500 --sync 20
```

Key flags: `--gens`, `--pop`, `--sync` (migration interval, `0` = off), `--migrants`
(individuals recombined with the global best per sync; default 3 - higher = more mixing,
less diversity), `--patience` (stop after this many stalled generations, `0` = off),
`--twoopt` (2-opt memetic period), `--seed`, `--auto-balance`,
`--out tour.txt` (also writes `tour.txt.history`), `--stats file.csv`, `--live stream.jsonl`.

## Cluster (4 nodes, LAN)

### Requirements for a stable OpenMPI connection

For ranks on different machines to connect and stay connected, every node needs:

- **A shared LAN with mutual reachability** - all nodes on the same network, able to `ping`
  each other directly. (Internet alone does not work: MPI opens node-to-node TCP on random
  high ports, which NAT/firewalls block.)
- **Password-less SSH** (key-based) from the launcher (node1) to every node - mpirun starts
  remote ranks over SSH.
- **The same OpenMPI version at the same path** on every node (here 5.0.9 in
  `/opt/openmpi-5.0.9`); a version mismatch causes PMIx errors.
- **The same Linux username** on each node (mpirun SSHes as the same user by default).
- **The same `/etc/hosts` IP -> name mapping** on every node (template: `cluster/hosts.sample`).
- **The same code on the same branch at the same path** (`~/parallel-tsp`), rebuilt on each
  node - the compiled binary is not portable, so run `cd cpp && make` on every node. The data
  files must also exist on every node at the same relative path (`cluster/03_sync_code.sh`
  syncs the tree).
- **The firewall open between nodes** (or disabled on a trusted LAN), so MPI's ports are not
  blocked - otherwise mpirun hangs.

Clock sync, internet access, and identical hardware are *not* required.

### Steps

1. On every node: `bash cluster/01_install.sh` (OpenMPI, build tools, rsync, ssh).
2. Map node names to IPs: copy `cluster/hosts.sample`, replace the IPs with your real ones
   (`hostname -I` on each box), and append the four lines to `/etc/hosts` on **every** node.
   Changing the LAN/IPs later means editing only this mapping.
3. Set up password-less ssh (`cluster/02_ssh_setup.sh`) and sync the code
   (`cluster/03_sync_code.sh`).
4. Launch from node1:

```bash
bash cluster/run_cluster.sh cluster/hosts 4 ./cpp/tsp_island data/cities_50.txt --gens 500 --sync 20
```

`run_cluster.sh` uses `--map-by seq --bind-to none` so heterogeneous nodes (different core
counts) work, and pins the launch agent so all nodes use the same OpenMPI build.

## Visualization & report figures (Python)

Install the plotting dependencies once: `pip install -r requirements.txt` (numpy + matplotlib;
**mpi4py is not needed**).

```bash
# Live demo (launches the C++ solver locally and animates it):
python3 python/live_view.py run data/cities_30.txt --islands 4 --gens 400 --sync 20

# Live view of a REAL cluster run:
#   window 1 (head node): mpirun --hostfile cluster/hosts -np 4 ./cpp/tsp_island \
#                         data/cities_30.txt --gens 400 --sync 20 --live results/stream.jsonl
#   window 2:             python3 python/live_view.py tail results/stream.jsonl data/cities_30.txt

# Static figures from a finished run:
mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_50.txt --gens 500 --sync 20 --out results/tour.txt
python3 python/visualize.py route data/cities_50.txt results/tour.txt --out results/route.png
python3 python/visualize.py converge results/tour.txt.history --out results/converge.png

# Speedup / size / granularity experiments (drives the C++ binary, then plots):
python3 python/experiments.py speedup --procs 1 2 4 8 --size 200
bash cluster/run_report_experiments.sh            # all three at once
```

## Tests

```bash
cd cpp && make test     # unit tests for the GA operators and the 2-opt / Or-opt local search
```
