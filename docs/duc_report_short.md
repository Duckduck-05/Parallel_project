# Báo cáo ngắn — Island-GA TSP song song (node2 / Duc)

## 1. Mức độ song song & kỹ thuật phân rã
- **Song song cấp dữ liệu** (data parallelism): mỗi tiến trình MPI giữ một quần thể
  (island) riêng, cùng chạy một thuật toán GA tuần tự trên dữ liệu (tour) khác nhau.
- Kỹ thuật phân rã: **data decomposition** — không chia bài toán TSP thành tác vụ con,
  mà chia *không gian tìm kiếm* (mỗi đảo seed khác nhau) và *quần thể* (population)
  cho từng tiến trình.

## 2. Cách song song hóa
- **Mapping**: 1D — mỗi tiến trình = 1 đảo độc lập, không chia ma trận/dữ liệu thành
  block 2D. `--map-by seq --bind-to none` để tránh PRRTE drop node do topology
  không đồng nhất (CPU core count khác nhau giữa 4 máy).
- **Giao tiếp**: topology **ring** (vòng tròn) — đảo *i* trao đổi cá thể tốt nhất với
  hàng xóm trái/phải qua `MPI_Sendrecv` (blocking, nhưng send+recv đồng thời nên
  không deadlock). Cuối chương trình: `MPI_Allreduce(MINLOC)` để tìm đảo tốt nhất
  toàn cục, sau đó `Send`/`Recv` điểm-điểm để gom tour về rank 0.
- **Cân bằng tải (mới thêm)**: cờ `--auto-balance` — mỗi tiến trình tự đo tốc độ máy
  bằng micro-benchmark (2 lần × 15 thế hệ × 100 cá thể) lúc khởi động, rồi chia
  population tỉ lệ nghịch với thời gian đo được (máy chậm nhận ít cá thể hơn), giới
  hạn lệch [0.5×, 2×] so với `--pop` để chống nhiễu đo. Tổng population toàn cụm
  giữ không đổi.

### Pseudo-code
```
rank, size = MPI.rank, MPI.size
D = distance_matrix(read_cities(file))
pop_size = auto_balance(D, args.pop) if --auto-balance else args.pop
pop, lengths = init_population(pop_size)

Barrier(); t0 = now()
for gen in 1..GENS:
    pop, lengths = evolve_one_generation(pop, lengths)      # elitism+tournament+OX+mutation
    if gen % MIGRATE == 0:
        incoming = Sendrecv(best(pop), dest=right, source=left)   # ring
        if length(incoming) < worst(lengths): replace worst with incoming
Barrier(); elapsed = now() - t0

global_best, best_rank = Allreduce((min(lengths), rank), op=MINLOC)
if rank == best_rank and rank != 0: Send(best_tour, dest=0)
if rank == 0: print/save result
```

## 3. Kết quả thực nghiệm — 4 node thật (LAN, OpenMPI 5.0.9)
Cụm: node1 (16 core) + node2 (12 core) + node4 (16 core) + node3 (16 core), tổng 4
tiến trình (1 đảo/node), dữ liệu `cities_200.txt`, 500 generations, di cư mỗi 100 thế hệ.

| rank | node  | population (auto) | compute (s) | comm (s) | total (s) |
|------|-------|-------------------:|------------:|---------:|----------:|
| 0    | node1 | 135                | 6.82        | 0.90     | 7.72      |
| 1    | node2 | 131                | 7.33        | 0.40     | 7.74      |
| 2    | node4 | 268                | 6.94        | 0.14     | 7.08      |
| 3    | node3 | 265                | 7.61        | 0.11     | 7.72      |

- **Makespan toàn cụm**: 7.74s. **Tour tốt nhất**: độ dài 2371.05 (đảo #0).
- **Tính đúng đắn**: tour hợp lệ (permutation đầy đủ 200 thành phố, không lặp/thiếu
  thành phố — kiểm tra bằng `set(tour) == set(range(n))`); độ dài giảm đơn điệu qua
  các thế hệ (lưu trong `*.history`), khớp với thuộc tính elitism của GA.
- **Cân bằng tải**: chênh lệch compute giữa rank nhanh nhất/chậm nhất chỉ ~12%
  (6.82s vs 7.61s) — trong ngưỡng cho phép (<25%) nhờ `--auto-balance` (lúc chưa
  cân bằng, độ lệch đo được lên tới ~120% giữa node1/node4 và node2/node3, do tốc
  độ CPU thực tế khác nproc gợi ý — node 12-core nhanh hơn 2 node 16-core).
- File raw: `results/duc_run_cities200_stats.csv`,
  `results/duc_run_cities200.tour(.history)`.
