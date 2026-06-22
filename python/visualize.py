#!/usr/bin/env python3
"""visualize.py - Plot the best route + the convergence graph (report figures).

Produces PNG images for the slides / report. Reads the tour file and (optionally) the
convergence-history file written by the C++ solver (cpp/tsp_island --out tour.txt also
writes tour.txt.history).

This file is a VISUALIZATION helper only: it does not run the GA. It carries small
self-contained readers (city file + tour length) so it has no dependency on any Python
algorithm module.

Usage:
  # plot the route:
  python3 visualize.py route ../data/cities_30.txt tour.txt --out ../results/route.png
  # plot the convergence graph (one or more history files):
  python3 visualize.py converge tour.txt.history --out ../results/converge.png
"""
import argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")            # no display needed -> works on a VM / server
import matplotlib.pyplot as plt


def read_cities(path):
    """Read a city-coordinate file. Each line: 'x y' (blank / '#' lines skipped)."""
    pts = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            x, y = line.split()[:2]
            pts.append((float(x), float(y)))
    return np.array(pts, dtype=float)


def tour_length(tour, coords):
    """Total length of the closed tour (returns to the start)."""
    loop = np.append(tour, tour[0])
    seg = coords[loop[1:]] - coords[loop[:-1]]
    return float(np.sqrt((seg ** 2).sum(axis=1)).sum())


def plot_route(cities_file, tour_file, out):
    coords = read_cities(cities_file)
    tour = np.loadtxt(tour_file, dtype=int)
    length = tour_length(tour, coords)
    loop = np.append(tour, tour[0])          # close the loop

    plt.figure(figsize=(7, 6))
    plt.plot(coords[loop, 0], coords[loop, 1], "-o", ms=5, lw=1.2)
    plt.plot(coords[tour[0], 0], coords[tour[0], 1], "rs", ms=10, label="start city")
    plt.title(f"Best TSP route - length = {length:.2f} ({len(tour)} cities)")
    plt.xlabel("x"); plt.ylabel("y"); plt.legend(); plt.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(out, dpi=130)
    print(f"Saved {out}")


def plot_converge(history_files, out):
    plt.figure(figsize=(7, 5))
    for hf in history_files:
        hist = np.loadtxt(hf)
        label = hf.replace("\\", "/").split("/")[-1].replace(".history", "")
        plt.plot(hist, lw=1.5, label=label)
    plt.title("Convergence (best tour length per generation)")
    plt.xlabel("Generation"); plt.ylabel("Best tour length")
    plt.legend(); plt.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(out, dpi=130)
    print(f"Saved {out}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("route", help="plot the best route")
    r.add_argument("cities"); r.add_argument("tour")
    r.add_argument("--out", default="route.png")

    c = sub.add_parser("converge", help="plot the convergence graph (one or more files)")
    c.add_argument("history", nargs="+")
    c.add_argument("--out", default="converge.png")

    args = ap.parse_args()
    if args.cmd == "route":
        plot_route(args.cities, args.tour, args.out)
    else:
        plot_converge(args.history, args.out)


if __name__ == "__main__":
    main()
