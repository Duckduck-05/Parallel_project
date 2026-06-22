// ga_core.hpp - Task 5: Lõi GA cho TSP (bản C++), dùng chung cho bản MPI.
// Cùng thuật toán với python/ga_core.py: OX crossover, tournament, mutation, elitism.
#pragma once
#include <vector>
#include <random>
#include <algorithm>
#include <cmath>
#include <numeric>
#include <fstream>
#include <sstream>
#include <string>

using Tour = std::vector<int>;

// Đọc file toạ độ "x y" mỗi dòng (bỏ dòng trống / bắt đầu bằng #).
inline std::vector<std::pair<double,double>> read_cities(const std::string& path) {
    std::vector<std::pair<double,double>> pts;
    std::ifstream f(path);
    std::string line;
    while (std::getline(f, line)) {
        if (line.empty() || line[0] == '#') continue;
        std::istringstream ss(line);
        double x, y;
        if (ss >> x >> y) pts.emplace_back(x, y);
    }
    return pts;
}

// Ma trận khoảng cách Euclid phẳng NxN (truy cập D[i*n+j]).
inline std::vector<double> distance_matrix(const std::vector<std::pair<double,double>>& c) {
    int n = (int)c.size();
    std::vector<double> D(n * n);
    for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++) {
            double dx = c[i].first - c[j].first, dy = c[i].second - c[j].second;
            D[i * n + j] = std::sqrt(dx * dx + dy * dy);
        }
    return D;
}

// Tổng độ dài lộ trình khép kín.
inline double tour_length(const Tour& t, const std::vector<double>& D, int n) {
    double s = 0.0;
    for (int i = 0; i < n; i++) s += D[t[i] * n + t[(i + 1) % n]];
    return s;
}

inline Tour random_tour(int n, std::mt19937& rng) {
    Tour t(n);
    std::iota(t.begin(), t.end(), 0);
    std::shuffle(t.begin(), t.end(), rng);
    return t;
}

// Chọn lọc giải đấu: trả về bản sao cá thể tốt nhất trong k cá thể ngẫu nhiên.
inline Tour tournament_select(const std::vector<Tour>& pop,
                              const std::vector<double>& len, int k, std::mt19937& rng) {
    std::uniform_int_distribution<int> pick(0, (int)pop.size() - 1);
    int best = pick(rng);
    for (int i = 1; i < k; i++) {
        int c = pick(rng);
        if (len[c] < len[best]) best = c;
    }
    return pop[best];
}

// Lai ghép thứ tự (OX): giữ đoạn [a,b] của p1, điền phần còn lại theo thứ tự p2.
inline Tour order_crossover(const Tour& p1, const Tour& p2, std::mt19937& rng) {
    int n = (int)p1.size();
    std::uniform_int_distribution<int> pick(0, n - 1);
    int a = pick(rng), b = pick(rng);
    if (a > b) std::swap(a, b);
    Tour child(n, -1);
    std::vector<char> taken(n, 0);
    for (int i = a; i <= b; i++) { child[i] = p1[i]; taken[p1[i]] = 1; }
    int j = 0;
    for (int i = 0; i < n; i++) {
        if (child[i] != -1) continue;
        while (j < n && taken[p2[j]]) j++;   // chặn tràn mảng nếu p2 không phải hoán vị hợp lệ
        child[i] = p2[j++];
    }
    return child;
}

// Đột biến: đổi chỗ 2 thành phố + đảo ngược 1 đoạn (kiểu 2-opt).
inline void mutate(Tour& t, double rate, std::mt19937& rng) {
    std::uniform_real_distribution<double> prob(0.0, 1.0);
    std::uniform_int_distribution<int> pick(0, (int)t.size() - 1);
    if (prob(rng) < rate) std::swap(t[pick(rng)], t[pick(rng)]);
    if (prob(rng) < rate) {
        int a = pick(rng), b = pick(rng);
        if (a > b) std::swap(a, b);
        std::reverse(t.begin() + a, t.begin() + b + 1);
    }
}

// Một thế hệ tiến hóa (in-place trên pop & len). Tách riêng để bản MPI tái dùng.
inline void evolve_one_gen(std::vector<Tour>& pop, std::vector<double>& len,
                           const std::vector<double>& D, int n,
                           int elite, int k, double mut, std::mt19937& rng) {
    std::vector<int> order(pop.size());
    std::iota(order.begin(), order.end(), 0);
    std::sort(order.begin(), order.end(),
              [&](int a, int b) { return len[a] < len[b]; });
    std::vector<Tour> np;
    np.reserve(pop.size());
    for (int i = 0; i < elite; i++) np.push_back(pop[order[i]]);
    while ((int)np.size() < (int)pop.size()) {
        Tour p1 = tournament_select(pop, len, k, rng);
        Tour p2 = tournament_select(pop, len, k, rng);
        Tour child = order_crossover(p1, p2, rng);
        mutate(child, mut, rng);
        np.push_back(std::move(child));
    }
    pop.swap(np);
    for (size_t i = 0; i < pop.size(); i++) len[i] = tour_length(pop[i], D, n);
}
