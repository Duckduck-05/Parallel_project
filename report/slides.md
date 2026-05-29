# Slides — Island-GA cho TSP trên cụm MPI

> Dùng cho thuyết trình. Mỗi `---` là một slide. Có thể mở bằng **Marp** (VS Code
> extension "Marp for VS Code") hoặc copy từng slide sang PowerPoint/Google Slides.
> Xuất PDF bằng Marp: `marp slides.md -o slides.pdf`.

---

# Giải thuật Di truyền Mô hình Đảo
## giải bài toán Người Giao Hàng (TSP) trên cụm MPI

Môn Lập trình song song — Nhóm _(tên nhóm)_
4 thành viên: _(liệt kê)_

---

## Bài toán: TSP

- Cho N thành phố → tìm lộ trình khép kín **ngắn nhất**, qua mỗi thành phố đúng 1 lần.
- **NP-hard**: N=50 → ~3×10⁶² lộ trình, không duyệt hết được.
- Giải pháp: **Giải thuật Di truyền (GA)** — tìm nghiệm gần tối ưu nhanh.

---

## Vì sao song song hóa?

- GA cần quần thể lớn + nhiều thế hệ → chậm.
- **Mô hình Đảo**: chia quần thể thành nhiều "đảo" chạy **đồng thời** trên nhiều máy.
- **Di cư** cá thể tốt giữa các đảo → vừa nhanh, vừa cho nghiệm tốt hơn.
- Tỉ lệ tính/giao tiếp **cao** → chạy tốt cả trên WiFi điện thoại.

---

## Giải thuật Di truyền (tuần tự)

- Cá thể = hoán vị thứ tự thành phố.
- **Chọn lọc giải đấu** (tournament).
- **Lai ghép thứ tự OX** → con luôn là hoán vị hợp lệ.
- **Đột biến**: đổi chỗ + đảo đoạn (2-opt).
- **Giữ tinh hoa**: nghiệm không bao giờ xấu đi.

---

## Song song hóa: Mô hình Đảo + Di cư Ring

```
 Đảo 0 ─► Đảo 1 ─► Đảo 2 ─┐
   ▲                       │
   └───────────────────────┘   (vòng ring)
```

- Mỗi **process MPI = 1 đảo** (seed khác nhau).
- Mỗi K thế hệ: gửi cá thể tốt nhất sang đảo kế (`MPI_Sendrecv`).
- Gom kết quả: `MPI_Allreduce(MPI_MINLOC)`.

---

## Các lời gọi MPI

| Lời gọi | Vai trò |
|---|---|
| `Sendrecv` | Di cư theo ring (tránh deadlock) |
| `Allreduce(MINLOC)` | Tìm đảo có tour ngắn nhất |
| `Send`/`Recv` | Gửi lộ trình về rank 0 |
| `Barrier` | Đồng bộ đo thời gian |

---

## Kiến trúc cụm

```
   📱 WiFi điện thoại (LAN)
 ┌──────┬──────┬──────┐
 Win1   Win2   Win3
 VM     VM     VM
 node1  node2  node3   (Bridged Adapter)
```

- 3 máy thật, mỗi máy 1 VM Ubuntu.
- SSH không mật khẩu + OpenMPI + rsync.

---

## Kết quả 1 — Di cư có lợi

| Chế độ | Độ dài tour |
|---|---|
| Không di cư | ~1344 |
| **Có di cư** | **~1181** (−12%) |

![](../results/converge.png)

---

## Kết quả 2 — Speedup

| Process | Speedup | Efficiency |
|---|---|---|
| 1 | 1.00 | 100% |
| 2 | 1.90 | 95% |
| 3 | 2.88 | 96% |
| 4 | 3.70 | 93% |

Amdahl: phần tuần tự **s ≈ 2.6%** → gần tuyến tính.

![](../results/speedup.png)

---

## Lộ trình tối ưu tìm được

![](../results/route.png)

---

## Khó khăn & Bài học

- Deadlock di cư → `Sendrecv`.
- Con lai không hợp lệ → **OX crossover**.
- SSH treo `mpirun` → khóa không mật khẩu.
- Đường dẫn khác nhau giữa máy → cùng `~/parallel-tsp` + rsync.

---

## Kết luận

- Dựng thành công cụm MPI 3 máy thật.
- Island-GA (Python + C++) + di cư ring.
- Speedup gần tuyến tính (3.7× / 4 process).
- **Demo:** xem video.

### Cảm ơn thầy và các bạn đã lắng nghe!
