#!/usr/bin/env python3
"""restyle_figures.py - Re-render all report figures from the data already in results/
using a publication style copied from the reference papers (arXiv-2601.18231 fixed_fig and
the diffusion-recon paper): bold large axis labels, dashed light-gray grid behind the data,
black-edged markers/bars, the seaborn-deep muted palette (blue/orange/green), a frameless
legend, and clean top/right spines removed.

This script does NOT run the solver or MPI. It only reads the CSV / .history / city files
that are already in results/ and data/, so it is safe to re-run any time:

  python python/restyle_figures.py

Regenerates: exp_speedup.png, exp_gran.png, exp_size.png, exp_tsplib.png, exp_quality.png,
converge.png, route.png  (exp_quality's convergence panel is drawn only if the two history
files exist; otherwise the figure falls back to the final-length bar panel alone).
"""
import csv
import os

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "results")
DATA = os.path.join(ROOT, "data")

# --- palette (seaborn "deep", matching the reference-paper bars/lines) ---
BLUE, ORANGE, GREEN, RED, PURPLE = "#4C72B0", "#DD8452", "#55A868", "#C44E52", "#8172B3"
GRAY = "#4D4D4D"

mpl.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 13,
    "axes.titlesize": 14,
    "axes.titleweight": "bold",
    "axes.labelsize": 15,
    "axes.labelweight": "bold",
    "axes.linewidth": 1.3,
    "axes.edgecolor": "#222222",
    "axes.grid": True,
    "axes.axisbelow": True,
    "grid.linestyle": "--",
    "grid.linewidth": 0.8,
    "grid.color": "#9A9A9A",
    "grid.alpha": 0.45,
    "xtick.labelsize": 12,
    "ytick.labelsize": 12,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "legend.fontsize": 12,
    "legend.frameon": False,
    "lines.linewidth": 2.4,
    "lines.markersize": 8,
    "lines.markeredgecolor": "black",
    "lines.markeredgewidth": 1.1,
    "figure.dpi": 200,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
})


def _clean(ax):
    """Remove top/right spines for the clean publication look used in the references."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def _read_csv(name):
    with open(os.path.join(RESULTS, name)) as f:
        return list(csv.DictReader(f))


def _save(fig, name):
    out = os.path.join(RESULTS, name)
    fig.savefig(out)
    plt.close(fig)
    print(f"-> {out}")


# --------------------------------------------------------------------------- speedup
def fig_speedup():
    rows = _read_csv("exp_speedup.csv")
    P = [float(r["procs"]) for r in rows]
    total = [float(r["total_s"]) for r in rows]
    compute = [float(r["compute_s"]) for r in rows]
    sp = [float(r["speedup"]) for r in rows]
    spnc = [float(r["speedup_nocomm"]) for r in rows]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.8))
    ax1.plot(P, total, "o-", color=BLUE, label="with communication")
    ax1.plot(P, compute, "s--", color=ORANGE, label="without communication")
    ax1.set_xlabel("Processes"); ax1.set_ylabel("Runtime (s)")
    ax1.set_title("Runtime (N=4800)"); ax1.legend(loc="upper right")

    ax2.plot(P, sp, "o-", color=BLUE, label="speedup (with comm)")
    ax2.plot(P, spnc, "s--", color=ORANGE, label="speedup (without comm)")
    ax2.plot(P, P, ":", color="black", lw=2.0, label="ideal")
    ax2.set_xlabel("Processes"); ax2.set_ylabel("Speedup  S(p) = T(1)/T(p)")
    ax2.set_title("Speedup"); ax2.legend(loc="upper left")
    for ax in (ax1, ax2):
        _clean(ax)
    fig.tight_layout()
    _save(fig, "exp_speedup.png")


# --------------------------------------------------------------------------- granularity
def fig_gran():
    rows = _read_csv("exp_gran.csv")
    ranks = [int(r["rank"]) for r in rows]
    comp = np.array([float(r["compute_s"]) for r in rows])
    comm = np.array([float(r["comm_s"]) for r in rows])
    idle = np.array([float(r["idle_s"]) for r in rows])
    makespan = float((comp + comm + idle).max())
    skew = (idle.max() - idle.min()) / makespan * 100 if makespan else 0.0

    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.bar(ranks, comp, color=BLUE, edgecolor="black", linewidth=0.4, label="compute")
    ax.bar(ranks, comm, bottom=comp, color=ORANGE, edgecolor="black", linewidth=0.4,
           label="comm")
    ax.bar(ranks, idle, bottom=comp + comm, color="#BFBFBF", edgecolor="black",
           linewidth=0.4, label="idle (wait)")
    ax.set_xlabel("Process (rank)"); ax.set_ylabel("Time (s)")
    ax.set_title(f"Granularity / load balance  (N=2400, procs={len(ranks)})  "
                 f"idle skew = {skew:.1f}%")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3)
    ax.grid(axis="x", visible=False)
    _clean(ax)
    fig.tight_layout()
    _save(fig, "exp_gran.png")


# --------------------------------------------------------------------------- size sweep
def fig_size():
    rows = _read_csv("exp_size.csv")
    N = [float(r["N"]) for r in rows]
    total = [float(r["total_s"]) for r in rows]
    compute = [float(r["compute_s"]) for r in rows]

    fig, ax = plt.subplots(figsize=(8.5, 5))
    ax.axhspan(120, 180, color=GREEN, alpha=0.15, label="target 2-3 minutes")
    ax.plot(N, total, "o-", color=BLUE, label="with communication (total)")
    ax.plot(N, compute, "s--", color=ORANGE, label="without communication (compute)")
    ax.set_xlabel("Problem size N (cities)"); ax.set_ylabel("Runtime (s)")
    ax.set_title("Runtime vs. N  (procs=48, gens=10500)")
    ax.legend(loc="upper left")
    _clean(ax)
    fig.tight_layout()
    _save(fig, "exp_size.png")


# --------------------------------------------------------------------------- TSPLIB gap
def fig_tsplib():
    rows = _read_csv("exp_tsplib.csv")
    names, scratch_gap, seed_gap = [], {}, {}
    scratch_gens = seed_gens = None
    for r in rows:
        inst = r["instance"]
        if inst not in names:
            names.append(inst)
        if r["mode"] == "scratch":
            scratch_gap[inst] = float(r["gap_pct"]); scratch_gens = r["gens"]
        else:
            seed_gap[inst] = float(r["gap_pct"]); seed_gens = r["gens"]

    x = np.arange(len(names)); width = 0.4
    sg = [scratch_gap.get(n, 0.0) for n in names]
    gg = [seed_gap.get(n, 0.0) for n in names]

    fig, ax = plt.subplots(figsize=(12, 5))
    ax.bar(x - width / 2, sg, width, color=ORANGE, edgecolor="black", linewidth=0.8,
           label=f"GA from scratch ({scratch_gens} gens)")
    ax.bar(x + width / 2, gg, width, color=BLUE, edgecolor="black", linewidth=0.8,
           label=f"GA greedy-seed ({seed_gens} gens)")
    ax.axhline(0, color="black", lw=1.0)
    ax.set_xticks(x); ax.set_xticklabels(names, rotation=30, ha="right")
    ax.set_ylabel("Gap above optimum (%)")
    ax.set_title("TSPLIB benchmark - gap vs optimum (procs=48)")
    ax.legend(loc="upper left")
    ax.grid(axis="x", visible=False)
    _clean(ax)
    fig.tight_layout()
    _save(fig, "exp_tsplib.png")


# --------------------------------------------------------------------------- quality
def fig_quality():
    rows = {r["arm"]: r for r in _read_csv("exp_quality.csv")}
    greedy = float(rows["greedy"]["best_len"])
    scratch = float(rows["from_scratch"]["best_len"])
    seed = float(rows["greedy_seed"]["best_len"])

    sc_h = os.path.join(RESULTS, "exp_quality_scratch.history")
    se_h = os.path.join(RESULTS, "exp_quality_seed.history")
    have_hist = os.path.exists(sc_h) and os.path.exists(se_h)

    if have_hist:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
        sc = np.loadtxt(sc_h); se = np.loadtxt(se_h)
        ax1.plot(range(1, len(sc) + 1), sc, "-", color=ORANGE,
                 label="GA from scratch (20000 gens)")
        ax1.plot(range(1, len(se) + 1), se, "-", color=BLUE,
                 label="GA greedy-seed (1000 gens)")
        ax1.axhline(greedy, ls="--", color=GRAY, lw=2.0,
                    label=f"parallel greedy = {greedy:.0f}")
        ax1.set_xscale("log")
        ax1.set_xlabel("Generation (log scale)"); ax1.set_ylabel("Best tour length")
        ax1.set_title("Convergence quality (N=1000, procs=48)")
        ax1.legend(loc="upper right")
        _clean(ax1)
    else:
        fig, ax2 = plt.subplots(figsize=(7, 5))

    arms = ["greedy", "from\nscratch", "greedy\nseed"]
    vals = [greedy, scratch, seed]
    cols = [GRAY, ORANGE, BLUE]
    bars = ax2.bar(arms, vals, color=cols, edgecolor="black", linewidth=1.0)
    ax2.bar_label(bars, fmt="%.0f", padding=3, fontweight="bold")
    ax2.set_ylabel("Final best tour length")
    ax2.set_title("Final solution quality (lower = better)")
    ax2.grid(axis="x", visible=False)
    ax2.set_ylim(0, max(vals) * 1.12)
    _clean(ax2)
    fig.tight_layout()
    _save(fig, "exp_quality.png")
    if not have_hist:
        print("   (note: convergence panel skipped - no exp_quality_*.history in results/)")


# --------------------------------------------------------------------------- convergence
def fig_converge():
    pairs = [("tour_mig.txt.history", "with migration", BLUE),
             ("tour_nomig.txt.history", "without migration (--sync 0)", ORANGE)]
    fig, ax = plt.subplots(figsize=(8.5, 5))
    for fname, label, color in pairs:
        path = os.path.join(RESULTS, fname)
        if not os.path.exists(path):
            continue
        hist = np.loadtxt(path)
        ax.plot(range(1, len(hist) + 1), hist, "-", color=color, label=label)
    ax.set_xlabel("Generation"); ax.set_ylabel("Best tour length")
    ax.set_title("Convergence: migration vs. no-sharing baseline")
    ax.legend(loc="upper right")
    _clean(ax)
    fig.tight_layout()
    _save(fig, "converge.png")


# --------------------------------------------------------------------------- route
def _read_cities(path):
    pts = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            x, y = line.split()[:2]
            pts.append((float(x), float(y)))
    return np.array(pts, dtype=float)


def fig_route():
    tour = np.loadtxt(os.path.join(RESULTS, "route_tour.txt"), dtype=int)
    coords = _read_cities(os.path.join(DATA, "cities_200.txt"))
    loop = np.append(tour, tour[0])
    seg = coords[loop[1:]] - coords[loop[:-1]]
    length = float(np.sqrt((seg ** 2).sum(axis=1)).sum())

    fig, ax = plt.subplots(figsize=(7.5, 6.5))
    ax.plot(coords[loop, 0], coords[loop, 1], "-", color=BLUE, lw=1.4, zorder=1)
    ax.plot(coords[tour, 0], coords[tour, 1], "o", color=BLUE, ms=5,
            markeredgewidth=0.5, zorder=2)
    ax.plot(coords[tour[0], 0], coords[tour[0], 1], "s", color=RED, ms=12,
            markeredgewidth=1.2, label="start city", zorder=3)
    ax.set_xlabel("x"); ax.set_ylabel("y")
    ax.set_title(f"TSP tour from the solver: length = {length:.2f} ({len(tour)} cities)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=1)
    ax.set_aspect("equal", adjustable="box")
    _clean(ax)
    fig.tight_layout()
    _save(fig, "route.png")


if __name__ == "__main__":
    fig_speedup()
    fig_gran()
    fig_size()
    fig_tsplib()
    fig_quality()
    fig_converge()
    fig_route()
    print("Done. All figures restyled into results/.")
