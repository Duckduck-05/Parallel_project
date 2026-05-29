#!/usr/bin/env python3
"""visualize.py - Task 8: Vẽ lộ trình tốt nhất + đồ thị hội tụ.

Sinh ảnh PNG cho slide/report. Đọc file tour và (tùy chọn) file lịch sử hội tụ
do tsp_island.py xuất ra (--out tour.txt -> tour.txt.history).

Chạy:
  # ve lo trinh:
  python3 visualize.py route ../data/cities_30.txt tour.txt --out ../results/route.png
  # ve do thi hoi tu:
  python3 visualize.py converge tour.txt.history --out ../results/converge.png
"""
import argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")            # khong can man hinh -> chay tot tren VM/server
import matplotlib.pyplot as plt
import ga_core as ga


def plot_route(cities_file, tour_file, out):
    coords = ga.read_cities(cities_file)
    tour = np.loadtxt(tour_file, dtype=int)
    D = ga.distance_matrix(coords)
    length = ga.tour_length(tour, D)
    loop = np.append(tour, tour[0])          # khep kin vong

    plt.figure(figsize=(7, 6))
    plt.plot(coords[loop, 0], coords[loop, 1], "-o", ms=5, lw=1.2)
    plt.plot(coords[tour[0], 0], coords[tour[0], 1], "rs", ms=10, label="diem xuat phat")
    plt.title(f"Lo trinh TSP tot nhat — do dai = {length:.2f} ({len(tour)} thanh pho)")
    plt.xlabel("x"); plt.ylabel("y"); plt.legend(); plt.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(out, dpi=130)
    print(f"Da luu {out}")


def plot_converge(history_files, out):
    plt.figure(figsize=(7, 5))
    for hf in history_files:
        hist = np.loadtxt(hf)
        label = hf.split("/")[-1].replace(".history", "")
        plt.plot(hist, lw=1.5, label=label)
    plt.title("Do thi hoi tu (do dai tour tot nhat theo the he)")
    plt.xlabel("The he"); plt.ylabel("Do dai tour tot nhat")
    plt.legend(); plt.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(out, dpi=130)
    print(f"Da luu {out}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("route", help="ve lo trinh tot nhat")
    r.add_argument("cities"); r.add_argument("tour")
    r.add_argument("--out", default="route.png")

    c = sub.add_parser("converge", help="ve do thi hoi tu (1 hoac nhieu file)")
    c.add_argument("history", nargs="+")
    c.add_argument("--out", default="converge.png")

    args = ap.parse_args()
    if args.cmd == "route":
        plot_route(args.cities, args.tour, args.out)
    else:
        plot_converge(args.history, args.out)


if __name__ == "__main__":
    main()
