"""Watermark hien (FR-4): chen chu mo lap cheo toan anh bang Pillow.

Anh goc khong bi ghi de, ket qua luu PNG (lossless). Anh co alpha van chay duoc
(chi ve tren kenh mau, giu nguyen kenh alpha).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


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


def _make_tile(text: str, font, opacity: int, angle: int = 30) -> Image.Image:
    """Tao mot o (tile) RGBA chua chu mo da xoay cheo."""
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    tw, th = right - left, bottom - top
    pad = 60

    tile = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tile)
    draw.text(
        (pad - left, pad - top),
        text,
        font=font,
        fill=(255, 255, 255, opacity),
        stroke_width=1,
        stroke_fill=(0, 0, 0, opacity),
    )
    return tile.rotate(angle, expand=True, resample=Image.BICUBIC)


def add_visible_watermark(src: Path, dst: Path, text: str, opacity: int = 90) -> Path:
    """Chen watermark hien (chu mo lap cheo) tu src, luu ra dst dang PNG.

    opacity: do dam cua chu (0-255), cang nho cang mo.
    """
    src, dst = Path(src), Path(dst)

    img = Image.open(src)
    img.load()
    if img.format != "PNG":
        raise ValueError(f"Chỉ chấp nhận ảnh PNG. File '{src.name}' có định dạng {img.format}.")

    has_alpha = img.mode in ("RGBA", "LA") or "transparency" in img.info
    base = img.convert("RGBA")

    font = _load_font(max(18, base.width // 22))
    tile = _make_tile(text, font, opacity)

    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    step_x, step_y = tile.width, tile.height
    for y in range(0, base.height + step_y, step_y):
        for x in range(0, base.width + step_x, step_x):
            overlay.alpha_composite(tile, (x, y))

    result = Image.alpha_composite(base, overlay)
    if not has_alpha:
        result = result.convert("RGB")

    dst.parent.mkdir(parents=True, exist_ok=True)
    result.save(dst, "PNG")
    return dst
