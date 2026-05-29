#!/usr/bin/env python3
"""test_local_search.py - Unit test cho 2-opt / Or-opt.
Chạy: python3 -m pytest test_local_search.py -v
"""
import numpy as np
import ga_core as ga
import local_search as ls


def _perm_ok(t, n):
    return sorted(np.asarray(t).tolist()) == list(range(n))


def test_two_opt_keeps_permutation():
    rng = np.random.default_rng(0)
    coords = rng.random((15, 2))
    D = ga.distance_matrix(coords)
    for _ in range(20):
        t = ga.random_tour(15, rng)
        out = ls.two_opt(t, D)
        assert _perm_ok(out, 15)


def test_two_opt_not_worse():
    # 2-opt không bao giờ làm tour dài hơn
    rng = np.random.default_rng(1)
    coords = rng.random((20, 2))
    D = ga.distance_matrix(coords)
    for _ in range(20):
        t = ga.random_tour(20, rng)
        before = ga.tour_length(t, D)
        after = ga.tour_length(ls.two_opt(t, D), D)
        assert after <= before + 1e-9


def test_two_opt_fixes_crossing():
    # 4 điểm vuông: thứ tự chéo 0-2-1-3 (có giao) phải được 2-opt sửa về chu vi = 4
    coords = np.array([[0, 0], [0, 1], [1, 1], [1, 0]], dtype=float)
    D = ga.distance_matrix(coords)
    crossed = np.array([0, 2, 1, 3])
    fixed = ls.two_opt(crossed, D)
    assert abs(ga.tour_length(fixed, D) - 4.0) < 1e-9


def test_or_opt_not_worse():
    rng = np.random.default_rng(2)
    coords = rng.random((18, 2))
    D = ga.distance_matrix(coords)
    for _ in range(15):
        t = ga.random_tour(18, rng)
        before = ga.tour_length(t, D)
        after = ga.tour_length(ls.or_opt(t, D, seg_len=2), D)
        assert after <= before + 1e-9


def test_polish_improves_random():
    rng = np.random.default_rng(3)
    coords = rng.random((25, 2))
    D = ga.distance_matrix(coords)
    t = ga.random_tour(25, rng)
    assert ga.tour_length(ls.polish(t, D), D) < ga.tour_length(t, D)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\nTat ca {len(fns)} test PASS.")
