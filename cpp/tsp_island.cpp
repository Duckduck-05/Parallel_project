// tsp_island.cpp - Island-model GA for the TSP, parallelized with MPI (C++).
//
// PARALLEL DESIGN: periodic GLOBAL-BEST BROADCAST + early stop on stagnation.
//   - Each process is an independent "island" running its own GA with its own seed,
//     so the islands explore different regions of the solution space in parallel.
//   - Every --sync generations the islands share results: Allreduce(MINLOC) finds the
//     single global-best tour across all islands and its owner Bcasts it. But instead of
//     cloning that whole tour into every island (which collapses diversity), each other
//     island performs PARTIAL migration: it splices only a random CONTIGUOUS SEGMENT of the
//     global best into --migrants of its individuals via OX crossover (segment from the best,
//     the rest from a random local individual). Random cut points + different local mates mean
//     every island ends up different, so good sub-routes spread while diversity is preserved.
//   - CONVERGENCE STOP: the global best is known to every rank at each sync (identical
//     value everywhere), so all ranks can agree to stop together once the global best has
//     not improved for --patience generations. No extra communication, no deadlock.
//   - --sync 0 disables sharing (embarrassingly-parallel baseline; also disables the stop).
//
// This is the MAIN SOURCE of the project (the whole algorithm + parallelization in C++).
// Python is used only for visualization / plotting (it reads the --out / --stats / --live
// files produced here).
//
// Build: mpicxx -O2 -std=c++17 -o tsp_island tsp_island.cpp   (or: make)
// Run on one machine: mpirun -np 4 ./tsp_island ../data/cities_30.txt --gens 500 --sync 20
// Run on a cluster:   mpirun --hostfile ../cluster/hosts -np 4 ./tsp_island ../data/cities_30.txt
// Baseline (no sharing): --sync 0
#include "ga_core.hpp"
#include "local_search.hpp"
#include <mpi.h>
#include <iostream>
#include <fstream>
#include <iomanip>
#include <algorithm>
#include <string>
#include <vector>

// Write one JSONL line for live_view.py to "tail" (rank 0 only). Adds no MPI traffic.
static void write_live_line(std::ofstream& f, int gen, double best_len,
                            const Tour& tour, bool done) {
    f << "{\"gen\": " << gen << ", \"best_len\": " << best_len << ", \"tour\": [";
    for (size_t i = 0; i < tour.size(); i++) {
        if (i) f << ", ";
        f << tour[i];
    }
    f << "]";
    if (done) f << ", \"done\": true";
    f << "}\n";
    f.flush();   // line-buffered so the tailing viewer sees it immediately
}

int main(int argc, char** argv) {
    MPI_Init(&argc, &argv);
    int rank, size;
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);

    // --- parse arguments ---
    std::string path = argc > 1 ? argv[1] : "../data/cities_30.txt";
    int gens = 500, pop_size = 200, sync = 20, twoopt = 0, patience = 0, migrants = 3;
    unsigned seed = 42;
    bool auto_balance = false;
    std::string out_file, stats_file, live_file;
    for (int i = 2; i < argc; i++) {
        std::string a = argv[i];
        if (a == "--gens" && i + 1 < argc) gens = std::stoi(argv[++i]);
        else if (a == "--pop" && i + 1 < argc) pop_size = std::stoi(argv[++i]);
        // --sync is the new name; --migrate kept as an alias for older scripts.
        else if ((a == "--sync" || a == "--migrate") && i + 1 < argc) sync = std::stoi(argv[++i]);
        else if (a == "--patience" && i + 1 < argc) patience = std::stoi(argv[++i]);
        else if (a == "--migrants" && i + 1 < argc) migrants = std::stoi(argv[++i]);
        else if (a == "--twoopt" && i + 1 < argc) twoopt = std::stoi(argv[++i]);
        else if (a == "--seed" && i + 1 < argc) seed = std::stoul(argv[++i]);
        else if (a == "--out" && i + 1 < argc) out_file = argv[++i];
        else if (a == "--stats" && i + 1 < argc) stats_file = argv[++i];
        else if (a == "--live" && i + 1 < argc) live_file = argv[++i];
        else if (a == "--auto-balance") auto_balance = true;
    }

    auto coords = read_cities(path);
    int n = (int)coords.size();
    auto D = distance_matrix(coords);
    // Each island gets a different seed -> searches a different region of the solution space.
    std::mt19937 rng(seed + rank * 1000);

    // --- AUTO-BALANCE: measure each machine's speed, then split the population inversely
    // to the measured time (faster machine -> bigger population), keeping the total constant.
    // The ratio is clamped to [0.5x, 2x] of --pop so one noisy measurement cannot wreck the
    // balance. Off by default so it does not affect the old benchmarks.
    if (auto_balance && size > 1) {
        const int BENCH_POP = 100, BENCH_GENS = 15, BENCH_REPS = 2;
        double best_t = 1e30;
        for (int rep = 0; rep < BENCH_REPS; rep++) {
            std::vector<Tour> bp(BENCH_POP);
            std::vector<double> bl(BENCH_POP);
            for (int i = 0; i < BENCH_POP; i++) {
                bp[i] = random_tour(n, rng);
                bl[i] = tour_length(bp[i], D, n);
            }
            double t = MPI_Wtime();
            for (int g = 0; g < BENCH_GENS; g++)
                evolve_one_gen(bp, bl, D, n, 1, 5, 0.3, rng);
            best_t = std::min(best_t, MPI_Wtime() - t);   // keep the fastest run (least noise)
        }
        best_t = std::max(best_t, 1e-6);
        std::vector<double> all_t(size);
        MPI_Allgather(&best_t, 1, MPI_DOUBLE, all_t.data(), 1, MPI_DOUBLE, MPI_COMM_WORLD);
        double total_speed = 0.0;
        for (double t : all_t) total_speed += 1.0 / t;
        long total_pop = (long)pop_size * size;
        int lo = pop_size / 2, hi = pop_size * 2;
        std::vector<int> raw(size);
        for (int r = 0; r < size; r++) {
            int v = (int)llround((double)total_pop * (1.0 / all_t[r]) / total_speed);
            raw[r] = std::max(lo, std::min(hi, v));
        }
        pop_size = raw[rank];
        if (rank == 0) {
            std::cout << "Auto-balance: benchmark time per island =";
            for (double t : all_t) std::cout << " " << std::fixed << std::setprecision(4) << t;
            std::cout << "\nAuto-balance: population per island     =";
            for (int v : raw) std::cout << " " << v;
            std::cout << "\n";
        }
    }

    std::vector<Tour> pop(pop_size);
    std::vector<double> len(pop_size);
    for (int i = 0; i < pop_size; i++) {
        pop[i] = random_tour(n, rng);
        len[i] = tour_length(pop[i], D, n);
    }
    std::vector<double> history;
    history.reserve(gens);

    // comm_time = total time spent inside MPI calls (sync broadcasts + result gathering).
    // compute_time = total - comm_time => feeds the "with/without communication" charts.
    double comm_time = 0.0;

    // --- LIVE: rank 0 opens a stream file so live_view.py can "tail" it in real time.
    // It only writes rank 0's LOCAL best each generation, so it adds NO MPI traffic and
    // does not distort the benchmark numbers.
    std::ofstream live_f;
    if (!live_file.empty() && rank == 0) live_f.open(live_file);

    std::vector<int> bcast_buf(n);
    double last_global = 1e30;     // best global length seen at the previous sync
    int stall = 0;                 // generations since the global best last improved
    int gens_run = 0;              // actual generations executed (may be < gens if stopped)
    bool stop = false;

    MPI_Barrier(MPI_COMM_WORLD);
    double t0 = MPI_Wtime();

    for (int g = 0; g < gens; g++) {
        evolve_one_gen(pop, len, D, n, 1, 5, 0.3, rng);

        // --- MEMETIC: polish the best individual with 2-opt (optional extension) ---
        if (twoopt > 0 && (g + 1) % twoopt == 0) {
            int bi = (int)(std::min_element(len.begin(), len.end()) - len.begin());
            polish(pop[bi], D, n);
            len[bi] = tour_length(pop[bi], D, n);
        }

        // --- SHARE RESULTS: broadcast the current GLOBAL best to every island ---
        if (sync > 0 && (g + 1) % sync == 0 && size > 1) {
            int bi = (int)(std::min_element(len.begin(), len.end()) - len.begin());
            struct { double val; int rank; } in{len[bi], rank}, out;
            double tc = MPI_Wtime();
            // 1) find the global-best (value, owner rank) across all islands
            MPI_Allreduce(&in, &out, 1, MPI_DOUBLE_INT, MPI_MINLOC, MPI_COMM_WORLD);
            // 2) the owner broadcasts that tour to everyone
            if (rank == out.rank) bcast_buf = pop[bi];
            MPI_Bcast(bcast_buf.data(), n, MPI_INT, out.rank, MPI_COMM_WORLD);
            comm_time += MPI_Wtime() - tc;
            // 3) PARTIAL migration: splice a random segment of the global best into a few
            //    individuals via OX (segment from the best + rest from a random local mate),
            //    replacing the worst slots. Keeps each island distinct -> preserves diversity.
            if (rank != out.rank) {
                const Tour& gbest = bcast_buf;
                for (int m = 0; m < migrants; m++) {
                    int wi = (int)(std::max_element(len.begin(), len.end()) - len.begin());
                    int mate = (int)(rng() % pop_size);          // random local individual
                    Tour child = order_crossover(gbest, pop[mate], rng);  // OX: keeps a segment of gbest
                    pop[wi] = std::move(child);
                    len[wi] = tour_length(pop[wi], D, n);
                }
            }
            // 4) convergence stop: identical on every rank, so all stop together
            if (out.val < last_global - 1e-6) { last_global = out.val; stall = 0; }
            else stall += sync;
            if (patience > 0 && stall >= patience) stop = true;
        }

        int bi = (int)(std::min_element(len.begin(), len.end()) - len.begin());
        history.push_back(len[bi]);
        gens_run = g + 1;

        // --- LIVE stream (rank 0): one JSON line per generation ---
        if (live_f.is_open())
            write_live_line(live_f, g + 1, len[bi], pop[bi], false);

        if (stop) break;           // all ranks reach this together (same global best)
    }

    MPI_Barrier(MPI_COMM_WORLD);
    double elapsed = MPI_Wtime() - t0;

    // --- Gather the result: Allreduce(MINLOC) finds the island with the shortest tour ---
    int bi = (int)(std::min_element(len.begin(), len.end()) - len.begin());
    struct { double val; int rank; } in{len[bi], rank}, out;
    double tc = MPI_Wtime();
    MPI_Allreduce(&in, &out, 1, MPI_DOUBLE_INT, MPI_MINLOC, MPI_COMM_WORLD);
    comm_time += MPI_Wtime() - tc;
    double global_best = out.val;
    int best_rank = out.rank;

    // The winning island sends its tour to rank 0 for printing / saving.
    std::vector<int> best_tour = pop[bi];
    if (best_rank != 0) {
        tc = MPI_Wtime();
        if (rank == best_rank)
            MPI_Send(best_tour.data(), n, MPI_INT, 0, 99, MPI_COMM_WORLD);
        else if (rank == 0) {
            best_tour.resize(n);
            MPI_Recv(best_tour.data(), n, MPI_INT, best_rank, 99,
                     MPI_COMM_WORLD, MPI_STATUS_IGNORE);
        }
        comm_time += MPI_Wtime() - tc;
    }

    // --- Per-process stats: compute = total - comm. Gathered to rank 0. ---
    double compute_time = elapsed - comm_time;
    double makespan;          // makespan = real wall-clock time = max(elapsed) over islands
    MPI_Allreduce(&elapsed, &makespan, 1, MPI_DOUBLE, MPI_MAX, MPI_COMM_WORLD);

    std::vector<double> all_compute(size), all_comm(size), all_total(size);
    std::vector<int> all_pop(size);
    MPI_Gather(&compute_time, 1, MPI_DOUBLE, all_compute.data(), 1, MPI_DOUBLE, 0, MPI_COMM_WORLD);
    MPI_Gather(&comm_time, 1, MPI_DOUBLE, all_comm.data(), 1, MPI_DOUBLE, 0, MPI_COMM_WORLD);
    MPI_Gather(&elapsed, 1, MPI_DOUBLE, all_total.data(), 1, MPI_DOUBLE, 0, MPI_COMM_WORLD);
    MPI_Gather(&pop_size, 1, MPI_INT, all_pop.data(), 1, MPI_INT, 0, MPI_COMM_WORLD);

    if (live_f.is_open()) {
        // final line = the true GLOBAL result (after gathering from the winning island)
        write_live_line(live_f, gens_run, global_best, best_tour, true);
        live_f.close();
    }

    // Per-rank convergence history (for the "islands race" demo): EVERY rank writes its own
    // local-best-per-generation file. No extra MPI communication, so timing is unaffected.
    if (!out_file.empty()) {
        std::ofstream rh(out_file + ".rank" + std::to_string(rank) + ".history");
        rh << std::fixed << std::setprecision(4);
        for (double h : history) rh << h << "\n";
    }

    if (rank == 0) {
        double comm_avg = 0.0;
        for (double c : all_comm) comm_avg += c;
        comm_avg /= size;
        std::string mode = sync > 0 ? "partial global-best migration" : "NO sharing (baseline)";
        std::string pop_label = auto_balance ? "auto (see table below)" : std::to_string(pop_size);
        bool stopped_early = gens_run < gens;
        std::cout << std::fixed;
        std::cout << "Islands (procs)  : " << size << "  |  mode: " << mode << "\n";
        std::cout << "Cities           : " << n << ", generations: " << gens_run
                  << (stopped_early ? " (converged early)" : "")
                  << ", population/island: " << pop_label << "\n";
        std::cout << std::setprecision(2)
                  << "Best length      : " << global_best << "  (from island #" << best_rank << ")\n";
        std::cout << "Time             : " << makespan << "s\n";
        std::cout << std::setprecision(4)
                  << "Comm time        : " << comm_avg << "s (avg/island)\n";
        std::cout << "Compute time     : " << (makespan - comm_avg) << "s (estimated = makespan - comm)\n";
        // per-process table (to check load balance / granularity)
        std::cout << "rank   compute_s   comm_s    total_s   pop\n";
        for (int r = 0; r < size; r++)
            std::cout << std::setw(4) << r << "   " << std::setw(8) << std::setprecision(3) << all_compute[r]
                      << "   " << std::setw(7) << std::setprecision(4) << all_comm[r]
                      << "   " << std::setw(7) << std::setprecision(3) << all_total[r]
                      << "   " << all_pop[r] << "\n";
        std::cout << "Route            :";
        for (int c : best_tour) std::cout << " " << c;
        std::cout << "\n";

        if (!out_file.empty()) {
            std::ofstream of(out_file);
            for (int c : best_tour) of << c << "\n";
            of.close();
            std::ofstream hf(out_file + ".history");
            hf << std::fixed << std::setprecision(4);
            for (double h : history) hf << h << "\n";
            hf.close();
            std::cout << "Saved tour -> " << out_file
                      << " and history -> " << out_file << ".history\n";
        }
        if (!stats_file.empty()) {
            // one CSV row per process; feeds the granularity + speedup charts in the report
            std::ofstream sf(stats_file);
            sf << "rank,n_cities,procs,gens,pop,compute_s,comm_s,total_s,makespan_s,best_len\n";
            sf << std::fixed;
            for (int r = 0; r < size; r++)
                sf << r << "," << n << "," << size << "," << gens_run << "," << all_pop[r] << ","
                   << std::setprecision(4) << all_compute[r] << ","
                   << all_comm[r] << "," << all_total[r] << "," << makespan << ","
                   << std::setprecision(2) << global_best << "\n";
            sf.close();
            std::cout << "Saved stats -> " << stats_file << "\n";
        }
    }

    MPI_Finalize();
    return 0;
}
