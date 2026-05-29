# Task 2 — Cấu hình mạng 3 máy ảo Ubuntu (Bridged Adapter)

Mục tiêu: 3 VM Ubuntu nằm trên 3 máy Windows, cùng nối WiFi điện thoại,
nhìn thấy nhau theo tên `node1 / node2 / node3` và ping được nhau.

> ⚠️ Quy tắc của thầy: **mỗi máy vật lý chỉ 1 VM**. Đừng chạy 2 VM trên 1 laptop.

---

## Bước 1 — Bật hotspot điện thoại
- Bật phát WiFi trên điện thoại (ví dụ tên `CLUSTER_WIFI`).
- Cho **cả 3 máy Windows** nối vào WiFi này. Đây chính là mạng LAN của cụm.

## Bước 2 — Đặt card mạng VM thành Bridged (làm trên cả 3 máy)
Trong **VirtualBox**, với từng máy ảo (đang tắt):
1. Chọn VM → **Settings** → **Network**.
2. Tab **Adapter 1**: tick **Enable Network Adapter**.
3. Mục **Attached to:** chọn **Bridged Adapter**.
4. Mục **Name:** chọn đúng card WiFi của laptop (tên có chữ *Wireless / Wi-Fi*,
   KHÔNG chọn card ảo `VirtualBox Host-Only`).
5. **OK**. Khởi động VM.

> Bridged = VM được cấp IP cùng dải với điện thoại, như một máy thật trong LAN.
> (Nếu dùng VMware: chọn **Bridged** trong Network Adapter, tick *Replicate physical
> network connection state*.)

## Bước 3 — Đặt hostname cho từng VM
Trên mỗi VM, mở terminal và đặt tên tương ứng (máy 1 → node1, máy 2 → node2, máy 3 → node3):

```bash
# Tren VM thu nhat:
sudo hostnamectl set-hostname node1
# VM thu hai:  sudo hostnamectl set-hostname node2
# VM thu ba:   sudo hostnamectl set-hostname node3
```

Đăng xuất/đăng nhập lại để dấu nhắc hiển thị tên mới.

> 💡 **Cùng một username trên cả 3 máy** (ví dụ đều là `mpiuser`).
> MPI mặc định dùng cùng tên user khi SSH sang máy khác. Kiểm tra: `whoami`.

## Bước 4 — Lấy IP của từng VM
Trên mỗi VM chạy:

```bash
hostname -I
```

Ghi lại IP (ví dụ `192.168.43.11`, `192.168.43.12`, `192.168.43.13`).
IP của điện thoại hotspot thường dạng `192.168.43.x` hoặc `192.168.137.x`.

## Bước 5 — Khai báo tên máy trong /etc/hosts (làm GIỐNG NHAU trên cả 3 máy)
Mở file:

```bash
sudo nano /etc/hosts
```

Thêm 3 dòng (thay IP bằng IP thật bạn vừa ghi ở Bước 4), xem mẫu `hosts.sample`:

```
192.168.43.11   node1
192.168.43.12   node2
192.168.43.13   node3
```

> Xóa/ vô hiệu dòng `127.0.1.1 node1` nếu có, để tránh MPI nhầm địa chỉ loopback.

## Bước 6 — DEMO kiểm tra: 3 máy ping được nhau theo tên
Từ node1:

```bash
ping -c 3 node2
ping -c 3 node3
```

Từ node2 ping node1, node3... Nếu tất cả đều có phản hồi → **mạng OK**, sang Task 3 (SSH).

---

## Lỗi thường gặp
| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| `ping: unknown host node2` | Chưa khai báo `/etc/hosts` | Kiểm tra lại Bước 5 trên máy đang ping |
| Ping ra IP `127.0.x.x` | Còn dòng `127.0.1.1 nodeX` | Xóa dòng đó trong `/etc/hosts` |
| Không ping được dù đúng IP | Tường lửa / chưa cùng WiFi | `sudo ufw disable` (mạng lab) + kiểm tra WiFi |
| IP đổi sau khi tắt mở | Hotspot cấp DHCP động | Đặt IP tĩnh hoặc kiểm tra `hostname -I` lại mỗi buổi |

> 🔒 Lưu ý bảo mật: trong lab ta tắt `ufw` cho nhanh và mạng chỉ là hotspot nội bộ.
> Đây là chấp nhận được cho bài tập lớp, KHÔNG nên làm vậy trên mạng thật/Internet.
