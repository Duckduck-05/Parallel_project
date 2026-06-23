#!/usr/bin/env python3
"""validate_tour.py - Independent correctness check for a tsp_island result.

Checks, given a city file + a route (city indices) + the reported "Best length":
  1. the route is a valid permutation of 0..n-1 (every city visited exactly once)
  2. recomputing the tour length from the raw coordinates matches the reported value
  3. for n <= 10, brute-force the true optimum and report the gap

Usage:
  python3 validate_tour.py data/cities_8.txt "2 4 7 0 1 3 6 5" 240.49
"""
import sys, itertools, math


def read_cities(path):
    pts = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            x, y = map(float, line.split())
            pts.append((x, y))
    return pts


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def tour_len(tour, pts):
    n = len(tour)
    return sum(dist(pts[tour[i]], pts[tour[(i + 1) % n]]) for i in range(n))


def main():
    cities_path, route_str, reported_len = sys.argv[1], sys.argv[2], float(sys.argv[3])
    route = list(map(int, route_str.split()))
    pts = read_cities(cities_path)
    n = len(pts)

    assert len(route) == n, f"route length {len(route)} != n {n}"
    assert sorted(route) == list(range(n)), "route is NOT a valid permutation of 0..n-1"
    print(f"[OK] route is a valid permutation of {n} cities, each exactly once")

    recomputed = tour_len(route, pts)
    print(f"[OK] recomputed length = {recomputed:.4f}  "
          f"(reported = {reported_len:.4f}, diff = {abs(recomputed - reported_len):.6f})")
    assert abs(recomputed - reported_len) < 0.01, "MISMATCH between recomputed and reported length"

    if n <= 10:
        best = min(tour_len((0,) + perm, pts) for perm in itertools.permutations(range(1, n)))
        gap = (recomputed - best) / best * 100
        print(f"[INFO] brute-force optimal = {best:.4f}, GA gap = {gap:.2f}%")
        print("[OK] GA found the EXACT global optimum" if gap < 1e-6
              else f"[OK] GA result is within {gap:.2f}% of the true optimum")
    else:
        print("[SKIP] n too large for brute force")


if __name__ == "__main__":
    main()
