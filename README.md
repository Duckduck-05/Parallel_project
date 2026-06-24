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
results/    generated figures (PNG/GIF) and CSVs
```

## Parallel design

Each MPI process is an independent **island** running its own GA (seed `base + rank*1000`), so
the islands explore different regions of the search space in parallel. Two MPI collective
patterns drive the parallelism:

1. **Parallel greedy init (optional, `--greedy-init`).** Each island builds a nearest-neighbor
   tour from a *different* random start city; `MPI_Allreduce(MINLOC)` picks the best of all `P`
   attempts and its owner `MPI_Bcast`s it, so every island seeds from the best greedy across the
   cluster. It runs *before* the timer, so it does not affect the benchmark - it only changes
   the starting solution (greedy seed vs. random). Off by default = GA from scratch.
2. **Partial global-best migration (every `--sync` generations).** `MPI_Allreduce(MINLOC)`
   finds the single best tour across all islands; its owner `MPI_Bcast`s it. Rather than
   cloning that whole tour into every island (which collapses diversity), each other island
   splices only a random contiguous **segment** of it into `--migrants` of its individuals via
   OX crossover (segment from the best, the rest from a random local individual). Good
   sub-routes spread, but random cut points + different local mates keep every island distinct
   so diversity is preserved.
3. **Convergence stop.** Because the global best is identical on every rank at each sync, all
   ranks can agree to **stop together** once it has not improved for `--patience` generations -
   no extra communication, no deadlock.
4. **Baseline.** `--sync 0` disables sharing entirely (embarrassingly parallel; also disables
   the early stop) - the "no communication" comparison in the report.

The final global best is gathered with `MPI_Allreduce(MINLOC)` and sent to rank 0.

## Setup - which environment, and when

The solver is C++ + MPI, so it **builds and runs on Linux**. There are three setups; pick by
what you are doing.

| You want to...                         | Where                              | Setup files                          | Build / run with |
|----------------------------------------|------------------------------------|--------------------------------------|------------------|
| Develop / run on one machine           | A Linux box, or **WSL** on Windows | `cpp/Makefile`, `cpp/BUILD.txt`      | `cd cpp && make`, then `mpirun -np N ./cpp/tsp_island ...` |
| Run the real multi-node experiments    | 4 Ubuntu nodes on a LAN            | `cluster/*.sh`, `cluster/hosts*` **+ the `cpp/` build on every node** | `00_build_openmpi.sh` -> `01_install.sh` -> build `cpp/` on each node -> `run_cluster.sh` |
| Only view results / demos / make plots | Any OS (Windows native is fine)    | `requirements.txt`                   | `pip install -r requirements.txt`, then `python3 python/...` |

### 1. C++ build - the solver (`cpp/`)

Needed everywhere the solver runs. Requires **OpenMPI (`mpicxx`) + a C++17 compiler**
(`sudo apt install openmpi-bin libopenmpi-dev build-essential` on Ubuntu).

```bash
cd cpp
make            # builds tsp_island (MPI) + tsp_sequential (baseline)
make test       # builds and runs the unit tests (no MPI needed)
make clean
```

If `mpicxx` is not on your PATH (e.g. a source build under `/opt`), point `CXX` at it:

```bash
make CXX=/opt/openmpi-5.0.9/bin/mpicxx
```

See `cpp/BUILD.txt` for the manual one-off compile commands.

### 2. Single machine / WSL (local development)

- **Native Linux:** do the `cpp/` build above, then run with `mpirun --oversubscribe -np N ...`
  (see [Run](#run)). `bash cluster/run_local.sh` builds + runs in one step.
- **Windows:** the solver cannot build natively - use **WSL** (Ubuntu). Inside WSL it is just
  a Linux box: install OpenMPI, build `cpp/`, run with `mpirun`. The repo is reachable at
  `/mnt/c/...`. This machine's WSL already has OpenMPI **5.0.9** at `/opt/openmpi-5.0.9`, but
  its system `mpicxx` wrapper is broken (no dev headers), so build and run with that prefix:
  ```bash
  export PATH=/opt/openmpi-5.0.9/bin:$PATH
  export LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib
  make -C cpp CXX=/opt/openmpi-5.0.9/bin/mpicxx
  mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_50.txt --gens 500 --sync 20
  ```
  (Note: WSL's `/tmp` is wiped between separate shell sessions - build and run in one shell.)
- **Plotting on Windows** can run with native Python (e.g. Anaconda) instead of WSL - the GUI
  window is more reliable than WSLg: run the solver in WSL, the viewer in Windows Python.

### 3. Cluster - 4 nodes (`cluster/`)

For the real multi-node experiments. This setup **builds on setup step 1**: the C++ binary is
not portable, so **every node must build `cpp/` itself** (`cd cpp && make`) after the code is
synced - the launcher does not compile the remote nodes for you. Full requirements +
step-by-step are in [Cluster (4 nodes, LAN)](#cluster-4-nodes-lan) below. On the nodes
themselves (Ubuntu) this is **native Linux - no WSL**.

### 4. Visualization deps - Python (`requirements.txt`)

Only `numpy` + `matplotlib` (no `mpi4py` - Python never touches MPI here).

```bash
pip install -r requirements.txt
```

## Run

```bash
# one machine, 4 islands, sharing every 20 generations
mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_50.txt --gens 500 --sync 20

# seed the GA with the (parallel) greedy tour instead of random
mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_50.txt --gens 500 --sync 20 --greedy-init

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
`--twoopt` (2-opt memetic period), `--greedy-init` (seed with the parallel greedy tour vs.
random), `--seed`, `--auto-balance`, `--out tour.txt` (also writes `tour.txt.history` +
`tour.txt.rankN.history`), `--stats file.csv`, `--live stream.jsonl`.

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

1. On every node, in order:
   - `bash cluster/00_build_openmpi.sh` - source-builds the **pinned** OpenMPI 5.0.9 into
     `/opt/openmpi-5.0.9` (guarantees the *exact same* MPI runtime everywhere; apt versions
     differ across Ubuntu releases and cause PMIx mismatches). Idempotent.
   - `bash cluster/01_install.sh` - build tools, ssh, rsync, numpy + matplotlib. Does **not**
     install OpenMPI (pinned by the step above).
2. Map node names to IPs: copy `cluster/hosts.sample`, replace the IPs with your real ones
   (`hostname -I` on each box), and append the lines to `/etc/hosts` on **every** node.
3. Set up password-less ssh (`cluster/02_ssh_setup.sh`) and sync the code
   (`cluster/03_sync_code.sh`).
4. **Build the solver on every node** - `cd cpp && make`. The launcher can do all nodes at
   once: `mpirun --hostfile cluster/hosts -N 1 bash -c 'cd ~/parallel-tsp/cpp && make'`.
5. Launch from node1:

```bash
bash cluster/run_cluster.sh cluster/hosts 4 ./cpp/tsp_island data/cities_50.txt --gens 500 --sync 20
```

`run_cluster.sh` uses `--map-by seq --bind-to none` so heterogeneous nodes (different core
counts) work, and pins the launch agent so all nodes use the same OpenMPI build. Hostfile
variants: `cluster/hosts` (4 nodes x 12 slots = 48 ranks), `cluster/hosts.seq48` (48 lines for
`-np` > 4), `cluster/hosts.demo4` / `cluster/hosts.no3.demo4` (one rank per machine for the
live demo, with/without node3). See `cluster/DEMO_COMMANDS.md` for copy-paste demo commands.

## Visualization & report figures (Python)

Needs the plotting deps from [Setup step 4](#4-visualization-deps---python-requirementstxt)
(`pip install -r requirements.txt`). All of these read files the C++ solver wrote, so they
run anywhere - including native Windows Python.

### Live view - islands searching in parallel

Run the solver with `--live <base>` and **every** rank streams its own best tour each
generation to `<base>.rankN` (no extra MPI traffic). The viewer draws one route panel per
island + a shared convergence chart. The first stream line is the **greedy (nearest-neighbor)
baseline**, drawn first and kept as a dashed reference the GA then beats.

Same 100-city data, two init modes - left: **GA from scratch** (random init, curve enters from
the top); right: **`--greedy-init`** (GA seeded with the greedy tour, curve starts at the greedy
line and drops below it, finishing lower):

| GA from scratch | GA greedy-seed (`--greedy-init`) |
|-----------------|----------------------------------|
| ![From scratch](results/live100.gif) | ![Greedy seed](results/live100_greedy.gif) |

```bash
# launch the solver locally and animate it (greedy baseline -> 4 islands evolving):
python3 python/live_view.py run data/cities_100.txt --islands 4 --gens 800 --sync 30

# seed the GA with the greedy tour first (curve starts at the greedy line, then drops):
python3 python/live_view.py run data/cities_100.txt --islands 4 --gens 800 --sync 30 --greedy-init

# live view of a REAL cluster run (two terminals):
#   window 1 (launcher): mpirun --hostfile cluster/hosts.demo4 -np 4 ./cpp/tsp_island \
#                        data/cities_100.txt --gens 30000 --sync 200 --live results/stream.jsonl
#   window 2:            python3 python/live_view.py tail results/stream.jsonl data/cities_100.txt --islands 4
```

### Static figures from a finished run

```bash
mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_200.txt --gens 3000 --sync 20 --twoopt 50 --out results/tour.txt
python3 python/visualize.py route     data/cities_200.txt results/tour.txt --out results/route.png
python3 python/visualize.py converge  results/tour.txt.history --out results/converge.png
```

### Report experiments (drive the C++ binary, then plot)

Four experiments, each writing `results/exp_*.csv` + `results/exp_*.png`:

```bash
# 1. runtime vs N (with/without comm) -> pick N for a ~2-3 min run
python3 python/experiments.py size    --procs 48 --sizes 1200 1800 2400 --gens 10500 --sync 20 --hostfile cluster/hosts.seq48

# 2. granularity / load balance (per-process compute+comm+idle bars, warns if idle skew > 25%)
python3 python/experiments.py gran    --procs 48 --size 2400 --gens 10500 --sync 20 --hostfile cluster/hosts.seq48

# 3. speedup at 2*N, procs 1,2,4,...,48 (runtime with/without comm + speedup)
python3 python/experiments.py speedup --procs 1 2 4 8 16 32 48 --size 4800 --gens 4000 --sync 20 --hostfile cluster/hosts.seq48

# 4. solution quality: parallel greedy vs GA-from-scratch (20x gens) vs GA greedy-seed
python3 python/experiments.py quality --procs 48 --size 1000 --gens 1000 --scratch-mult 20 --hostfile cluster/hosts.seq48

bash cluster/run_report_experiments.sh    # the standard size+gran+speedup set
```

Drop `--hostfile` to run on a single machine (`mpirun --oversubscribe`).

## Tests

```bash
cd cpp && make test     # unit tests for the GA operators and the 2-opt / Or-opt local search
```
