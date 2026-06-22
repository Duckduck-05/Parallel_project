# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

University parallel-programming project: solve the TSP with an **island-model Genetic
Algorithm**, parallelized with **MPI** across a real multi-node cluster (up to 4 nodes).

On this branch the entire solver is **C++** (the algorithm + all MPI). **Python exists only
for visualization, the live demo, and plotting report figures** - it contains no algorithm.
Everything on this branch is in **English** (comments, output, docs); keep it that way.

## Commands

Most work runs under **WSL/Linux**. On the Windows host there is no usable MPI toolchain.
A source build of OpenMPI 5.0.9 lives at `/opt/openmpi-5.0.9` in WSL; the system `mpicxx`
wrapper is broken (missing dev headers), so build with explicit flags or point `CXX` at the
/opt wrapper. Note: WSL `/tmp` is wiped between separate `wsl` invocations - build and run
in a single shell command.

```bash
# Build + unit tests (run inside one WSL invocation)
cd cpp && make CXX=/opt/openmpi-5.0.9/bin/mpicxx          # or plain `make` on the cluster
make test                                                 # GA + local-search unit tests, no MPI

# Build manually if the mpicxx wrapper misbehaves:
g++ -O2 -std=c++17 -I/opt/openmpi-5.0.9/include cpp/tsp_island.cpp \
    -L/opt/openmpi-5.0.9/lib -Wl,-rpath,/opt/openmpi-5.0.9/lib -lmpi -o cpp/tsp_island

# Run on one machine
mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_50.txt --gens 500 --sync 20
bash cluster/run_local.sh 4 data/cities_50.txt --gens 500 --sync 20

# Run on the cluster (from node1)
bash cluster/run_cluster.sh cluster/hosts 4 ./cpp/tsp_island data/cities_50.txt --gens 500 --sync 20

# Report figures (Python drives the C++ binary, then plots)
python3 python/experiments.py speedup --procs 1 2 4 8 --size 200
bash cluster/run_report_experiments.sh
```

Flags: `--sync N` (migration interval; `0` = no-sharing baseline), `--migrants K` (individuals
recombined with the global best per sync; default 3), `--patience N` (stop after N stalled
generations; `0` = off), `--pop`, `--gens`, `--twoopt`, `--seed`, `--auto-balance`, `--out`,
`--stats`, `--live`. `--migrate` is kept as an alias for `--sync`.

## Architecture

**The C++ source is the whole solver.** `cpp/ga_core.hpp` (GA operators: tournament k=5, OX
crossover, mutation = swap + segment reverse rate 0.3, elitism=1), `cpp/local_search.hpp`
(2-opt then Or-opt seg_len=2 = the memetic polish), `cpp/tsp_island.cpp` (MPI island solver,
the main deliverable), `cpp/tsp_sequential.cpp` (single-process baseline for T(1)).

**Parallelism = islands + periodic partial global-best migration + convergence stop.** Each
rank is an independent island (seed `base + rank*1000`). Every `--sync` generations:
`Allreduce(MINLOC)` finds the global-best (value, owner); the owner `Bcast`s that tour; each
other island then splices only a random contiguous SEGMENT of it into `--migrants` individuals
via OX crossover (segment from the best + rest from a random local mate), replacing its worst
slots. This spreads good sub-routes while preserving diversity (no whole-tour cloning). Because
the global-best *value* is identical on every rank, all ranks **break together** once it stalls
for `--patience` generations (no extra comm). `--sync 0` is the no-sharing baseline. Final
result gathered via `Allreduce(MINLOC)` + a point-to-point send to rank 0. (History: this
replaced first a ring-migration scheme, then a full global-best broadcast.)

**Instrumentation is built into `tsp_island.cpp`.** It splits `comm_time` (time inside MPI
calls) from `compute_time`, computes `makespan = max(elapsed)`, and emits: a per-rank stdout
table, `--stats` CSV (columns: `rank,n_cities,procs,gens,pop,compute_s,comm_s,total_s,makespan_s,best_len`),
`--out` tour + `.history`, and `--live` JSONL. The Python tools parse these - if you change the
stdout "Time" line or the CSV columns, update `python/benchmark.py` (regex `^Time\s*:`) and
`python/experiments.py` (CSV reader) to match.

**Python tooling (plotting/demo only).** `experiments.py` and `benchmark.py` shell out to
`mpirun ./cpp/tsp_island` (locally, or via `cluster/run_cluster.sh` on the cluster) and plot.
`visualize.py` draws the route + convergence from `--out`/`.history` files. `live_view.py` has
two modes: `run` launches the C++ solver with a temp `--live` stream and animates it; `tail`
follows a real cluster run's stream. All Python files carry their own tiny city-file reader so
they depend on no algorithm module.

## Cluster gotchas (see `cluster/run_cluster.sh` header)

- **All nodes must run the same OpenMPI build** (5.0.9 from source in `/opt/openmpi-5.0.9`),
  else PMIx version mismatch. `run_cluster.sh` pins PATH and passes `prte_launch_agent` as an
  absolute path (remote non-interactive SSH PATH won't find it otherwise).
- **Heterogeneous nodes** need `--map-by seq --bind-to none` - the default topology-aware
  mapper drops nodes whose topology differs from the launcher's.
- Node names resolve via `/etc/hosts`; `cluster/hosts.sample` is the editable IP->name map for
  LAN use (change IPs there, nothing else). `cluster/hosts` is the 4-node hostfile.
- Cluster topology specifics are in the user's memory (`cluster-setup.md`).
