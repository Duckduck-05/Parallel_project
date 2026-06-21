#!/usr/bin/env python3
"""experiments.py - Sinh du lieu + bieu do cho BAO CAO (theo report_requirements.md).

Ba thi nghiem:
  size    : do thoi gian chay theo kich thuoc N (so thanh pho), CO va KHONG co
            thoi gian truyen thong  -> chon N de chuong trinh chay ~2-3 phut.
  gran    : chay 1 lan voi N, P tien trinh; ve cot compute+comm tung tien trinh
            (kiem tra can bang tai - granularity; canh bao neu lech idle > 25%).
  speedup : kich thuoc 2N, doi so tien trinh 1,2,4,8,...; ve thoi gian (co/khong
            truyen thong) + do tang toc S(p)=T(1)/T(p) va hieu suat.

Chay 1 may (oversubscribe):
  python3 experiments.py size    --procs 4 --sizes 50 100 200 400
  python3 experiments.py speedup --procs 1 2 4 8 --size 200
  python3 experiments.py gran    --procs 4 --size 200

Chay tren CUM (dung launcher chuan):
  python3 experiments.py speedup --procs 1 2 4 8 --size 200 --hostfile ../cluster/hosts.cur

Ket qua: ../results/exp_*.csv + ../results/exp_*.png
"""
import argparse, csv, os, subprocess, sys, tempfile
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "results")
DATA = os.path.join(ROOT, "data")


def make_cities(n, seed=1):
    """Sinh file toa do n thanh pho (ngau nhien, on dinh theo seed).
    Tra ve duong dan TUONG DOI (data/cities_n.txt) de moi node tu giai duoc trong
    ~/parallel-tsp cua minh (home khac nhau giua cac may)."""
    os.makedirs(DATA, exist_ok=True)
    path = os.path.join(DATA, f"cities_{n}.txt")
    if not os.path.exists(path):
        rng = np.random.default_rng(seed)
        pts = rng.uniform(0, 100, size=(n, 2))
        np.savetxt(path, pts, fmt="%.4f", header="x y (auto-generated)")
    return os.path.join("data", f"cities_{n}.txt")    # relative to ROOT / ~/parallel-tsp


def _hosts(hostfile):
    """Ten cac node trong hostfile (token dau moi dong, bo dong trong/#)."""
    out = []
    for line in open(hostfile):
        line = line.strip()
        if line and not line.startswith("#"):
            out.append(line.split()[0])
    return out


def sync_data(cities, hostfile):
    """Dong bo file thanh pho sang ~/parallel-tsp tren cac node tu xa (tru node1).
    Moi node phai co cung file o cung duong dan tuong doi."""
    src = os.path.join(ROOT, cities)
    for h in _hosts(hostfile):
        if h == "node1":
            continue
        subprocess.run(["rsync", "-az", src, f"{h}:parallel-tsp/{cities}"],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def run(procs, cities, gens, pop, migrate, hostfile):
    """Chay 1 lan, tra ve (makespan, comm_avg, per_rank[list]). Doc tu --stats CSV."""
    if hostfile:
        sync_data(cities, hostfile)          # bao dam moi node co file thanh pho
    stats = tempfile.NamedTemporaryFile(suffix=".csv", delete=False).name
    prog = ["python3", "python/tsp_island.py", cities,
            "--gens", str(gens), "--pop", str(pop), "--migrate", str(migrate),
            "--stats", stats]
    if hostfile:
        # launcher chuan cho cum (dat path 5.0.9 + map-by node + cd remote)
        cmd = ["bash", os.path.join("cluster", "run_cluster.sh"), hostfile, str(procs)] + prog
        cwd = ROOT
    else:
        cmd = ["mpirun", "--oversubscribe", "-np", str(procs)] + \
              [prog[0], os.path.join("python", "tsp_island.py")] + prog[2:]
        cwd = ROOT
    subprocess.run(cmd, cwd=cwd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    rows = list(csv.DictReader(open(stats)))
    os.remove(stats)
    makespan = float(rows[0]["makespan_s"])
    per_rank = [(int(r["rank"]), float(r["compute_s"]), float(r["comm_s"]),
                 float(r["total_s"])) for r in rows]
    comm_avg = sum(r[2] for r in per_rank) / len(per_rank)
    return makespan, comm_avg, per_rank


# ---------------- Thi nghiem 1: thoi gian theo kich thuoc N ----------------
def exp_size(a):
    os.makedirs(RESULTS, exist_ok=True)
    rows = []
    for n in a.sizes:
        cities = make_cities(n)
        mk, cm, _ = run(a.procs, cities, a.gens, a.pop, a.migrate, a.hostfile)
        rows.append((n, mk, cm, mk - cm))
        print(f"N={n:5d}  total={mk:7.2f}s  comm={cm:6.3f}s  compute={mk-cm:7.2f}s")
    csvp = os.path.join(RESULTS, "exp_size.csv")
    with open(csvp, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["N", "total_s", "comm_s", "compute_s"])
        w.writerows([(n, f"{t:.4f}", f"{c:.4f}", f"{k:.4f}") for n, t, c, k in rows])
    N = [r[0] for r in rows]
    plt.figure(figsize=(8, 5))
    plt.plot(N, [r[1] for r in rows], "o-", label="co truyen thong (total)")
    plt.plot(N, [r[3] for r in rows], "s--", label="khong truyen thong (compute)")
    plt.axhspan(120, 180, color="green", alpha=0.12, label="muc tieu 2-3 phut")
    plt.xlabel("Kich thuoc N (so thanh pho)"); plt.ylabel("Thoi gian chay (s)")
    plt.title(f"Thoi gian theo N  (procs={a.procs}, gens={a.gens})")
    plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    png = os.path.join(RESULTS, "exp_size.png"); plt.savefig(png, dpi=130)
    print(f"-> {csvp}\n-> {png}")


# ---------------- Thi nghiem 2: granularity / can bang tai ----------------
def exp_gran(a):
    os.makedirs(RESULTS, exist_ok=True)
    cities = make_cities(a.size)
    mk, cm, per = run(a.procs, cities, a.gens, a.pop, a.migrate, a.hostfile)
    per.sort()
    ranks = [p[0] for p in per]; comp = [p[1] for p in per]; comm = [p[2] for p in per]
    idle = [mk - p[3] for p in per]          # thoi gian ranh = makespan - total cua rank
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
            label="idle (cho)", color="#CCCCCC")
    plt.xlabel("Tien trinh (rank)"); plt.ylabel("Thoi gian (s)")
    plt.title(f"Granularity / can bang tai  (N={a.size}, procs={a.procs})  "
              f"lech idle={skew:.1f}%")
    plt.legend(); plt.grid(axis="y", alpha=0.3); plt.tight_layout()
    png = os.path.join(RESULTS, "exp_gran.png"); plt.savefig(png, dpi=130)
    verdict = "CAN BANG OK" if skew <= 25 else "MAT CAN BANG (>25%) -> chinh do min"
    print(f"lech idle = {skew:.1f}%  => {verdict}")
    print(f"-> {csvp}\n-> {png}")


# ---------------- Thi nghiem 3: speedup ----------------
def exp_speedup(a):
    os.makedirs(RESULTS, exist_ok=True)
    cities = make_cities(a.size)
    rows = []
    for p in a.procs:
        pop = max(1, a.total // p)            # giu tong quan the co dinh (strong scaling)
        mk, cm, _ = run(p, cities, a.gens, pop, a.migrate, a.hostfile)
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
    ax1.plot(P, [r[1] for r in rows], "o-", label="co truyen thong")
    ax1.plot(P, [r[3] for r in rows], "s--", label="khong truyen thong")
    ax1.set_xlabel("So tien trinh"); ax1.set_ylabel("Thoi gian (s)")
    ax1.set_title(f"Thoi gian chay (N={a.size})"); ax1.legend(); ax1.grid(alpha=0.3)
    ax2.plot(P, [t1 / r[1] for r in rows], "o-", label="speedup (co comm)")
    ax2.plot(P, [t1c / r[3] for r in rows], "s--", label="speedup (khong comm)")
    ax2.plot(P, P, "k:", label="ly tuong")
    ax2.set_xlabel("So tien trinh"); ax2.set_ylabel("Speedup S(p)=T(1)/T(p)")
    ax2.set_title("Do tang toc"); ax2.legend(); ax2.grid(alpha=0.3)
    plt.tight_layout()
    png = os.path.join(RESULTS, "exp_speedup.png"); plt.savefig(png, dpi=130)
    print(f"-> {csvp}\n-> {png}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = dict()
    for name in ("size", "gran", "speedup"):
        s = sub.add_parser(name)
        s.add_argument("--gens", type=int, default=400)
        s.add_argument("--pop", type=int, default=200)
        s.add_argument("--migrate", type=int, default=20)
        s.add_argument("--hostfile", default=None, help="dung launcher cum; bo trong = chay 1 may")
        if name == "size":
            s.add_argument("--procs", type=int, default=4)
            s.add_argument("--sizes", type=int, nargs="+", default=[50, 100, 200, 400, 800])
        elif name == "gran":
            s.add_argument("--procs", type=int, default=4)
            s.add_argument("--size", type=int, default=200)
        else:  # speedup
            s.add_argument("--procs", type=int, nargs="+", default=[1, 2, 4, 8])
            s.add_argument("--size", type=int, default=200)
            s.add_argument("--total", type=int, default=480, help="tong quan the (chia cho cac dao)")
    a = ap.parse_args()
    {"size": exp_size, "gran": exp_gran, "speedup": exp_speedup}[a.cmd](a)


if __name__ == "__main__":
    main()
