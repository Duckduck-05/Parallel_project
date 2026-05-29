// test_ga_core.cpp - Task 5: Unit test cho lõi GA bản C++.
// Biên dịch: g++ -O2 -o test_ga test_ga_core.cpp && ./test_ga
#include "ga_core.hpp"
#include <iostream>
#include <cassert>

static int passed = 0;
#define CHECK(cond, name) do { if (!(cond)) { \
    std::cerr << "FAIL " << name << "\n"; return 1; } \
    std::cout << "OK  " << name << "\n"; passed++; } while (0)

static bool is_permutation(const Tour& t, int n) {
    std::vector<char> seen(n, 0);
    for (int c : t) { if (c < 0 || c >= n || seen[c]) return false; seen[c] = 1; }
    return (int)t.size() == n;
}

int main() {
    // 4 thanh pho goc hinh vuong canh 1
    std::vector<std::pair<double,double>> sq = {{0,0},{0,1},{1,1},{1,0}};
    auto D = distance_matrix(sq);

    CHECK(std::abs(D[0*4+0]) < 1e-9, "distance_matrix_diag_zero");
    CHECK(std::abs(tour_length({0,1,2,3}, D, 4) - 4.0) < 1e-9, "tour_length_known");
    CHECK(tour_length({0,2,1,3}, D, 4) > 4.0, "diagonal_longer");

    std::mt19937 rng(0);
    Tour p1 = {0,1,2,3,4,5}, p2 = {5,4,3,2,1,0};
    for (int i = 0; i < 100; i++)
        CHECK(is_permutation(order_crossover(p1, p2, rng), 6), "ox_valid_perm");

    for (int i = 0; i < 100; i++) {
        Tour t = random_tour(8, rng);
        mutate(t, 1.0, rng);
        CHECK(is_permutation(t, 8), "mutate_keeps_perm");
    }

    // evolve cải thiện so với tour ngẫu nhiên
    std::mt19937 r2(7);
    std::vector<std::pair<double,double>> pts;
    std::uniform_real_distribution<double> u(0, 1);
    for (int i = 0; i < 20; i++) pts.emplace_back(u(r2), u(r2));
    auto D2 = distance_matrix(pts);
    double start = tour_length(random_tour(20, r2), D2, 20);
    std::vector<Tour> pop(80);
    std::vector<double> len(80);
    for (int i = 0; i < 80; i++) { pop[i] = random_tour(20, r2); len[i] = tour_length(pop[i], D2, 20); }
    for (int g = 0; g < 150; g++) evolve_one_gen(pop, len, D2, 20, 1, 5, 0.3, r2);
    double best = *std::min_element(len.begin(), len.end());
    CHECK(best < start, "evolve_improves");

    std::cout << "\nTat ca test PASS (" << passed << " kiem tra).\n";
    return 0;
}
