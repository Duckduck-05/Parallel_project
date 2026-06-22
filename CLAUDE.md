# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

University parallel-programming project: solve TSP with an **island-model Genetic Algorithm**, parallelized with **MPI** across a real multi-node cluster. Two parallel implementations of the **same algorithm**: Python (`mpi4py`) and C++ (OpenMPI). Grading weighs topic interest, how the problem is parallelized, a live demo, the report, and whether each member understands their code. Comments and docs are in Vietnamese — match that when editing.

## Commands

Most work runs under **WSL/Linux** (MPI + matplotlib live there). On this Windows host there is no compiler/MPI — shell into WSL: paths mount at `/mnt/c/...`.

```bash
# Python tests (no MPI needed)
cd python && python3 -m pytest test_ga_core.py test_local_search.py -v
python3 test_ga_core.py            # also runnable directly (no pytest)

# C++ build + tests (needs OpenMPI mpicxx, C++17)
cd cpp && mpicxx -O2 -std=c++17 -o tsp_island tsp_island.cpp
g++ -O2 -o test_ls test_local_search.cpp && ./test_ls   # local_search has no MPI dep

# Run on one machine (oversubscribe cores)
bash cluster/run_local.sh 4 data/cities_50.txt --gens 500 --migrate 20

# Run on the cluster (from launcher node; see flags note below)
bash cluster/run_cluster.sh cluster/hosts.cur 4 python3 python/tsp_island.py data/cities_50.txt --gens 500 --migrate 20

# Generate report figures (CSV + PNG into results/)
cd python && python3 experiments.py speedup --procs 1 2 4 8 --size 200
python3 experiments.py size --procs 4 --sizes 50 100 200 400
python3 experiments.py gran --procs 4 --size 200
```

`--migrate 0` disables migration (the no-share baseline, "Task 6"); `--migrate N` migrates every N generations ("Task 7"). `--twoopt N` turns on memetic 2-opt/Or-opt polishing. `--auto-balance` (Python only) micro-benchmarks each node and sizes its population inversely to runtime (for heterogeneous clusters). `--live FILE` makes rank 0 stream JSONL for `live_view.py`.

## Architecture

**Shared GA core, two languages.** `python/ga_core.py` ≙ `cpp/ga_core.hpp`, `python/local_search.py` ≙ `cpp/local_search.hpp`, `python/tsp_island.py` ≙ `cpp/tsp_island.cpp`. The algorithm is intentionally kept identical: tournament(k=5) selection, order crossover (OX), mutation (swap + segment reverse, rate 0.3), elitism=1; memetic polish = 2-opt then Or-opt(seg_len=2). **When you change one language's algorithm, mirror it in the other.** Note RNGs differ (numpy PCG64 vs `mt19937`), so identical seeds do NOT produce identical tours — this is expected.

**Parallelism = island model.** Each MPI rank is an independent island (own seed `base + rank*1000`). Periodically each island sends its best tour to its `right` neighbor and receives from `left` in a ring, via a single `Sendrecv` (send+recv together → no deadlock). The immigrant replaces the island's worst individual **only if it is better**. Final gather uses `Allreduce(MINLOC)` to find the rank holding the global-best tour, which then `Send`s it to rank 0. This "share results during searching" (migration) vs not is the project's central experiment.

**Timing/instrumentation lives only in the Python version.** `tsp_island.py` splits `comm_time` (time inside MPI calls) from `compute_time = elapsed - comm_time`, computes `makespan = max(elapsed)` across ranks, and emits per-rank stats (`--stats` CSV, `--out`+`.history`). The C++ version is the lean speed baseline and prints only the result — do not assume C++ has these flags.

**`experiments.py` orchestrates report figures** by shelling out to `mpirun ... tsp_island.py --stats`, parsing the CSVs, and plotting speedup/efficiency, size scaling, and per-rank granularity. `benchmark.py` is the simpler speedup-table generator. Results land in `results/`.

**`live_view.py`** has two modes: `run` (runs multi-island GA in-process, no MPI, for laptop demos) and `tail` (follows a real cluster run's `--live` JSONL). The `--live` stream is rank-0 IO only — it adds no MPI traffic, so it does not distort benchmarks.

## Cluster gotchas (hard-won — see `cluster/run_cluster.sh` header)

- **All nodes must run the exact same OpenMPI build** (5.0.9 from source in `/opt/openmpi-5.0.9`), else PMIx version-mismatch. `run_cluster.sh` pins PATH and passes `prte_launch_agent` as an absolute path because the remote non-interactive SSH PATH won't find it.
- **Heterogeneous nodes** (different core counts) require `--map-by seq --bind-to none` — the default topology-aware mapper drops nodes whose topology differs from the launcher.
- Hostfile variants: `cluster/hosts*` — `hosts.cur` is the active one; `hosts.tailscale` for the remote-over-VPN setup. Each rank `cd`s into its own `$HOME/parallel-tsp` because homes differ per node.
- Cluster topology, Tailscale, and `/etc/hosts` specifics are in the user's memory (`cluster-setup.md`) and `cluster/TASK*` / `docs/TASK_remote_tailscale_guide.md`.
