#!/usr/bin/env python3
"""experiments.py - Generate the data + figures for the REPORT.

This is a PLOTTING / orchestration tool only. The solver is the C++ binary
cpp/tsp_island; this script launches it (locally with mpirun, or on the cluster through
cluster/run_cluster.sh), reads the per-process --stats CSV it writes, and plots.

Four experiments:
  size    : runtime vs. problem size N (number of cities), WITH and WITHOUT communication
            time -> pick N so the program runs ~2-3 minutes.
  gran    : one run with N cities on P processes; stacked compute+comm+idle bars per
            process (load-balance / granularity check; warns if idle skew > 25%).
  speedup : fixed total work, varying processes 1,2,4,8,...; runtime (with/without comm)
            + speedup S(p)=T(1)/T(p) + efficiency.
  quality : solution quality - parallel greedy vs GA-from-scratch (20x gens) vs GA greedy-seed;
            convergence curves + final-length bar + % improvement over greedy.

Run on one machine (oversubscribe):
  python3 experiments.py size    --procs 4 --sizes 50 100 200 400
  python3 experiments.py speedup --procs 1 2 4 8 --size 200
  python3 experiments.py gran    --procs 4 --size 200

Run on a cluster (uses the standard launcher):
  python3 experiments.py speedup --procs 1 2 4 8 --size 200 --hostfile ../cluster/hosts.cur

Output: results/exp_*.csv + results/exp_*.png
"""
import argparse, csv, os, subprocess, tempfile
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "results")
DATA = os.path.join(ROOT, "data")
BIN = os.path.join("cpp", "tsp_island")        # relative to ROOT / ~/parallel-tsp


def make_cities(n, seed=1):
    """Create a file with n city coordinates (random, stable per seed). Returns a
    RELATIVE path (data/cities_n.txt) so every node can read it inside its own
    ~/parallel-tsp (home dirs differ across machines)."""
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, f"cities_{n}.txt")
    if not os.path.exists(path):
        rng = np.random.default_rng(seed)
        pts = rng.uniform(0, 100, size=(n, 2))
        np.savetxt(path, pts, fmt="%.4f", header="x y (auto-generated)")
    return os.path.join("data", f"cities_{n}.txt")


def _hosts(hostfile):
    """Node names in a hostfile (first token of each non-blank, non-# line)."""
    out = []
    for line in open(hostfile):
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line.split()[0])
    return out


def sync_data(cities, hostfile):
    """Copy the city file to ~/parallel-tsp on every remote node (except node1).
    Each node must have the same file at the same relative path."""
    src = os.path.join(ROOT, cities)
    for h in _hosts(hostfile):
        if h == "node1":
            continue
        subprocess.run(["rsync", "-az", src, f"{h}:parallel-tsp/{cities}"],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run(procs, cities, gens, pop, sync, hostfile):
    """Run once, return (makespan, comm_avg, per_rank[list]). Reads the --stats CSV."""
    if hostfile:
        sync_data(cities, hostfile)          # make sure every node has the city file
    stats = tempfile.NamedTemporaryFile(suffix=".csv", delete=False).name
    solver = [BIN, cities, "--gens", str(gens), "--pop", str(pop),
              "--sync", str(sync), "--stats", stats]
    if hostfile:
        # standard cluster launcher (pins the 5.0.9 path + maps by node + cd's remote)
        cmd = ["bash", os.path.join("cluster", "run_cluster.sh"), hostfile, str(procs)] + solver
    else:
        cmd = ["mpirun", "--oversubscribe", "-np", str(procs)] + solver
    subprocess.run(cmd, cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if hostfile:
        # rank 0 (which writes --stats) is mapped to the FIRST host in the hostfile
        # (--map-by seq), not necessarily the launcher machine -> fetch it back.
        rank0_host = _hosts(hostfile)[0]
        subprocess.run(["scp", "-q", f"{rank0_host}:{stats}", stats],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rows = list(csv.DictReader(open(stats)))
    os.remove(stats)
    makespan = float(rows[0]["makespan_s"])
    per_rank = [(int(r["rank"]), float(r["compute_s"]), float(r["comm_s"]),
                 float(r["total_s"])) for r in rows]
    comm_avg = sum(r[2] for r in per_rank) / len(per_rank)
    return makespan, comm_avg, per_rank


def run_quality(procs, cities, gens, pop, sync, hostfile, greedy_init):
    """Run once with --out + --stats. Returns (makespan, best_len, history[np.array]).
    best_len = the global best tour length (solution quality); history = global best per
    generation (the .history file rank 0 writes). greedy_init toggles --greedy-init."""
    if hostfile:
        sync_data(cities, hostfile)
    stats = tempfile.NamedTemporaryFile(suffix=".csv", delete=False).name
    outpref = tempfile.NamedTemporaryFile(suffix=".out", delete=False).name
    solver = [BIN, cities, "--gens", str(gens), "--pop", str(pop),
              "--sync", str(sync), "--stats", stats, "--out", outpref]
    if greedy_init:
        solver.append("--greedy-init")
    if hostfile:
        cmd = ["bash", os.path.join("cluster", "run_cluster.sh"), hostfile, str(procs)] + solver
    else:
        cmd = ["mpirun", "--oversubscribe", "-np", str(procs)] + solver
    subprocess.run(cmd, cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    hist_path = outpref + ".history"
    if hostfile:
        # rank 0 (writes --out/--stats) is the FIRST host in the hostfile -> fetch both back
        rank0_host = _hosts(hostfile)[0]
        for p in (stats, hist_path):
            subprocess.run(["scp", "-q", f"{rank0_host}:{p}", p],
                           check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rows = list(csv.DictReader(open(stats)))
    makespan = float(rows[0]["makespan_s"])
    best_len = min(float(r["best_len"]) for r in rows)
    hist = np.array([])
    if gens > 0 and os.path.exists(hist_path) and os.path.getsize(hist_path) > 0:
        hist = np.atleast_1d(np.loadtxt(hist_path))
    import glob as _glob
    for p in [stats, outpref, hist_path] + _glob.glob(outpref + ".rank*.history"):
        try:
            os.remove(p)
        except OSError:
            pass
    return makespan, best_len, hist


# ---------------- Experiment 4: solution quality (greedy vs GA arms) ----------------
def exp_quality(a):
    """Compare solution QUALITY of three arms at the same N / procs:
      1. parallel greedy   - best of P nearest-neighbor starts (no GA), the baseline,
      2. GA from scratch    - random init, run for scratch_mult x the normal generations,
      3. GA greedy-seed     - seeded with the parallel greedy, normal generations.
    Plots the convergence curves (vs generation) + a final-length bar, and writes a CSV with
    final length, runtime and % improvement over greedy. Showcases that the GA beats greedy and
    that seeding reaches a good solution in far fewer generations."""
    os.makedirs(RESULTS, exist_ok=True)
    cities = make_cities(a.size)
    scratch_gens = a.gens * a.scratch_mult
    print(f"N={a.size}, procs={a.procs}, normal gens={a.gens}, "
          f"scratch gens={scratch_gens} (x{a.scratch_mult})")

    g_mk, g_len, _ = run_quality(a.procs, cities, 0, a.pop, a.sync, a.hostfile, True)
    print(f"[greedy]        len={g_len:8.2f}  (parallel best of {a.procs} NN starts)")
    sc_mk, sc_len, sc_hist = run_quality(a.procs, cities, scratch_gens, a.pop, a.sync, a.hostfile, False)
    print(f"[from-scratch]  len={sc_len:8.2f}  time={sc_mk:7.2f}s  gens={scratch_gens}")
    se_mk, se_len, se_hist = run_quality(a.procs, cities, a.gens, a.pop, a.sync, a.hostfile, True)
    print(f"[greedy-seed]   len={se_len:8.2f}  time={se_mk:7.2f}s  gens={a.gens}")

    def imp(x):
        return (g_len - x) / g_len * 100 if g_len else 0.0
    csvp = os.path.join(RESULTS, "exp_quality.csv")
    with open(csvp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arm", "gens", "makespan_s", "best_len", "improve_vs_greedy_pct"])
        w.writerow(["greedy", 0, f"{g_mk:.4f}", f"{g_len:.2f}", "0.00"])
        w.writerow(["from_scratch", scratch_gens, f"{sc_mk:.4f}", f"{sc_len:.2f}", f"{imp(sc_len):.2f}"])
        w.writerow(["greedy_seed", a.gens, f"{se_mk:.4f}", f"{se_len:.2f}", f"{imp(se_len):.2f}"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))
    if len(sc_hist):
        ax1.plot(range(1, len(sc_hist) + 1), sc_hist, "-", color="#DD8452",
                 label=f"GA from scratch ({scratch_gens} gens)")
    if len(se_hist):
        ax1.plot(range(1, len(se_hist) + 1), se_hist, "-", color="#4C72B0",
                 label=f"GA greedy-seed ({a.gens} gens)")
    ax1.axhline(g_len, ls="--", color="#555", label=f"parallel greedy = {g_len:.0f}")
    ax1.set_xscale("log")
    ax1.set_xlabel("Generation (log scale)"); ax1.set_ylabel("Best tour length")
    ax1.set_title(f"Convergence quality (N={a.size}, procs={a.procs})")
    ax1.legend(); ax1.grid(alpha=0.3)

    arms = ["greedy", "from\nscratch", "greedy\nseed"]
    vals = [g_len, sc_len, se_len]
    cols = ["#555555", "#DD8452", "#4C72B0"]
    ax2.bar(arms, vals, color=cols)
    for i, v in enumerate(vals):
        ax2.text(i, v, f"{v:.0f}", ha="center", va="bottom", fontsize=9)
    ax2.set_ylabel("Final best tour length"); ax2.set_title("Final solution quality (lower = better)")
    ax2.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    png = os.path.join(RESULTS, "exp_quality.png"); plt.savefig(png, dpi=130)
    print(f"-> {csvp}\n-> {png}")


# Known TSPLIB EUC_2D optimal tour lengths (integer metric) for the benchmark set.
TSPLIB_OPTIMA = {
    "eil51": 426, "st70": 675, "rd100": 7910, "lin105": 14379, "ch130": 6110,
    "pr144": 58537, "ch150": 6528, "u159": 42080, "rat195": 2323, "kroA200": 29368,
}


def run_solver_stats(procs, cities, gens, pop, sync, hostfile, greedy, round_dist):
    """Run once; read the --stats CSV. Returns (n_cities, gens_run, best_len, makespan_s)."""
    if hostfile:
        sync_data(cities, hostfile)
    stats = tempfile.NamedTemporaryFile(suffix=".csv", delete=False).name
    solver = [BIN, cities, "--gens", str(gens), "--pop", str(pop), "--sync", str(sync),
              "--stats", stats]
    if greedy:
        solver.append("--greedy-init")
    if round_dist:
        solver.append("--round")
    if hostfile:
        cmd = ["bash", os.path.join("cluster", "run_cluster.sh"), hostfile, str(procs)] + solver
    else:
        cmd = ["mpirun", "--oversubscribe", "-np", str(procs)] + solver
    subprocess.run(cmd, cwd=ROOT, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if hostfile:
        rank0_host = _hosts(hostfile)[0]
        subprocess.run(["scp", "-q", f"{rank0_host}:{stats}", stats],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rows = list(csv.DictReader(open(stats)))
    os.remove(stats)
    n = int(rows[0]["n_cities"])
    gens_run = int(rows[0]["gens"])
    best = min(float(r["best_len"]) for r in rows)
    makespan = float(rows[0]["makespan_s"])
    return n, gens_run, best, makespan


# ---------------- Experiment 5: TSPLIB benchmark (vs known optima) ----------------
def exp_tsplib(a):
    """Run the solver (integer EUC_2D metric, --round) on standard TSPLIB instances in two
    modes - GA greedy-seed (normal gens) and GA from scratch (scratch_mult x gens) - and compare
    the best tour length to the published optimum. Writes results/exp_tsplib.csv (instance, n,
    optimal, mode, gens, best_len, gap%, time) + a grouped gap% bar chart."""
    os.makedirs(RESULTS, exist_ok=True)
    insts = a.instances if a.instances else list(TSPLIB_OPTIMA)
    scratch_gens = a.gens * a.scratch_mult
    rows = []
    print(f"procs={a.procs}, greedy gens={a.gens}, scratch gens={scratch_gens} (x{a.scratch_mult}), "
          f"metric=integer EUC_2D")
    for nm in insts:
        cities = os.path.join("data", "tsplib", nm + ".txt")
        opt = TSPLIB_OPTIMA.get(nm, 0)
        n, g_gen, g_best, g_t = run_solver_stats(a.procs, cities, a.gens, a.pop, a.sync,
                                                 a.hostfile, True, True)
        n, s_gen, s_best, s_t = run_solver_stats(a.procs, cities, scratch_gens, a.pop, a.sync,
                                                 a.hostfile, False, True)
        def gap(b):
            return (b - opt) / opt * 100 if opt else float("nan")
        rows.append((nm, n, opt, "greedy", g_gen, g_best, gap(g_best), g_t))
        rows.append((nm, n, opt, "scratch", s_gen, s_best, gap(s_best), s_t))
        print(f"{nm:8s} n={n:4d} opt={opt:7d} | greedy {g_best:9.0f} ({gap(g_best):+5.2f}%, "
              f"{g_t:6.1f}s) | scratch {s_best:9.0f} ({gap(s_best):+5.2f}%, {s_t:6.1f}s)")

    csvp = os.path.join(RESULTS, "exp_tsplib.csv")
    with open(csvp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["instance", "n", "optimal", "mode", "gens", "best_len", "gap_pct", "time_s"])
        for nm, n, opt, mode, gen, best, gp, t in rows:
            w.writerow([nm, n, opt, mode, gen, f"{best:.0f}", f"{gp:.2f}", f"{t:.2f}"])

    names = insts
    greedy_gap = [next(r[6] for r in rows if r[0] == nm and r[3] == "greedy") for nm in names]
    scratch_gap = [next(r[6] for r in rows if r[0] == nm and r[3] == "scratch") for nm in names]
    x = np.arange(len(names)); width = 0.4
    plt.figure(figsize=(12, 5))
    plt.bar(x - width/2, scratch_gap, width, label=f"GA from scratch ({scratch_gens} gens)", color="#DD8452")
    plt.bar(x + width/2, greedy_gap, width, label=f"GA greedy-seed ({a.gens} gens)", color="#4C72B0")
    plt.axhline(0, color="#333", lw=0.8)
    plt.xticks(x, names, rotation=30, ha="right")
    plt.ylabel("Gap above optimum (%)"); plt.title(f"TSPLIB benchmark - gap vs optimum (procs={a.procs})")
    plt.legend(); plt.grid(axis="y", alpha=0.3); plt.tight_layout()
    png = os.path.join(RESULTS, "exp_tsplib.png"); plt.savefig(png, dpi=130)
    print(f"-> {csvp}\n-> {png}")


# ---------------- Experiment 1: runtime vs. size N ----------------
def exp_size(a):
    os.makedirs(RESULTS, exist_ok=True)
    rows = []
    for n in a.sizes:
        cities = make_cities(n)
        mk, cm, _ = run(a.procs, cities, a.gens, a.pop, a.sync, a.hostfile)
        rows.append((n, mk, cm, mk - cm))
        print(f"N={n:5d}  total={mk:7.2f}s  comm={cm:6.3f}s  compute={mk-cm:7.2f}s")
    csvp = os.path.join(RESULTS, "exp_size.csv")
    with open(csvp, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["N", "total_s", "comm_s", "compute_s"])
        w.writerows([(n, f"{t:.4f}", f"{c:.4f}", f"{k:.4f}") for n, t, c, k in rows])
    N = [r[0] for r in rows]
    plt.figure(figsize=(8, 5))
    plt.plot(N, [r[1] for r in rows], "o-", label="with communication (total)")
    plt.plot(N, [r[3] for r in rows], "s--", label="without communication (compute)")
    plt.axhspan(120, 180, color="green", alpha=0.12, label="target 2-3 minutes")
    plt.xlabel("Problem size N (cities)"); plt.ylabel("Runtime (s)")
    plt.title(f"Runtime vs. N  (procs={a.procs}, gens={a.gens})")
    plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    png = os.path.join(RESULTS, "exp_size.png"); plt.savefig(png, dpi=130)
    print(f"-> {csvp}\n-> {png}")


# ---------------- Experiment 2: granularity / load balance ----------------
def exp_gran(a):
    os.makedirs(RESULTS, exist_ok=True)
    cities = make_cities(a.size)
    mk, cm, per = run(a.procs, cities, a.gens, a.pop, a.sync, a.hostfile)
    per.sort()
    ranks = [p[0] for p in per]; comp = [p[1] for p in per]; comm = [p[2] for p in per]
    idle = [mk - p[3] for p in per]          # idle = makespan - this rank's total
    skew = (max(idle) - min(idle)) / mk * 100 if mk else 0
    csvp = os.path.join(RESULTS, "exp_gran.csv")
    with open(csvp, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["rank", "compute_s", "comm_s", "idle_s"])
        for p, i in zip(per, idle):
            w.writerow([p[0], f"{p[1]:.4f}", f"{p[2]:.4f}", f"{i:.4f}"])
    plt.figure(figsize=(9, 5))
    plt.bar(ranks, comp, label="compute", color="#4C72B0")
    plt.bar(ranks, comm, bottom=comp, label="comm", color="#DD8452")
    plt.bar(ranks, idle, bottom=[c + m for c, m in zip(comp, comm)],
            label="idle (wait)", color="#CCCCCC")
    plt.xlabel("Process (rank)"); plt.ylabel("Time (s)")
    plt.title(f"Granularity / load balance  (N={a.size}, procs={a.procs})  "
              f"idle skew={skew:.1f}%")
    plt.legend(); plt.grid(axis="y", alpha=0.3); plt.tight_layout()
    png = os.path.join(RESULTS, "exp_gran.png"); plt.savefig(png, dpi=130)
    verdict = "BALANCED OK" if skew <= 25 else "IMBALANCED (>25%) -> tune the workload split"
    print(f"idle skew = {skew:.1f}%  => {verdict}")
    print(f"-> {csvp}\n-> {png}")


# ---------------- Experiment 3: speedup ----------------
def exp_speedup(a):
    os.makedirs(RESULTS, exist_ok=True)
    cities = make_cities(a.size)
    rows = []
    for p in a.procs:
        pop = max(1, a.total // p)            # keep the total population fixed (strong scaling)
        mk, cm, _ = run(p, cities, a.gens, pop, a.sync, a.hostfile)
        rows.append((p, mk, cm, mk - cm))
        print(f"procs={p:3d}  total={mk:7.2f}s  comm={cm:6.3f}s  compute={mk-cm:7.2f}s")
    t1, t1c = rows[0][1], rows[0][3]
    csvp = os.path.join(RESULTS, "exp_speedup.csv")
    with open(csvp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["procs", "total_s", "comm_s", "compute_s", "speedup", "speedup_nocomm", "eff"])
        for p, t, c, k in rows:
            w.writerow([p, f"{t:.4f}", f"{c:.4f}", f"{k:.4f}",
                        f"{t1/t:.4f}", f"{t1c/k:.4f}", f"{(t1/t)/p:.4f}"])
    P = [r[0] for r in rows]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    ax1.plot(P, [r[1] for r in rows], "o-", label="with communication")
    ax1.plot(P, [r[3] for r in rows], "s--", label="without communication")
    ax1.set_xlabel("Processes"); ax1.set_ylabel("Runtime (s)")
    ax1.set_title(f"Runtime (N={a.size})"); ax1.legend(); ax1.grid(alpha=0.3)
    ax2.plot(P, [t1 / r[1] for r in rows], "o-", label="speedup (with comm)")
    ax2.plot(P, [t1c / r[3] for r in rows], "s--", label="speedup (without comm)")
    ax2.plot(P, P, "k:", label="ideal")
    ax2.set_xlabel("Processes"); ax2.set_ylabel("Speedup S(p)=T(1)/T(p)")
    ax2.set_title("Speedup"); ax2.legend(); ax2.grid(alpha=0.3)
    plt.tight_layout()
    png = os.path.join(RESULTS, "exp_speedup.png"); plt.savefig(png, dpi=130)
    print(f"-> {csvp}\n-> {png}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("size", "gran", "speedup", "quality", "tsplib"):
        s = sub.add_parser(name)
        s.add_argument("--gens", type=int, default=400)
        s.add_argument("--pop", type=int, default=200)
        s.add_argument("--sync", type=int, default=20, help="global-best broadcast interval")
        s.add_argument("--hostfile", default=None, help="use the cluster launcher; empty = one machine")
        if name == "tsplib":
            s.add_argument("--procs", type=int, default=48)
            s.add_argument("--scratch-mult", type=int, default=10,
                           help="GA-from-scratch runs this many x --gens (default 10)")
            s.add_argument("--instances", nargs="*", default=None,
                           help="subset of TSPLIB instances (default: all 10)")
        elif name == "size":
            s.add_argument("--procs", type=int, default=4)
            s.add_argument("--sizes", type=int, nargs="+", default=[100, 200, 400, 800, 1600, 3200])
        elif name == "gran":
            s.add_argument("--procs", type=int, default=4)
            s.add_argument("--size", type=int, default=200)
        elif name == "quality":
            s.add_argument("--procs", type=int, default=4)
            s.add_argument("--size", type=int, default=200)
            s.add_argument("--scratch-mult", type=int, default=20,
                           help="GA-from-scratch runs this many x --gens (default 20)")
        else:  # speedup
            s.add_argument("--procs", type=int, nargs="+", default=[1, 2, 4, 8])
            s.add_argument("--size", type=int, default=200)
            s.add_argument("--total", type=int, default=480, help="total population (split across islands)")
    a = ap.parse_args()
    {"size": exp_size, "gran": exp_gran, "speedup": exp_speedup, "quality": exp_quality,
     "tsplib": exp_tsplib}[a.cmd](a)


if __name__ == "__main__":
    main()
