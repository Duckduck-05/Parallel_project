#!/usr/bin/env python3
"""ga_core.py - Task 5: Lõi Giải thuật Di truyền (GA) cho bài toán TSP.

Đây là phần "tuần tự" dùng chung cho cả bản đảo song song (Task 6, 7).
Các toán tử GA: chọn lọc giải đấu (tournament), lai ghép thứ tự (OX),
đột biến (đổi chỗ + đảo đoạn kiểu 2-opt), và vòng tiến hóa có giữ tinh hoa (elitism).
"""
import numpy as np


def read_cities(path):
    """Đọc file toạ độ thành phố. Mỗi dòng: 'x y' (bỏ dòng trống / bắt đầu bằng #)."""
    pts = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            x, y = line.split()[:2]
            pts.append((float(x), float(y)))
    return np.array(pts, dtype=float)


def distance_matrix(coords):
    """Ma trận khoảng cách Euclid NxN giữa mọi cặp thành phố."""
    diff = coords[:, None, :] - coords[None, :, :]
    return np.sqrt((diff ** 2).sum(axis=2))


def tour_length(tour, D):
    """Tổng độ dài lộ trình khép kín (quay về điểm đầu)."""
    return float(D[tour, np.roll(tour, -1)].sum())


def random_tour(n, rng):
    """Một lộ trình ngẫu nhiên: hoán vị của 0..n-1."""
    return rng.permutation(n)


def tournament_select(pop, lengths, k, rng):
    """Chọn k cá thể ngẫu nhiên, trả về bản sao của cá thể tốt nhất (tour ngắn nhất)."""
    idx = rng.integers(0, len(pop), size=k)
    best = min(idx, key=lambda i: lengths[i])
    return pop[best].copy()


def order_crossover(p1, p2, rng):
    """Lai ghép thứ tự (OX): giữ một đoạn của p1, điền phần còn lại theo thứ tự của p2.
    Bảo đảm con là hoán vị hợp lệ (đủ và không trùng thành phố)."""
    n = len(p1)
    a, b = sorted(rng.integers(0, n, size=2))
    child = -np.ones(n, dtype=int)
    child[a:b + 1] = p1[a:b + 1]
    taken = set(p1[a:b + 1].tolist())
    fill = [c for c in p2 if c not in taken]
    j = 0
    for i in range(n):
        if child[i] == -1:
            child[i] = fill[j]
            j += 1
    return child


def mutate(tour, rate, rng):
    """Đột biến tại chỗ: đổi chỗ 2 thành phố, và đảo ngược 1 đoạn (kiểu 2-opt)."""
    if rng.random() < rate:
        i, j = rng.integers(0, len(tour), size=2)
        tour[i], tour[j] = tour[j], tour[i]
    if rng.random() < rate:
        i, j = sorted(rng.integers(0, len(tour), size=2))
        tour[i:j + 1] = tour[i:j + 1][::-1]


def evolve(D, pop_size, generations, rng,
           elite=1, tournament_k=5, mutation_rate=0.3, on_generation=None):
    """Vòng tiến hóa GA. Trả về (tour tốt nhất, độ dài, lịch sử độ dài tốt nhất mỗi thế hệ).

    on_generation(gen, pop): callback tùy chọn, có thể sửa `pop` tại chỗ
    (dùng cho di cư ở Task 7). Được gọi sau khi sinh quần thể mới mỗi thế hệ.
    """
    n = D.shape[0]
    pop = [random_tour(n, rng) for _ in range(pop_size)]
    lengths = [tour_length(t, D) for t in pop]
    history = []

    for gen in range(generations):
        order = np.argsort(lengths)
        pop = [pop[i] for i in order]
        lengths = [lengths[i] for i in order]       # giữ lengths khớp với pop sau khi sắp xếp
        new_pop = pop[:elite]                       # giữ tinh hoa
        while len(new_pop) < pop_size:
            p1 = tournament_select(pop, lengths, tournament_k, rng)
            p2 = tournament_select(pop, lengths, tournament_k, rng)
            child = order_crossover(p1, p2, rng)
            mutate(child, mutation_rate, rng)
            new_pop.append(child)
        pop = new_pop

        if on_generation is not None:
            on_generation(gen, pop)                 # móc di cư (Task 7)

        lengths = [tour_length(t, D) for t in pop]
        history.append(min(lengths))

    best = int(np.argmin(lengths))
    return pop[best], lengths[best], history
