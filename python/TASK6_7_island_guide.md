# Task 6 & 7 — Island-GA song song + Di cư (phần "ăn điểm")

Đây là phần song song hóa cốt lõi của đồ án. Mỗi **process MPI = 1 đảo** chạy GA độc
lập với seed riêng (nên mỗi đảo khám phá vùng nghiệm khác nhau). Định kỳ các đảo **di cư**
cá thể tốt nhất sang đảo kế bên theo **vòng ring**.

## Các lời gọi MPI dùng (để trả bài)
| Mục đích | Lời gọi MPI | Ở đâu |
|---|---|---|
| Đồng bộ trước khi bấm giờ | `MPI_Barrier` / `comm.Barrier()` | trước & sau vòng lặp |
| Di cư cá thể tốt nhất theo ring | `MPI_Sendrecv` / `comm.sendrecv` | mỗi K thế hệ |
| Tìm đảo có tour ngắn nhất | `MPI_Allreduce(MPI_MINLOC)` | sau tiến hóa |
| Gửi tour thắng về rank 0 | `MPI_Send` / `MPI_Recv` | in kết quả |

**Vì sao dùng `Sendrecv`?** Nếu mọi đảo cùng `Send` rồi mới `Recv` sẽ **deadlock** (ai
cũng chờ gửi). `Sendrecv` gửi và nhận đồng thời nên an toàn trên vòng ring.

**Vì sao `MINLOC`?** Nó vừa lấy giá trị nhỏ nhất (tour ngắn nhất) vừa cho biết **đảo nào**
(rank) đạt được, để gọi đúng đảo đó gửi lộ trình về.

## Demo Task 6 — nhiều đảo, CHƯA di cư
```bash
cd ~/parallel-tsp/python
mpirun --oversubscribe -np 3 python3 tsp_island.py ../data/cities_30.txt --gens 400 --migrate 0
```
→ Kết quả là tour tốt nhất trong 3 đảo độc lập (lấy bằng `Reduce(MINLOC)`).

## Demo Task 7 — CÓ di cư vòng ring
```bash
mpirun --oversubscribe -np 3 python3 tsp_island.py ../data/cities_30.txt --gens 400 --migrate 20
```
→ Cứ 20 thế hệ, mỗi đảo gửi cá thể tốt nhất sang đảo phải, nhận từ đảo trái, thay cá thể tệ
nhất. Thường **hội tụ tốt hơn** so với không di cư (đã kiểm chứng: 747 → 678 trên máy test).

## Bản C++ (tương đương, nhanh hơn nhiều)
```bash
cd ~/parallel-tsp/cpp
mpicxx -O2 -o tsp_island tsp_island.cpp
mpirun --oversubscribe -np 3 ./tsp_island ../data/cities_30.txt --gens 400 --migrate 20
```

## Chạy trên CỤM 3 máy thật
Thêm `--hostfile`:
```bash
mpirun --hostfile ~/parallel-tsp/cluster/hosts -np 3 \
    python3 ~/parallel-tsp/python/tsp_island.py ~/parallel-tsp/data/cities_30.txt --gens 400 --migrate 20
```

> Ghi chú: cờ `--oversubscribe` chỉ cần khi chạy nhiều process hơn số core trên 1 máy
> (lúc test ở nhà). Trên cụm 3 máy với `-np 3` thì không cần.
