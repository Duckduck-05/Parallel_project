# Đồ án Lập trình song song — Island-GA cho TSP trên cụm MPI

Giải bài toán Người Giao Hàng (TSP) bằng **Giải thuật Di truyền mô hình Đảo**, song song
hóa bằng **MPI** trên cụm **3 máy Ubuntu** (VirtualBox Bridged + WiFi điện thoại).
Cài đặt ở **cả Python (mpi4py) lẫn C/C++ (OpenMPI)**.

## Cấu trúc thư mục
```
parallel-tsp/
  cluster/   # script + hướng dẫn dựng cụm (Task 1-4, 10)
  python/    # bản mpi4py: GA, island, migration, viz, benchmark
  cpp/       # bản OpenMPI C++ (cùng thuật toán)
  data/      # toạ độ thành phố + script sinh dữ liệu
  results/   # ảnh lộ trình, đồ thị hội tụ, biểu đồ speedup
  report/    # report.md + slides.md + hướng dẫn xuất PDF
```

## Bắt đầu nhanh (chạy thử trên 1 máy)
```bash
bash cluster/01_install.sh                       # cai OpenMPI + thu vien
cd python
python3 -m pytest test_ga_core.py -v             # test loi GA (7 PASS)
mpirun --oversubscribe -np 3 python3 tsp_island.py ../data/cities_50.txt --gens 500 --migrate 20
```

## Dựng cụm 3 máy (đọc theo thứ tự)
1. `cluster/01_install.sh` — cài trên cả 3 máy.
2. `cluster/TASK2_network_guide.md` — mạng Bridged + `/etc/hosts`.
3. `cluster/02_ssh_setup.sh` + `TASK3_ssh_guide.md` — SSH không mật khẩu.
4. `cluster/TASK4_hostfile_sharing_guide.md` — hostfile + rsync.
5. `cluster/TASK10_cluster_run_demo.md` — chạy thật + quay video.

## Chạy trên cụm
```bash
mpirun --hostfile cluster/hosts -np 3 \
    python3 python/tsp_island.py data/cities_50.txt --gens 500 --migrate 20
```
> Cụm 4 máy (mỗi thành viên 1 node): dùng `-np 4` và thêm dòng `node4 slots=2` vào
> `cluster/hosts`.

## (Tùy chọn) Cụm các máy ở xa qua Tailscale
Nếu các máy **không cùng WiFi** (khác nhà/khác mạng), có thể nối chúng bằng VPN overlay
**Tailscale** — mỗi máy có IP `100.x` cố định xuyên NAT, MPI chạy y như trong LAN. Vẫn tự
cài OpenMPI/SSH/hostfile như bình thường (chỉ thay lớp mạng). Hướng dẫn:
- `docs/TASK_remote_tailscale_guide.md` — dựng cụm từ xa.
- `docs/TEAM_wsl_tailscale_setup.md` — gửi cho thành viên cài WSL + Tailscale.

> ⚠️ **Hỏi giảng viên trước.** Thuê server đám mây (GCP/AWS) bị trừ điểm vì "dựng cụm là
> một phần lập trình". Tailscale **khác** (vẫn dùng máy của mình, tự dựng cụm), nhưng nên
> xác nhận với giảng viên cho chắc.

## Bản C++
```bash
cd cpp && mpicxx -O2 -o tsp_island tsp_island.cpp
mpirun --hostfile ../cluster/hosts -np 3 ./tsp_island ../data/cities_50.txt --gens 500 --migrate 20
```

## Trực quan hóa THỜI GIAN THỰC (`python/live_view.py`)
Xem GA tiến hóa **trực tiếp**: trái = lộ trình tốt nhất vẽ lại mỗi thế hệ, phải = đồ thị
hội tụ lớn dần (1 đường/đảo + đường đỏ đậm = tốt nhất toàn cục, vạch xanh = thời điểm di cư).

**Chế độ 1 — demo trên 1 máy (KHÔNG cần MPI):** chạy GA nhiều đảo ngay trong tiến trình.
```bash
cd python
python3 live_view.py run ../data/cities_30.txt --islands 4 --gens 400 --migrate 20
# tuy chon: --twoopt 25 (Memetic) | --every 2 (muot hon) | --save demo.gif | --save-final last.png
```

**Chế độ 2 — bám đuôi lần chạy MPI THẬT trên cụm:** `tsp_island.py --live` để rank 0 ghi
luồng JSONL (1 dòng/thế hệ, **chỉ IO trên rank 0, không thêm giao tiếp MPI** nên không làm
sai benchmark); `live_view.py tail` đọc và vẽ trực tiếp.
```bash
# cua so 1 (may chu / rank 0):
mpirun --hostfile ../cluster/hosts -np 4 python3 tsp_island.py ../data/cities_50.txt \
       --gens 500 --migrate 20 --live ../results/stream.jsonl
# cua so 2:
python3 live_view.py tail ../results/stream.jsonl ../data/cities_50.txt
```

---

## Phân công & số dòng code (yêu cầu ≥250 dòng/người, ≥1000 dòng/nhóm)

| Thành viên | Nhiệm vụ | File chính |
|---|---|---|
| **Trưởng nhóm** | Hạ tầng cụm + benchmark + ráp máy thật | `cluster/*.sh`, `cluster/*.md`, `python/benchmark.py` |
| **Thành viên 2** | Lõi GA (fitness, OX, mutation) | `python/ga_core.py`, `cpp/ga_core.hpp`, `*/test_ga_core.*` |
| **Thành viên 3** | Tầng MPI: island + di cư ring | `python/tsp_island.py`, `cpp/tsp_island.cpp` |
| **Thành viên 4** | I/O + visualization + report + slide | `data/generate_cities.py`, `python/visualize.py`, `report/*` |

> **Số dòng code hiện tại:** ~911 dòng code thuần (Python + C++ + shell), chưa tính
> ~600 dòng tài liệu hướng dẫn (`.md`) và report. Nếu cần đủ **1000 dòng code thuần**,
> xem mục mở rộng bên dưới — mỗi ý thêm ~80-150 dòng và đều tăng điểm "độ khó".

### Gợi ý mở rộng (nếu muốn tăng dòng code + điểm)
- Thêm **tối ưu cục bộ 2-opt đầy đủ** trên mỗi đảo (vòng lặp cải thiện cạnh).
- Thêm cấu trúc di cư **lưới 2D** hoặc **sao** ngoài ring (so sánh trong report).
- Thêm bản đọc file TSPLIB chuẩn + so sánh với nghiệm tối ưu đã biết.
- ✅ **Đã làm:** trực quan hóa real-time + animation (matplotlib FuncAnimation) — `python/live_view.py`.

---

## Checklist trả bài (mỗi thành viên phải hiểu phần mình + tổng thể)

- [ ] Trưởng nhóm: giải thích được Bridged Adapter, hostfile, vì sao SSH không mật khẩu.
- [ ] TV2: giải thích OX crossover bảo toàn hoán vị thế nào, tournament selection.
- [ ] TV3: giải thích `Sendrecv` tránh deadlock, `MINLOC` lấy rank đảo tốt nhất.
- [ ] TV4: giải thích đồ thị hội tụ + biểu đồ speedup, định luật Amdahl.
- [ ] Cả nhóm: demo chạy được trên 3–4 máy thật (video) + nộp report PDF.
- [ ] Điền Google Sheet: tăng group-id +1, thêm màu mới cho nhóm.

> 🔒 **Bảo mật:** cụm chỉ bảo vệ bằng khóa SSH trên WiFi nội bộ, không có xác thực tầng
> ứng dụng. Phù hợp môi trường lab; không mở ra Internet.
