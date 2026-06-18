#!/usr/bin/env python3
"""tsp_island.py - Task 6 & 7: Island-model GA cho TSP chạy song song bằng MPI.

Mỗi process = 1 "đảo" chạy GA độc lập với seed riêng. Định kỳ (mỗi --migrate thế hệ)
các đảo DI CƯ cá thể tốt nhất sang đảo kế bên theo VÒNG RING (Sendrecv), thay cá thể
tệ nhất của đảo nhận. Cuối cùng gom kết quả tốt nhất toàn cục bằng MPI_Reduce(MINLOC).

Chạy 1 máy:   mpirun -np 3 python3 tsp_island.py ../data/cities_30.txt --gens 500 --migrate 20
Chạy cụm:     mpirun --hostfile ../cluster/hosts -np 3 python3 tsp_island.py ...
Task 6 (không di cư): đặt --migrate 0
"""
import argparse
import time
import numpy as np
from mpi4py import MPI
import ga_core as ga
import local_search as ls


def main():
    ap = argparse.ArgumentParser(description="Island-GA cho TSP (MPI)")
    ap.add_argument("cities")
    ap.add_argument("--gens", type=int, default=500)
    ap.add_argument("--pop", type=int, default=200)
    ap.add_argument("--migrate", type=int, default=20,
                    help="chu ky di cu (so the he); 0 = khong di cu (Task 6)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--twoopt", type=int, default=0,
                    help="chu ky danh bong 2-opt cho ca the tot nhat (Memetic); 0 = tat")
    ap.add_argument("--out", default=None, help="luu tour tot nhat toan cuc")
    args = ap.parse_args()

    comm = MPI.COMM_WORLD
    rank = comm.Get_rank()
    size = comm.Get_size()

    coords = ga.read_cities(args.cities)
    D = ga.distance_matrix(coords)
    n = len(coords)
    # Mỗi đảo seed khác nhau -> tìm kiếm ở vùng khác nhau của không gian nghiệm.
    rng = np.random.default_rng(args.seed + rank * 1000)

    left = (rank - 1) % size      # hàng xóm trái trong vòng ring
    right = (rank + 1) % size     # hàng xóm phải

    pop = [ga.random_tour(n, rng) for _ in range(args.pop)]
    lengths = [ga.tour_length(t, D) for t in pop]
    history = []

    comm.Barrier()
    t0 = MPI.Wtime()

    for gen in range(args.gens):
        # --- 1 thế hệ tiến hóa (giữ tinh hoa + tournament + OX + mutation) ---
        order = np.argsort(lengths)
        pop = [pop[i] for i in order]
        lengths = [lengths[i] for i in order]
        new_pop = pop[:1]
        while len(new_pop) < args.pop:
            p1 = ga.tournament_select(pop, lengths, 5, rng)
            p2 = ga.tournament_select(pop, lengths, 5, rng)
            child = ga.order_crossover(p1, p2, rng)
            ga.mutate(child, 0.3, rng)
            new_pop.append(child)
        pop = new_pop
        lengths = [ga.tour_length(t, D) for t in pop]

        # --- MEMETIC: danh bong ca the tot nhat bang 2-opt (Task mo rong) ---
        if args.twoopt > 0 and (gen + 1) % args.twoopt == 0:
            bi = int(np.argmin(lengths))
            polished = ls.polish(pop[bi], D)
            pop[bi] = polished
            lengths[bi] = ga.tour_length(polished, D)

        # --- DI CƯ theo vòng ring (Task 7) ---
        if args.migrate > 0 and (gen + 1) % args.migrate == 0 and size > 1:
            best_local = pop[int(np.argmin(lengths))]
            # gửi sang phải, nhận từ trái (Sendrecv = gửi+nhận đồng thời, tránh deadlock)
            incoming = comm.sendrecv(best_local.copy(), dest=right, source=left)
            worst = int(np.argmax(lengths))      # thay cá thể tệ nhất bằng khách di cư
            incoming_len = ga.tour_length(incoming, D)
            if incoming_len < lengths[worst]:
                pop[worst] = incoming
                lengths[worst] = incoming_len

        history.append(min(lengths))

    comm.Barrier()
    elapsed = MPI.Wtime() - t0

    # --- Gom kết quả: tìm đảo có tour ngắn nhất bằng Reduce(MINLOC) ---
    local_best = min(lengths)
    global_best, best_rank = comm.allreduce((local_best, rank), op=MPI.MINLOC)

    # Đảo thắng gửi tour của nó về rank 0 để in / lưu.
    best_tour = pop[int(np.argmin(lengths))]
    if best_rank != 0:
        if rank == best_rank:
            comm.Send(np.ascontiguousarray(best_tour, dtype=np.int64), dest=0, tag=99)
        elif rank == 0:
            buf = np.empty(n, dtype=np.int64)
            comm.Recv(buf, source=best_rank, tag=99)
            best_tour = buf

    if rank == 0:
        mode = "co di cu" if args.migrate > 0 else "KHONG di cu"
        print(f"So dao (process): {size}  |  che do: {mode}")
        print(f"So thanh pho     : {n}, the he: {args.gens}, quan the/dao: {args.pop}")
        print(f"Do dai tot nhat  : {global_best:.2f}  (tu dao #{best_rank})")
        print(f"Thoi gian        : {elapsed:.2f}s")
        print(f"Lo trinh         : {np.asarray(best_tour).tolist()}")
        if args.out:
            np.savetxt(args.out, np.asarray(best_tour), fmt="%d")
            # lưu lịch sử hội tụ của rank 0 để vẽ đồ thị (Task 8)
            np.savetxt(args.out + ".history", history, fmt="%.4f")
            print(f"Da luu tour -> {args.out} va lich su -> {args.out}.history")


if __name__ == "__main__":
    main()
