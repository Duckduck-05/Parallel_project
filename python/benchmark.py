#!/usr/bin/env python3
"""benchmark.py - Measure speedup & efficiency of the Island-GA vs. the number of processes.

Keeps the TOTAL work fixed (total population = --total, split evenly across islands, so
pop/island = total/np) -> a proper strong-scaling measurement: speedup S(p) = T(1)/T(p).

This is a PLOTTING / reporting tool only. The solver itself is the C++ binary
cpp/tsp_island; this script just launches it with mpirun and reads its "Time" line.

Run on one machine:  python3 benchmark.py ../data/cities_50.txt --procs 1 2 3 4 --total 240 --gens 400
Run on a cluster:    python3 benchmark.py ... --hostfile ../cluster/hosts
Output: results/bench.csv + results/speedup.png
"""
import argparse
import os
import re
import subprocess
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TIME_RE = re.compile(r"^Time\s*:\s*([0-9.]+)", re.MULTILINE)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def default_binary():
    for cand in ("tsp_island", "tsp_island.exe"):
        p = os.path.join(ROOT, "cpp", cand)
        if os.path.exists(p):
            return p
    return os.path.join(ROOT, "cpp", "tsp_island")


def run_once(binary, np_count, hostfile, total, gens, cities, sync):
    pop = max(1, total // np_count)        # split the total population evenly across islands
    cmd = ["mpirun"]
    if hostfile:
        cmd += ["--hostfile", hostfile]
    else:
        cmd += ["--oversubscribe"]
    cmd += ["-np", str(np_count), binary,
            cities, "--gens", str(gens), "--pop", str(pop), "--sync", str(sync)]
    out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
    m = TIME_RE.search(out)
    return float(m.group(1))


def amdahl(p, s):
    """Amdahl's law: theoretical speedup with a serial fraction s."""
    return 1.0 / (s + (1 - s) / p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cities")
    ap.add_argument("--procs", type=int, nargs="+", default=[1, 2, 3, 4])
    ap.add_argument("--total", type=int, default=240, help="total population (split across islands)")
    ap.add_argument("--gens", type=int, default=400)
    ap.add_argument("--sync", type=int, default=20, help="global-best broadcast interval")
    ap.add_argument("--reps", type=int, default=3, help="repetitions, keep the minimum")
    ap.add_argument("--hostfile", default=None)
    ap.add_argument("--binary", default=None, help="path to cpp/tsp_island")
    ap.add_argument("--csv", default=os.path.join(ROOT, "results", "bench.csv"))
    ap.add_argument("--out", default=os.path.join(ROOT, "results", "speedup.png"))
    args = ap.parse_args()

    binary = args.binary or default_binary()

    rows = []
    for p in args.procs:
        times = [run_once(binary, p, args.hostfile, args.total, args.gens, args.cities, args.sync)
                 for _ in range(args.reps)]
        t = min(times)                     # keep the minimum to reduce noise
        rows.append((p, t))
        print(f"np={p:2d}  time={t:.3f}s")

    procs = [r[0] for r in rows]
    t1 = max(rows[0][1], 1e-9)             # time with 1 process is the baseline (avoid /0)
    speedup = [t1 / max(r[1], 1e-9) for r in rows]
    eff = [s / p for s, p in zip(speedup, procs)]

    os.makedirs(os.path.dirname(args.csv), exist_ok=True)
    with open(args.csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["procs", "time_s", "speedup", "efficiency"])
        for (p, t), s, e in zip(rows, speedup, eff):
            w.writerow([p, f"{t:.4f}", f"{s:.4f}", f"{e:.4f}"])
    print(f"Saved {args.csv}")

    # fit the serial fraction s to Amdahl's law (simple least squares over a grid)
    grid = np.linspace(0.001, 0.5, 500)
    err = [sum((amdahl(p, s) - sp) ** 2 for p, sp in zip(procs, speedup)) for s in grid]
    s_fit = grid[int(np.argmin(err))]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    ax1.plot(procs, speedup, "o-", label="measured")
    ax1.plot(procs, procs, "k--", label="ideal (linear)")
    ax1.plot(procs, [amdahl(p, s_fit) for p in procs], "r:",
             label=f"Amdahl (s={s_fit:.3f})")
    ax1.set_xlabel("Processes"); ax1.set_ylabel("Speedup")
    ax1.set_title("Speedup"); ax1.legend(); ax1.grid(alpha=0.3)

    ax2.plot(procs, eff, "s-", color="green")
    ax2.axhline(1.0, ls="--", color="k")
    ax2.set_xlabel("Processes"); ax2.set_ylabel("Efficiency")
    ax2.set_title("Efficiency = Speedup / p"); ax2.set_ylim(0, 1.2); ax2.grid(alpha=0.3)

    plt.tight_layout(); plt.savefig(args.out, dpi=130)
    print(f"Saved {args.out}")


if __name__ == "__main__":
    main()
