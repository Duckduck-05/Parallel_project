#!/usr/bin/env python3
"""generate_cities.py - Generate city-coordinate data for the TSP.

Two modes: uniform random, or clustered (more city-like). This is a small data
utility; the solver itself is the C++ binary in cpp/.

Usage: python3 generate_cities.py --n 50 --seed 1 --out cities_50.txt
       python3 generate_cities.py --n 100 --mode cluster --out cities_100.txt
"""
import argparse
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50, help="number of cities")
    ap.add_argument("--mode", choices=["random", "cluster"], default="random")
    ap.add_argument("--size", type=float, default=100.0, help="area size")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    if args.mode == "random":
        pts = rng.uniform(0, args.size, size=(args.n, 2))
    else:
        # group into ~sqrt(n)/2 clusters, each a Gaussian blob
        k = max(2, int(np.sqrt(args.n) / 2))
        centers = rng.uniform(0, args.size, size=(k, 2))
        idx = rng.integers(0, k, size=args.n)
        pts = centers[idx] + rng.normal(0, args.size * 0.06, size=(args.n, 2))
        pts = np.clip(pts, 0, args.size)

    with open(args.out, "w") as f:
        f.write(f"# {args.n} cities, mode={args.mode}, seed={args.seed}\n")
        for x, y in pts:
            f.write(f"{x:.2f} {y:.2f}\n")
    print(f"Generated {args.n} cities ({args.mode}) -> {args.out}")


if __name__ == "__main__":
    main()
