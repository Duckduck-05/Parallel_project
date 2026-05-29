#!/usr/bin/env python3
"""local_search.py - Tối ưu cục bộ 2-opt + Or-opt cho TSP (biến GA -> Memetic Algorithm).

Ý tưởng: sau khi GA sinh ra cá thể, ta "đánh bóng" nó bằng tìm kiếm cục bộ để gỡ các
cạnh chéo (2-opt) và dời các đoạn ngắn sang vị trí tốt hơn (Or-opt). Memetic = GA (tìm
kiếm toàn cục) + local search (tìm kiếm cục bộ) -> hội tụ nhanh & sâu hơn nhiều.
"""
import numpy as np


def two_opt_once(tour, D, max_no_improve=None):
    """Một lượt 2-opt theo chiến lược first-improvement: đảo ngược đoạn [i+1, j]
    nếu việc đó làm tour ngắn hơn. Trả về (tour mới, có cải thiện không).

    2-opt loại bỏ phép giao nhau: thay 2 cạnh (a-b) và (c-d) bằng (a-c) và (b-d)
    rồi đảo đoạn ở giữa. Độ phức tạp 1 lượt O(n^2).
    """
    n = len(tour)
    t = tour.copy()
    improved = False
    for i in range(n - 1):
        a, b = t[i], t[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue                       # không tách cạnh khép kín đầu-cuối
            c, d = t[j], t[(j + 1) % n]
            # delta = (cạnh mới) - (cạnh cũ); <0 nghĩa là ngắn hơn
            delta = (D[a, c] + D[b, d]) - (D[a, b] + D[c, d])
            if delta < -1e-9:
                t[i + 1:j + 1] = t[i + 1:j + 1][::-1]
                improved = True
                break
        if improved:
            break
    return t, improved


def two_opt(tour, D, max_iter=1000):
    """Lặp 2-opt đến khi không cải thiện được nữa (đạt cực tiểu cục bộ) hoặc hết max_iter."""
    t = tour.copy()
    for _ in range(max_iter):
        t, improved = two_opt_once(t, D)
        if not improved:
            break
    return t


def or_opt(tour, D, seg_len=1, max_iter=200):
    """Or-opt: dời một đoạn liên tiếp dài seg_len sang vị trí khác nếu giảm độ dài.
    Bổ trợ cho 2-opt (2-opt không di chuyển được các đoạn ngắn hiệu quả)."""
    n = len(tour)
    t = tour.copy()
    for _ in range(max_iter):
        improved = False
        for i in range(n):
            seg = [t[(i + k) % n] for k in range(seg_len)]
            prev = t[(i - 1) % n]
            nxt = t[(i + seg_len) % n]
            removed = D[prev, seg[0]] + D[seg[-1], nxt] - D[prev, nxt]
            rest = [c for c in t if c not in seg]
            for p in range(len(rest)):
                a, b = rest[p], rest[(p + 1) % len(rest)]
                added = D[a, seg[0]] + D[seg[-1], b] - D[a, b]
                if added - removed < -1e-9:
                    t = np.array(rest[:p + 1] + seg + rest[p + 1:])
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break
    return t


def polish(tour, D, seg_len=2):
    """Đánh bóng cá thể: chạy 2-opt rồi Or-opt. Dùng trong Memetic-GA."""
    t = two_opt(tour, D)
    t = or_opt(t, D, seg_len=seg_len)
    return t
