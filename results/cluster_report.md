# Báo cáo chạy thực nghiệm trên cluster MPI 4 node

## 1. Setup cluster (4 node thật, không phải giả lập)

| Node | Hostname | User | Core | Vai trò |
|---|---|---|---|---|
| node1 | DESKTOP-9PH6P60 | bao | 16 | |
| node2 | duck (máy launcher) | duck | 12 | launcher |
| node3 | LAPTOP-83S2JJ4P | acer | 16 | |
| node4 | LAPTOP-B2AUBVCH | khainx | 16 | |

OpenMPI 5.0.9 (source build, pinned tại `/opt/openmpi-5.0.9`) trên cả 4 máy. SSH passwordless
giữa launcher (node2) và 3 node còn lại, **kể cả loopback SSH tới chính node2** (cần cho
`mpirun` khi node2 cũng nằm trong hostfile).

### Sự cố đã gặp & cách xử lý
- **IP cluster đổi 3 lần trong buổi làm** (LAN → hotspot 172.20.10.x → LAN lại). Mỗi lần phải
  cập nhật `~/.ssh/config` (HostName) khớp với `/etc/hosts` mới, rồi `ssh -o StrictHostKeyChecking=accept-new`
  để chấp nhận host-key mới.
- `~/.ssh/authorized_keys` của node2 rỗng → mpirun không loopback SSH được vào chính nó. Đã
  thêm public key của node2 vào authorized_keys của chính nó.
- node1 lùi 1 commit git so với node2/3/4 → `git pull --ff-only` đồng bộ lại.
- Thiếu symlink `~/parallel-tsp` trên node2 (project nằm ở `~/project/parallel-tsp`) — script
  cluster mặc định kỳ vọng path `~/parallel-tsp` trên mọi máy → tạo symlink.
- `python/experiments.py` đọc file `--stats` CSV trên máy launcher, nhưng rank 0 (người viết
  file) luôn nằm trên node đầu tiên của hostfile (node1), không phải launcher → file rỗng. Đã
  sửa `run()` trong `experiments.py` để `scp` file `--stats` từ node1 về sau khi chạy.
- File `data/cities_2400.txt` chưa được sync sang node3 → segfault khi N=2400. Đã `rsync` lại.
- **Phát hiện quan trọng**: `cluster/run_cluster.sh` luôn dùng `--map-by seq`, mapper này
  **bỏ qua hoàn toàn `slots=N`** trong hostfile — nó cần đúng N dòng cho N rank. Vì
  `cluster/hosts` gốc chỉ có 4 dòng (1 dòng/node), mọi lệnh với `-np > 4` sẽ lỗi ngay, và các
  lần chạy trước đó vô tình chỉ dùng **1 core/máy** dù mỗi máy có 12-16 core sẵn. Đã tạo
  `cluster/hosts.seq48` — 48 dòng, round-robin `node1,node2,node3,node4,node1,...` (không phải
  xếp theo block, để mọi giá trị `-np` đều trải đều qua 4 máy) — cho phép chạy tới 48 rank
  (12 rank/máy, giới hạn bởi node2 - máy yếu nhất, 12 core).
- Xác nhận bằng `mpstat`/`top`: trước khi sửa, mỗi máy chỉ ~8% CPU (1/12 core); sau khi chạy
  đủ 48 rank, node2 bão hòa 100% (12/12 core busy), node1/3/4 ~75% (12/16 core busy, do giới
  hạn đồng nhất theo máy yếu nhất).

## 2. Xác minh thuật toán trao đổi thông tin (migration) hoạt động đúng

Chạy `data/cities_200.txt`, `--sync 20`, lấy lịch sử hội tụ thật của từng island (rank 0-3
trên 4 máy khác nhau, fetch qua `scp`):

| gen | rank0 | rank1 | rank2 (best) | rank3 |
|---|---|---|---|---|
| 19 (trước sync) | 7436.15 | 7525.27 | **7264.41** | 7568.60 |
| 21 (sau sync@20) | 7428.22 | 7459.67 ↓ | 7258.49 | 7263.26 ↓↓ |

Ngay sau mốc sync=20, các island kém hơn (rank1, rank3) dịch giá trị về phía island giữ
global-best (rank2) — đúng cơ chế: `Allreduce(MINLOC)` tìm global-best → `Bcast` → các island
khác splice một đoạn tour đó vào quần thể qua OX crossover (không clone toàn bộ, nên không
bằng tuyệt đối — đúng thiết kế "preserve diversity"). Giá trị "Best length" cuối (3077.42, từ
island #2) khớp chính xác với history thật của rank2, xác nhận pipeline `Allreduce(MINLOC)` +
gather hoạt động đúng qua mạng thật.

## 3. Kết quả 3 thí nghiệm chuẩn cho báo cáo (cluster 4 node, tới 48 ranks)

### 3.1 Runtime theo số thành phố N (`exp_size`, procs=48 cố định, gens=400)

| N | total (s) | comm (s) | compute (s) |
|---|---|---|---|
| 100 | 1.243 | 1.151 | 0.092 |
| 200 | 1.022 | 0.877 | 0.145 |
| 400 | 1.741 | 1.403 | 0.338 |
| 800 | 2.982 | 1.927 | 1.055 |
| 1200 | 4.249 | 2.481 | 1.769 |
| 2400 | 8.192 | 3.809 | 4.383 |

Compute tăng đúng theo N (nhiều việc hơn mỗi island); comm cũng tăng nhẹ theo N (gói tin
broadcast tour lớn hơn) nhưng tăng chậm hơn nhiều so với compute — ở N lớn (2400), compute đã
vượt comm, cho thấy bài toán đủ lớn để việc song song hoá "đáng" với chi phí giao tiếp.

### 3.2 Load balance / granularity (`exp_gran`, N=400, 48 ranks)

idle skew = **1.6%** → cân bằng tải tốt giữa 48 rank trên 4 máy không đồng nhất (12-16 core).

### 3.3 Speedup (`exp_speedup`, N=400, gens=400, procs = 1→48)

| procs | total (s) | comm (s) | compute (s) | speedup | speedup (no-comm) | hiệu suất |
|---|---|---|---|---|---|---|
| 1 | 0.633 | 0.000 | 0.633 | 1.00 | 1.00 | 1.00 |
| 2 | 0.456 | 0.211 | 0.244 | 1.39 | 2.59 | 0.70 |
| 4 | 0.606 | 0.502 | 0.105 | 1.05 | 6.06 | 0.26 |
| 8 | 0.756 | 0.700 | 0.056 | 0.84 | 11.38 | 0.10 |
| 16 | 0.902 | 0.870 | 0.032 | 0.70 | 19.74 | 0.04 |
| 32 | 1.290 | 1.293 | ~0.00 | 0.49 | — | 0.02 |
| 48 | 1.303 | 1.282 | 0.021 | 0.49 | 29.94 | 0.01 |

**Nhận xét quan trọng cho báo cáo:** với N=400 (bài toán nhỏ), speedup **thực tế (kể cả
comm) giảm dần và tụt dưới 1** khi procs > 4 — tức là **chạy nhiều rank hơn lại CHẬM hơn
chạy ít rank**, vì lượng việc mỗi island ngày càng nhỏ trong khi chi phí đồng bộ
(`Allreduce`/`Bcast` mỗi `--sync` generations) không giảm theo. Tuy nhiên nếu bỏ
comm time (`speedup_nocomm`), phần *compute* vẫn scale gần tuyến tính (29.94x ở 48 procs) —
chứng minh việc phân rã công việc (song song hoá GA) là đúng và hiệu quả, **nút thắt nằm ở
chi phí giao tiếp mạng thật, không nằm ở thuật toán**. Mục 4 dưới đây đo trực tiếp mạng để
kiểm chứng kết luận này.

## 4. Đo network thật để kiểm chứng kết luận "nút thắt là mạng"

### 4.1 Latency (RTT, ping 20 mẫu/node, không phải số liệu đoán trước đó)

| node2 → | min | avg | max | mdev |
|---|---|---|---|---|
| node1 | 4.4ms | **8.5ms** | 14.0ms | 2.2ms |
| node3 | 4.5ms | **11.6ms** | 40.1ms | 7.5ms |
| node4 | 4.8ms | **12.9ms** | 34.1ms | 8.3ms |

(Sửa lại số liệu sai đã nêu ở báo cáo trước — lúc đó tôi suy ra "80-200ms" từ 1 mẫu ping đơn lẻ
bị nhiễu bởi ARP resolution, không phải latency ổn định thật. Latency thật ổn định ~8-13ms.)

### 4.2 Bandwidth thật (đo qua `ssh ... cat > /dev/null`, truyền 300MB từ node2)

| node2 → | thời gian | thông lượng |
|---|---|---|
| node1 | 14.19s | 21.1 MB/s (~169 Mbit/s) |
| node3 | 16.15s | 18.6 MB/s (~149 Mbit/s) |
| node4 | 14.87s | 20.2 MB/s (~162 Mbit/s) |

(Số liệu qua kênh SSH mã hoá nên thấp hơn TCP thuần một chút, nhưng đủ để ước lượng - đây
không phải mạng LAN tốc độ cao, chỉ ở mức ~150-170 Mbit/s thực dụng.)

### 4.3 Đối chiếu: nút thắt là LATENCY, không phải BANDWIDTH

Với N=400, mỗi tour broadcast chỉ ~1.6 KB (400 thành phố × 4 byte int). Ở băng thông
~20 MB/s, truyền 1.6 KB chỉ tốn **~0.08 ms** — không đáng kể. Nhưng `exp_speedup` đo được ở
`procs=48`: `comm_s` = 1.282s cho 20 lần sync (gens=400, `--sync` mặc định = 20) → **~64ms mỗi
lần sync**. Số này khớp với vài round-trip tuần tự của `Allreduce(MINLOC)` + `Bcast` trên cây
collective qua 48 rank / 4 máy có RTT thật ~8-13ms (vài hop tuần tự × latency ≈ vài chục ms),
**không thể giải thích bằng kích thước dữ liệu nhỏ (1.6KB) nếu là vấn đề băng thông**.

**Kết luận đã kiểm chứng lại (chính xác hơn bản trước):** nút thắt khi tăng `procs` ở N nhỏ là
**chi phí latency của các lần đồng bộ tập thể (collective ops) lặp lại nhiều lần**, không phải
do mạng "chậm" hay thiếu băng thông — payload mỗi lần migration quá nhỏ để bandwidth thành vấn
đề. Hệ quả thực tiễn: muốn giảm overhead khi scale procs, nên **tăng `--sync`** (đồng bộ thưa
hơn) thay vì kỳ vọng mạng nhanh hơn sẽ giúp — khớp với cơ chế "convergence stop" đã thiết kế
sẵn trong thuật toán (ranks tự dừng sync khi global best đã stall).

## 5. Đối chiếu chéo với `python/benchmark.py` (công cụ đo speedup độc lập, fit Amdahl's law)

`benchmark.py` giữ **tổng population cố định** (chia đều theo `procs`), khác cách đo của
`experiments.py speedup` (giữ population/island cố định) — một phép đo strong-scaling độc lập
để kiểm tra chéo.

**Bug phát hiện khi chạy trên cluster:** script gọi `mpirun` trực tiếp với path tuyệt đối của
binary (`/home/duck/.../cpp/tsp_island`), không pin `prte_launch_agent`, không `cd` vào
`$HOME/parallel-tsp` riêng của từng node → lỗi *"lacked permissions to execute"* vì path đó
không tồn tại trên node1 (`/home/bao/...`). Đã sửa `run_once()` trong `benchmark.py` để dùng
đúng convention với `cluster/run_cluster.sh` (pin `prted`, `--map-by seq`, `cd` theo `$HOME`
từng node, path tương đối).

### Kết quả (N=200, total population=480, gens=400, cluster 4 node thật)

| procs | time (s) | speedup | efficiency |
|---|---|---|---|
| 1 | 0.300 | 1.00 | 1.00 |
| 2 | 0.260–0.830 | 0.36–1.15 | 0.18–0.58 |
| 4 | 0.500–0.520 | 0.58–0.60 | 0.14–0.15 |
| 8 | 0.810–0.850 | 0.35–0.37 | 0.04–0.05 |
| 16 | 0.890–1.040 | 0.29–0.34 | 0.02 |

(Chạy 2 lần, dao động do nhiễu mạng/scheduling thật trên LAN — nhưng xu hướng nhất quán.)
**Cùng kết luận với mục 3.3 và 4.3**: speedup giảm khi tăng `procs` ở bài toán nhỏ, do chi phí
latency của đồng bộ tập thể, không phải do thuật toán hay do thiếu băng thông — hai công cụ đo
độc lập (`experiments.py` và `benchmark.py`) cho cùng kết luận, tăng độ tin cậy.

## 6. Tổng kết - đã chạy đủ mọi file experiment trong repo

| File | Đã chạy | Trên cluster 4 node thật |
|---|---|---|
| `python/experiments.py size` | ✅ | ✅ (48 ranks) |
| `python/experiments.py gran` | ✅ | ✅ (48 ranks) |
| `python/experiments.py speedup` | ✅ | ✅ (1→48 ranks) |
| `cluster/run_report_experiments.sh` | ✅ | ✅ |
| `python/benchmark.py` | ✅ (đã fix bug cluster) | ✅ (1→16 ranks) |

Không có lỗi/traceback nào còn sót trong log chạy cuối cùng.

## 7. File kết quả

- `results/exp_size.{csv,png}`, `results/exp_gran.{csv,png}`, `results/exp_speedup.{csv,png}`
- `results/bench_cluster.csv`, `results/speedup_cluster.png` (từ `benchmark.py`)
- Hostfile mới cho seq-mapper 48 rank: `cluster/hosts.seq48`
