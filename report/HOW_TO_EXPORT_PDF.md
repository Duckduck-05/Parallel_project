# Cách xuất report.md ra PDF

Chọn 1 trong các cách dưới. Cách 1 (pandoc) đẹp nhất, hỗ trợ tiếng Việt tốt.

## Cách 1 — Pandoc + LaTeX (khuyên dùng)
```bash
sudo apt install -y pandoc texlive-xetex texlive-fonts-recommended texlive-lang-other
cd report
pandoc report.md -o report.pdf \
    --pdf-engine=xelatex \
    -V mainfont="DejaVu Sans" \
    -V geometry:margin=2.5cm \
    --toc
```
> `--toc` tự tạo mục lục. `mainfont=DejaVu Sans` để hiển thị tiếng Việt có dấu.
> Ảnh trong report dùng đường dẫn `../results/*.png` nên chạy lệnh từ thư mục `report`.

## Cách 2 — Trình duyệt (không cài LaTeX)
```bash
sudo apt install -y grip
grip report.md --export report.html
# Mo report.html bang trinh duyet -> Ctrl+P -> Save as PDF
```

## Cách 3 — VS Code
Cài tiện ích **"Markdown PDF"** (yzane) → mở `report.md` → chuột phải →
*Markdown PDF: Export (pdf)*.

---

## Trước khi xuất PDF, nhớ:
- Cập nhật **tên nhóm + 4 thành viên** ở đầu `report.md`.
- Thay **số liệu speedup** bằng số đo **trên cụm 3 máy thật** của nhóm (mục 5.2).
- Đảm bảo 3 ảnh đã tồn tại trong `results/`: `route.png`, `converge.png`, `speedup.png`.
