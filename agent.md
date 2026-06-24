# agent.md — Project status summary

## What this is

University parallel-programming project: Island-model Genetic Algorithm solving TSP,
parallelized with MPI (OpenMPI 5.0.9) across a real 4-node LAN cluster (node1-node4,
node2 = launcher). The whole solver is C++ (`cpp/`); Python (`python/`) is visualization/
tooling only (no algorithm code). See `CLAUDE.md` for architecture/build details.

## Cluster

- 4 physical machines: node1 (Ryzen 7 4800HS, 8c/16t), node2 (i5-11400H, 6c/12t, launcher),
  node3 (i5-12500H, 8c/16t), node4 (i5-12500H, 8c/16t).
- All nodes pinned to the same OpenMPI 5.0.9 build at `/opt/openmpi-5.0.9` (PMIx/PRRTE
  version match required).
- `--map-by seq --bind-to none` required for heterogeneous CPUs, but it **ignores
  hostfile `slots=`** — needs literal N lines per N ranks. Expanded hostfiles live in
  `cluster/hosts.seq48`, `cluster/hosts.no3`, `cluster/hosts.no3.12`, `cluster/hosts.no3.demo4`.
- Rank cap is 12/node (node2's full thread count) — empirically confirmed faster than
  oversubscribing to 16/node (hyperthread contention).
- **node3 is currently flaky** (Wi-Fi, IP changes) — last check showed "No route to host."
  Demo workflows have a 3-node fallback (node1+node2+node4) via `cluster/hosts.no3.demo4`.
- Uncommitted local code changes do NOT reach remote nodes via `git pull` — must `rsync`
  the changed file(s) + rebuild manually on node1/node3/node4 when testing pre-commit code.

## Completed this session

1. Full real 4-node MPI run verified, migration algorithm (Allreduce(MINLOC)+Bcast+OX-splice)
   validated as actually exchanging info across ranks.
2. Root-caused CPU under-utilization → `--map-by seq` ignoring `slots=`.
3. Ran the full report experiment suite (size/gran/speedup + benchmark.py) on the real
   cluster; fixed a stats-file-location bug (rank 0 writes on its own physical host, not
   the launcher) in `python/experiments.py` via an `scp` step.
4. node3-removal A/B test, with hyperthread-oversubscription confound explicitly separated
   out (first attempt was slower due to 16-rank oversubscription; re-tested at the proper
   12/node cap, which WAS ~8% faster without node3).
5. Measured real network latency/bandwidth — confirmed the bottleneck is sync-wait from
   hardware heterogeneity, not raw bandwidth for the migration payload size.
6. Found and respected an O(N²)-memory hard RAM ceiling (`distance_matrix()` in
   `ga_core.hpp`, node3's 3.7GB) when picking N* (target 2-3 min runtime) and 2×N*.
7. Correctness validation: `python/validate_tour.py` (permutation check, length recompute,
   brute-force optimum at N=8) — all passing.
8. Produced `results/cluster_report.md` covering all of the above, through several rounds
   of user fact-checking (fixed inconsistent N* numbers, a speedup-table/CSV mismatch,
   softened two overclaimed conclusions to acknowledge single-trial evidence).
9. Fully rewrote `report/report.docx` (was describing a defunct ring/Sendrecv + Tailscale +
   macOS-node + Python-solver architecture) to match the current C++/MPI island-model
   reality, via direct python-docx edits. Fixed a missing procs=16 speedup-table row and
   stale `docProps/app.xml` page-count metadata (verified real page count = 14 via
   LibreOffice headless → PDF export).
10. Changed the `--live` streaming protocol in `cpp/tsp_island.cpp`: every rank now writes
    its own file (`<path>.rank<N>`) instead of only rank 0, so the viewer can show every
    island independently.
11. Rewrote `python/live_view.py`: new `MultiCanvas`/`MultiTailer` classes render a grid of
    per-island route panels + one shared convergence chart (per-island faint lines + bold
    global-best line + sync markers), replacing the old single-route view.
12. Wrote `cluster/DEMO_COMMANDS.md` — single reference of every command needed to build/
    run/demo the project on 1 machine or the real 3-4 node cluster, including the new live
    multi-island grid demo and a tested 3-node (node1+node2+node4) real-cluster workflow
    with a background rsync loop (no shared filesystem between nodes).

## Open / pending

- **report.docx contribution table is a placeholder** — needs the real team name and real
  per-member role breakdown from the user. Cannot be fabricated. Still unanswered.
- node3 connectivity itself was not fixed — demo workflows just route around it.
- A GIF export job (`results/demo_multi_islands.gif`) started in a prior session via
  `nohup` was lost when the session/WSL `/tmp` was wiped before it finished — not a
  blocker, just needs re-running if a GIF artifact is wanted (see `cluster/DEMO_COMMANDS.md`
  §4.5 for the command).
