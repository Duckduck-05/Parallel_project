# Đồ án Lập trình song song — Island-GA giải TSP trên cụm MPI

> **File tổng hợp duy nhất**: hướng dẫn sử dụng + toàn bộ mã nguồn (Python & C++) + phân
> việc đọc cho 4 thành viên. Tổng **1231 dòng code thuần** (đã vượt yêu cầu 1000 dòng).

**Chủ đề:** Giải bài toán Người Giao Hàng (TSP) bằng **Giải thuật Di truyền mô hình Đảo**
(Island-model GA), song song hóa bằng **MPI**, có **di cư vòng ring** và **tối ưu cục bộ
2-opt** (Memetic Algorithm). Cài đặt ở **cả Python (mpi4py) lẫn C/C++ (OpenMPI)**.

---

## 0. ĐỀ BÀI & Ý TƯỞNG (đọc phần này TRƯỚC khi xem code)

### 0.1. Đề bài của thầy (nguyên văn tóm tắt)
> Lập một nhóm 4 người, dựng một **cụm MPI gồm ít nhất 3 máy vật lý**. Sau khi dựng xong,
> cài đặt một **thuật toán song song** trên cụm đó. Điểm phụ thuộc vào **độ khó/độ thú vị
> của bài toán và thuật toán**. Cụ thể chấm theo: (1) chủ đề có thú vị không, (2) bài toán
> được **song song hóa** thế nào, (3) **demo có chạy** không, (4) **report** tốt không,
> (5) **mỗi thành viên có hiểu code** của nhóm không. Yêu cầu **tối thiểu 250 dòng code/người
> → ≥1000 dòng cho nhóm 4 người**. Demo **offline** (được precompute), phải nộp **report**.

**Kiến trúc cụm gợi ý:** dùng điện thoại phát WiFi làm mạng LAN; 3 máy Windows, **mỗi máy
cài 1 máy ảo Ubuntu** (VirtualBox, mạng để **Bridged Adapter**); KHÔNG cài 2 VM trên 1 máy.

### 0.2. Nhóm mình chọn làm gì? (giải thích cho người chưa biết gì)

**Bài toán: TSP — Người Giao Hàng.**
Tưởng tượng một shipper phải giao hàng tới N địa điểm rồi quay về kho. Hỏi: đi theo **thứ
tự nào** để **tổng quãng đường ngắn nhất**? Nghe đơn giản nhưng số cách sắp xếp là giai
thừa — với 50 điểm đã có ~3×10⁶² cách, máy tính mạnh nhất cũng không thử hết nổi. Đây là
bài toán **NP-hard** kinh điển, rất "đáng giá" để làm đồ án.

**Cách giải: Giải thuật Di truyền (GA) — bắt chước tiến hóa tự nhiên.**
Vì không thử hết được, ta "tiến hóa" dần ra lời giải tốt:
- Mỗi **lời giải** (một thứ tự đi các thành phố) = một **"cá thể"**.
- Một tập nhiều cá thể = một **"quần thể"**.
- Qua mỗi **"thế hệ"**: giữ lại cá thể tốt (lộ trình ngắn), cho chúng **"lai ghép"** sinh
  con, thỉnh thoảng **"đột biến"** (đổi chỗ vài thành phố). Cá thể tốt sống sót, cá thể tệ
  bị loại — giống chọn lọc tự nhiên. Sau nhiều thế hệ, quần thể hội tụ về lời giải tốt.

**Song song hóa: Mô hình "Đảo" (Island model) — phần ăn điểm nhất.**
Thay vì 1 quần thể chạy trên 1 máy, ta cho **mỗi máy nuôi 1 quần thể riêng** gọi là một
**"hòn đảo"**. 3 máy = 3 đảo tiến hóa **cùng lúc** (đây chính là *song song*). Mỗi đảo bắt
đầu khác nhau nên khám phá các vùng lời giải khác nhau.

**Di cư (Migration): các đảo "trao đổi" cá thể tốt.**
Cứ sau một số thế hệ, mỗi đảo gửi **cá thể tốt nhất** của mình cho đảo bên cạnh (xếp thành
**vòng tròn** — đảo 0→1→2→0). Nhờ đó cái hay của đảo này lan sang đảo khác → cả nhóm cùng
tốt lên nhanh hơn. Đây là lúc các máy **giao tiếp với nhau qua mạng** — phần "song song
thật sự" mà thầy muốn thấy.

**Memetic (nâng cao): thêm "2-opt" để đánh bóng lời giải.**
GA tìm tốt ở tầm tổng quát nhưng hay để sót các đoạn đường **bắt chéo nhau** (rõ ràng là
phí). **2-opt** là kỹ thuật gỡ các nút chéo đó: nếu thấy 2 cạnh cắt nhau thì đảo lại một
đoạn để chúng hết cắt → tour ngắn hơn. GA + 2-opt = **Memetic Algorithm**, cho nghiệm
đẹp hơn hẳn (trong thực nghiệm: từ ~1181 xuống ~537).

### 0.3. MPI là gì? Vì sao dùng?
**MPI (Message Passing Interface)** là "ngôn ngữ chung" để nhiều tiến trình chạy trên
**nhiều máy khác nhau** nói chuyện với nhau bằng cách **gửi/nhận thông điệp**. Ta dùng MPI để:
- Khởi chạy đồng thời 3 tiến trình (3 đảo) trên 3 máy bằng 1 lệnh `mpirun`.
- Cho các đảo **gửi cá thể di cư** cho nhau (`Sendrecv`).
- **Gom kết quả** cuối cùng để tìm đảo có lời giải tốt nhất (`Allreduce`).

| Thuật ngữ | Nghĩa nôm na |
|---|---|
| **process / rank** | một tiến trình MPI; ở đây = một hòn đảo. `rank` là số thứ tự (0,1,2). |
| **`mpirun -np 3`** | chạy chương trình thành 3 process cùng lúc. |
| **`hostfile`** | file liệt kê các máy trong cụm (node1, node2, node3). |
| **`Sendrecv`** | gửi và nhận thông điệp **đồng thời** (dùng để di cư, tránh kẹt). |
| **`Allreduce(MINLOC)`** | tất cả cùng tìm giá trị nhỏ nhất + biết nó ở máy nào. |
| **Bridged Adapter** | chế độ mạng cho máy ảo có IP riêng như máy thật trong LAN. |

### 0.4. Vì sao chọn bài này? (lý lẽ để trả lời thầy)
- **Thú vị & khó:** TSP là bài NP-hard nổi tiếng; Island-GA + di cư + 2-opt là kỹ thuật
  HPC thật, không phải chia việc tầm thường.
- **Song song hóa rõ ràng:** có giao tiếp thật giữa các máy (di cư, gom kết quả).
- **Chạy tốt trên WiFi yếu:** mỗi đảo tính nhiều, chỉ trao đổi 1 cá thể nhỏ mỗi lần →
  ít phụ thuộc mạng.
- **Dễ demo đẹp:** vẽ được lộ trình + đồ thị hội tụ + biểu đồ speedup.
- **Dễ chia 4 người & dễ hiểu** để ai cũng trả bài được.

### 0.5. Luồng hoạt động tổng thể
```
Đọc toạ độ thành phố
        │
        ▼
Mỗi máy (đảo) khởi tạo quần thể ngẫu nhiên riêng
        │
        ▼
Lặp qua các thế hệ:
   ├─ Tiến hóa: chọn lọc → lai ghép (OX) → đột biến → giữ tinh hoa
   ├─ (Memetic) Đánh bóng cá thể tốt nhất bằng 2-opt
   └─ (Mỗi K thế hệ) Di cư: gửi cá thể tốt nhất sang đảo kế bên (vòng ring)
        │
        ▼
Gom kết quả: Allreduce(MINLOC) → tìm đảo có lộ trình ngắn nhất
        │
        ▼
Rank 0 in & lưu lộ trình + lịch sử hội tụ → vẽ hình, đo speedup
```

### 0.6. Bảng thuật ngữ GA (tra nhanh khi đọc code)
| Thuật ngữ | Nghĩa | Ở hàm nào |
|---|---|---|
| Cá thể (individual) | một lộ trình = hoán vị các thành phố | `random_tour` |
| Độ thích nghi (fitness) | lộ trình càng ngắn càng tốt | `tour_length` |
| Chọn lọc giải đấu | bốc k cá thể, giữ cái tốt nhất | `tournament_select` |
| Lai ghép OX | ghép 2 cha thành con hợp lệ | `order_crossover` |
| Đột biến | đổi chỗ / đảo đoạn ngẫu nhiên | `mutate` |
| Tinh hoa (elitism) | luôn giữ cá thể tốt nhất | trong `evolve` |
| Di cư (migration) | trao đổi cá thể giữa các đảo | `tsp_island` |
| 2-opt / Or-opt | gỡ cạnh chéo / dời điểm | `local_search` |

---

## 1. Thống kê số dòng code (1231 dòng)

| Nhóm file | File | Dòng |
|---|---|---|
| **Python** | `ga_core.py` | 105 |
| | `local_search.py` (2-opt/Or-opt) | 79 |
| | `tsp_island.py` (MPI) | 117 |
| | `tsp_sequential.py` | 42 |
| | `benchmark.py` | 100 |
| | `visualize.py` | 70 |
| | `test_ga_core.py` | 64 |
| | `test_local_search.py` | 69 |
| | `generate_cities.py` | 40 |
| **C/C++** | `ga_core.hpp` | 117 |
| | `local_search.hpp` | 62 |
| | `tsp_island.cpp` (MPI) | 108 |
| | `tsp_sequential.cpp` | 43 |
| | `test_ga_core.cpp` | 54 |
| | `test_local_search.cpp` | 51 |
| **Shell + hello** | `01_install.sh`, `02_ssh_setup.sh`, `03_sync_code.sh`, `hello.c`, `hello.py` | 110 |
| | **TỔNG** | **1231** |

---

## 2. Phân việc đọc cho 4 thành viên

Mỗi người chịu trách nhiệm hiểu sâu phần của mình (để trả lời thầy) **và** nắm tổng thể.

### 👤 Thành viên 1 — Hạ tầng cụm & Hiệu năng (~210 dòng)
- **Đọc:** `01_install.sh`, `02_ssh_setup.sh`, `03_sync_code.sh`, `hello.c`, `hello.py`,
  `benchmark.py`.
- **Phải giải thích được:** Bridged Adapter là gì; vì sao cần SSH không mật khẩu; hostfile;
  speedup S(p)=T(1)/T(p), efficiency, định luật Amdahl.

### 👤 Thành viên 2 — Lõi Giải thuật Di truyền (~340 dòng)
- **Đọc:** `python/ga_core.py`, `cpp/ga_core.hpp`, `test_ga_core.py`, `test_ga_core.cpp`.
- **Phải giải thích được:** biểu diễn cá thị bằng hoán vị; tournament selection; **OX
  crossover bảo toàn hoán vị thế nào**; mutation; elitism.

### 👤 Thành viên 3 — Tầng MPI: Đảo + Di cư (~225 dòng)
- **Đọc:** `python/tsp_island.py`, `cpp/tsp_island.cpp`.
- **Phải giải thích được:** mỗi process = 1 đảo; **vì sao `Sendrecv` tránh deadlock**;
  `Allreduce(MINLOC)` lấy cả giá trị lẫn rank; gửi tour về rank 0.

### 👤 Thành viên 4 — Tối ưu cục bộ + Trực quan hóa (~320 dòng)
- **Đọc:** `python/local_search.py`, `cpp/local_search.hpp`, `test_local_search.py`,
  `test_local_search.cpp`, `visualize.py`, `generate_cities.py`.
- **Phải giải thích được:** **2-opt gỡ cạnh chéo** thế nào; Or-opt; Memetic = GA + local
  search; cách vẽ lộ trình & đồ thị hội tụ.

---

## 3. Hướng dẫn sử dụng nhanh

### 3.1. Cài đặt (mỗi máy)
```bash
bash cluster/01_install.sh
```

### 3.2. Test lõi thuật toán (1 máy)
```bash
cd python
python3 -m pytest test_ga_core.py test_local_search.py -v   # 10 test PASS
python3 tsp_sequential.py ../data/cities_30.txt --gens 500
```

### 3.3. Chạy song song (1 máy, 3 đảo)
```bash
# co di cu:
mpirun --oversubscribe -np 3 python3 tsp_island.py ../data/cities_50.txt --gens 500 --migrate 20
# Memetic (them 2-opt) -> nghiem tot hon nhieu:
mpirun --oversubscribe -np 3 python3 tsp_island.py ../data/cities_50.txt --gens 500 --migrate 20 --twoopt 25
```

### 3.4. Chạy trên cụm 3 máy
```bash
mpirun --hostfile cluster/hosts -np 3 \
    python3 python/tsp_island.py data/cities_50.txt --gens 500 --migrate 20 --twoopt 25
```

### 3.5. Bản C++
```bash
cd cpp && mpicxx -O2 -o tsp_island tsp_island.cpp
mpirun --hostfile ../cluster/hosts -np 3 ./tsp_island ../data/cities_50.txt --gens 500 --migrate 20 --twoopt 25
```

### 3.6. Vẽ hình + đo speedup
```bash
cd python
python3 visualize.py route ../data/cities_50.txt ../results/tour_mig.txt --out ../results/route.png
python3 benchmark.py ../data/cities_50.txt --procs 1 2 3 4 --total 240 --gens 400
```

### Tham số chương trình island
| Cờ | Ý nghĩa |
|---|---|
| `--gens N` | số thế hệ |
| `--pop N` | quần thể mỗi đảo |
| `--migrate K` | di cư mỗi K thế hệ (0 = tắt) |
| `--twoopt K` | đánh bóng 2-opt mỗi K thế hệ (0 = tắt; bật = Memetic) |
| `--out FILE` | lưu tour + lịch sử hội tụ |

---

# PHẦN A — MÃ NGUỒN PYTHON

## A1. `python/ga_core.py` — Lõi Giải thuật Di truyền (105 dòng)

```python
#!/usr/bin/env python3
"""ga_core.py - Task 5: Lõi Giải thuật Di truyền (GA) cho bài toán TSP."""
import numpy as np


def read_cities(path):
    """Đọc file toạ độ thành phố. Mỗi dòng: 'x y' (bỏ dòng trống / bắt đầu bằng #)."""
    pts = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            x, y = line.split()[:2]
            pts.append((float(x), float(y)))
    return np.array(pts, dtype=float)


def distance_matrix(coords):
    """Ma trận khoảng cách Euclid NxN giữa mọi cặp thành phố."""
    diff = coords[:, None, :] - coords[None, :, :]
    return np.sqrt((diff ** 2).sum(axis=2))


def tour_length(tour, D):
    """Tổng độ dài lộ trình khép kín (quay về điểm đầu)."""
    return float(D[tour, np.roll(tour, -1)].sum())


def random_tour(n, rng):
    """Một lộ trình ngẫu nhiên: hoán vị của 0..n-1."""
    return rng.permutation(n)


def tournament_select(pop, lengths, k, rng):
    """Chọn k cá thể ngẫu nhiên, trả về bản sao của cá thể tốt nhất (tour ngắn nhất)."""
    idx = rng.integers(0, len(pop), size=k)
    best = min(idx, key=lambda i: lengths[i])
    return pop[best].copy()


def order_crossover(p1, p2, rng):
    """Lai ghép thứ tự (OX): giữ một đoạn của p1, điền phần còn lại theo thứ tự của p2.
    Bảo đảm con là hoán vị hợp lệ (đủ và không trùng thành phố)."""
    n = len(p1)
    a, b = sorted(rng.integers(0, n, size=2))
    child = -np.ones(n, dtype=int)
    child[a:b + 1] = p1[a:b + 1]
    taken = set(p1[a:b + 1].tolist())
    fill = [c for c in p2 if c not in taken]
    j = 0
    for i in range(n):
        if child[i] == -1:
            child[i] = fill[j]
            j += 1
    return child


def mutate(tour, rate, rng):
    """Đột biến tại chỗ: đổi chỗ 2 thành phố, và đảo ngược 1 đoạn (kiểu 2-opt)."""
    if rng.random() < rate:
        i, j = rng.integers(0, len(tour), size=2)
        tour[i], tour[j] = tour[j], tour[i]
    if rng.random() < rate:
        i, j = sorted(rng.integers(0, len(tour), size=2))
        tour[i:j + 1] = tour[i:j + 1][::-1]


def evolve(D, pop_size, generations, rng,
           elite=1, tournament_k=5, mutation_rate=0.3, on_generation=None):
    """Vòng tiến hóa GA. Trả về (tour tốt nhất, độ dài, lịch sử độ dài tốt nhất mỗi thế hệ)."""
    n = D.shape[0]
    pop = [random_tour(n, rng) for _ in range(pop_size)]
    lengths = [tour_length(t, D) for t in pop]
    history = []

    for gen in range(generations):
        order = np.argsort(lengths)
        pop = [pop[i] for i in order]
        new_pop = pop[:elite]                       # giữ tinh hoa
        while len(new_pop) < pop_size:
            p1 = tournament_select(pop, lengths, tournament_k, rng)
            p2 = tournament_select(pop, lengths, tournament_k, rng)
            child = order_crossover(p1, p2, rng)
            mutate(child, mutation_rate, rng)
            new_pop.append(child)
        pop = new_pop

        if on_generation is not None:
            on_generation(gen, pop)                 # móc di cư (Task 7)

        lengths = [tour_length(t, D) for t in pop]
        history.append(min(lengths))

    best = int(np.argmin(lengths))
    return pop[best], lengths[best], history
```

## A2. `python/local_search.py` — Tối ưu cục bộ 2-opt + Or-opt (79 dòng)

```python
#!/usr/bin/env python3
"""local_search.py - Tối ưu cục bộ 2-opt + Or-opt cho TSP (biến GA -> Memetic Algorithm)."""
import numpy as np


def two_opt_once(tour, D, max_no_improve=None):
    """Một lượt 2-opt first-improvement: đảo ngược đoạn [i+1, j] nếu làm tour ngắn hơn.
    2-opt loại bỏ giao nhau: thay 2 cạnh (a-b),(c-d) bằng (a-c),(b-d). O(n^2)/lượt."""
    n = len(tour)
    t = tour.copy()
    improved = False
    for i in range(n - 1):
        a, b = t[i], t[(i + 1) % n]
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue                       # không tách cạnh khép kín đầu-cuối
            c, d = t[j], t[(j + 1) % n]
            delta = (D[a, c] + D[b, d]) - (D[a, b] + D[c, d])
            if delta < -1e-9:
                t[i + 1:j + 1] = t[i + 1:j + 1][::-1]
                improved = True
                break
        if improved:
            break
    return t, improved


def two_opt(tour, D, max_iter=1000):
    """Lặp 2-opt đến cực tiểu cục bộ hoặc hết max_iter."""
    t = tour.copy()
    for _ in range(max_iter):
        t, improved = two_opt_once(t, D)
        if not improved:
            break
    return t


def or_opt(tour, D, seg_len=1, max_iter=200):
    """Or-opt: dời một đoạn dài seg_len sang vị trí khác nếu giảm độ dài (bổ trợ 2-opt)."""
    n = len(tour)
    t = tour.copy()
    for _ in range(max_iter):
        improved = False
        for i in range(n):
            seg = [t[(i + k) % n] for k in range(seg_len)]
            prev = t[(i - 1) % n]
            nxt = t[(i + seg_len) % n]
            removed = D[prev, seg[0]] + D[seg[-1], nxt] - D[prev, nxt]
            rest = [c for c in t if c not in seg]
            for p in range(len(rest)):
                a, b = rest[p], rest[(p + 1) % len(rest)]
                added = D[a, seg[0]] + D[seg[-1], b] - D[a, b]
                if added - removed < -1e-9:
                    t = np.array(rest[:p + 1] + seg + rest[p + 1:])
                    improved = True
                    break
            if improved:
                break
        if not improved:
            break
    return t


def polish(tour, D, seg_len=2):
    """Đánh bóng cá thể: chạy 2-opt rồi Or-opt. Dùng trong Memetic-GA."""
    t = two_opt(tour, D)
    t = or_opt(t, D, seg_len=seg_len)
    return t
```

## A3. `python/tsp_island.py` — Island-GA song song MPI (117 dòng)

```python
#!/usr/bin/env python3
"""tsp_island.py - Task 6 & 7: Island-model GA cho TSP chạy song song bằng MPI.

Mỗi process = 1 "đảo" chạy GA độc lập với seed riêng. Mỗi --migrate thế hệ các đảo DI CƯ
cá thể tốt nhất sang đảo kế bên theo VÒNG RING (Sendrecv). Gom kết quả bằng Allreduce(MINLOC).
Task 6 (không di cư): --migrate 0.   Memetic: thêm --twoopt K.
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
    rng = np.random.default_rng(args.seed + rank * 1000)  # mỗi đảo 1 seed

    left = (rank - 1) % size      # hàng xóm trái trong vòng ring
    right = (rank + 1) % size     # hàng xóm phải

    pop = [ga.random_tour(n, rng) for _ in range(args.pop)]
    lengths = [ga.tour_length(t, D) for t in pop]
    history = []

    comm.Barrier()
    t0 = MPI.Wtime()

    for gen in range(args.gens):
        # --- 1 thế hệ tiến hóa ---
        order = np.argsort(lengths)
        pop = [pop[i] for i in order]
        new_pop = pop[:1]
        while len(new_pop) < args.pop:
            p1 = ga.tournament_select(pop, lengths, 5, rng)
            p2 = ga.tournament_select(pop, lengths, 5, rng)
            child = ga.order_crossover(p1, p2, rng)
            ga.mutate(child, 0.3, rng)
            new_pop.append(child)
        pop = new_pop
        lengths = [ga.tour_length(t, D) for t in pop]

        # --- MEMETIC: đánh bóng cá thể tốt nhất bằng 2-opt ---
        if args.twoopt > 0 and (gen + 1) % args.twoopt == 0:
            bi = int(np.argmin(lengths))
            polished = ls.polish(pop[bi], D)
            pop[bi] = polished
            lengths[bi] = ga.tour_length(polished, D)

        # --- DI CƯ theo vòng ring ---
        if args.migrate > 0 and (gen + 1) % args.migrate == 0 and size > 1:
            best_local = pop[int(np.argmin(lengths))]
            incoming = comm.sendrecv(best_local.copy(), dest=right, source=left)
            worst = int(np.argmax(lengths))      # thay cá thể tệ nhất bằng khách di cư
            pop[worst] = incoming
            lengths[worst] = ga.tour_length(incoming, D)

        history.append(min(lengths))

    comm.Barrier()
    elapsed = MPI.Wtime() - t0

    # --- Gom kết quả: tìm đảo có tour ngắn nhất bằng Allreduce(MINLOC) ---
    local_best = min(lengths)
    global_best, best_rank = comm.allreduce((local_best, rank), op=MPI.MINLOC)

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
            np.savetxt(args.out + ".history", history, fmt="%.4f")
            print(f"Da luu tour -> {args.out} va lich su -> {args.out}.history")


if __name__ == "__main__":
    main()
```

## A4. `python/tsp_sequential.py` — GA tuần tự (42 dòng)

```python
#!/usr/bin/env python3
"""tsp_sequential.py - Task 5: Chạy GA tuần tự trên 1 process cho 1 bài TSP."""
import argparse
import time
import numpy as np
import ga_core as ga


def main():
    ap = argparse.ArgumentParser(description="GA tuan tu cho TSP")
    ap.add_argument("cities", help="file toa do thanh pho")
    ap.add_argument("--gens", type=int, default=500, help="so the he")
    ap.add_argument("--pop", type=int, default=200, help="kich thuoc quan the")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", default=None, help="file luu tour tot nhat")
    args = ap.parse_args()

    coords = ga.read_cities(args.cities)
    D = ga.distance_matrix(coords)
    rng = np.random.default_rng(args.seed)

    t0 = time.time()
    tour, length, history = ga.evolve(D, args.pop, args.gens, rng)
    dt = time.time() - t0

    print(f"So thanh pho   : {len(coords)}")
    print(f"The he         : {args.gens}, quan the: {args.pop}")
    print(f"Do dai tot nhat: {length:.2f}")
    print(f"Thoi gian       : {dt:.2f}s")
    print(f"Lo trinh        : {tour.tolist()}")

    if args.out:
        np.savetxt(args.out, tour, fmt="%d")
        print(f"Da luu tour vao {args.out}")


if __name__ == "__main__":
    main()
```

## A5. `python/benchmark.py` — Đo speedup & efficiency (100 dòng)

```python
#!/usr/bin/env python3
"""benchmark.py - Task 9: Đo speedup & efficiency của Island-GA theo số process.
Giữ TỔNG quần thể cố định (--total), chia đều cho các đảo -> strong scaling S(p)=T(1)/T(p)."""
import argparse
import re
import subprocess
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

TIME_RE = re.compile(r"Thoi gian\s*:\s*([0-9.]+)")


def run_once(prog_cmd, np_count, hostfile, total, gens, cities):
    pop = max(1, total // np_count)        # chia đều tổng quần thể cho các đảo
    cmd = ["mpirun"]
    if hostfile:
        cmd += ["--hostfile", hostfile]
    else:
        cmd += ["--oversubscribe", "--mca", "btl", "self,sm,vader"]
    cmd += ["-np", str(np_count)] + prog_cmd + [
        cities, "--gens", str(gens), "--pop", str(pop), "--migrate", "20"]
    out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
    m = TIME_RE.search(out)
    return float(m.group(1))


def amdahl(p, s):
    """Định luật Amdahl: tăng tốc lý thuyết với phần tuần tự s."""
    return 1.0 / (s + (1 - s) / p)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cities")
    ap.add_argument("--procs", type=int, nargs="+", default=[1, 2, 3, 4])
    ap.add_argument("--total", type=int, default=240, help="tong quan the")
    ap.add_argument("--gens", type=int, default=400)
    ap.add_argument("--reps", type=int, default=3, help="so lan lap lay min")
    ap.add_argument("--hostfile", default=None)
    ap.add_argument("--lang", choices=["py", "cpp"], default="py")
    ap.add_argument("--csv", default="../results/bench.csv")
    ap.add_argument("--out", default="../results/speedup.png")
    args = ap.parse_args()

    prog = ["python3", "tsp_island.py"] if args.lang == "py" else ["./tsp_island"]

    rows = []
    for p in args.procs:
        times = [run_once(prog, p, args.hostfile, args.total, args.gens, args.cities)
                 for _ in range(args.reps)]
        t = min(times)                     # lấy min để giảm nhiễu
        rows.append((p, t))
        print(f"np={p:2d}  time={t:.3f}s")

    t1 = rows[0][1]
    procs = [r[0] for r in rows]
    speedup = [t1 / r[1] for r in rows]
    eff = [s / p for s, p in zip(speedup, procs)]

    with open(args.csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["procs", "time_s", "speedup", "efficiency"])
        for (p, t), s, e in zip(rows, speedup, eff):
            w.writerow([p, f"{t:.4f}", f"{s:.4f}", f"{e:.4f}"])
    print(f"Da luu {args.csv}")

    grid = np.linspace(0.001, 0.5, 500)
    err = [sum((amdahl(p, s) - sp) ** 2 for p, sp in zip(procs, speedup)) for s in grid]
    s_fit = grid[int(np.argmin(err))]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
    ax1.plot(procs, speedup, "o-", label="thuc te")
    ax1.plot(procs, procs, "k--", label="ly tuong (tuyen tinh)")
    ax1.plot(procs, [amdahl(p, s_fit) for p in procs], "r:", label=f"Amdahl (s={s_fit:.3f})")
    ax1.set_xlabel("So process"); ax1.set_ylabel("Speedup")
    ax1.set_title("Speedup"); ax1.legend(); ax1.grid(alpha=0.3)

    ax2.plot(procs, eff, "s-", color="green")
    ax2.axhline(1.0, ls="--", color="k")
    ax2.set_xlabel("So process"); ax2.set_ylabel("Efficiency")
    ax2.set_title("Efficiency = Speedup / p"); ax2.set_ylim(0, 1.2); ax2.grid(alpha=0.3)

    plt.tight_layout(); plt.savefig(args.out, dpi=130)
    print(f"Da luu {args.out}")


if __name__ == "__main__":
    main()
```

## A6. `python/visualize.py` — Vẽ lộ trình + đồ thị hội tụ (70 dòng)

```python
#!/usr/bin/env python3
"""visualize.py - Task 8: Vẽ lộ trình tốt nhất + đồ thị hội tụ (xuất PNG cho slide)."""
import argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")            # không cần màn hình -> chạy tốt trên VM/server
import matplotlib.pyplot as plt
import ga_core as ga


def plot_route(cities_file, tour_file, out):
    coords = ga.read_cities(cities_file)
    tour = np.loadtxt(tour_file, dtype=int)
    D = ga.distance_matrix(coords)
    length = ga.tour_length(tour, D)
    loop = np.append(tour, tour[0])          # khép kín vòng

    plt.figure(figsize=(7, 6))
    plt.plot(coords[loop, 0], coords[loop, 1], "-o", ms=5, lw=1.2)
    plt.plot(coords[tour[0], 0], coords[tour[0], 1], "rs", ms=10, label="diem xuat phat")
    plt.title(f"Lo trinh TSP tot nhat — do dai = {length:.2f} ({len(tour)} thanh pho)")
    plt.xlabel("x"); plt.ylabel("y"); plt.legend(); plt.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(out, dpi=130)
    print(f"Da luu {out}")


def plot_converge(history_files, out):
    plt.figure(figsize=(7, 5))
    for hf in history_files:
        hist = np.loadtxt(hf)
        label = hf.split("/")[-1].replace(".history", "")
        plt.plot(hist, lw=1.5, label=label)
    plt.title("Do thi hoi tu (do dai tour tot nhat theo the he)")
    plt.xlabel("The he"); plt.ylabel("Do dai tour tot nhat")
    plt.legend(); plt.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(out, dpi=130)
    print(f"Da luu {out}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("route", help="ve lo trinh tot nhat")
    r.add_argument("cities"); r.add_argument("tour")
    r.add_argument("--out", default="route.png")

    c = sub.add_parser("converge", help="ve do thi hoi tu (1 hoac nhieu file)")
    c.add_argument("history", nargs="+")
    c.add_argument("--out", default="converge.png")

    args = ap.parse_args()
    if args.cmd == "route":
        plot_route(args.cities, args.tour, args.out)
    else:
        plot_converge(args.history, args.out)


if __name__ == "__main__":
    main()
```

## A7. `data/generate_cities.py` — Sinh dữ liệu thành phố (40 dòng)

```python
#!/usr/bin/env python3
"""generate_cities.py - Task 8: Sinh dữ liệu toạ độ thành phố cho TSP (random / cluster)."""
import argparse
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50, help="so thanh pho")
    ap.add_argument("--mode", choices=["random", "cluster"], default="random")
    ap.add_argument("--size", type=float, default=100.0, help="kich thuoc vung")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    rng = np.random.default_rng(args.seed)
    if args.mode == "random":
        pts = rng.uniform(0, args.size, size=(args.n, 2))
    else:
        k = max(2, int(np.sqrt(args.n) / 2))         # ~sqrt(n)/2 cụm Gauss
        centers = rng.uniform(0, args.size, size=(k, 2))
        idx = rng.integers(0, k, size=args.n)
        pts = centers[idx] + rng.normal(0, args.size * 0.06, size=(args.n, 2))
        pts = np.clip(pts, 0, args.size)

    with open(args.out, "w") as f:
        f.write(f"# {args.n} thanh pho, mode={args.mode}, seed={args.seed}\n")
        for x, y in pts:
            f.write(f"{x:.2f} {y:.2f}\n")
    print(f"Da sinh {args.n} thanh pho ({args.mode}) -> {args.out}")


if __name__ == "__main__":
    main()
```

## A8. `python/test_ga_core.py` — Test lõi GA (64 dòng)

```python
#!/usr/bin/env python3
"""test_ga_core.py - Task 5: Unit test cho lõi GA. Chạy: python3 -m pytest test_ga_core.py -v"""
import numpy as np
import ga_core as ga


def _square_D():
    coords = np.array([[0, 0], [0, 1], [1, 1], [1, 0]], dtype=float)  # vuông cạnh 1
    return coords, ga.distance_matrix(coords)


def test_distance_matrix_symmetric():
    _, D = _square_D()
    assert np.allclose(D, D.T)
    assert np.allclose(np.diag(D), 0)


def test_tour_length_known():
    _, D = _square_D()
    assert abs(ga.tour_length(np.array([0, 1, 2, 3]), D) - 4.0) < 1e-9   # chu vi = 4
    assert ga.tour_length(np.array([0, 2, 1, 3]), D) > 4.0               # đường chéo dài hơn


def test_ox_valid_permutation():
    rng = np.random.default_rng(0)
    p1 = np.array([0, 1, 2, 3, 4, 5])
    p2 = np.array([5, 4, 3, 2, 1, 0])
    for _ in range(100):
        child = ga.order_crossover(p1, p2, rng)
        assert sorted(child.tolist()) == [0, 1, 2, 3, 4, 5]   # hoán vị hợp lệ


def test_mutate_keeps_permutation():
    rng = np.random.default_rng(1)
    for _ in range(100):
        tour = rng.permutation(8)
        ga.mutate(tour, rate=1.0, rng=rng)
        assert sorted(tour.tolist()) == list(range(8))


def test_evolve_improves():
    rng = np.random.default_rng(7)
    coords = rng.random((20, 2))
    D = ga.distance_matrix(coords)
    start = ga.tour_length(ga.random_tour(20, rng), D)
    _, best, history = ga.evolve(D, pop_size=80, generations=150, rng=rng)
    assert best < start
    assert history[-1] <= history[0]


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\nTat ca {len(fns)} test PASS.")
```

## A9. `python/test_local_search.py` — Test 2-opt / Or-opt (69 dòng)

```python
#!/usr/bin/env python3
"""test_local_search.py - Unit test cho 2-opt / Or-opt."""
import numpy as np
import ga_core as ga
import local_search as ls


def _perm_ok(t, n):
    return sorted(np.asarray(t).tolist()) == list(range(n))


def test_two_opt_keeps_permutation():
    rng = np.random.default_rng(0)
    coords = rng.random((15, 2))
    D = ga.distance_matrix(coords)
    for _ in range(20):
        t = ga.random_tour(15, rng)
        assert _perm_ok(ls.two_opt(t, D), 15)


def test_two_opt_not_worse():
    rng = np.random.default_rng(1)
    coords = rng.random((20, 2))
    D = ga.distance_matrix(coords)
    for _ in range(20):
        t = ga.random_tour(20, rng)
        before = ga.tour_length(t, D)
        assert ga.tour_length(ls.two_opt(t, D), D) <= before + 1e-9


def test_two_opt_fixes_crossing():
    coords = np.array([[0, 0], [0, 1], [1, 1], [1, 0]], dtype=float)
    D = ga.distance_matrix(coords)
    fixed = ls.two_opt(np.array([0, 2, 1, 3]), D)   # thứ tự chéo -> sửa về chu vi 4
    assert abs(ga.tour_length(fixed, D) - 4.0) < 1e-9


def test_or_opt_not_worse():
    rng = np.random.default_rng(2)
    coords = rng.random((18, 2))
    D = ga.distance_matrix(coords)
    for _ in range(15):
        t = ga.random_tour(18, rng)
        before = ga.tour_length(t, D)
        assert ga.tour_length(ls.or_opt(t, D, seg_len=2), D) <= before + 1e-9


def test_polish_improves_random():
    rng = np.random.default_rng(3)
    coords = rng.random((25, 2))
    D = ga.distance_matrix(coords)
    t = ga.random_tour(25, rng)
    assert ga.tour_length(ls.polish(t, D), D) < ga.tour_length(t, D)


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"OK  {fn.__name__}")
    print(f"\nTat ca {len(fns)} test PASS.")
```

# PHẦN B — MÃ NGUỒN C/C++

## B1. `cpp/ga_core.hpp` — Lõi GA (117 dòng)

```cpp
// ga_core.hpp - Task 5: Lõi GA cho TSP (bản C++), dùng chung cho bản MPI.
#pragma once
#include <vector>
#include <random>
#include <algorithm>
#include <cmath>
#include <numeric>
#include <fstream>
#include <sstream>
#include <string>

using Tour = std::vector<int>;

// Đọc file toạ độ "x y" mỗi dòng (bỏ dòng trống / bắt đầu bằng #).
inline std::vector<std::pair<double,double>> read_cities(const std::string& path) {
    std::vector<std::pair<double,double>> pts;
    std::ifstream f(path);
    std::string line;
    while (std::getline(f, line)) {
        if (line.empty() || line[0] == '#') continue;
        std::istringstream ss(line);
        double x, y;
        if (ss >> x >> y) pts.emplace_back(x, y);
    }
    return pts;
}

// Ma trận khoảng cách Euclid phẳng NxN (truy cập D[i*n+j]).
inline std::vector<double> distance_matrix(const std::vector<std::pair<double,double>>& c) {
    int n = (int)c.size();
    std::vector<double> D(n * n);
    for (int i = 0; i < n; i++)
        for (int j = 0; j < n; j++) {
            double dx = c[i].first - c[j].first, dy = c[i].second - c[j].second;
            D[i * n + j] = std::sqrt(dx * dx + dy * dy);
        }
    return D;
}

// Tổng độ dài lộ trình khép kín.
inline double tour_length(const Tour& t, const std::vector<double>& D, int n) {
    double s = 0.0;
    for (int i = 0; i < n; i++) s += D[t[i] * n + t[(i + 1) % n]];
    return s;
}

inline Tour random_tour(int n, std::mt19937& rng) {
    Tour t(n);
    std::iota(t.begin(), t.end(), 0);
    std::shuffle(t.begin(), t.end(), rng);
    return t;
}

// Chọn lọc giải đấu: trả về bản sao cá thể tốt nhất trong k cá thể ngẫu nhiên.
inline Tour tournament_select(const std::vector<Tour>& pop,
                              const std::vector<double>& len, int k, std::mt19937& rng) {
    std::uniform_int_distribution<int> pick(0, (int)pop.size() - 1);
    int best = pick(rng);
    for (int i = 1; i < k; i++) {
        int c = pick(rng);
        if (len[c] < len[best]) best = c;
    }
    return pop[best];
}

// Lai ghép thứ tự (OX): giữ đoạn [a,b] của p1, điền phần còn lại theo thứ tự p2.
inline Tour order_crossover(const Tour& p1, const Tour& p2, std::mt19937& rng) {
    int n = (int)p1.size();
    std::uniform_int_distribution<int> pick(0, n - 1);
    int a = pick(rng), b = pick(rng);
    if (a > b) std::swap(a, b);
    Tour child(n, -1);
    std::vector<char> taken(n, 0);
    for (int i = a; i <= b; i++) { child[i] = p1[i]; taken[p1[i]] = 1; }
    int j = 0;
    for (int i = 0; i < n; i++) {
        if (child[i] != -1) continue;
        while (taken[p2[j]]) j++;
        child[i] = p2[j++];
    }
    return child;
}

// Đột biến: đổi chỗ 2 thành phố + đảo ngược 1 đoạn (kiểu 2-opt).
inline void mutate(Tour& t, double rate, std::mt19937& rng) {
    std::uniform_real_distribution<double> prob(0.0, 1.0);
    std::uniform_int_distribution<int> pick(0, (int)t.size() - 1);
    if (prob(rng) < rate) std::swap(t[pick(rng)], t[pick(rng)]);
    if (prob(rng) < rate) {
        int a = pick(rng), b = pick(rng);
        if (a > b) std::swap(a, b);
        std::reverse(t.begin() + a, t.begin() + b + 1);
    }
}

// Một thế hệ tiến hóa (in-place trên pop & len). Tách riêng để bản MPI tái dùng.
inline void evolve_one_gen(std::vector<Tour>& pop, std::vector<double>& len,
                           const std::vector<double>& D, int n,
                           int elite, int k, double mut, std::mt19937& rng) {
    std::vector<int> order(pop.size());
    std::iota(order.begin(), order.end(), 0);
    std::sort(order.begin(), order.end(),
              [&](int a, int b) { return len[a] < len[b]; });
    std::vector<Tour> np;
    np.reserve(pop.size());
    for (int i = 0; i < elite; i++) np.push_back(pop[order[i]]);
    while ((int)np.size() < (int)pop.size()) {
        Tour p1 = tournament_select(pop, len, k, rng);
        Tour p2 = tournament_select(pop, len, k, rng);
        Tour child = order_crossover(p1, p2, rng);
        mutate(child, mut, rng);
        np.push_back(std::move(child));
    }
    pop.swap(np);
    for (size_t i = 0; i < pop.size(); i++) len[i] = tour_length(pop[i], D, n);
}
```

## B2. `cpp/local_search.hpp` — 2-opt + Or-opt (62 dòng)

```cpp
// local_search.hpp - Tối ưu cục bộ 2-opt + Or-opt cho TSP (bản C++).
#pragma once
#include "ga_core.hpp"

// Một lượt 2-opt (first-improvement): đảo đoạn [i+1, j] nếu làm tour ngắn hơn.
inline bool two_opt_once(Tour& t, const std::vector<double>& D, int n) {
    for (int i = 0; i < n - 1; i++) {
        int a = t[i], b = t[(i + 1) % n];
        for (int j = i + 2; j < n; j++) {
            if (i == 0 && j == n - 1) continue;       // giữ cạnh khép kín
            int c = t[j], d = t[(j + 1) % n];
            double delta = (D[a * n + c] + D[b * n + d]) - (D[a * n + b] + D[c * n + d]);
            if (delta < -1e-9) {
                std::reverse(t.begin() + i + 1, t.begin() + j + 1);
                return true;
            }
        }
    }
    return false;
}

inline void two_opt(Tour& t, const std::vector<double>& D, int n, int max_iter = 1000) {
    for (int it = 0; it < max_iter; it++)
        if (!two_opt_once(t, D, n)) break;          // lặp đến cực tiểu cục bộ
}

// Or-opt: dời 1 thành phố sang vị trí tốt hơn (bổ trợ 2-opt).
inline bool or_opt_once(Tour& t, const std::vector<double>& D, int n) {
    for (int i = 0; i < n; i++) {
        int prev = t[(i - 1 + n) % n], cur = t[i], nxt = t[(i + 1) % n];
        double removed = D[prev * n + cur] + D[cur * n + nxt] - D[prev * n + nxt];
        for (int j = 0; j < n; j++) {
            if (j == i || j == (i - 1 + n) % n) continue;
            int a = t[j], b = t[(j + 1) % n];
            double added = D[a * n + cur] + D[cur * n + b] - D[a * n + b];
            if (added - removed < -1e-9) {
                Tour nt;
                nt.reserve(n);
                for (int k = 0; k < n; k++) {
                    if (k == i) continue;
                    nt.push_back(t[k]);
                    if (t[k] == a) nt.push_back(cur);
                }
                if ((int)nt.size() == n) { t.swap(nt); return true; }
            }
        }
    }
    return false;
}

inline void or_opt(Tour& t, const std::vector<double>& D, int n, int max_iter = 200) {
    for (int it = 0; it < max_iter; it++)
        if (!or_opt_once(t, D, n)) break;
}

// Đánh bóng cá thể: 2-opt rồi Or-opt.
inline void polish(Tour& t, const std::vector<double>& D, int n) {
    two_opt(t, D, n);
    or_opt(t, D, n);
}
```

## B3. `cpp/tsp_island.cpp` — Island-GA song song MPI (108 dòng)

```cpp
// tsp_island.cpp - Task 6 & 7: Island-model GA cho TSP song song bằng MPI (C++).
// Biên dịch: mpicxx -O2 -o tsp_island tsp_island.cpp
// Chạy cụm:  mpirun --hostfile ../cluster/hosts -np 3 ./tsp_island ../data/cities_50.txt --migrate 20 --twoopt 25
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

    // --- đọc tham số ---
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
    std::mt19937 rng(seed + rank * 1000);   // mỗi đảo 1 seed
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

        // --- MEMETIC: đánh bóng cá thể tốt nhất bằng 2-opt ---
        if (twoopt > 0 && (g + 1) % twoopt == 0) {
            int bi = (int)(std::min_element(len.begin(), len.end()) - len.begin());
            polish(pop[bi], D, n);
            len[bi] = tour_length(pop[bi], D, n);
        }

        // --- DI CƯ vòng ring ---
        if (migrate > 0 && (g + 1) % migrate == 0 && size > 1) {
            int bi = (int)(std::min_element(len.begin(), len.end()) - len.begin());
            sendbuf = pop[bi];
            // Sendrecv: gửi sang phải, nhận từ trái, tránh deadlock.
            MPI_Sendrecv(sendbuf.data(), n, MPI_INT, right, 0,
                         recvbuf.data(), n, MPI_INT, left, 0,
                         MPI_COMM_WORLD, MPI_STATUS_IGNORE);
            int wi = (int)(std::max_element(len.begin(), len.end()) - len.begin());
            pop[wi] = recvbuf;                 // thay cá thể tệ nhất
            len[wi] = tour_length(pop[wi], D, n);
        }
    }

    MPI_Barrier(MPI_COMM_WORLD);
    double elapsed = MPI_Wtime() - t0;

    // --- Gom kết quả: Reduce(MINLOC) tìm đảo có tour ngắn nhất ---
    int bi = (int)(std::min_element(len.begin(), len.end()) - len.begin());
    struct { double val; int rank; } in{len[bi], rank}, out;
    MPI_Allreduce(&in, &out, 1, MPI_DOUBLE_INT, MPI_MINLOC, MPI_COMM_WORLD);

    // đảo thắng gửi tour về rank 0
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
```

## B4. `cpp/tsp_sequential.cpp` — GA tuần tự (43 dòng)

```cpp
// tsp_sequential.cpp - Task 5: Chạy GA tuần tự (C++) cho 1 bài TSP.
// Biên dịch: g++ -O2 -o tsp_seq tsp_sequential.cpp ; Chạy: ./tsp_seq ../data/cities_30.txt 300 150 42
#include "ga_core.hpp"
#include <iostream>
#include <chrono>

int main(int argc, char** argv) {
    if (argc < 2) { std::cerr << "Dung: " << argv[0]
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
    std::cout << "So thanh pho   : " << n << "\n"
              << "The he         : " << gens << ", quan the: " << pop_size << "\n"
              << "Do dai tot nhat: " << len[best] << "\n"
              << "Thoi gian       : " << secs << "s\n";
    std::cout << "Lo trinh        :";
    for (int c : pop[best]) std::cout << " " << c;
    std::cout << "\n";
    return 0;
}
```

## B5. `cpp/test_ga_core.cpp` — Test lõi GA (54 dòng)

```cpp
// test_ga_core.cpp - Task 5: Unit test cho lõi GA bản C++.
// Biên dịch: g++ -O2 -o test_ga test_ga_core.cpp && ./test_ga
#include "ga_core.hpp"
#include <iostream>
#include <cassert>

static int passed = 0;
#define CHECK(cond, name) do { if (!(cond)) { \
    std::cerr << "FAIL " << name << "\n"; return 1; } \
    std::cout << "OK  " << name << "\n"; passed++; } while (0)

static bool is_permutation(const Tour& t, int n) {
    std::vector<char> seen(n, 0);
    for (int c : t) { if (c < 0 || c >= n || seen[c]) return false; seen[c] = 1; }
    return (int)t.size() == n;
}

int main() {
    std::vector<std::pair<double,double>> sq = {{0,0},{0,1},{1,1},{1,0}};  // vuông cạnh 1
    auto D = distance_matrix(sq);

    CHECK(std::abs(D[0*4+0]) < 1e-9, "distance_matrix_diag_zero");
    CHECK(std::abs(tour_length({0,1,2,3}, D, 4) - 4.0) < 1e-9, "tour_length_known");
    CHECK(tour_length({0,2,1,3}, D, 4) > 4.0, "diagonal_longer");

    std::mt19937 rng(0);
    Tour p1 = {0,1,2,3,4,5}, p2 = {5,4,3,2,1,0};
    for (int i = 0; i < 100; i++)
        CHECK(is_permutation(order_crossover(p1, p2, rng), 6), "ox_valid_perm");

    for (int i = 0; i < 100; i++) {
        Tour t = random_tour(8, rng);
        mutate(t, 1.0, rng);
        CHECK(is_permutation(t, 8), "mutate_keeps_perm");
    }

    std::mt19937 r2(7);                              // evolve cải thiện so với ngẫu nhiên
    std::vector<std::pair<double,double>> pts;
    std::uniform_real_distribution<double> u(0, 1);
    for (int i = 0; i < 20; i++) pts.emplace_back(u(r2), u(r2));
    auto D2 = distance_matrix(pts);
    double start = tour_length(random_tour(20, r2), D2, 20);
    std::vector<Tour> pop(80);
    std::vector<double> len(80);
    for (int i = 0; i < 80; i++) { pop[i] = random_tour(20, r2); len[i] = tour_length(pop[i], D2, 20); }
    for (int g = 0; g < 150; g++) evolve_one_gen(pop, len, D2, 20, 1, 5, 0.3, r2);
    double best = *std::min_element(len.begin(), len.end());
    CHECK(best < start, "evolve_improves");

    std::cout << "\nTat ca test PASS (" << passed << " kiem tra).\n";
    return 0;
}
```

## B6. `cpp/test_local_search.cpp` — Test 2-opt / Or-opt (51 dòng)

```cpp
// test_local_search.cpp - Unit test cho 2-opt / Or-opt (C++).
// Biên dịch: g++ -O2 -o test_ls test_local_search.cpp && ./test_ls
#include "local_search.hpp"
#include <iostream>

static int passed = 0;
#define CHECK(cond, name) do { if (!(cond)) { \
    std::cerr << "FAIL " << name << "\n"; return 1; } \
    passed++; } while (0)

static bool is_perm(const Tour& t, int n) {
    std::vector<char> seen(n, 0);
    for (int c : t) { if (c < 0 || c >= n || seen[c]) return false; seen[c] = 1; }
    return (int)t.size() == n;
}

int main() {
    std::mt19937 rng(0);

    std::vector<std::pair<double,double>> sq = {{0,0},{0,1},{1,1},{1,0}};
    auto Dsq = distance_matrix(sq);
    Tour crossed = {0, 2, 1, 3};
    two_opt(crossed, Dsq, 4);
    CHECK(std::abs(tour_length(crossed, Dsq, 4) - 4.0) < 1e-9, "two_opt_fixes_crossing");

    std::vector<std::pair<double,double>> pts;
    std::uniform_real_distribution<double> u(0, 1);
    for (int i = 0; i < 20; i++) pts.emplace_back(u(rng), u(rng));
    auto D = distance_matrix(pts);
    for (int rep = 0; rep < 30; rep++) {
        Tour t = random_tour(20, rng);
        double before = tour_length(t, D, 20);
        Tour t2 = t; two_opt(t2, D, 20);
        CHECK(is_perm(t2, 20), "two_opt_perm");
        CHECK(tour_length(t2, D, 20) <= before + 1e-9, "two_opt_not_worse");
        Tour t3 = t; or_opt(t3, D, 20);
        CHECK(is_perm(t3, 20), "or_opt_perm");
        CHECK(tour_length(t3, D, 20) <= before + 1e-9, "or_opt_not_worse");
    }

    Tour t = random_tour(20, rng);                  // polish cải thiện tour ngẫu nhiên
    double before = tour_length(t, D, 20);
    polish(t, D, 20);
    CHECK(tour_length(t, D, 20) < before, "polish_improves");

    std::cout << "Tat ca test PASS (" << passed << " kiem tra).\n";
    return 0;
}
```

# PHẦN C — SCRIPT DỰNG CỤM

## C1. `cluster/01_install.sh` — Cài đặt (21 dòng)

```bash
#!/usr/bin/env bash
# Task 1 - Cai dat OpenMPI + cong cu can thiet tren MOI may Ubuntu.
set -e

echo "==> Cap nhat danh sach goi..."
sudo apt update

echo "==> Cai OpenMPI, trinh bien dich C/C++, va thu vien Python..."
sudo apt install -y \
    openmpi-bin libopenmpi-dev build-essential \
    python3-pip python3-mpi4py python3-numpy python3-matplotlib \
    openssh-server rsync

echo "==> Kiem tra phien ban:"
mpirun --version
mpicc --version | head -n 1
python3 -c "import mpi4py; print('mpi4py OK', mpi4py.__version__)"

echo ""
echo "HOAN TAT. Buoc tiep theo: chay thu hello (xem README cluster)."
```

## C2. `cluster/02_ssh_setup.sh` — SSH không mật khẩu (38 dòng)

```bash
#!/usr/bin/env bash
# Task 3 - Thiet lap SSH khong can mat khau giua cac node.
# Chay tren TUNG may (node1, node2, node3): bash 02_ssh_setup.sh
set -e

NODES=(node1 node2 node3)
USER_NAME=$(whoami)

echo "==> Bao dam co OpenSSH server..."
sudo apt install -y openssh-server
sudo systemctl enable --now ssh

# 1) Tao khoa SSH neu chua co (khong dat passphrase de MPI tu dong dang nhap).
if [ ! -f "$HOME/.ssh/id_rsa" ]; then
    echo "==> Tao cap khoa SSH..."
    ssh-keygen -t rsa -b 4096 -N "" -f "$HOME/.ssh/id_rsa"
else
    echo "==> Da co khoa SSH, bo qua buoc tao."
fi

# 2) Chep khoa cong khai sang TAT CA node.
echo "==> Chep khoa cong khai sang cac node (se hoi mat khau LAN DAU)..."
for n in "${NODES[@]}"; do
    ssh-copy-id -o StrictHostKeyChecking=no "${USER_NAME}@${n}" || \
        echo "   (Bo qua $n neu chua bat hoac la chinh may nay)"
done

echo ""
echo "==> DEMO kiem tra: dang nhap khong mat khau"
for n in "${NODES[@]}"; do
    echo -n "ssh $n => "
    ssh -o BatchMode=yes -o StrictHostKeyChecking=no "${USER_NAME}@${n}" hostname || \
        echo "CHUA OK (chay lai script tren $n)"
done

echo ""
echo "Neu moi dong in ra dung ten node ma KHONG hoi mat khau => Task 3 HOAN TAT."
```

## C3. `cluster/03_sync_code.sh` — Đồng bộ code (18 dòng)

```bash
#!/usr/bin/env bash
# Task 4 - Dong bo thu muc code sang cac node khac bang rsync.
# Chay tren node1 (may chu): bash 03_sync_code.sh
set -e

NODES=(node2 node3)              # cac may dich (khong gom node1)
SRC="$HOME/parallel-tsp"          # thu muc du an
USER_NAME=$(whoami)

for n in "${NODES[@]}"; do
    echo "==> Dong bo sang $n ..."
    rsync -avz --delete \
        --exclude '.git' --exclude 'results/*.png' \
        "$SRC/" "${USER_NAME}@${n}:$SRC/"
done

echo "HOAN TAT. Code tren ca 3 may da giong nhau."
```

## C4. `cluster/hello.c` & `cluster/hello.py` — Hello MPI (33 dòng)

```c
/* hello.c - Task 1: kiem tra OpenMPI. mpicc hello.c -o hello && mpirun -np 4 ./hello */
#include <mpi.h>
#include <stdio.h>

int main(int argc, char **argv) {
    MPI_Init(&argc, &argv);
    int rank, size, len;
    char node[MPI_MAX_PROCESSOR_NAME];
    MPI_Comm_rank(MPI_COMM_WORLD, &rank);
    MPI_Comm_size(MPI_COMM_WORLD, &size);
    MPI_Get_processor_name(node, &len);
    printf("Hello tu process %d / %d tren may %s\n", rank, size, node);
    MPI_Finalize();
    return 0;
}
```

```python
#!/usr/bin/env python3
"""hello.py - Task 1: kiem tra mpi4py. mpirun -np 4 python3 hello.py"""
from mpi4py import MPI

comm = MPI.COMM_WORLD
print(f"Hello tu process {comm.Get_rank()} / {comm.Get_size()} tren may {MPI.Get_processor_name()}")
```

---

> **Hướng dẫn dựng cụm chi tiết** (mạng Bridged, /etc/hosts, hostfile, demo, quay video):
> xem các file `cluster/TASK2_network_guide.md`, `TASK3_ssh_guide.md`,
> `TASK4_hostfile_sharing_guide.md`, `TASK10_cluster_run_demo.md`.
> **Report đầy đủ + slide:** xem thư mục `report/`.
