#!/usr/bin/env python3
"""benchmark.py - Task 9: Đo speedup & efficiency của Island-GA theo số process.

Giữ TỔNG khối lượng công việc cố định (tổng quần thể = --total), chia đều cho các đảo
(pop/đảo = total/np) -> đo "strong scaling" đúng nghĩa: speedup S(p)=T(1)/T(p).

Chạy 1 máy:  python3 benchmark.py ../data/cities_50.txt --procs 1 2 3 4 --total 240 --gens 400
Chạy cụm:    python3 benchmark.py ... --hostfile ../cluster/hosts
Kết quả: results/bench.csv + results/speedup.png
"""
import argparse
import re
import subprocess
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TIME_RE = re.compile(r"Thoi gian\s*:\s*([0-9.]+)")


def run_once(prog_cmd, np_count, hostfile, total, gens, cities):
    pop = max(1, total // np_count)        # chia deu tong quan the cho cac dao
    cmd = ["mpirun"]
    if hostfile:
        cmd += ["--hostfile", hostfile]
    else:
        cmd += ["--oversubscribe", "--mca", "btl", "self,sm,vader"]
    cmd += ["-np", str(np_count)] + prog_cmd + [
        cities, "--gens", str(gens), "--pop", str(pop), "--migrate", "20"]
    out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
    m = TIME_RE.search(out)
    return float(m.group(1))


def amdahl(p, s):
    """Định luật Amdahl: tăng tốc lý thuyết với phần tuần tự s."""
    return 1.0 / (s + (1 - s) / p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cities")
    ap.add_argument("--procs", type=int, nargs="+", default=[1, 2, 3, 4])
    ap.add_argument("--total", type=int, default=240, help="tong quan the (chia cho cac dao)")
    ap.add_argument("--gens", type=int, default=400)
    ap.add_argument("--reps", type=int, default=3, help="so lan lap lay min")
    ap.add_argument("--hostfile", default=None)
    ap.add_argument("--lang", choices=["py", "cpp"], default="py")
    ap.add_argument("--csv", default="../results/bench.csv")
    ap.add_argument("--out", default="../results/speedup.png")
    args = ap.parse_args()

    prog = ["python3", "tsp_island.py"] if args.lang == "py" else ["./tsp_island"]

    rows = []
    for p in args.procs:
        times = [run_once(prog, p, args.hostfile, args.total, args.gens, args.cities)
                 for _ in range(args.reps)]
        t = min(times)                     # lay min de giam nhieu
        rows.append((p, t))
        print(f"np={p:2d}  time={t:.3f}s")

    t1 = rows[0][1]                        # thoi gian voi 1 process lam chuan
    procs = [r[0] for r in rows]
    speedup = [t1 / r[1] for r in rows]
    eff = [s / p for s, p in zip(speedup, procs)]

    with open(args.csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["procs", "time_s", "speedup", "efficiency"])
        for (p, t), s, e in zip(rows, speedup, eff):
            w.writerow([p, f"{t:.4f}", f"{s:.4f}", f"{e:.4f}"])
    print(f"Da luu {args.csv}")

    # uoc luong phan tuan tu s khop Amdahl (binh phuong toi thieu don gian)
    grid = np.linspace(0.001, 0.5, 500)
    err = [sum((amdahl(p, s) - sp) ** 2 for p, sp in zip(procs, speedup)) for s in grid]
    s_fit = grid[int(np.argmin(err))]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    ax1.plot(procs, speedup, "o-", label="thuc te")
    ax1.plot(procs, procs, "k--", label="ly tuong (tuyen tinh)")
    ax1.plot(procs, [amdahl(p, s_fit) for p in procs], "r:",
             label=f"Amdahl (s={s_fit:.3f})")
    ax1.set_xlabel("So process"); ax1.set_ylabel("Speedup")
    ax1.set_title("Speedup"); ax1.legend(); ax1.grid(alpha=0.3)

    ax2.plot(procs, eff, "s-", color="green")
    ax2.axhline(1.0, ls="--", color="k")
    ax2.set_xlabel("So process"); ax2.set_ylabel("Efficiency")
    ax2.set_title("Efficiency = Speedup / p"); ax2.set_ylim(0, 1.2); ax2.grid(alpha=0.3)

    plt.tight_layout(); plt.savefig(args.out, dpi=130)
    print(f"Da luu {args.out}")


if __name__ == "__main__":
    main()
