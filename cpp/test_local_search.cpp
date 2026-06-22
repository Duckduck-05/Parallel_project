// test_local_search.cpp - Unit test for 2-opt / Or-opt (C++).
// Compile: g++ -O2 -o test_ls test_local_search.cpp && ./test_ls
#include "local_search.hpp"
#include <iostream>

static int passed = 0;
#define CHECK(cond, name) do { if (!(cond)) { \
    std::cerr << "FAIL " << name << "\n"; return 1; } \
    passed++; } while (0)

static bool is_perm(const Tour& t, int n) {
    std::vector<char> seen(n, 0);
    for (int c : t) { if (c < 0 || c >= n || seen[c]) return false; seen[c] = 1; }
    return (int)t.size() == n;
}

int main() {
    std::mt19937 rng(0);

    // 2-opt fixes the crossing back to perimeter 4
    std::vector<std::pair<double,double>> sq = {{0,0},{0,1},{1,1},{1,0}};
    auto Dsq = distance_matrix(sq);
    Tour crossed = {0, 2, 1, 3};
    two_opt(crossed, Dsq, 4);
    CHECK(std::abs(tour_length(crossed, Dsq, 4) - 4.0) < 1e-9, "two_opt_fixes_crossing");

    // 2-opt & or-opt do not make it worse, and preserve the permutation
    std::vector<std::pair<double,double>> pts;
    std::uniform_real_distribution<double> u(0, 1);
    for (int i = 0; i < 20; i++) pts.emplace_back(u(rng), u(rng));
    auto D = distance_matrix(pts);
    for (int rep = 0; rep < 30; rep++) {
        Tour t = random_tour(20, rng);
        double before = tour_length(t, D, 20);
        Tour t2 = t; two_opt(t2, D, 20);
        CHECK(is_perm(t2, 20), "two_opt_perm");
        CHECK(tour_length(t2, D, 20) <= before + 1e-9, "two_opt_not_worse");
        Tour t3 = t; or_opt(t3, D, 20);
        CHECK(is_perm(t3, 20), "or_opt_perm");
        CHECK(tour_length(t3, D, 20) <= before + 1e-9, "or_opt_not_worse");
    }

    // polish improves a random tour
    Tour t = random_tour(20, rng);
    double before = tour_length(t, D, 20);
    polish(t, D, 20);
    CHECK(tour_length(t, D, 20) < before, "polish_improves");

    std::cout << "All tests passed (" << passed << " checks).\n";
    return 0;
}
