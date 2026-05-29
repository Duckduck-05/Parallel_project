#!/usr/bin/env python3
"""tsp_sequential.py - Task 5: Chạy GA tuần tự trên 1 process cho 1 bài TSP.

Demo: python3 tsp_sequential.py ../data/cities_30.txt --gens 500 --pop 200
In ra độ dài tour tốt nhất và lưu lộ trình ra file (tùy chọn).
"""
import argparse
import time
import numpy as np
import ga_core as ga


def main():
    ap = argparse.ArgumentParser(description="GA tuan tu cho TSP")
    ap.add_argument("cities", help="file toa do thanh pho")
    ap.add_argument("--gens", type=int, default=500, help="so the he")
    ap.add_argument("--pop", type=int, default=200, help="kich thuoc quan the")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=None, help="file luu tour tot nhat")
    args = ap.parse_args()

    coords = ga.read_cities(args.cities)
    D = ga.distance_matrix(coords)
    rng = np.random.default_rng(args.seed)

    t0 = time.time()
    tour, length, history = ga.evolve(D, args.pop, args.gens, rng)
    dt = time.time() - t0

    print(f"So thanh pho   : {len(coords)}")
    print(f"The he         : {args.gens}, quan the: {args.pop}")
    print(f"Do dai tot nhat: {length:.2f}")
    print(f"Thoi gian       : {dt:.2f}s")
    print(f"Lo trinh        : {tour.tolist()}")

    if args.out:
        np.savetxt(args.out, tour, fmt="%d")
        print(f"Da luu tour vao {args.out}")


if __name__ == "__main__":
    main()
