# Task 4 — Hostfile + chia sẻ code giữa các node

MPI cần biết (1) chạy trên những máy nào — qua **hostfile**, và (2) code phải
**giống nhau** trên mọi máy. Có 2 cách chia sẻ code: `rsync` (đơn giản, khuyên dùng)
hoặc `NFS` (chuyên nghiệp hơn). Bài này dùng `rsync`.

> Điều kiện: đã xong Task 3 — `ssh node2`, `ssh node3` vào thẳng không hỏi pass.

---

## 1. Hostfile
File `cluster/hosts` đã có sẵn:

```
node1 slots=2
node2 slots=2
node3 slots=2
```

- `slots=2` = mỗi VM chạy tối đa 2 process (đặt bằng số core của VM, xem bằng `nproc`).
- Tổng slots = 6 → có thể chạy tới `-np 6`.

## 2. Chép code lên cả 3 máy (lần đầu)
Đặt dự án ở `~/parallel-tsp` trên **node1**. Đồng bộ sang 2 máy còn lại:

```bash
cd ~/parallel-tsp/cluster
bash 03_sync_code.sh
```

Mỗi lần sửa code trên node1, chạy lại lệnh trên để node2/node3 cập nhật theo.

> Đường dẫn dự án phải **giống hệt nhau** trên cả 3 máy (đều là `~/parallel-tsp`),
> nếu không `mpirun` sẽ không tìm thấy file trên máy ở xa.

## 3. DEMO — bằng chứng cụm đã chạy
Từ node1, trong thư mục `cluster`:

```bash
# In ten cả 3 may:
mpirun --hostfile hosts -np 3 hostname

# Chay hello tren ca cum:
mpicc hello.c -o hello
mpirun --hostfile hosts -np 6 ./hello
```

Nếu thấy đủ `node1, node2, node3` in ra → **CỤM ĐÃ HOẠT ĐỘNG**. Hết Giai đoạn A 🎉

---

## (Tùy chọn) Dùng NFS thay cho rsync
Nếu muốn 3 máy dùng CHUNG một thư mục (không phải copy qua lại):

```bash
# Tren node1 (server):
sudo apt install -y nfs-kernel-server
echo "$HOME/parallel-tsp node2(rw,sync,no_subtree_check) node3(rw,sync,no_subtree_check)" | sudo tee -a /etc/exports
sudo exportfs -ra && sudo systemctl restart nfs-kernel-server

# Tren node2, node3 (client):
sudo apt install -y nfs-common
sudo mount node1:$HOME/parallel-tsp $HOME/parallel-tsp
```

Ưu điểm NFS: sửa 1 nơi, mọi máy thấy ngay. Nhược điểm: phụ thuộc node1, mạng yếu thì chậm.
Với bài này `rsync` là đủ và ổn định hơn trên WiFi.

## Lỗi thường gặp
| Triệu chứng | Cách xử lý |
|---|---|
| `mpirun` báo không tìm thấy file | Đường dẫn dự án khác nhau giữa các máy; phải cùng `~/parallel-tsp` |
| Treo khi chạy đa máy | SSH còn hỏi pass (làm lại Task 3) hoặc tường lửa chặn |
| `node2: command not found python3` | node2 chưa cài (chạy lại `01_install.sh` trên node2) |
| rsync `Permission denied` | Sai username/khóa SSH; kiểm tra Task 3 |
