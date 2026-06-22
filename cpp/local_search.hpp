// local_search.hpp - Local optimization 2-opt + Or-opt for TSP (C++ version).
// Same idea as python/local_search.py: turns the GA into a Memetic Algorithm.
#pragma once
#include "ga_core.hpp"

// One 2-opt pass (first-improvement): reverse segment [i+1, j] if it shortens the tour.
inline bool two_opt_once(Tour& t, const std::vector<double>& D, int n) {
    for (int i = 0; i < n - 1; i++) {
        int a = t[i], b = t[(i + 1) % n];
        for (int j = i + 2; j < n; j++) {
            if (i == 0 && j == n - 1) continue;       // keep the closing edge
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

// Iterate 2-opt until a local minimum is reached.
inline void two_opt(Tour& t, const std::vector<double>& D, int n, int max_iter = 1000) {
    for (int it = 0; it < max_iter; it++)
        if (!two_opt_once(t, D, n)) break;
}

// Or-opt: move one contiguous segment of length seg_len to a better position (complements 2-opt).
// Same logic as python/local_search.py: the segment is taken with wrap-around, reinserted WITHOUT reversal.
inline bool or_opt_once(Tour& t, const std::vector<double>& D, int n, int seg_len) {
    for (int i = 0; i < n; i++) {
        Tour seg(seg_len);
        for (int k = 0; k < seg_len; k++) seg[k] = t[(i + k) % n];
        int prev = t[(i - 1 + n) % n], nxt = t[(i + seg_len) % n];
        double removed = D[prev * n + seg[0]] + D[seg[seg_len - 1] * n + nxt]
                         - D[prev * n + nxt];
        // rest = the cities not contained in seg (compared by city value)
        std::vector<char> in_seg(n, 0);
        for (int c : seg) in_seg[c] = 1;
        Tour rest;
        rest.reserve(n - seg_len);
        for (int k = 0; k < n; k++) if (!in_seg[t[k]]) rest.push_back(t[k]);
        int m = (int)rest.size();
        for (int p = 0; p < m; p++) {
            int a = rest[p], b = rest[(p + 1) % m];
            double added = D[a * n + seg[0]] + D[seg[seg_len - 1] * n + b] - D[a * n + b];
            if (added - removed < -1e-9) {
                Tour nt;
                nt.reserve(n);
                for (int k = 0; k <= p; k++) nt.push_back(rest[k]);
                for (int c : seg) nt.push_back(c);
                for (int k = p + 1; k < m; k++) nt.push_back(rest[k]);
                t.swap(nt);
                return true;
            }
        }
    }
    return false;
}

inline void or_opt(Tour& t, const std::vector<double>& D, int n,
                   int seg_len = 1, int max_iter = 200) {
    for (int it = 0; it < max_iter; it++)
        if (!or_opt_once(t, D, n, seg_len)) break;
}

// Polish an individual: 2-opt then Or-opt (seg_len=2, matching python/local_search.py).
inline void polish(Tour& t, const std::vector<double>& D, int n) {
    two_opt(t, D, n);
    or_opt(t, D, n, 2);
}
