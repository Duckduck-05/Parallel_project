#!/usr/bin/env python3
"""experiments.py - Generate the data + figures for the REPORT.

This is a PLOTTING / orchestration tool only. The solver is the C++ binary
cpp/tsp_island; this script launches it (locally with mpirun, or on the cluster through
cluster/run_cluster.sh), reads the per-process --stats CSV it writes, and plots.

Three experiments:
  size    : runtime vs. problem size N (number of cities), WITH and WITHOUT communication
            time -> pick N so the program runs ~2-3 minutes.
  gran    : one run with N cities on P processes; stacked compute+comm+idle bars per
            process (load-balance / granularity check; warns if idle skew > 25%).
  speedup : fixed total work, varying processes 1,2,4,8,...; runtime (with/without comm)
            + speedup S(p)=T(1)/T(p) + efficiency.

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
    rows = list(csv.DictReader(open(stats)))
    os.remove(stats)
    makespan = float(rows[0]["makespan_s"])
    per_rank = [(int(r["rank"]), float(r["compute_s"]), float(r["comm_s"]),
                 float(r["total_s"])) for r in rows]
    comm_avg = sum(r[2] for r in per_rank) / len(per_rank)
    return makespan, comm_avg, per_rank


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
    for name in ("size", "gran", "speedup"):
        s = sub.add_parser(name)
        s.add_argument("--gens", type=int, default=400)
        s.add_argument("--pop", type=int, default=200)
        s.add_argument("--sync", type=int, default=20, help="global-best broadcast interval")
        s.add_argument("--hostfile", default=None, help="use the cluster launcher; empty = one machine")
        if name == "size":
            s.add_argument("--procs", type=int, default=4)
            s.add_argument("--sizes", type=int, nargs="+", default=[50, 100, 200, 400, 800])
        elif name == "gran":
            s.add_argument("--procs", type=int, default=4)
            s.add_argument("--size", type=int, default=200)
        else:  # speedup
            s.add_argument("--procs", type=int, nargs="+", default=[1, 2, 4, 8])
            s.add_argument("--size", type=int, default=200)
            s.add_argument("--total", type=int, default=480, help="total population (split across islands)")
    a = ap.parse_args()
    {"size": exp_size, "gran": exp_gran, "speedup": exp_speedup}[a.cmd](a)


if __name__ == "__main__":
    main()
