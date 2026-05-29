// local_search.hpp - Tối ưu cục bộ 2-opt + Or-opt cho TSP (bản C++).
// Cùng ý tưởng với python/local_search.py: biến GA -> Memetic Algorithm.
#pragma once
#include "ga_core.hpp"

// Một lượt 2-opt (first-improvement): đảo đoạn [i+1, j] nếu làm tour ngắn hơn.
inline bool two_opt_once(Tour& t, const std::vector<double>& D, int n) {
    for (int i = 0; i < n - 1; i++) {
        int a = t[i], b = t[(i + 1) % n];
        for (int j = i + 2; j < n; j++) {
            if (i == 0 && j == n - 1) continue;       // giu canh khep kin
            int c = t[j], d = t[(j + 1) % n];
            double delta = (D[a * n + c] + D[b * n + d]) - (D[a * n + b] + D[c * n + d]);
            if (delta < -1e-9) {
                std::reverse(t.begin() + i + 1, t.begin() + j + 1);
                return true;
            }
        }
    }
    return false;
}

// Lặp 2-opt đến cực tiểu cục bộ.
inline void two_opt(Tour& t, const std::vector<double>& D, int n, int max_iter = 1000) {
    for (int it = 0; it < max_iter; it++)
        if (!two_opt_once(t, D, n)) break;
}

// Or-opt: dời 1 thành phố sang vị trí tốt hơn (seg_len = 1, bổ trợ 2-opt).
inline bool or_opt_once(Tour& t, const std::vector<double>& D, int n) {
    for (int i = 0; i < n; i++) {
        int prev = t[(i - 1 + n) % n], cur = t[i], nxt = t[(i + 1) % n];
        double removed = D[prev * n + cur] + D[cur * n + nxt] - D[prev * n + nxt];
        for (int j = 0; j < n; j++) {
            if (j == i || j == (i - 1 + n) % n) continue;
            int a = t[j], b = t[(j + 1) % n];
            double added = D[a * n + cur] + D[cur * n + b] - D[a * n + b];
            if (added - removed < -1e-9) {
                Tour nt;
                nt.reserve(n);
                for (int k = 0; k < n; k++) {
                    if (k == i) continue;
                    nt.push_back(t[k]);
                    if (t[k] == a) nt.push_back(cur);
                }
                if ((int)nt.size() == n) { t.swap(nt); return true; }
            }
        }
    }
    return false;
}

inline void or_opt(Tour& t, const std::vector<double>& D, int n, int max_iter = 200) {
    for (int it = 0; it < max_iter; it++)
        if (!or_opt_once(t, D, n)) break;
}

// Đánh bóng cá thể: 2-opt rồi Or-opt.
inline void polish(Tour& t, const std::vector<double>& D, int n) {
    two_opt(t, D, n);
    or_opt(t, D, n);
}
