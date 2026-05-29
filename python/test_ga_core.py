#!/usr/bin/env python3
"""test_ga_core.py - Task 5: Unit test cho lõi GA.
Chạy: cd python && python3 -m pytest test_ga_core.py -v
Hoặc:  python3 test_ga_core.py  (chạy không cần pytest)
"""
import numpy as np
import ga_core as ga


def _square_D():
    # 4 thanh pho o 4 goc hinh vuong canh 1 -> chu vi toi uu = 4.0
    coords = np.array([[0, 0], [0, 1], [1, 1], [1, 0]], dtype=float)
    return coords, ga.distance_matrix(coords)


def test_distance_matrix_symmetric():
    _, D = _square_D()
    assert np.allclose(D, D.T)
    assert np.allclose(np.diag(D), 0)


def test_tour_length_known():
    _, D = _square_D()
    # di vong quanh chu vi = 4 canh dai 1
    assert abs(ga.tour_length(np.array([0, 1, 2, 3]), D) - 4.0) < 1e-9
    # duong cheo: 0->2->1->3->0 dai hon
    assert ga.tour_length(np.array([0, 2, 1, 3]), D) > 4.0


def test_ox_valid_permutation():
    rng = np.random.default_rng(0)
    p1 = np.array([0, 1, 2, 3, 4, 5])
    p2 = np.array([5, 4, 3, 2, 1, 0])
    for _ in range(100):
        child = ga.order_crossover(p1, p2, rng)
        # con phai la hoan vi hop le: du va khong trung
        assert sorted(child.tolist()) == [0, 1, 2, 3, 4, 5]


def test_mutate_keeps_permutation():
    rng = np.random.default_rng(1)
    for _ in range(100):
        tour = rng.permutation(8)
        ga.mutate(tour, rate=1.0, rng=rng)
        assert sorted(tour.tolist()) == list(range(8))


def test_evolve_improves():
    # GA phai cho tour tot hon (ngan hon) tour ngau nhien ban dau
    rng = np.random.default_rng(7)
    coords = rng.random((20, 2))
    D = ga.distance_matrix(coords)
    start = ga.tour_length(ga.random_tour(20, rng), D)
    _, best, history = ga.evolve(D, pop_size=80, generations=150, rng=rng)
    assert best < start            # co cai thien
    assert history[-1] <= history[0]  # khong te di theo thoi gian


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\nTat ca {len(fns)} test PASS.")
