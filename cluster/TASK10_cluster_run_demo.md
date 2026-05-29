# Task 10 — Chạy thật trên cụm 3 máy + Quay video demo

Đây là buổi "ráp máy thật". Mục tiêu: chạy toàn hệ thống end-to-end trên 3 VM Ubuntu
và quay lại video demo (vì thầy cho demo **offline**, ta quay sẵn để trình bày).

> Điều kiện: đã xong Task 1–4 (cụm chạy `mpirun --hostfile hosts -np 3 hostname` OK).

---

## A. Chuẩn bị (1 lần, trên node1)
```bash
# 1) Cap nhat code moi nhat sang node2, node3:
cd ~/parallel-tsp/cluster && bash 03_sync_code.sh

# 2) Bien dich ban C++ tren CA 3 may (vi binary phu thuoc may):
for h in node1 node2 node3; do
  ssh $h "cd ~/parallel-tsp/cpp && mpicxx -O2 -o tsp_island tsp_island.cpp" 
done
```

## B. Kịch bản quay video demo (chạy lần lượt, vừa chạy vừa nói)

**Cảnh 1 — Giới thiệu cụm (chứng minh 3 máy thật):**
```bash
cd ~/parallel-tsp/cluster
cat hosts                                   # cho thay 3 node
mpirun --hostfile hosts -np 3 hostname      # in node1, node2, node3
```

**Cảnh 2 — Bài toán & dữ liệu:**
```bash
cd ~/parallel-tsp
head data/cities_50.txt                      # cho thay toa do thanh pho
```

**Cảnh 3 — Chạy SONG SONG trên cả cụm (bản Python, dễ nhìn):**
```bash
cd ~/parallel-tsp/python
mpirun --hostfile ../cluster/hosts -np 3 \
    python3 tsp_island.py ../data/cities_50.txt --gens 500 --pop 200 --migrate 20 \
    --out ../results/tour_cluster.txt
```
→ Nói: mỗi máy chạy 1 đảo, di cư cá thể tốt nhất theo vòng ring, cuối cùng gom kết quả.

**Cảnh 4 — So sánh có/không di cư (điểm nhấn thuật toán):**
```bash
mpirun --hostfile ../cluster/hosts -np 3 \
    python3 tsp_island.py ../data/cities_50.txt --gens 500 --migrate 0 \
    --out ../results/tour_nomig.txt
# -> chi ra: co di cu cho tour ngan hon
```

**Cảnh 5 — Vẽ kết quả:**
```bash
python3 visualize.py route ../data/cities_50.txt ../results/tour_cluster.txt \
    --out ../results/route.png
python3 visualize.py converge ../results/tour_nomig.txt.history \
    ../results/tour_cluster.txt.history --out ../results/converge.png
```
→ Mở 2 ảnh PNG cho thấy lộ trình + đồ thị hội tụ.

**Cảnh 6 — Đo speedup trên cụm (bản C++ cho số đẹp):**
```bash
cd ~/parallel-tsp/python
python3 benchmark.py ../data/cities_50.txt --procs 1 2 3 --total 240 --gens 500 \
    --lang cpp --hostfile ../cluster/hosts
# (chay tu thu muc cpp neu dung ./tsp_island; xem ghi chu ben duoi)
```
→ Mở `results/speedup.png`: biểu đồ tăng tốc gần tuyến tính.

## C. Mẹo quay video
- Dùng OBS Studio (Windows) hoặc `Ctrl+Alt+Shift+R` (GNOME) để quay màn hình node1.
- Mở thêm 2 cửa sổ SSH vào node2, node3 chạy `htop` để thấy **cả 3 máy đều bận** khi
  chạy → bằng chứng trực quan là tính toán chạy phân tán thật.
- Độ dài video ~3–5 phút là đủ.

---

## Ghi chú quan trọng
- **Bản C++ với `--hostfile`:** binary `./tsp_island` phải tồn tại ở **cùng đường dẫn**
  trên cả 3 máy (đã biên dịch ở bước A). Chạy `benchmark.py --lang cpp` từ thư mục `cpp`.
- **`-np` lớn hơn tổng slots:** thêm `--oversubscribe`. Trên 3 máy `-np 3` thì không cần.
- **Nếu WiFi yếu/chập chờn:** tăng `--migrate` (di cư thưa hơn) để giảm giao tiếp.

> 🔒 Bảo mật: cụm chỉ bảo vệ bằng khóa SSH trên mạng hotspot nội bộ, không có xác thực
> ứng dụng. Đủ cho bài tập lớp; KHÔNG mở ra Internet.
