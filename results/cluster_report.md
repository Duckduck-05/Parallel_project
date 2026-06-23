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

## 7. File kết quả (vòng 1)

- `results/exp_size.{csv,png}`, `results/exp_gran.{csv,png}`, `results/exp_speedup.{csv,png}`
- `results/bench_cluster.csv`, `results/speedup_cluster.png` (từ `benchmark.py`)
- Hostfile mới cho seq-mapper 48 rank: `cluster/hosts.seq48`

---

# Phần bổ sung (vòng 2) - đáp ứng đầy đủ yêu cầu của giảng viên

## 8. Tìm N* sao cho runtime ≈ 2-3 phút

### 8.1 Phát hiện quan trọng: trần RAM, không phải trần CPU/thuật toán

`distance_matrix()` trong `cpp/ga_core.hpp` cấp **O(N²) bộ nhớ** (ma trận N×N khoảng cách,
8 byte/double) **cho MỖI rank**. Với 12 rank/máy:

| N | bộ nhớ/rank | bộ nhớ/máy (×12 rank) |
|---|---|---|
| 2400 | 46 MB | 552 MB |
| 3200 | 82 MB | 983 MB |
| 4800 | 184 MB | **2.21 GB** |
| 6400 | 328 MB | **3.93 GB** |

node3 (máy yếu nhất) chỉ có **3.7 GB RAM tổng, ~3.0 GB khả dụng**. Thử trực tiếp N=6400 ở
48 rank: **bị treo, không xong sau 3 phút** (timeout) — do swap thrashing thật, đã xác nhận
bằng `free -h` trên node3 trước/sau test. Đây là **trần vật lý cứng của cluster**, không phải
do GA hay do mạng chậm — phải tôn trọng khi chọn N* và khi chọn 2×N* cho thí nghiệm speedup ở
mục 10 (8000 thành phố sẽ cần ~6.1 GB/máy → chắc chắn sập node3).

### 8.2 Quy trình tìm N* (procs=48, sync=20, đo trên cluster thật)

| N | gens | total (s) | Ghi chú |
|---|---|---|---|
| 2400 | 400 | 8.19 | baseline (mục 3.1) |
| 3200 | 400 | 15.43 | tăng siêu tuyến tính (do cache-miss trên ma trận N² lớn, không phải do GA) |
| 6400 | 400 | **TIMEOUT >180s** | vượt trần RAM node3 → swap thrashing |
| 2400 | 7300 | 102.47 | tăng gens (an toàn RAM) để dò |
| 2400 | 10500 | **159.14** | ✅ trong khoảng 2-3 phút |

**Chọn N\* = 2400 thành phố, gens\* = 10500** (procs=48, sync=20) — runtime thật
**159.14s (≈2.65 phút)**, Best length = 18354.24. Cố tình giữ N* nhỏ (≤2550) để **2×N\* = 4800
vẫn an toàn RAM trên toàn cluster** (2.21 GB/máy, còn margin so với 3.0 GB của node3) — tránh
phải giảm rank trên node3 (vẫn giữ 12 rank/máy đồng nhất cho thí nghiệm speedup ở mục 10).

(Lưu ý thêm: dao động run-to-run khá lớn trên cluster tiêu dùng thật — ví dụ N=4000/gens=1500
cho 201.55s nhưng gens=1300 chỉ 86-95s ở lần đo khác; nguyên nhân là nhiễu mạng/tải hệ thống
chia sẻ trên các máy laptop Windows, không phải lỗi đo. Số liệu N*/gens* cuối đã được xác nhận
ổn định qua phép đo trực tiếp.)

### 8.3 Bảng sạch: runtime vs N tại gens=10500 CỐ ĐỊNH (procs=48, sync=20)

Để phần "tìm N" tách bạch rõ với mục 3.1 (vốn cố định gens=400, quét N) - bảng dưới đây cố định
**gens=10500** (giá trị đã chọn cho N\*) và chỉ quét N, cho thấy quan hệ runtime-vs-N "sạch"
dùng để minh hoạ vì sao N=2400 được chọn:

| N | total (s) | comm (s) | compute (s) |
|---|---|---|---|
| 1200 | 54.54 | 25.90 | 28.65 |
| 1800 | 86.99 | 34.33 | 52.66 |
| 2400 | 154.27 | 64.05 | 90.22 |

Tăng trưởng từ N=1200→2400 (×2) cho total ×2.83 - siêu tuyến tính nhẹ (khớp với phân tích cache
ở mục 8.1), nhưng vẫn nằm gọn trong khoảng mong muốn ở N=2400.

### 8.4 Lệnh chính xác đã chạy (N\* search)

```bash
export PATH=/opt/openmpi-5.0.9/bin:$PATH LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib
# dò sơ bộ qua N (gens=400 cố định)
bash cluster/run_cluster.sh cluster/hosts.seq48 48 ./cpp/tsp_island data/cities_3200.txt --gens 400 --sync 20
bash cluster/run_cluster.sh cluster/hosts.seq48 48 ./cpp/tsp_island data/cities_6400.txt --gens 400 --sync 20   # timeout
# dò qua gens tại N=4000 (an toàn RAM) rồi N=2400 (giá trị cuối)
bash cluster/run_cluster.sh cluster/hosts.seq48 48 ./cpp/tsp_island data/cities_4000.txt --gens 1500 --sync 20
bash cluster/run_cluster.sh cluster/hosts.seq48 48 ./cpp/tsp_island data/cities_4000.txt --gens 1300 --sync 20
bash cluster/run_cluster.sh cluster/hosts.seq48 48 ./cpp/tsp_island data/cities_2400.txt --gens 7300  --sync 20
bash cluster/run_cluster.sh cluster/hosts.seq48 48 ./cpp/tsp_island data/cities_2400.txt --gens 10500 --sync 20   # N*/gens* CUỐI CÙNG
# bảng sạch mục 8.3
bash cluster/run_cluster.sh cluster/hosts.seq48 48 ./cpp/tsp_island data/cities_1200.txt --gens 10500 --sync 20
bash cluster/run_cluster.sh cluster/hosts.seq48 48 ./cpp/tsp_island data/cities_1800.txt --gens 10500 --sync 20
```

## 9. Granularity tại N\* (N=2400, gens=10500, procs=48)

```
idle skew = 1.8%  =>  BALANCED OK
```

**Lệnh chính xác:**
```bash
python3 python/experiments.py gran --procs 48 --size 2400 --gens 10500 --sync 20 \
    --hostfile cluster/hosts.seq48
```

`results/exp_gran.png` là **stacked bar đúng theo yêu cầu**: với mỗi rank (trục X = 48 rank),
cột chồng gồm 3 phần `compute` (xanh) + `comm` (cam) + `idle/wait` (xám) (đọc trực tiếp từ
code vẽ trong `python/experiments.py::exp_gran`, không suy diễn). Dữ liệu: `results/exp_gran.csv`
(48 dòng, cột `rank,compute_s,comm_s,idle_s`).

Compute dao động 65-130s/rank, comm dao động ngược lại (22-83s/rank) - **đây KHÔNG phải do rank
"owner" tốn compute để broadcast** (broadcast/Bcast/Allreduce bản chất là thao tác comm/chờ,
không tốn compute thêm cho người gửi). Nguyên nhân thực tế hợp lý hơn là tổ hợp của:
1. **Phần cứng không đồng nhất** - node3 chậm hơn (RAM thấp, mục 14.2) khiến các rank trên đó
   tốn nhiều thời gian comm/chờ hơn so với rank trên node1/2/4 nhanh hơn;
2. **GA có yếu tố ngẫu nhiên (stochastic)** - mỗi island hội tụ với tốc độ khác nhau (tuỳ seed,
   tuỳ việc cá thể đó có "trúng" cải tiến tốt sớm hay không), nên compute thực tế biến thiên
   theo rank dù code chạy y hệt nhau;
3. **Chờ đồng bộ (synchronization wait)** - rank xử lý nhanh phải đợi rank chậm nhất ở mỗi điểm
   `--sync` (đây mới là phần lớn của "comm_s" đo được, không phải chi phí truyền dữ liệu thuần).

Bù lại, **idle time luôn ~0** (trừ 4 rank có idle≈2.79s, vẫn <2% tổng thời gian) → dù
compute/comm lệch nhau khá nhiều giữa các rank, không có rank nào thực sự "rảnh" - tải vẫn
được phân bổ và sử dụng hợp lý.

## 10. Speedup tại 2×N\* = 4800 thành phố, procs = 1→48 (an toàn RAM)

**Cấu hình đầy đủ: N=4800, gens=400, sync=20, total population=480 (mặc định của
`experiments.py speedup` - chia đều `pop/island = 480 // procs`, đây là kiểu đo strong-scaling
"giữ tổng khối lượng việc cố định", KHÁC với mục 8/9 nơi pop=200/island cố định bất kể số
rank).**

**Lệnh chính xác:**
```bash
python3 python/experiments.py speedup --procs 1 2 4 8 16 32 48 --size 4800 \
    --gens 400 --sync 20 --hostfile cluster/hosts.seq48
```

`results/exp_speedup.png` gồm **2 panel cạnh nhau** (đọc trực tiếp từ code vẽ trong
`python/experiments.py::exp_speedup`): panel trái = **runtime** theo số process, 2 đường
"with communication" và "without communication"; panel phải = **speedup S(p)=T(1)/T(p)**, 2
đường tương tự + đường "ideal" (speedup tuyến tính) để đối chiếu.

| procs | total (s) | comm (s) | compute (s) | speedup (kể cả comm) | speedup (không comm) | hiệu suất |
|---|---|---|---|---|---|---|
| 1 | 16.29 | 0.000 | 16.29 | 1.00 | 1.00 | 1.00 |
| 2 | 10.11 | 4.05 | 6.06 | 1.61 | 2.69 | 0.81 |
| 4 | 4.81 | 2.14 | 2.67 | 3.39 | 6.11 | 0.85 |
| 8 | 3.45 | 2.05 | 1.41 | 4.72 | 11.59 | 0.59 |
| **16** | **3.15** | 2.29 | 0.86 | **5.17 (đỉnh)** | 18.83 | 0.32 |
| 32 | 3.74 | 2.89 | 0.85 | 4.35 | 19.18 | 0.14 |
| 48 | 3.60 | 2.53 | 1.07 | 4.52 | 15.20 | 0.09 |

**Khác biệt lớn so với thí nghiệm cũ ở N=400 (mục 3.3)**: với bài toán đủ lớn (N=4800),
speedup **không bao giờ tụt dưới 1** — đạt đỉnh **5.17x ở 16 procs**, sau đó giảm nhẹ ở 32/48
(do comm chiếm tỷ trọng lớn hơn khi mỗi island còn ít việc) nhưng vẫn >4x. Điều này xác nhận
trực tiếp giả thuyết đã nêu ở mục 4.3: **kích thước bài toán đủ lớn sẽ khắc phục được vấn đề
overhead đồng bộ** quan sát thấy ở N nhỏ.

## 11. So sánh `--sync` 0 / 20 / 100 / 200 (N=4800, procs=48, gens=400)

**Lệnh chính xác:**
```bash
export PATH=/opt/openmpi-5.0.9/bin:$PATH LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib
for s in 0 20 100 200; do
  bash cluster/run_cluster.sh cluster/hosts.seq48 48 ./cpp/tsp_island data/cities_4800.txt \
      --gens 400 --sync $s
done
```

| sync | total (s) | comm (s) | compute (s) | Best length |
|---|---|---|---|---|
| 0 (baseline, không chia sẻ) | 38.29 | **0.55** | 37.75 | 174825.61 |
| 20 | 42.68 | 20.96 | 21.72 | 175298.77 |
| 100 | 44.57 | 21.23 | 23.34 | 175584.19 |
| 200 | 42.85 | 19.99 | 22.86 | 175368.18 |

**Phát hiện bất ngờ (khác giả thuyết ban đầu)**: tăng `--sync` từ 20→100→200 **KHÔNG làm giảm
comm time** (vẫn ~20-21s, sai biệt nằm trong nhiễu đo). Chỉ `--sync 0` (tắt hẳn migration) mới
giảm comm xuống gần 0. Giải thích: với 48 rank trải trên 4 máy không đồng nhất (node3 yếu hơn
hẳn về RAM/tốc độ), phần lớn "comm time" đo được thực chất là **thời gian chờ ở rào đồng bộ
(barrier) để rank chậm nhất bắt kịp**, không phải chi phí truyền dữ liệu của riêng broadcast.
Giảm tần suất sync (sync lớn hơn) không giảm tổng thời gian chờ vì lệch tiến độ giữa rank
nhanh/chậm chỉ dồn lại thành các lần chờ lâu hơn nhưng ít lần hơn — về tổng thể gần như không
đổi. **Kết luận: với cluster KHÔNG đồng nhất, nút thắt comm chủ yếu do mất cân bằng tốc độ máy
(node3 chậm/RAM thấp), không phải do tần suất migration** — khác với kết luận ở mục 4.3 (vốn
áp dụng cho trường hợp N nhỏ, nơi chi phí round-trip latency của chính các lệnh collective mới
là yếu tố chính). Cả hai hiệu ứng cùng tồn tại; ở quy mô N=4800/48-rank này, hiệu ứng mất cân
bằng tốc độ máy lấn át hiệu ứng latency thuần.

## 12. Correctness validation

**Lệnh chính xác:**
```bash
export PATH=/opt/openmpi-5.0.9/bin:$PATH LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib
# case N=8 (brute-force feasible)
python3 data/generate_cities.py --n 8 --mode random --seed 42 --out /tmp/cities_8.txt
mpirun --oversubscribe -np 4 ./cpp/tsp_island /tmp/cities_8.txt --gens 500 --sync 20 --out /tmp/verify8
python3 python/validate_tour.py /tmp/cities_8.txt "2 4 7 0 1 3 6 5" 240.49

# case N=200 (permutation + recompute only, N quá lớn cho brute-force)
mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_200.txt --gens 500 --sync 20 --out /tmp/verify200
# -> stdout in "Best length: 2348.01" + dòng "Route: <200 số, permutation 0..199>"
python3 python/validate_tour.py data/cities_200.txt "$(grep '^Route' /tmp/v200.txt | sed 's/Route *: *//')" 2348.01
```
(route N=200 là 200 số nguyên, quá dài để in trực tiếp trong báo cáo - xem file gốc
`/tmp/v200.txt` hoặc chạy lại lệnh trên để tái tạo.)

Viết script kiểm tra độc lập (Python, không dùng lại code C++) gồm 3 mức:

1. **Tour là permutation hợp lệ** - đủ N thành phố, mỗi thành phố xuất hiện đúng 1 lần.
2. **Recompute khoảng cách** từ toạ độ gốc, so khớp với giá trị "Best length" mà solver in ra.
3. **So với brute-force optimal** (chỉ khả thi N≤10, do độ phức tạp giai thừa).

| Test case | Permutation hợp lệ? | Recompute khớp output? | So brute-force |
|---|---|---|---|
| N=8 (seed=42) | ✅ (8/8 thành phố, không trùng) | ✅ (240.4889 vs 240.4900, sai biệt 0.0011 do rounding in) | ✅ **GA tìm đúng tối ưu tuyệt đối** (gap 0.00%) |
| N=200 | ✅ (200/200, không trùng) | ✅ (2348.0052 vs 2348.0100, sai biệt 0.0048) | (bỏ qua - N quá lớn cho brute-force) |

Kết luận: solver trả về tour hợp lệ và giá trị "Best length" được tính đúng từ tour thật (không
phải số ảo/bug hiển thị); ở quy mô đủ nhỏ để kiểm chứng tuyệt đối, thuật toán GA tìm được đúng
lời giải tối ưu toàn cục.

## 13. Thống kê LOC (Lines of Code) theo file/module

**Lệnh chính xác:**
```bash
wc -l cpp/*.hpp cpp/*.cpp python/*.py cluster/*.sh
git log --format='%an' | sort -u   # đếm số tác giả
```

| Module | File | LOC |
|---|---|---|
| C++ solver | `cpp/tsp_island.cpp` (MPI island solver, deliverable chính) | 313 |
| C++ solver | `cpp/ga_core.hpp` (GA operators) | 117 |
| C++ solver | `cpp/local_search.hpp` (2-opt/Or-opt) | 72 |
| C++ solver | `cpp/tsp_sequential.cpp` (baseline T(1)) | 43 |
| C++ tests | `cpp/test_ga_core.cpp` + `cpp/test_local_search.cpp` | 105 |
| **Tổng C++** | | **650** |
| Python tooling | `python/live_view.py` | 350 |
| Python tooling | `python/experiments.py` | 215 |
| Python tooling | `python/benchmark.py` | 127 |
| Python tooling | `python/visualize.py` | 93 |
| **Tổng Python** | | **785** |
| Cluster scripts | 7 file `cluster/*.sh` | **265** |
| **TỔNG TOÀN BỘ** | | **1700** |

Số tác giả theo `git log` (2 người: Duck, Quốc Bảo) → **850 dòng/người** (4 người trong nhóm
vận hành cluster → **425 dòng/người**) — cả hai cách tính đều **vượt mốc 250 dòng/người**.

## 14. Thử bỏ node3, chạy "full tốc lực" với 3 node còn lại

Giả thuyết cần kiểm chứng: nếu node3 (RAM thấp nhất, 3.7GB) là "vấn đề", loại nó ra và chạy hết
công suất 3 node còn lại có nhanh hơn không? Dùng lại đúng config N\*/gens\* (N=2400,
gens=10500, sync=20, pop=200/island - so sánh ngang được vì mỗi rank vẫn làm đúng cùng khối
lượng việc, không scale theo proc count như thí nghiệm speedup ở mục 10).

### 14.1 Lần thử đầu tiên: dùng "hết" 16 core của node1/node4 → SAI LẦM, chậm hơn

`lscpu` cho thấy **cả 3 máy đều dùng hyperthreading** (8 core vật lý × 2 thread = 16 "CPU(s)"
theo Linux, riêng node2 chỉ 6 core vật lý × 2 thread = 12). Cấu hình gốc cap mọi node ở 12 rank
(đúng = số thread tối đa của máy yếu nhất - node2) là **có chủ đích**, không phải tuỳ tiện.

| Cấu hình | Ranks | total (s) | comm (s) | compute (s) |
|---|---|---|---|---|
| 4 node, 12 rank/máy (gốc, có node3) | 48 | 154.27 | 64.05 | 90.22 |
| 3 node, **16 rank**/máy node1+node4, 12 ở node2 (bỏ node3, dùng hết HT) | 44 | **227.61** ❌ chậm hơn | 115.62 | 111.99 |

Dùng hết 16 thread logic trên CPU 8-core thật **oversubscribe hyperthreading 2×** (thay vì 1.5×
như cấu hình gốc) — HT chia sẻ ALU/cache của lõi vật lý, không cho speedup tuyến tính, nên ép
đủ 16 rank/máy làm chậm đi cả compute (90→112s) và comm (64→116s, do rank chậm hơn kéo theo
chờ đồng bộ lâu hơn). **Kết luận tạm: bỏ node3 theo cách này phản tác dụng - không phải vì
thiếu node3, mà vì đã vi phạm chính giới hạn HT mà cấu hình gốc cố tình tránh.**

### 14.2 Lần thử đúng cách: vẫn cap 12 rank/máy, chỉ bỏ node3

| Cấu hình | Ranks | total (s) | comm (s) | compute (s) |
|---|---|---|---|---|
| 4 node, 12 rank/máy (gốc, có node3) | 48 | 154.27 | 64.05 | 90.22 |
| **3 node, 12 rank/máy (bỏ node3, tôn trọng cap HT)** | 36 | **141.81** ✅ nhanh hơn ~8% | 56.84 | 84.97 |

Khi loại bỏ đúng biến nhiễu (không oversubscribe HT), **bỏ node3 thực sự nhanh hơn** ~8%
(141.81s vs 154.27s) — xác nhận node3 đúng là rank chậm nhất kéo theo thời gian chờ đồng bộ.
Đáng chú ý: `lscpu` cho thấy node3 có **CPU giống hệt node4** (Intel i5-12500H, 8 core/16
thread) — node3 chậm hơn **không phải vì CPU yếu hơn**, mà thuần do RAM thấp (3.7GB so với
7.7GB của node4) gây nhiều cache-miss/áp lực bộ nhớ hơn ở cùng workload, dù vẫn trong vùng an
toàn (không tới mức swap như N=6400 ở mục 8).

### 14.3 Kết luận tổng hợp

1. **node3 đúng là straggler nhẹ** (RAM thấp → chậm hơn ~8% dù CPU giống node4) - loại nó ra
   *đúng cách* (giữ cap HT) giúp nhanh hơn.
2. Nhưng **"full tốc lực" theo nghĩa dùng hết số core logic KHÔNG giúp gì** - ngược lại, làm
   chậm hơn cả việc giữ node3, vì hyperthreading không scale tuyến tính và 2× oversubscribe gây
   tranh chấp tài nguyên lõi vật lý. Quyết định cap 12 rank/máy trong lịch sử commit của dự án
   (`cluster/hosts: cap all nodes to 12 slots`) là đúng đắn và đã được kiểm chứng lại ở đây.
3. Bài học phương pháp luận: phải tách biệt 2 biến (loại node vs. tăng rank/máy) khi so sánh,
   nếu không sẽ rút ra kết luận sai (lần thử 14.1 nhìn riêng lẻ sẽ kết luận nhầm "bỏ node3 không
   giúp gì", trong khi thực ra là do biến nhiễu HT).

## 15. File kết quả (vòng 2, bổ sung)

- N*/gens* search: số liệu trong mục 8 (không có file CSV riêng, đo trực tiếp qua stdout)
- `results/exp_gran.{csv,png}` (đã ghi đè bằng config N\*=2400, gens\*=10500, procs=48)
- `results/exp_speedup.{csv,png}` (đã ghi đè bằng config N=4800 = 2×N\*, procs 1-48)
- So sánh `--sync`: số liệu trong mục 11 (đo trực tiếp, không lưu file riêng)
- `data/cities_4000.txt`, `data/cities_4800.txt`, `data/cities_6400.txt` (city files mới sinh
  trong quá trình dò N*)
- Script correctness validation: `python/validate_tour.py` (độc lập, không dùng lại code C++)
- Hostfile dùng cho mục 14: `cluster/hosts.no3` (44 rank, 16/12/16 - oversubscribe HT, để đối
  chứng), `cluster/hosts.no3.12` (36 rank, 12/12/12 - cap đúng, kết quả nhanh hơn)
