# Tóm tắt thực nghiệm & phương pháp song song — Parallel TSP (Island-GA + MPI)

Tài liệu này tổng hợp nội dung cho báo cáo (theo `report_requirements.md`): mức độ song
song, kỹ thuật phân rã, ánh xạ, giao tiếp, cân bằng tải, mã giả, và **kết quả thực nghiệm**
(speedup, granularity, kích thước N). Số liệu lấy từ lần chạy thực tế — xem
`results/exp_speedup.png`, `results/exp_gran.png`, `results/exp_size.png`
và các file `.csv` tương ứng.

> Môi trường đo: **node1** (AMD Ryzen 7 4800HS, 8 nhân/16 luồng), OpenMPI 5.0.9, Python
> 3, mpi4py. Cụm phân tán **node1+node4** qua Tailscale đã được kiểm chứng chạy đúng
> (TSP 2 đảo, di cư ring); các biểu đồ cuối dùng node1 (một máy, nhiều nhân) để có đường
> cong sạch, không nhiễu mạng WAN và không bị máy thành viên ngủ giữa chừng.

---

## 1. Mức độ song song & phân rã

- **Mức độ song song: song song DỮ LIỆU** (data parallelism). Quần thể (population) được
  chia thành `p` **đảo** (island); mỗi tiến trình MPI sở hữu một đảo và tiến hóa độc lập.
- **Kỹ thuật phân rã: HỖN HỢP (hybrid)** =
  - *Data decomposition*: tổng quần thể `P` chia đều `P/p` cá thể mỗi đảo.
  - *Exploratory decomposition*: mỗi đảo là một cuộc tìm kiếm độc lập trong không gian
    nghiệm (seed khác nhau ⇒ khám phá vùng khác nhau), thỉnh thoảng trao đổi cá thể tốt.
- **Hạt (task/grain)**: một đảo = một tác vụ; kích thước hạt = `P/p` cá thể × `gens` thế hệ.

## 2. Ánh xạ tiến trình (mapping)

- **1D**: `p` tiến trình xếp thành **vòng 1 chiều (ring)**, rank `0..p-1`.
- Mỗi tiến trình ⇒ 1 đảo (1 process / island). Trên cụm dùng `--map-by node` để rải mỗi
  đảo sang một máy khác nhau (1 đảo/máy trước khi nhồi thêm).
- Không dùng lưới 2D vì giao tiếp chỉ là láng giềng trên vòng (xem mục 3).

## 3. Chiến lược giao tiếp & topology

- **Topology: VÒNG (ring)**. Láng giềng của rank `i`: trái `(i-1)%p`, phải `(i+1)%p`.
- **Di cư (migration)**: mỗi `--migrate` thế hệ, mỗi đảo gửi *cá thể tốt nhất* sang phải,
  nhận từ trái, thay *cá thể tệ nhất* nếu khách tốt hơn.
- **Kiểu giao tiếp: chặn nhưng an toàn — `MPI_Sendrecv`** (gửi+nhận đồng thời ⇒ không
  deadlock trên vòng). KHÔNG phải master–slave; đây là mô hình **ngang hàng (peer)**.
- **Thu kết quả**: `MPI_Allreduce(MINLOC)` tìm đảo có tour ngắn nhất, rồi `Send/Recv` tour
  thắng về rank 0. Đây là phần giao tiếp tập thể (collective) duy nhất, chạy 1 lần ở cuối.

## 4. Cân bằng tải (load balancing)

- **Cân bằng tĩnh, tự nhiên**: mọi đảo có cùng `P/p` cá thể và cùng số thế hệ ⇒ khối lượng
  tính toán gần như bằng nhau. Không cần lập lịch động.
- **Đo đạc**: với 8 tiến trình, **độ lệch thời gian rảnh (idle skew) = 0.0%** (yêu cầu
  <25%) ⇒ **đạt cân bằng**, không cần chỉnh độ mịn. Xem `results/exp_gran.png`.
- rank 0 có thời gian truyền thông nhỉnh hơn (gom kết quả cuối) nhưng không gây mất cân bằng.

## 5. Mã giả thuật toán song song (pseudo-code)

```
INPUT: cities, p (số tiến trình), G (gens), Pop (quần thể/đảo), k (chu kỳ di cư)
rank  = MPI_Comm_rank ;  size = MPI_Comm_size
left  = (rank-1) % size ;  right = (rank+1) % size
rng   = seed(BASE + rank*1000)            # mỗi đảo seed riêng

pop   = [random_tour() for _ in 1..Pop]   # khởi tạo đảo
MPI_Barrier ;  t0 = Wtime()

for gen in 1..G:
    sort pop theo độ dài tour
    new = [elite tốt nhất]                 # elitism
    while |new| < Pop:                     # sinh sản
        p1,p2 = tournament_select(pop)
        child = order_crossover(p1,p2);  mutate(child)
        new.append(child)
    pop = new
    if k>0 and gen % k == 0 and size>1:    # DI CƯ vòng ring
        t=Wtime(); recv = MPI_Sendrecv(best(pop) -> right, <- left); comm += Wtime()-t
        if len(recv) < len(worst(pop)): thay worst bằng recv

MPI_Barrier ;  elapsed = Wtime() - t0
(global_best, win) = MPI_Allreduce((best_local, rank), MINLOC)   # gom kết quả
gửi tour của đảo `win` về rank 0 ;  rank 0 in/lưu
```

## 6. Kết quả

### 6.1 Tính đúng đắn
Nghiệm song song là **một hoán vị hợp lệ** của `0..n-1` (mỗi thành phố đúng 1 lần, tour
khép kín) ⇒ đúng dạng lời giải TSP. Kết quả khớp với bản tuần tự khi `p=1`. Bản có di cư
hội tụ tới tour ngắn hơn/nhanh hơn bản không di cư (đa dạng nguồn gen qua ring).

### 6.2 Thời gian theo kích thước N — chọn N cho 2–3 phút
`results/exp_size.csv` (procs=4, gens=400):

| N (thành phố) | total (s) | compute (s) | comm (s) |
|---|---|---|---|
| 100 |  7.15 |  6.80 | 0.345 |
| 200 | 10.42 | 10.00 | 0.416 |
| 400 | 16.71 | 16.11 | 0.604 |
| 800 | 29.66 | 28.96 | 0.696 |

Thời gian tăng theo N; truyền thông gần như phẳng (di cư chỉ gửi 1 cá thể/chu kỳ). Ngoại
suy xu hướng, để chạm **2–3 phút (120–180 s)** cần **N ≈ 4000–5000** (giữ gens=400, procs=4)
hoặc tăng `gens`. → Lấy **N (báo cáo) ≈ 5000**; phần speedup dùng **2N ≈ 10000** (hoặc tăng
gens tương ứng) khi chạy bản đo chính thức.

### 6.3 Độ mịn / cân bằng tải (granularity)
`results/exp_gran.csv` (procs=8, N=200): compute ~12–13.7 s/đảo, comm 0.1–1.5 s, **idle
skew = 0.0%** ⇒ hệ cân bằng tốt, không cần chỉnh độ mịn. Biểu đồ cột chồng (compute+comm)
ở `results/exp_gran.png`.

### 6.4 Độ tăng tốc (speedup)
`results/exp_speedup.csv` (N=200, tổng quần thể cố định = 960, strong scaling):

| procs | total (s) | comm (s) | speedup | speedup (bỏ comm) | efficiency |
|---|---|---|---|---|---|
| 1 | 39.32 | 0.002 | 1.00 | 1.00 | 1.00 |
| 2 | 21.10 | 0.076 | 1.86 | 1.87 | 0.93 |
| 4 | 11.80 | 0.526 | 3.33 | 3.49 | 0.83 |
| 8 |  7.88 | 0.622 | 4.99 | 5.42 | 0.62 |

- Speedup gần tuyến tính ở 2–4 tiến trình; tới 8 đạt **~5×** (efficiency 0.62).
- Đường "bỏ thời gian truyền thông" cao hơn một chút ⇒ chi phí giao tiếp + phần tuần tự
  (sort/elitism + gom kết quả) làm efficiency giảm khi `p` tăng (đúng định luật Amdahl).
- Biểu đồ thời gian + speedup ở `results/exp_speedup.png`.

### 6.5 Chạy phân tán THẬT trên 2 máy (node1 WSL + node2 native Linux, qua Tailscale)
Đây là kết quả "cụm thật" (2 máy vật lý khác nhau), file `results/exp_*_n12.{csv,png}`:

| procs | total (s) | **comm (s)** | speedup | speedup (bỏ comm) | eff |
|---|---|---|---|---|---|
| 1 (node1) | 20.38 | 0.004 | 1.00 | 1.00 | 1.00 |
| 2 (node1+node2) | 10.26 | **2.34** | **1.99** | 2.57 | **0.99** |

Điểm khác biệt quan trọng so với chạy 1 máy: **thời gian truyền thông là THẬT (2.34 s)** =
chi phí mạng Tailscale WAN giữa 2 máy (so với ~0 khi chạy trên 1 máy nhiều nhân). Speedup
1.99 / efficiency 0.99 ⇒ với 2 đảo, di cư thưa (mỗi 20 thế hệ) nên overhead mạng vẫn nhỏ
so với tính toán.

**Quan sát cân bằng tải trên phần cứng KHÁC NHAU** (granularity 2 máy, `exp_gran_n12.png`):
- node1 (WSL, Ryzen 7): compute 8.15 s, comm 0.39 s
- node2 (native, i5-11400H): compute **4.86 s** (nhanh hơn), comm **3.68 s** (chờ nhiều hơn)

node2 tính nhanh hơn nên **phải chờ** node1 chậm hơn tại điểm di cư (`Sendrecv` đồng bộ) ⇒
thời gian "chờ" hiện ra dưới dạng comm. Đây là minh hoạ thực tế của **mất cân bằng do phần
cứng dị thể** (heterogeneous): muốn cân bằng hơn nên chia quần thể theo tốc độ máy (máy
nhanh nhận nhiều cá thể hơn) thay vì chia đều.

---

## 7. Ghi chú hạ tầng cụm (để thảo luận "real-world cluster")

Cụm thật gồm 4 máy của 4 thành viên nối qua **Tailscale** (VPN overlay, IP `100.x` xuyên
NAT). Các thách thức gặp & cách xử lý (đáng đưa vào báo cáo phần "khó khăn"):

- **Phải đồng bộ phiên bản launch-layer**: OpenMPI phải cùng 5.0.x; quan trọng hơn là
  **PMIx/PRRTE/hwloc phải tương thích**. node1+node4 chạy được vì cùng dùng *system hwloc*.
- **node2**: build OpenMPI lỡ dùng *hwloc bundled* (khác node1) ⇒ topology không
  unpack được (`bfrop_base_unpack` lỗi) ⇒ bị loại khỏi mapping. Khắc phục: build lại với
  `--with-hwloc=/usr`.
- **node3 (macOS)**: OpenMPI cài bằng Homebrew (PMIx/PRRTE khác) ⇒ không tương thích;
  cần build từ nguồn 5.0.9.
- **Mạng**: cố định giao tiếp vào card Tailscale (`oob_tcp_if_include=tailscale0`,
  `btl_tcp_if_include=tailscale0`) để tránh chọn nhầm card LAN/docker.
- **Bản chạy launcher**: xem `cluster/run_cluster.sh` (đặt PATH 5.0.9, `prte_launch_agent`,
  `--map-by node`, `cd ~/parallel-tsp` trên mỗi node).

> Tóm lại: thuật toán + đo đạc đã hoàn chỉnh và cho kết quả tốt trên 1 máy nhiều nhân; cụm
> phân tán node1+node4 đã chứng minh chạy đúng. Để lấy số speedup đa máy đầy đủ, cần các
> máy thành viên online đồng thời và đồng bộ OpenMPI/hwloc như trên.
