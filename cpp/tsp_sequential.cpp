// tsp_sequential.cpp - Task 5: Run sequential GA (C++) for one TSP instance.
// Compile: g++ -O2 -o tsp_seq tsp_sequential.cpp
// Run:     ./tsp_seq ../data/cities_30.txt 300 150 42
#include "ga_core.hpp"
#include <iostream>
#include <chrono>

int main(int argc, char** argv) {
    if (argc < 2) { std::cerr << "Usage: " << argv[0]
        << " <file_cities> [gens] [pop] [seed]\n"; return 1; }
    std::string path = argv[1];
    int gens = argc > 2 ? std::stoi(argv[2]) : 500;
    int pop_size = argc > 3 ? std::stoi(argv[3]) : 200;
    unsigned seed = argc > 4 ? std::stoul(argv[4]) : 42;

    auto coords = read_cities(path);
    int n = (int)coords.size();
    auto D = distance_matrix(coords);
    std::mt19937 rng(seed);

    std::vector<Tour> pop(pop_size);
    std::vector<double> len(pop_size);
    for (int i = 0; i < pop_size; i++) {
        pop[i] = random_tour(n, rng);
        len[i] = tour_length(pop[i], D, n);
    }

    auto t0 = std::chrono::high_resolution_clock::now();
    for (int g = 0; g < gens; g++)
        evolve_one_gen(pop, len, D, n, 1, 5, 0.3, rng);
    auto t1 = std::chrono::high_resolution_clock::now();

    int best = (int)(std::min_element(len.begin(), len.end()) - len.begin());
    double secs = std::chrono::duration<double>(t1 - t0).count();
    std::cout << "Cities         : " << n << "\n"
              << "Generations    : " << gens << ", population: " << pop_size << "\n"
              << "Best length    : " << len[best] << "\n"
              << "Time            : " << secs << "s\n";
    std::cout << "Route           :";
    for (int c : pop[best]) std::cout << " " << c;
    std::cout << "\n";
    return 0;
}
