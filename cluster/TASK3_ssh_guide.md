# Task 3 — SSH không mật khẩu giữa các node

MPI khởi chạy tiến trình trên máy khác bằng SSH. Nếu SSH còn hỏi mật khẩu,
`mpirun` sẽ treo. Ta tạo khóa SSH và chép sang tất cả các node.

> Điều kiện: đã xong Task 2 — `ping node2`, `ping node3` đều được.

---

## Cách làm (chạy trên CẢ 3 máy)

```bash
cd ~/parallel-tsp/cluster
bash 02_ssh_setup.sh
```

Lần đầu nó sẽ hỏi mật khẩu của từng máy (để chép khóa sang). Nhập mật khẩu user.
Các lần sau sẽ không hỏi nữa.

## DEMO — bằng chứng đạt yêu cầu
Từ node1 gõ:

```bash
ssh node2 hostname   # phai in ra: node2  (khong hoi mat khau)
ssh node3 hostname   # phai in ra: node3
```

Làm tương tự từ node2, node3. Tất cả vào thẳng không hỏi pass → **Task 3 xong**.

---

## Giải thích nhanh (để trả bài)
- `ssh-keygen -t rsa -b 4096 -N ""`: tạo cặp khóa public/private, `-N ""` = không
  đặt passphrase để MPI tự đăng nhập.
- `ssh-copy-id user@nodeX`: thêm khóa **công khai** của mình vào
  `~/.ssh/authorized_keys` trên nodeX → nodeX tin tưởng máy mình, cho vào không cần pass.
- Cần chép cả sang chính nó (`ssh node1` từ node1) vì `mpirun` đôi khi cũng dùng SSH
  cho tiến trình local.

> 🔒 Bảo mật: khóa private không đặt passphrase nên ai chiếm được máy sẽ vào được cả
> cụm. Chấp nhận trong môi trường lab/hotspot nội bộ; KHÔNG dùng trên máy thật quan trọng.

## Lỗi thường gặp
| Triệu chứng | Cách xử lý |
|---|---|
| `ssh` vẫn hỏi mật khẩu | Chạy lại `ssh-copy-id user@nodeX`; kiểm tra cùng username trên các máy |
| `Permission denied (publickey)` | Sai user, hoặc `~/.ssh` sai quyền: `chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys` |
| `Host key verification failed` | Lần đầu gõ `yes`, hoặc đã set `StrictHostKeyChecking=no` trong script |
| `Connection refused` | Chưa bật sshd: `sudo systemctl enable --now ssh` |
