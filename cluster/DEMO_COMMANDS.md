# Sổ tay lệnh demo - cụm 4 máy (node1-node4)

Tổng hợp MỌI lệnh cần để demo trực tiếp cho giảng viên: build, chạy 1 máy, chạy cả 4 máy thật,
visualization, sinh số liệu báo cáo. Copy-paste trực tiếp được (đã test thật trong session này).

## 0. Trước khi demo - kiểm tra cụm còn sống không

```bash
# Từ node2 (launcher) - ping + SSH tới 3 máy còn lại
for n in node1 node3 node4; do echo "== $n =="; ssh -o ConnectTimeout=5 $n 'hostname'; done

# Nếu IP đổi (đổi mạng/wifi) - cập nhật theo thứ tự:
# 1. /etc/hosts trên MỌI máy (map tên node -> IP mới)
# 2. ~/.ssh/config trên node2 (HostName của node1/node3/node4)
# 3. ssh -o StrictHostKeyChecking=accept-new <node> 'echo ok'   (chấp nhận host-key mới)
```

Nếu cần xác định lại IP nào ứng với node nào sau khi đổi mạng:
```bash
hostname -I                                  # IP của chính máy mình
for i in $(seq 1 14); do ping -c1 -W1 172.20.10.$i >/dev/null 2>&1 && echo "172.20.10.$i is up"; done
# rồi thử ssh user@<ip_nghi_ngờ> 'hostname' với từng username (bao/acer/khainx) để khớp tên máy
```

## 1. Build (chạy trên TỪNG máy, binary không portable giữa máy)

```bash
export PATH=/opt/openmpi-5.0.9/bin:$PATH
export LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib
cd ~/parallel-tsp/cpp && make CXX=/opt/openmpi-5.0.9/bin/mpicxx
make test          # unit test GA + local search, không cần MPI
```

Build trên cả 4 máy cùng lúc từ launcher (1 lệnh):
```bash
mpirun --hostfile cluster/hosts -N 1 bash -c 'cd ~/parallel-tsp/cpp && make CXX=/opt/openmpi-5.0.9/bin/mpicxx'
```

## 2. Chạy 1 máy (sanity check nhanh, không cần cụm)

```bash
export PATH=/opt/openmpi-5.0.9/bin:$PATH LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib
mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_50.txt --gens 500 --sync 20
```

## 3. Chạy CẢ 4 MÁY THẬT (demo chính)

### 3.1 Sanity check - mỗi rank chạy đúng trên máy nào
```bash
bash cluster/run_cluster.sh cluster/hosts 4 hostname
# kỳ vọng: in ra 4 hostname khác nhau (1 rank/máy)
```

### 3.2 Chạy GA thật, 4 islands (1 rank/máy) - DEMO ĐƠN GIẢN NHẤT
```bash
bash cluster/run_cluster.sh cluster/hosts 4 ./cpp/tsp_island data/cities_200.txt --gens 1000 --sync 50
```

### 3.3 Chạy FULL TỐC LỰC 48 ranks (12 rank/máy - dùng hết core, có log/stats)
```bash
bash cluster/run_cluster.sh cluster/hosts 48 ./cpp/tsp_island data/cities_2400.txt \
    --gens 10500 --sync 20 --stats results/demo_stats.csv
# runtime kỳ vọng ~150-160s (đã đo nhiều lần: 145.97s / 154.27s / 159.14s)
```

### 3.4 Baseline KHÔNG chia sẻ (so sánh) - `--sync 0`
```bash
bash cluster/run_cluster.sh cluster/hosts 48 ./cpp/tsp_island data/cities_4800.txt --gens 400 --sync 0
```

**Lưu ý quan trọng về hostfile:**
- `cluster/hosts` (4 dòng, `slots=12`) chỉ dùng được với **`-np ≤ 4`** vì launcher dùng
  `--map-by seq` (bỏ qua hoàn toàn trường `slots=`, cần đúng N dòng cho N rank).
- Muốn `-np` lớn hơn 4 (tới 48), dùng **`cluster/hosts.seq48`** (48 dòng, round-robin
  node1,node2,node3,node4,...) - đã có sẵn trong repo.
- File `--stats`/`--out` khi chạy cluster sẽ được **rank 0 ghi trên máy ĐẦU TIÊN trong
  hostfile** (thường là node1), KHÔNG phải trên launcher. Nếu cần lấy file đó về:
  ```bash
  scp node1:~/parallel-tsp/results/demo_stats.csv results/
  ```

## 4. Visualization (Python - chỉ vẽ, không có thuật toán)

**Cập nhật quan trọng**: `tsp_island --live <base>` giờ làm MỖI rank ghi file riêng
(`<base>.rank0`, `<base>.rank1`, ...) thay vì chỉ rank 0. `live_view.py` đọc TẤT CẢ file đó
cùng lúc và vẽ **grid 1 ô nhỏ/island** (route riêng của từng đảo, viền màu khác nhau) + 1 panel
convergence chung (đường mờ mỗi đảo + đường global-best đậm + marker xanh tại mỗi mốc sync) -
nhìn vào thấy ngay "N island đang đua song song, rồi học hỏi nhau qua di cư", thay vì chỉ 1
route trông đơn điệu như bản cũ.

**Để demo "xịn" hơn**: dùng N=100-200 thành phố (route nhìn có hình dạng rõ, đẹp hơn N=30/50
quá thưa) + `--islands 4` hoặc `6` (nhiều ô nhỏ nhìn ấn tượng hơn nhưng đừng quá 6, chữ sẽ
nhỏ khó đọc) + `--step` nhỏ (3-5) để animation chạy mượt, không nhảy cóc.

### 4.1 Vẽ route + convergence từ 1 lần chạy (ảnh tĩnh, để chèn slide)
```bash
export PATH=/opt/openmpi-5.0.9/bin:$PATH LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib
mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_200.txt --gens 1000 --sync 20 --out results/demo_tour.txt
python3 python/visualize.py route data/cities_200.txt results/demo_tour.txt --out results/demo_route.png
python3 python/visualize.py converge results/demo_tour.txt.history --out results/demo_converge.png
```

### 4.2 Demo TRỰC TIẾP grid nhiều island (mở window matplotlib, cho thầy xem trực tiếp) - LỆNH CHÍNH
```bash
export PATH=/opt/openmpi-5.0.9/bin:$PATH LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib
python3 python/live_view.py run data/cities_100.txt --islands 4 --gens 800 --sync 30 \
    --step 4 --interval 70
# mở 1 window: grid 4 ô route (mỗi đảo 1 màu viền) + convergence chung bên phải
# bấm đóng window để dừng khi xong
```
Muốn 6 island cho "hoành tráng" hơn (cần máy đủ mạnh, --oversubscribe nếu ít core):
```bash
python3 python/live_view.py run data/cities_150.txt --islands 6 --gens 800 --sync 30 --step 4
```

### 4.3 Demo "islands race" - xem N đảo tìm kiếm song song + di cư (overlay convergence)
```bash
mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_500.txt --gens 2000 --sync 100 --out results/race
python3 python/live_view.py race results/race --sync 100
```

### 4.4 Xem live MỘT LẦN CHẠY THẬT TRÊN CỤM (2 cửa sổ terminal, máy nào chạy nhiều rank ghi local)
```bash
# Terminal 1 (launcher, node2): chạy cụm thật với --live (lưu ý --islands ở terminal 2 PHẢI khớp -np ở đây)
bash cluster/run_cluster.sh cluster/hosts 4 ./cpp/tsp_island data/cities_100.txt \
    --gens 2000 --sync 30 --live results/stream.jsonl

# Terminal 2: theo dõi trực tiếp (chạy SONG SONG, không phải sau khi xong)
python3 python/live_view.py tail results/stream.jsonl data/cities_100.txt --islands 4 --sync 30
```
**Lưu ý nếu chạy thật trên NHIỀU MÁY (không phải 1 máy)**: mỗi rank ghi file `--live` trên máy
NÓ ĐANG CHẠY, không phải trên launcher - xem mục 4.6 để biết cách lấy file về real-time.

### 4.5 Xuất animation ra GIF (không cần mở window - dùng khi demo qua remote/headless, hoặc để gửi trước cho thầy)
```bash
MPLBACKEND=Agg python3 python/live_view.py run data/cities_100.txt --islands 4 --gens 800 \
    --sync 30 --step 4 --interval 80 --save results/demo_live.gif
# Pillow writer (không cần ffmpeg) - chậm, vài chục giây tới vài phút tuỳ số frame, CHẠY NỀN:
#   nohup <lệnh trên> > /tmp/gif.log 2>&1 &   rồi theo dõi: tail -f /tmp/gif.log
```

### 4.6b Demo TÙY BIẾN số island/máy (N rank/máy, không hardcode) - launch từ node1, xem ở node2

**Phát hiện quan trọng (đã test kỹ, không phải do gõ lệnh sai):** nếu máy LAUNCHER (máy gọi
`mpirun`/`run_cluster.sh`) vừa điều phối vừa TỰ nhận rank tính toán, VÀ có bất kỳ máy khác nhận
≥2 rank, job sẽ TREO VĨNH VIỄN (giới hạn thật của OpenMPI 5.0.9 + PRTE, không phải do code dự
án). Cách né an toàn: chọn 1 máy làm LAUNCHER THUẦN (không tự tính toán), các máy còn lại nhận
bao nhiêu rank cũng được.

Dùng `cluster/make_hostfile.sh <rank/máy> <node...>` để sinh hostfile theo số lượng tùy ý
(không cần viết tay file cố định cho từng số island):

```bash
# Trên node1 (launcher thuần - không tham gia compute):
ssh node1
cd ~/parallel-tsp
export PATH=/opt/openmpi-5.0.9/bin:$PATH LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib

# (1) chọn RANKS_PER_NODE và danh sách máy COMPUTE (không liệt kê node1 ở đây nếu node1 là launcher thuần)
RANKS_PER_NODE=3                       # đổi số này theo ý muốn (1, 2, 3, ...)
bash cluster/make_hostfile.sh "$RANKS_PER_NODE" node2 node3 node4 > /tmp/hosts_custom
cat /tmp/hosts_custom                  # kiểm tra lại trước khi chạy

# (2) kiểm tra node3 còn sống không (máy hay rớt wifi) trước khi chạy thật
ping -c2 -W2 node3

# (3) chạy job thật - np = RANKS_PER_NODE * số máy compute
NP=$(wc -l < /tmp/hosts_custom)
rm -f results/stream_custom.jsonl*
bash cluster/run_cluster.sh /tmp/hosts_custom "$NP" ./cpp/tsp_island data/cities_100.txt \
    --gens 30000 --sync 200 --live results/stream_custom.jsonl
exit   # về lại node2 (launcher của session SSH, không phải MPI)
```

```bash
# Trên node2 (nơi xem demo) - kéo file rank về rồi mở viewer:
cd ~/parallel-tsp   # hoặc path repo thật trên máy bạn

# Lưu ý: node1 SSH vào node2 bằng user khác (xem ~/.ssh/config trên node1, vd "mpiuser"),
# nên rank chạy trên CHÍNH MÁY NÀY có thể nằm ở $HOME của user đó, không phải $HOME của bạn -
# kiểm tra `ls /home/<user_đó>/parallel-tsp/results/` nếu rsync từ "node2:" không thấy file.

NP=9   # = RANKS_PER_NODE * 3 máy (vd RANKS_PER_NODE=3 ở trên) - đổi theo số bạn chọn
for ((r=0; r<NP; r++)); do
  for n in node2 node3 node4; do :; done   # (chỉ để nhắc: rank thuộc máy nào theo make_hostfile.sh là tuần tự theo từng máy)
done
# Đơn giản nhất: rsync TẤT CẢ rank file từ cả 3 máy compute, file không tồn tại sẽ tự bị rsync báo lỗi và bỏ qua:
for n in node2 node3 node4; do
  for ((i=0; i<NP; i++)); do
    rsync -az "$n:parallel-tsp/results/stream_custom.jsonl.rank$i" results/ 2>/dev/null
  done
done
ls -la results/stream_custom.jsonl.rank*   # phải thấy đủ NP file

# Mở viewer (islands = NP):
export PATH=/opt/openmpi-5.0.9/bin:$PATH LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib
python3 python/live_view.py tail results/stream_custom.jsonl data/cities_100.txt \
    --islands "$NP" --sync 200 --step 100 --interval 50
```

Đổi `RANKS_PER_NODE` (ví dụ 1, 2, 3, 4...) và đổi `NP` tương ứng ở bước cuối là customize được
số island theo ý - không cần sửa code, không cần file hostfile viết tay riêng cho từng số.

### 4.6a Demo THẬT trên ĐỦ 4 MÁY (node1+node2+node3+node4 - dùng khi node3 đã online)

Giống 4.6 nhưng với cả 4 node, dùng hostfile `cluster/hosts.demo4` (1 rank/máy, rank0->node1,
rank1->node2/launcher, rank2->node3, rank3->node4 nhờ `--map-by seq`):

```bash
cd ~/parallel-tsp
export PATH=/opt/openmpi-5.0.9/bin:$PATH LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib

# (1) chạy cụm thật 4 máy
rm -f results/stream4node.jsonl*
nohup bash cluster/run_cluster.sh cluster/hosts.demo4 4 ./cpp/tsp_island data/cities_100.txt \
    --gens 30000 --sync 200 --live results/stream4node.jsonl > /tmp/cluster4_run.log 2>&1 &

# (2) loop rsync nền - kéo file rank ở node1 (rank0), node3 (rank2), node4 (rank3) về local
#     (rank1 chạy trên launcher/node2 nên đã sẵn ở local)
nohup bash -c '
while pgrep -f "run_cluster.sh cluster/hosts.demo4" >/dev/null; do
  rsync -az node1:parallel-tsp/results/stream4node.jsonl.rank0 results/ 2>/dev/null
  rsync -az node3:parallel-tsp/results/stream4node.jsonl.rank2 results/ 2>/dev/null
  rsync -az node4:parallel-tsp/results/stream4node.jsonl.rank3 results/ 2>/dev/null
  sleep 1
done' > /tmp/sync_loop4.log 2>&1 &

# (3) mở viewer realtime (đợi vài giây cho bước 1-2 kịp ghi file đầu tiên)
sleep 4
python3 python/live_view.py tail results/stream4node.jsonl data/cities_100.txt --islands 4 --sync 200 --step 100 --interval 50
```

Dọn dẹp sau khi xem xong:
```bash
pkill -f "run_cluster.sh cluster/hosts.demo4"; pkill -f "rsync -az node"
ssh node1 'pkill -f tsp_island'; ssh node3 'pkill -f tsp_island'; ssh node4 'pkill -f tsp_island'
```

**Lưu ý quan trọng nếu trước đó từng đổi mạng/wifi** (như session này): cả `/etc/hosts` (trên
MỌI máy) VÀ `~/.ssh/config` (trên node2/launcher) phải khớp IP LAN hiện tại - chỉ sửa
`/etc/hosts` là CHƯA ĐỦ, vì `ssh`/`mpirun` resolve hostname theo `~/.ssh/config` trước (ssh
config override IP cũ → connection timed out, dù `ping nodeX` qua `/etc/hosts` vẫn ra). Sửa cả
hai rồi `ssh node1/node3/node4 'hostname'` phải trả đúng tên máy, không hỏi password, mới chạy
được job thật trên cụm. Username đúng cho từng máy: node1=bao, node3=acer, node4=khainx.

### 4.6 Demo THẬT trên NHIỀU MÁY (3 node: node1+node2+node4 - dùng khi node3 chưa kết nối được)

Vì các máy không có filesystem chung, file `--live` của rank chạy trên node1/node4 nằm TRÊN máy
đó, không tự về launcher. Cần 1 loop rsync nền kéo file về liên tục trong lúc job chạy:

```bash
cd ~/parallel-tsp   # hoặc path repo thật trên launcher (node2)
export PATH=/opt/openmpi-5.0.9/bin:$PATH LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib

# (1) hostfile 4 dòng, round-robin qua 3 máy (KHÔNG có node3) - đã có sẵn trong repo:
cat cluster/hosts.no3.demo4    # node1 node2 node4 node1

# (2) chạy cụm thật, --live ghi theo từng rank trên máy nó chạy
nohup bash cluster/run_cluster.sh cluster/hosts.no3.demo4 4 ./cpp/tsp_island data/cities_100.txt \
    --gens 30000 --sync 200 --live results/stream3node.jsonl > /tmp/cluster3_run.log 2>&1 &

# (3) loop rsync nền - kéo file rank ở node1 (rank0,3) và node4 (rank2) về local mỗi 1s
#     (rank1 chạy trên launcher/node2 nên đã sẵn ở local, không cần kéo)
nohup bash -c '
while pgrep -f "run_cluster.sh cluster/hosts.no3.demo4" >/dev/null; do
  rsync -az node1:parallel-tsp/results/stream3node.jsonl.rank0 results/ 2>/dev/null
  rsync -az node1:parallel-tsp/results/stream3node.jsonl.rank3 results/ 2>/dev/null
  rsync -az node4:parallel-tsp/results/stream3node.jsonl.rank2 results/ 2>/dev/null
  sleep 1
done' > /tmp/sync_loop.log 2>&1 &

# (4) mở viewer realtime (đợi vài giây cho bước 2-3 kịp ghi file đầu tiên)
sleep 4
python3 python/live_view.py tail results/stream3node.jsonl data/cities_100.txt --islands 4 --sync 200 --step 100 --interval 50
```

Lưu ý chọn `--gens` đủ lớn (vd 30000 ở N=100) để job KHÔNG xong quá nhanh (N nhỏ + gens nhỏ có
thể chạy xong dưới 1s, viewer mở ra sẽ thấy ngay "DONE" thay vì xem được quá trình hội tụ). Nếu
job đã chạy xong trước khi mở viewer, không sao - viewer vẫn REPLAY lại từ gen 1 theo `--step`
(không snap thẳng tới cuối), chỉ là không phải "trực tiếp đang tính" nữa mà là "replay dữ liệu
thật đã ghi" - vẫn là dữ liệu 3-máy thật 100%, chỉ khác ở tốc độ xem.

Dọn dẹp sau khi xem xong:
```bash
pkill -f "run_cluster.sh cluster/hosts.no3.demo4"; pkill -f "rsync -az node"
ssh node1 'pkill -f tsp_island'; ssh node4 'pkill -f tsp_island'
```

## 5. Sinh số liệu cho báo cáo (đã chạy thật, dùng lại khi cần tái tạo)

```bash
export PATH=/opt/openmpi-5.0.9/bin:$PATH LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib

# size: runtime vs N (N* search, gens=10500 cố định)
python3 python/experiments.py size --procs 48 --sizes 1200 1800 2400 --gens 10500 --sync 20 \
    --hostfile cluster/hosts.seq48

# gran: load-balance tại N*=2400
python3 python/experiments.py gran --procs 48 --size 2400 --gens 10500 --sync 20 \
    --hostfile cluster/hosts.seq48

# speedup: tại 2xN*=4800, procs 1->48
python3 python/experiments.py speedup --procs 1 2 4 8 16 32 48 --size 4800 --gens 400 --sync 20 \
    --hostfile cluster/hosts.seq48

# benchmark.py (đo speedup độc lập khác, fit Amdahl's law)
python3 python/benchmark.py data/cities_200.txt --procs 1 2 4 8 16 --total 480 --gens 400 \
    --hostfile cluster/hosts.seq48 --csv results/bench_cluster.csv --out results/speedup_cluster.png

# bộ 3 thí nghiệm cùng lúc (size+gran+speedup)
GENS=400 SIZES="1200 1800 2400" SPEEDUP_PROCS="1 2 4 8 16 32 48" GRAN_N=2400 SPEEDUP_N=4800 \
    bash cluster/run_report_experiments.sh cluster/hosts.seq48
```

## 6. Correctness validation (nếu thầy hỏi "sao biết đúng?")

```bash
export PATH=/opt/openmpi-5.0.9/bin:$PATH LD_LIBRARY_PATH=/opt/openmpi-5.0.9/lib
# N=8 - so brute-force optimal
mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_8.txt --gens 500 --sync 20 --out /tmp/v8
python3 python/validate_tour.py data/cities_8.txt "2 4 7 0 1 3 6 5" 240.49

# N=200 - permutation + recompute (N quá lớn cho brute-force)
mpirun --oversubscribe -np 4 ./cpp/tsp_island data/cities_200.txt --gens 500 --sync 20 --out /tmp/v200
# lấy $ROUTE, $BEST từ stdout rồi:
python3 python/validate_tour.py data/cities_200.txt "$ROUTE" "$BEST"
```

## 7. Dọn dẹp sau demo (nếu job bị Ctrl-C giữa chừng)

```bash
pkill -f tsp_island 2>/dev/null
for n in node1 node3 node4; do ssh $n 'pkill -f tsp_island 2>/dev/null; pkill -f prted 2>/dev/null'; done
```

## 8. Thông tin nhanh về cụm (để trả lời câu hỏi tại chỗ)

| Node | OS | CPU | RAM | Vai trò |
|---|---|---|---|---|
| node1 | Windows/WSL | AMD Ryzen 7 4800HS (8c/16t) | 7.5GB | |
| node2 | Ubuntu native | Intel i5-11400H (6c/12t) | 23GB | launcher |
| node3 | Windows/WSL | Intel i5-12500H (8c/16t) | 3.7GB | máy yếu nhất (RAM) |
| node4 | Windows/WSL | Intel i5-12500H (8c/16t) | 7.7GB | |

- OpenMPI 5.0.9 build từ nguồn, pinned tại `/opt/openmpi-5.0.9` trên mọi máy.
- Mọi node CAP 12 rank/máy (= số luồng của node2, máy yếu nhất) để tránh oversubscribe
  hyperthreading - đã đo thật: dùng đủ 16 luồng làm CHẬM hơn, không nhanh hơn.
- N* (runtime mục tiêu 2-3 phút) = 2400 thành phố, gens=10500 → ~150-160s thật.
- Speedup đỉnh đo được: 5.73x ở 16 procs (N=4800, 2×N*).
- **node3 hay bị rớt mạng/đổi IP** (Wi-Fi không ổn định) - nếu trước buổi demo `ssh node3
  'echo ok'` không vào được, dùng tạm `cluster/hosts.no3.demo4` (3 máy: node1+node2+node4) cho
  mục 4.6, hoặc `cluster/hosts.no3.12` (36 rank, 12/máy) nếu cần demo full tốc lực 3 máy. Đừng
  quên `rsync` 2 file `cpp/tsp_island.cpp` + `python/live_view.py` và rebuild trên node1/node4
  nếu vừa sửa code mà CHƯA commit+push (git pull trên các node đó sẽ không lấy được thay đổi
  chưa commit) - xem ví dụ ở mục 4.6.
