# Code Review — Parallel TSP (Island-GA over MPI)

**Reviewer:** Claude (acting as judge)
**Date:** 2026-06-18
**Branch:** `bao-dev`
**Verdict:** Project is well-structured and runs, but contained **one critical correctness bug that crippled the genetic algorithm**. Tests passed only because they asserted weak invariants that the bug did not violate.

---

## ✅ RESOLUTION (all bugs fixed — 2026-06-18)

| Bug | Status | Fix |
|---|---|---|
| 🔴 Stale `lengths` breaks selection (`ga_core.py`, `tsp_island.py`) | **FIXED** | Added `lengths = [lengths[i] for i in order]` after the pop reorder in both files. Verified: best tour 7.736 → **5.211** (−32.6%), history now strictly non-increasing. |
| 🟡 C++ OX fill lacks bounds guard (`cpp/ga_core.hpp`) | **FIXED** | `while (j < n && taken[p2[j]]) j++;` |
| 🟡 Migration replaces worst unconditionally (`tsp_island.py`) | **FIXED** | Guard added: migrant accepted only if `incoming_len < lengths[worst]`. |
| Weak tests (couldn't catch the bug) | **FIXED** | Added `test_evolve_history_monotone` + `test_evolve_reaches_optimum_square` (optimal=4.0). Suite now 7/7; the new optimum test fails on the old buggy code. |

Remaining items below (fitness recompute, mutation annealing, or_opt perf, input validation, benchmark regex coupling) are **non-blocking quality nits**, left as-is.

The original analysis is kept below for record.

---

## Severity legend
- 🔴 **Critical** — wrong results / breaks core algorithm
- 🟠 **Major** — significant correctness or robustness problem
- 🟡 **Minor** — quality, robustness, or clarity
- ⚪ **Nit** — style / cosmetic

---

## 🔴 CRITICAL — Stale `lengths` array breaks tournament selection

**Files:**
- `python/ga_core.py:86-96` (`evolve`)
- `python/tsp_island.py:55-65` (inline evolution loop)
- C++ mirror — see C++ section below.

**Problem.** Each generation sorts the population but does **not** reorder the parallel `lengths` array:

```python
order = np.argsort(lengths)
pop = [pop[i] for i in order]   # pop reordered by fitness
new_pop = pop[:elite]           # elitism OK (pop[0] is true best)
while len(new_pop) < pop_size:
    p1 = tournament_select(pop, lengths, tournament_k, rng)  # BUG: lengths NOT reordered
    ...
```

After `pop = [pop[i] for i in order]`, `pop[i]` and `lengths[i]` refer to **different individuals**. `tournament_select` picks indices and compares `lengths[i]`, then returns `pop[best]` — so it selects parents using the fitness of *unrelated* individuals. Selection pressure is effectively destroyed; the GA improves only via elitism + lucky mutation.

**Proof (verified by running the code):**
```
lengths aligned with pop after reorder?  False
pop[0] true len=9.104   lengths[0]=12.063     # index 0 mismatched
```
End-to-end impact (30 cities, pop 200, 400 gens, same seed):
```
buggy best = 7.736
fixed best = 5.211      ->  32.6% worse tours due to the bug
```

**Why tests miss it.** `test_evolve_improves` only asserts `best < random_start` and `history[-1] <= history[0]` — both still hold with crippled selection (elitism alone clears that bar).

**Fix.** Reorder `lengths` together with `pop`:
```python
order = np.argsort(lengths)
pop = [pop[i] for i in order]
lengths = [lengths[i] for i in order]   # <-- add this line
```
Apply the identical fix in `python/tsp_island.py` and the C++ evolution loop. (Alternatively, have `tournament_select` recompute or accept aligned fitness; the one-line reorder is simplest.)

---

## 🟡 MINOR — `evolve` recomputes all fitnesses every generation

`python/ga_core.py:101` recomputes `lengths` for the whole population each generation via `tour_length` per individual. Elites are unchanged, so their lengths are known. Minor inefficiency; not a correctness issue. Caching elite fitness (and computing only children) would roughly halve fitness evaluations.

## 🟡 MINOR — Mutation strength fixed and high

`mutate` (`ga_core.py:64-71`) applies swap + segment-reversal each at `rate=0.3` (0.3 in `tsp_island.py:62`). No annealing/decay. With selection fixed, high constant mutation slows late convergence. Consider decaying mutation rate over generations. Quality, not correctness.

## 🟡 MINOR — `or_opt` rebuilds tour with Python lists + `in` checks

`local_search.py:59-65`: `rest = [c for c in t if c not in seg]` is O(n·seg_len) per position and allocates per move. Fine for n≤50 but won't scale. Vectorizing or using index bookkeeping would help if city counts grow.

## 🟡 MINOR — Migration replaces worst unconditionally

`tsp_island.py:79-81`: incoming migrant always overwrites the local worst, even if the migrant is worse than the local worst. Harmless given ring topology sends *best* individuals, but a guard (`if incoming_len < lengths[worst]`) is cleaner and avoids importing a stale/duplicate tour.

## ⚪ NIT — `read_cities` has no validation

`ga_core.py:11-21`: assumes every non-comment line has ≥2 float tokens; a malformed line raises a bare `ValueError`. Acceptable for a course project; a clearer error message would help graders.

## ⚪ NIT — Benchmark parses timing from localized stdout

`benchmark.py:20` regexes `"Thoi gian : ..."` out of program stdout. Tightly couples benchmark to the exact print string in `tsp_island.py:107`. If that line changes, benchmark silently fails (`m` is `None` → `AttributeError`). A `--machine-readable` timing output would be more robust.

---

## ✅ What is correct (verified)

- **OX crossover** (`order_crossover`) produces valid permutations — verified over 100 random trials (`test_ox_valid_permutation` passes; logic confirmed by reading).
- **Mutation** preserves permutation validity (swap + reversal). ✔
- **`distance_matrix`** symmetric, zero diagonal. ✔
- **`tour_length`** correct closed-tour cost (uses `np.roll`). ✔
- **2-opt / Or-opt** never worsen a tour and fix crossings — `test_local_search.py` 5/5 pass. ✔
- **MPI ring migration** uses `comm.sendrecv(dest=right, source=left)` — correct deadlock-free pattern. ✔
- **Global reduction** uses `allreduce(..., op=MPI.MINLOC)` then point-to-point `Send`/`Recv` of the winning tour with explicit `int64` contiguous buffers — correct. ✔
- **Elitism** keeps the true best each generation (sort happens while `lengths` is still aligned at `argsort` time), so the best-tour result is valid even with the selection bug — the algorithm just converges far worse than it should.

**Test results (this machine, Python 3.14, numpy installed):**
```
test_ga_core.py        5/5 PASS
test_local_search.py   5/5 PASS
```

---

## C++ review

**Headline:** The C++ port is **correct** and, importantly, **does NOT reproduce the critical Python selection bug** — so the two implementations are *not* algorithmically equivalent. C++ converges properly; Python does not.

### 🟢 C++ is correct where Python is broken — `cpp/ga_core.hpp` (`evolve_one_gen`)
C++ computes a sorted index array `order` but **never reorders `pop`**. It uses `order` only to copy elites into the new population, then calls `tournament_select(pop, len, …)` on the **original, still-aligned** `pop`/`len`. After building the new generation it `swap`s and recomputes all fitnesses. Selection pressure is intact.

This means: **if a grader compares Python vs C++ output quality, they will differ** — C++ finds clearly shorter tours for the same parameters. Fixing the Python bug (above) brings them in line.

### 🟡 MINOR — OX fill loop lacks a bounds guard — `cpp/ga_core.hpp` (`order_crossover`)
```cpp
while (taken[p2[j]]) j++;     // no `j < n` guard
child[i] = p2[j++];
```
Safe **only** while `p1`/`p2` are valid permutations (always true in this GA), but it is undefined behavior if ever fed a malformed parent. Python's version is structurally safe (`fill = [c for c in p2 if c not in taken]`). Add the guard for defensiveness:
```cpp
while (j < n && taken[p2[j]]) j++;
```

### ✅ Verified correct in C++
- **OX crossover** — produces valid permutations; logic matches Python. ✔
- **`tournament_select`** — picks exactly `k` candidates (1 seed + k−1 loop), returns the best. ✔
- **`mutate`** — swap + segment reverse; `std::reverse(begin+i+1, begin+j+1)` bounds correct. ✔
- **`two_opt_once`** — correctly skips the closing edge (`i==0 && j==n-1`), reverses `[i+1, j]`. ✔
- **`or_opt_once`** — segment relocation rebuilds a valid n-city tour (insert `cur` right after city `a`); order correct for both `i<j` and `i>j`. ✔
- **MPI ring migration** — `MPI_Sendrecv(... dest=right ... source=left ...)`, deadlock-free. ✔
- **Global best** — `MPI_Allreduce(MPI_DOUBLE_INT, MPI_MINLOC)` with a `{double val; int rank;}` struct (correct layout for `MPI_DOUBLE_INT`), then `MPI_Send`/`MPI_Recv` of the winning tour as `MPI_INT` from contiguous `std::vector<int>`. ✔
- **Fitness/population alignment** — `len` recomputed immediately after every population mutation (`evolve_one_gen`, memetic polish, migration). ✔

---

## Bottom line (judge's verdict)

| Area | Python | C++ |
|---|---|---|
| GA operators (OX, mutation, 2-opt, Or-opt) | ✅ correct | ✅ correct |
| **Selection / pop-fitness alignment** | 🔴 **broken** (~33% worse tours) | ✅ correct |
| MPI (ring migration, MINLOC reduce, buffers) | ✅ correct | ✅ correct |
| Tests | pass, but too weak to catch the bug | pass |
| Defensive bounds checking | ✅ safe | 🟡 OX lacks a `j<n` guard (harmless in practice) |

**Single must-fix:** the stale-`lengths` reorder bug in `python/ga_core.py` and `python/tsp_island.py`. One line each. Everything else is minor or cosmetic. The C++ side is solid.

For a course submission: the architecture, MPI usage, documentation, and test coverage are good. But the Python GA — the headline deliverable — is silently underperforming, and the unit tests are too lax to reveal it. Fix the one line and strengthen `test_evolve_improves` to assert convergence to near-optimal on the 4-city square (optimal = 4.0).

