"""Tao anh gia de demo (FR-3 mo rong) va dung chung cho CLI + web.

Ba che do: text (che chu), crop (cat 5% mep duoi), pixel (doi 1 diem anh).
Anh goc khong bi ghi de; ket qua luu PNG (lossless).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TAMPER_MODES = ("text", "crop", "pixel")


def load_png(src: Path) -> Image.Image:
    """Mo file va chắc chắn la PNG hop le (kiem tra bang Pillow, khong chi nhin duoi)."""
    src = Path(src)
    try:
        img = Image.open(src)
        img.load()
    except (OSError, SyntaxError, ValueError):
        raise ValueError(f"File '{src.name}' không phải ảnh hợp lệ.")
    if img.format != "PNG":
        raise ValueError(
            f"Chỉ chấp nhận ảnh PNG. File '{src.name}' có định dạng {img.format}."
        )
    return img


def _load_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    """Nap font he thong neu co, khong thi dung font mac dinh cua Pillow."""
    for name in ("arial.ttf", "DejaVuSans.ttf", "times.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _tamper_text(img: Image.Image, dst: Path) -> str:
    """Che chu de len anh de gia lap sua noi dung."""
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)
    font = _load_font(max(16, img.width // 20))
    text = "TEN DA BI SUA - GIA MAO"

    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    tw, th = right - left, bottom - top
    x, y = (img.width - tw) // 2, (img.height - th) // 2

    draw.rectangle([x - 8, y - 8, x + tw + 8, y + th + 8], fill=(255, 255, 255))
    draw.text((x, y), text, fill=(220, 0, 0), font=font)
    img.save(dst, "PNG")
    return f"Đã chèn chữ '{text}' đè lên ảnh"


def _tamper_crop(img: Image.Image, dst: Path) -> str:
    """Cat bo 5% mep duoi cua anh."""
    img = img.convert("RGB")
    crop_h = max(1, int(img.height * 0.05))
    old_h = img.height
    img.crop((0, 0, img.width, img.height - crop_h)).save(dst, "PNG")
    return f"Đã cắt bỏ {crop_h} px mép dưới ({old_h} -> {old_h - crop_h})"


def _tamper_pixel(img: Image.Image, dst: Path) -> str:
    """Doi dung 1 diem anh o tam anh."""
    img = img.convert("RGB")
    cx, cy = img.width // 2, img.height // 2
    r, g, b = img.getpixel((cx, cy))
    img.putpixel((cx, cy), ((r + 1) % 256, g, b))
    img.save(dst, "PNG")
    return f"Đã đổi 1 điểm ảnh tại ({cx}, {cy})"


_HANDLERS = {"text": _tamper_text, "crop": _tamper_crop, "pixel": _tamper_pixel}


def apply_tamper(src: Path, dst: Path, mode: str) -> str:
    """Tao anh gia tu src theo mode, luu ra dst. Tra ve mo ta da lam."""
    if mode not in _HANDLERS:
        raise ValueError(f"Chế độ làm giả không hợp lệ: {mode}. Chọn một trong {TAMPER_MODES}.")

    img = load_png(src)
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    return _HANDLERS[mode](img, dst)
