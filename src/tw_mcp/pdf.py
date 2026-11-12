"""PDF 轉圖：把 PDF 的指定頁面轉成 JPG／PNG（例如謄本、合約、型錄要貼到 LINE 或簡報）。

頁碼範圍、檔名、DPI 上下限、畫布安全尺寸、避免同名覆蓋 的邏輯移植自 tw-pdf2jpg 的 js/pdf2img.js；
瀏覽器版用 pdf.js，這裡改用 pypdfium2（Apache-2.0／BSD-3-Clause，PDFium 引擎）在本機算圖，檔案不會上傳。
"""
import re
from pathlib import Path

MAX_PAGES_PER_CALL = 200
MAX_SIDE = 10000               # 長邊像素上限
MAX_PIXELS = 40_000_000        # 單頁像素上限


def parse_page_range(text, total: int):
    """「1-3,5,8-」→ [1,2,3,5,8,...,total]；空白＝全部。回傳 (pages, errors)。"""
    pages, errors = set(), []
    src = re.sub(r"[，、；;\s]+", ",", str(text or ""))
    src = re.sub(r"[－—～~]", "-", src).strip()
    if not src or src == ",":
        return list(range(1, total + 1)), errors
    for part in [p for p in src.split(",") if p]:
        m = re.fullmatch(r"(\d*)-(\d*)", part)
        if m:
            a = int(m.group(1)) if m.group(1) else 1
            b = int(m.group(2)) if m.group(2) else total
            if a > b:
                errors.append(f"「{part}」起訖顛倒")
                continue
            pages.update(range(max(1, a), min(total, b) + 1))
            if a > total:
                errors.append(f"「{part}」超過總頁數 {total}")
        elif part.isdigit():
            n = int(part)
            if 1 <= n <= total:
                pages.add(n)
            else:
                errors.append(f"第 {n} 頁不存在（共 {total} 頁）")
        else:
            errors.append(f"看不懂「{part}」")
    return sorted(pages), errors


def base_name(file_name) -> str:
    name = re.sub(r"\.pdf$", "", str(file_name or "document"), flags=re.I)
    safe = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name)
    safe = re.sub(r"^\.+", "", safe).strip()
    return safe or "document"


def page_file_name(file_name, page_num: int, total_pages: int, fmt: str) -> str:
    width = max(3, len(str(total_pages)))
    ext = "png" if fmt == "png" else "jpg"
    return f"{base_name(file_name)}_p{str(page_num).zfill(width)}.{ext}"


def unique_name(name: str, used: set) -> str:
    dot = name.rfind(".")
    stem, ext = (name[:dot], name[dot:]) if dot > 0 else (name, "")
    out, i = name, 2
    while out.lower() in used:
        out = f"{stem} ({i}){ext}"
        i += 1
    used.add(out.lower())
    return out


def clamp_dpi(dpi) -> int:
    try:
        d = int(dpi)
    except (TypeError, ValueError):
        d = 150
    return min(600, max(36, d))


def safe_scale(width_pt: float, height_pt: float, scale: float, max_side=MAX_SIDE, max_pixels=MAX_PIXELS) -> float:
    s = scale
    longest = max(width_pt, height_pt) * s
    if longest > max_side:
        s *= max_side / longest
    px = width_pt * s * height_pt * s
    if px > max_pixels:
        s *= (max_pixels / px) ** 0.5
    return s


def format_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 / 1024:.2f} MB"


def convert(pdf_path: str, pages: str = "", dpi: int = 150, fmt: str = "jpg", quality: int = 92,
            out_dir: str = "", password: str = "") -> dict:
    import pypdfium2 as pdfium      # 延後載入：其他工具不需要 PDFium

    src = Path(pdf_path).expanduser()
    if src.suffix.lower() != ".pdf":
        raise ValueError("只接受 .pdf 檔")
    if not src.is_file():
        raise ValueError(f"找不到檔案：{src}")
    fmt = "png" if str(fmt).lower() == "png" else "jpg"
    q = min(100, max(1, int(quality or 92)))
    dpi = clamp_dpi(dpi)
    try:
        doc = pdfium.PdfDocument(str(src), password=password or None)
    except pdfium.PdfiumError as e:
        msg = str(e)
        if "password" in msg.lower():
            raise ValueError("這份 PDF 有密碼保護，請提供 password")
        raise ValueError(f"PDF 打不開（檔案可能損毀）：{msg}")
    try:
        total = len(doc)
        want, errors = parse_page_range(pages, total)
        if not want:
            raise ValueError("沒有可轉換的頁面：" + ("；".join(errors) or "PDF 沒有頁面"))
        if len(want) > MAX_PAGES_PER_CALL:
            raise ValueError(f"一次最多轉 {MAX_PAGES_PER_CALL} 頁（這次選了 {len(want)} 頁），請分批指定 pages")
        out = Path(out_dir).expanduser() if out_dir else src.with_name(base_name(src.name) + "_pages")
        out.mkdir(parents=True, exist_ok=True)
        used = {p.name.lower() for p in out.iterdir()}      # 不覆蓋資料夾裡既有的檔案
        files = []
        for n in want:
            page = doc[n - 1]
            w, h = page.get_size()
            scale = safe_scale(w, h, dpi / 72)
            bitmap = page.render(scale=scale)
            img = bitmap.to_pil()
            name = unique_name(page_file_name(src.name, n, total, fmt), used)
            target = out / name
            if fmt == "png":
                img.save(target, "PNG", optimize=True)
            else:
                img.convert("RGB").save(target, "JPEG", quality=q, optimize=True)
            size = target.stat().st_size
            files.append({"page": n, "path": str(target), "width": img.width, "height": img.height,
                          "bytes": size, "size": format_bytes(size),
                          "downscaled": abs(scale - dpi / 72) > 1e-9})
            page.close()
    finally:
        doc.close()
    return {"pdf": str(src), "total_pages": total, "converted": len(files), "dpi": dpi, "format": fmt,
            "out_dir": str(out), "files": files, "warnings": errors}
