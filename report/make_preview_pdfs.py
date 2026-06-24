#!/usr/bin/env python3
"""Generate lightweight PDF previews from the report/slides LaTeX sources.

This avoids a hard dependency on pdflatex for quick local review. It renders
plain text only; figures are represented by their filenames.
"""
from __future__ import annotations

import os
import re
import struct
import textwrap
import zlib


ROOT = os.path.dirname(os.path.abspath(__file__))


def pdf_escape(text: str) -> str:
    text = text.encode("latin-1", "replace").decode("latin-1")
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class SimplePDF:
    def __init__(self, path: str, page_size=(595, 842)):
        self.path = path
        self.page_w, self.page_h = page_size
        self.pages: list[list[tuple[float, float, int, str, bool]]] = []

    def add_page(self, lines):
        self.pages.append(lines)

    def save(self):
        objects: dict[int, bytes] = {}
        objects[1] = b""
        objects[2] = b""
        objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
        # 1 catalog, 2 pages, 3 font, then page/content pairs, then images.
        kids = []
        next_obj = 4 + len(self.pages) * 2
        for i, page_lines in enumerate(self.pages):
            page_obj = 4 + i * 2
            content_obj = page_obj + 1
            kids.append(f"{page_obj} 0 R")
            stream_parts = []
            xobjects = []
            image_index = 1
            for item in page_lines:
                if item and item[0] == "image":
                    _, path, x, y, w, h = item
                    try:
                        iw, ih, rgb = read_png_rgb(path)
                    except Exception as exc:
                        stream_parts.append(
                            f"BT /F1 10 Tf {x:.2f} {y:.2f} Td "
                            f"({pdf_escape('[Could not load image: ' + str(exc))}) Tj ET\n"
                        )
                        continue
                    im_name = f"Im{image_index}"
                    image_index += 1
                    im_obj = next_obj
                    next_obj += 1
                    comp = zlib.compress(rgb)
                    objects[im_obj] = (
                        f"<< /Type /XObject /Subtype /Image /Width {iw} /Height {ih} "
                        f"/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /FlateDecode "
                        f"/Length {len(comp)} >>\nstream\n"
                    ).encode("latin-1") + comp + b"\nendstream"
                    xobjects.append(f"/{im_name} {im_obj} 0 R")
                    stream_parts.append(f"q {w:.2f} 0 0 {h:.2f} {x:.2f} {y:.2f} cm /{im_name} Do Q\n")
                else:
                    x, y, size, text, bold = item
                    stream_parts.append(
                        f"BT /F1 {size} Tf {x:.2f} {y:.2f} Td ({pdf_escape(text)}) Tj ET\n"
                    )
            stream = "".join(stream_parts).encode("latin-1", "replace")
            xobj_res = ""
            if xobjects:
                xobj_res = " /XObject << " + " ".join(xobjects) + " >>"
            page = (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.page_w} {self.page_h}] "
                f"/Resources << /Font << /F1 3 0 R >>{xobj_res} >> /Contents {content_obj} 0 R >>"
            ).encode()
            content = b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"endstream"
            objects[page_obj] = page
            objects[content_obj] = content

        objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
        objects[2] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(self.pages)} >>".encode()

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for idx in range(1, max(objects) + 1):
            obj = objects[idx]
            offsets.append(len(out))
            out += f"{idx} 0 obj\n".encode() + obj + b"\nendobj\n"
        xref = len(out)
        out += f"xref\n0 {max(objects) + 1}\n".encode()
        out += b"0000000000 65535 f \n"
        for off in offsets[1:]:
            out += f"{off:010d} 00000 n \n".encode()
        out += (
            f"trailer << /Size {max(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode()
        with open(self.path, "wb") as f:
            f.write(out)


def paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def read_png_rgb(path: str) -> tuple[int, int, bytes]:
    data = open(path, "rb").read()
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError(f"{path} is not a PNG")
    pos = 8
    width = height = bit_depth = color_type = None
    idat = bytearray()
    while pos < len(data):
        length = struct.unpack(">I", data[pos:pos + 4])[0]
        typ = data[pos + 4:pos + 8]
        chunk = data[pos + 8:pos + 8 + length]
        pos += 12 + length
        if typ == b"IHDR":
            width, height, bit_depth, color_type, comp, filt, interlace = struct.unpack(">IIBBBBB", chunk)
            if bit_depth != 8 or interlace != 0:
                raise ValueError("only 8-bit non-interlaced PNGs are supported")
        elif typ == b"IDAT":
            idat.extend(chunk)
        elif typ == b"IEND":
            break
    if width is None or color_type not in (0, 2, 6):
        raise ValueError("unsupported PNG color type")
    channels = {0: 1, 2: 3, 6: 4}[color_type]
    bpp = channels
    stride = width * channels
    raw = zlib.decompress(bytes(idat))
    rows = []
    p = 0
    prev = [0] * stride
    for _ in range(height):
        ftype = raw[p]
        p += 1
        cur = list(raw[p:p + stride])
        p += stride
        recon = [0] * stride
        for i, val in enumerate(cur):
            left = recon[i - bpp] if i >= bpp else 0
            up = prev[i]
            up_left = prev[i - bpp] if i >= bpp else 0
            if ftype == 0:
                x = val
            elif ftype == 1:
                x = val + left
            elif ftype == 2:
                x = val + up
            elif ftype == 3:
                x = val + ((left + up) // 2)
            elif ftype == 4:
                x = val + paeth(left, up, up_left)
            else:
                raise ValueError("unsupported PNG filter")
            recon[i] = x & 255
        rows.append(recon)
        prev = recon
    rgb = bytearray()
    for row in rows:
        if color_type == 0:
            for g in row:
                rgb.extend((g, g, g))
        elif color_type == 2:
            rgb.extend(row)
        else:
            for i in range(0, len(row), 4):
                r, g, b, a = row[i:i + 4]
                if a < 255:
                    r = (r * a + 255 * (255 - a)) // 255
                    g = (g * a + 255 * (255 - a)) // 255
                    b = (b * a + 255 * (255 - a)) // 255
                rgb.extend((r, g, b))
    return width, height, bytes(rgb)


def clean_tex(s: str) -> str:
    s = s.strip()
    s = re.sub(r"%.*$", "", s)
    replacements = {
        r"\textbf": "",
        r"\texttt": "",
        r"\emph": "",
        r"\large": "",
        r"\small": "",
        r"\tiny": "",
        r"\fbox": "",
    }
    for k, v in replacements.items():
        s = s.replace(k, v)
    s = s.replace("\\_", "_")
    s = s.replace("\\%", "%")
    s = s.replace("\\$", "$")
    s = s.replace("\\&", "&")
    s = s.replace("--", "-")
    s = s.replace("``", '"').replace("''", '"')
    s = re.sub(r"\\[a-zA-Z]+\*?(?:\[[^\]]*\])?", "", s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace("$", "")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def report_lines(tex_path: str) -> list[tuple[str, int]]:
    out: list[tuple[str, int]] = []
    in_doc = False
    skip_env = None
    for raw in open(tex_path, encoding="utf-8"):
        line = raw.strip()
        if line == r"\begin{document}":
            in_doc = True
            continue
        if not in_doc:
            continue
        if line == r"\end{document}":
            break
        if line.startswith(r"\begin{lstlisting}"):
            skip_env = "lstlisting"
            out.append(("Pseudocode / command listing omitted in preview PDF.", 10))
            continue
        if line.startswith(r"\begin{tabular}") or line.startswith(r"\begin{longtable}"):
            skip_env = "table"
            continue
        if skip_env:
            if line.startswith(r"\end{" + skip_env):
                skip_env = None
            elif skip_env == "table" and line and not line.startswith("\\"):
                txt = clean_tex(line.replace("&", " | ").replace(r"\\", ""))
                if txt:
                    out.append((txt, 9))
            continue
        m = re.match(r"\\section\*?\{(.+)\}", line)
        if m:
            out.append((clean_tex(m.group(1)), 16))
            continue
        m = re.match(r"\\subsection\*?\{(.+)\}", line)
        if m:
            out.append((clean_tex(m.group(1)), 13))
            continue
        m = re.match(r"\\includegraphics.*\{(.+)\}", line)
        if m:
            out.append((f"[Figure: {m.group(1)}]", 10))
            continue
        if line.startswith("\\") or not line:
            continue
        txt = clean_tex(line)
        if txt:
            out.append((txt, 10))
    return out


def slide_frames(tex_path: str) -> list[tuple[str, list[str]]]:
    frames = []
    in_frame = False
    title = "Slide"
    body = []
    for raw in open(tex_path, encoding="utf-8"):
        line = raw.strip()
        m = re.match(r"\\begin\{frame\}(?:\{(.+)\})?", line)
        if m:
            in_frame = True
            title = clean_tex(m.group(1) or "Title")
            body = []
            continue
        if in_frame and line == r"\end{frame}":
            frames.append((title, body))
            in_frame = False
            continue
        if not in_frame or not line:
            continue
        if line.startswith(r"\includegraphics"):
            m = re.search(r"\{(.+)\}", line)
            body.append(f"[Figure: {m.group(1) if m else 'image'}]")
            continue
        if line.startswith(r"\item"):
            body.append("- " + clean_tex(line.replace(r"\item", "", 1)))
            continue
        if line.startswith("\\") and not line.startswith(r"\texttt"):
            continue
        txt = clean_tex(line)
        if txt:
            body.append(txt)
    return frames


def render_report():
    src = os.path.join(ROOT, "parallel_tsp_report.tex")
    dst = os.path.join(ROOT, "parallel_tsp_report_preview.pdf")
    pdf = SimplePDF(dst)
    page = []
    y = 800
    page.append((55, y, 18, "Parallel Travelling Salesman Problem Solver", True))
    y -= 28
    page.append((55, y, 12, "Island-Model Genetic Algorithm with MPI", False))
    y -= 35
    for text, size in report_lines(src):
        width = 55 if size <= 10 else 44
        for wrapped in textwrap.wrap(text, width=width) or [""]:
            fig = re.match(r"\[Figure: (.+)\]", wrapped)
            if fig:
                img = os.path.join(ROOT, "figures", os.path.basename(fig.group(1)))
                try:
                    iw, ih, _ = read_png_rgb(img)
                    max_w, max_h = 460, 260
                    scale = min(max_w / iw, max_h / ih)
                    dw, dh = iw * scale, ih * scale
                    if y - dh < 50:
                        pdf.add_page(page)
                        page = []
                        y = 800
                    page.append(("image", img, (595 - dw) / 2, y - dh, dw, dh))
                    y -= dh + 18
                except Exception:
                    page.append((55, y, size, wrapped, size >= 13))
                    y -= size + 5
                continue
            if y < 50:
                pdf.add_page(page)
                page = []
                y = 800
            page.append((55, y, size, wrapped, size >= 13))
            y -= size + 5
        if size >= 13:
            y -= 5
    if page:
        pdf.add_page(page)
    pdf.save()
    return dst


def render_slides():
    src = os.path.join(ROOT, "parallel_tsp_slides.tex")
    dst = os.path.join(ROOT, "parallel_tsp_slides_preview.pdf")
    pdf = SimplePDF(dst, page_size=(960, 540))
    for idx, (title, body) in enumerate(slide_frames(src), start=1):
        page = [(45, 490, 24, f"{idx}. {title}", True)]
        y = 440
        for text in body:
            fig = re.match(r"\[Figure: (.+)\]", text)
            if fig:
                img = os.path.join(ROOT, "figures", os.path.basename(fig.group(1)))
                try:
                    iw, ih, _ = read_png_rgb(img)
                    max_w, max_h = 760, 330
                    if len(body) > 1:
                        max_w, max_h = 420, 230
                    scale = min(max_w / iw, max_h / ih)
                    dw, dh = iw * scale, ih * scale
                    if y - dh < 45:
                        continue
                    page.append(("image", img, (960 - dw) / 2, y - dh, dw, dh))
                    y -= dh + 22
                except Exception as exc:
                    page.append((60, y, 15, f"[Could not load figure: {exc}]", False))
                    y -= 24
                continue
            for wrapped in textwrap.wrap(text, width=86) or [""]:
                if y < 55:
                    page.append((45, y, 11, "[continued on source slide]", False))
                    y = 0
                    break
                page.append((60, y, 15, wrapped, False))
                y -= 24
            if y == 0:
                break
        pdf.add_page(page)
    pdf.save()
    return dst


if __name__ == "__main__":
    print(render_report())
    print(render_slides())
