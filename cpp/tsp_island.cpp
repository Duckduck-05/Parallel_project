// tsp_island.cpp - Task 6 & 7: Island-model GA cho TSP song song bằng MPI (C++).
// Cùng thuật toán với python/tsp_island.py: ring migration (Sendrecv) + Reduce(MINLOC).
//
// Biên dịch: mpicxx -O2 -o tsp_island tsp_island.cpp
// Chạy 1 máy: mpirun -np 3 ./tsp_island ../data/cities_30.txt --gens 500 --migrate 20
// Chạy cụm:  mpirun --hostfile ../cluster/hosts -np 3 ./tsp_island ../data/cities_30.txt
// Task 6 (không di cư): --migrate 0
#include "ga_core.hpp"
#include "local_search.hpp"
#include <mpi.h>
#include <iostream>
#include <cstring>

int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);
    int rank, size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    // --- doc tham so ---
    std::string path = argc > 1 ? argv[1] : "../data/cities_30.txt";
    int gens = 500, pop_size = 200, migrate = 20, twoopt = 0;
    unsigned seed = 42;
    for (int i = 2; i < argc - 1; i++) {
        std::string a = argv[i];
        if (a == "--gens") gens = std::stoi(argv[++i]);
        else if (a == "--pop") pop_size = std::stoi(argv[++i]);
        else if (a == "--migrate") migrate = std::stoi(argv[++i]);
        else if (a == "--twoopt") twoopt = std::stoi(argv[++i]);
        else if (a == "--seed") seed = std::stoul(argv[++i]);
    }

    auto coords = read_cities(path);
    int n = (int)coords.size();
    auto D = distance_matrix(coords);
    std::mt19937 rng(seed + rank * 1000);   // moi dao 1 seed
    int left = (rank - 1 + size) % size, right = (rank + 1) % size;

    std::vector<Tour> pop(pop_size);
    std::vector<double> len(pop_size);
    for (int i = 0; i < pop_size; i++) {
        pop[i] = random_tour(n, rng);
        len[i] = tour_length(pop[i], D, n);
    }

    MPI_Barrier(MPI_COMM_WORLD);
    double t0 = MPI_Wtime();

    std::vector<int> sendbuf(n), recvbuf(n);
    for (int g = 0; g < gens; g++) {
        evolve_one_gen(pop, len, D, n, 1, 5, 0.3, rng);

        // --- MEMETIC: danh bong ca the tot nhat bang 2-opt (Task mo rong) ---
        if (twoopt > 0 && (g + 1) % twoopt == 0) {
            int bi = (int)(std::min_element(len.begin(), len.end()) - len.begin());
            polish(pop[bi], D, n);
            len[bi] = tour_length(pop[bi], D, n);
        }

        // --- DI CU vong ring (Task 7) ---
        if (migrate > 0 && (g + 1) % migrate == 0 && size > 1) {
            int bi = (int)(std::min_element(len.begin(), len.end()) - len.begin());
            sendbuf = pop[bi];
            // Sendrecv: gui sang phai, nhan tu trai, tranh deadlock.
            MPI_Sendrecv(sendbuf.data(), n, MPI_INT, right, 0,
                         recvbuf.data(), n, MPI_INT, left, 0,
                         MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            int wi = (int)(std::max_element(len.begin(), len.end()) - len.begin());
            double in_len = tour_length(recvbuf, D, n);
            if (in_len < len[wi]) {            // chi nhan neu khach tot hon ca the te nhat
                pop[wi] = recvbuf;             // thay ca the te nhat
                len[wi] = in_len;
            }
        }
    }

    MPI_Barrier(MPI_COMM_WORLD);
    double elapsed = MPI_Wtime() - t0;

    // --- Gom ket qua: Reduce(MINLOC) tim dao co tour ngan nhat ---
    int bi = (int)(std::min_element(len.begin(), len.end()) - len.begin());
    struct { double val; int rank; } in{len[bi], rank}, out;
    MPI_Allreduce(&in, &out, 1, MPI_DOUBLE_INT, MPI_MINLOC, MPI_COMM_WORLD);

    // dao thang gui tour ve rank 0
    std::vector<int> best_tour = pop[bi];
    if (out.rank != 0) {
        if (rank == out.rank)
            MPI_Send(best_tour.data(), n, MPI_INT, 0, 99, MPI_COMM_WORLD);
        else if (rank == 0) {
            best_tour.resize(n);
            MPI_Recv(best_tour.data(), n, MPI_INT, out.rank, 99,
                     MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        }
    }

    if (rank == 0) {
        std::cout << "So dao (process): " << size
                  << "  |  che do: " << (migrate > 0 ? "co di cu" : "KHONG di cu") << "\n"
                  << "So thanh pho     : " << n << ", the he: " << gens
                  << ", quan the/dao: " << pop_size << "\n"
                  << "Do dai tot nhat  : " << out.val << "  (tu dao #" << out.rank << ")\n"
                  << "Thoi gian        : " << elapsed << "s\n";
        std::cout << "Lo trinh         :";
        for (int c : best_tour) std::cout << " " << c;
        std::cout << "\n";
    }

    MPI_Finalize();
    return 0;
}
