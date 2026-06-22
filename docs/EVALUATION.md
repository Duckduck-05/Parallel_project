# Project Evaluation — Parallel TSP (Island-GA + MPI)

**Role:** independent judge. **Date:** 2026-06-21.
**Criteria sources:** `docs/scoring_criterion.md` (grading basis) + `docs/report_requirements.md`
(required report structure/experiments).

---

## Scores
| Aspect | Score | Note |
|---|---|---|
| **Report (vs report_requirements.md)** | **6.5 / 10** | well-written but missing several *required* experiments/labels — yet the data exists in `results/` |
| **Project overall (vs scoring_criterion.md)** | **8 / 10** | strong topic, correct MPI, working demo, honest analysis |
| Lines of code (≥1000 for 4) | ✅ PASS | ~1555 LOC (Python 959, C++ 435, Shell 161) |

> Highest-leverage fix: fold the already-generated `results/exp_*` data + taxonomy labels
> into `report/report.md`. That alone moves the report ~6.5 → ~9.

---

## scoring_criterion.md — criterion-by-criterion
- **LOC ≥250/person, ≥1000/group:** ✅ ~1555 total. ⚠️ Member 4 light on code (~110 lines: data gen + visualize) — relies on report/slides; add a code extension if per-person is enforced.
- **Interest of topic:** ★★★★★ TSP (NP-hard) via Island-model GA — genuine parallel metaheuristic.
- **How parallelized:** ★★★★★ island (data+exploratory) decomposition, ring migration via `MPI_Sendrecv` (deadlock-free), `MPI_Allreduce(MINLOC)` gather. Correct, non-trivial.
- **Demo runs:** ✅ VERIFIED — distributed node1(WSL)+node2(native) over Tailscale (tour 567.56); single-node on node1 (4 islands) and node3/mac (`run_local.sh`); both Python and C++.
- **Report quality:** ★★★★½ comprehensive + intellectually honest (reports migration *not* helping after a selection-bug fix, with correct exploration/exploitation analysis; documents a real ~33% bug fix). But misses rubric-required experiments (below).
- **Member understanding:** ★★★★ code well-commented, unit tests present; report depth supports it. (Final check is the oral defense.)

---

## report_requirements.md — flaws ranked by importance

### 🔴 CRITICAL — required experiments missing (cost the most points)

1. **"Find N for 2–3 min" experiment — MISSING.** Rubric: #procs=#cores, plot runtime vs
   input size (with & without comm), choose N for 2–3 min. Report uses fixed 50 cities.
   → Data exists: `results/exp_size.{csv,png}`. Add section; extend N to ~5000 for 2–3 min
   (current max N=800 ≈ 30 s).

2. **Granularity / load-balance experiment — MISSING.** Rubric: per-process stacked bar
   (compute vs comm, different colors), check balance, rebalance if idle differs >25%.
   Report has none. → Data exists: `results/exp_gran.{csv,png}` (idle-skew computed). The
   2-node run even shows a real imbalance (node2 idle-waits on slower node1) — ideal here.

3. **Speedup doesn't meet spec.** Rubric: size 2N, procs 1,2,4,8,…,2X, runtime WITH and
   WITHOUT comm time + speedup. Report: procs 1–4, single value, no comm/no-comm split,
   not 2N. → Data exists: `results/exp_speedup.{csv,png}` has the comm/no-comm split +
   1,2,4,8. Replace the report's table.

### 🟠 IMPORTANT — required framing/labels absent
4. **Decomposition taxonomy not stated** (rubric: data/exploratory/recursive/speculative/
   hybrid? task vs data?). Answer = data + exploratory hybrid (see `REPORT_SUMMARY.md`).
5. **Mapping technique not discussed** (rubric: 1D/2D, processor assignment). It's 1D ring,
   one island per process — state it.
6. **No full *parallel* pseudocode** (report §2.3 is only the sequential GA loop).
7. **Blocking vs non-blocking not classified** (`Sendrecv` = blocking but deadlock-free).
8. **Correctness verification not an explicit section** (valid permutation / matches
   sequential at p=1).

### 🟡 MODERATE
9. **Headline numbers are single-machine oversubscribe** (report admits). Real 2-machine
   distributed data now exists: `results/exp_*_n12.*` (speedup 1.99 @ 2 machines, real WAN
   comm 2.34 s). Use it.
10. **Architecture §4 ≠ reality.** Report describes VirtualBox + Bridged WiFi; actual build
    is WSL/native + Tailscale. Update it. The macOS-utun and hwloc-mismatch issues are
    excellent unused "difficulties" material (see below).
11. **Length risk:** rubric wants 10–20 pages; current report renders ~8–10. Adding the 3
    missing experiments fixes this naturally.

### ⚪ LOW
12. Group name still placeholder (`_(điền tên nhóm)_`).
13. Per-person LOC: Member 4 borderline (see above).

---

## Real-cluster findings worth adding to "Difficulties" (§6)
These came out of actually building the cluster and are strong report material:
- **OpenMPI version/launch-layer must match**: PMIx/PRRTE/hwloc compatibility matters, not
  just "OpenMPI 5.0.x". node1 (apt 5.0.10) had to be rebuilt to 5.0.9 from source.
- **hwloc**: node2 first built with *bundled* hwloc → topology unpack failed → dropped from
  mapping. Fix: rebuild `--with-hwloc=/usr` (system hwloc).
- **Heterogeneous CPUs**: different core counts (16 vs 12) made the topology-aware mapper
  drop nodes ("lacks topology"); fixed with `--map-by seq --bind-to none`.
- **macOS + Tailscale dead-end**: the mac's tailnet interface is `utun*` (point-to-point),
  which OpenMPI does **not** enumerate (sees only `en0`); the LAN path is a different
  physical network. So the mac can run the project **locally** but **cannot join** the MPI
  cluster. Legit limitation to document.
- **Heterogeneous load imbalance**: even-population split underuses the faster machine
  (fast node idle-waits at migration) → weight islands by node speed.

---

## Recommendation (priority order)
1. Rewrite `report/report.md` to satisfy the rubric: add §(N-sweep), §(granularity stacked
   bars + 25% check), §(speedup with/without comm at 2N, procs to 2X) using the existing
   `results/exp_*` files; add the decomposition/mapping/blocking labels + full parallel
   pseudocode + a correctness paragraph.
2. Swap single-machine numbers for the real distributed `exp_*_n12` results.
3. Fix architecture §4 to WSL+Tailscale; move the findings above into §6.
4. Fill group name; (optionally) add code for Member 4.

Doing #1–#3 lifts the report from ~6.5 to ~9 with no new experiments needed — the data is
already collected.
