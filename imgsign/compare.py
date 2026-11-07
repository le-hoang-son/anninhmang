"""So sanh anh de tim vung khac biet (FR-12).

Dung Pillow ImageChops.difference de tinh khac biet. Neu hai anh khac kich thuoc,
chi so sanh phan chung (goc tren-trai) va bao ro kich thuoc tung anh.
Vung khac biet duoc ve khung do tren anh nghi gia.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw

CELL = 32          # kich thuoc o luoi de ve khung do
BOX_WIDTH = 3      # do day khung do
RED = (220, 0, 0)


@dataclass
class CompareResult:
    """Ket qua so sanh hai anh."""

    ref_size: tuple[int, int]
    suspect_size: tuple[int, int]
    same_size: bool
    diff_pixels: int
    total_pixels: int
    percent: float
    box_count: int
    annotated_name: str
    suspect_name: str


def _load_rgb(path: Path) -> Image.Image:
    """Mo anh va chuyen ve RGB de so sanh."""
    img = Image.open(path)
    img.load()
    return img.convert("RGB")


def compare_images(ref_path: Path, suspect_path: Path, out_dir: Path) -> CompareResult:
    """So sanh anh tham chieu va anh nghi gia, luu anh danh dau vao out_dir."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ref = _load_rgb(ref_path)
    suspect_full = _load_rgb(suspect_path)

    same_size = ref.size == suspect_full.size
    width = min(ref.width, suspect_full.width)
    height = min(ref.height, suspect_full.height)

    ref_common = ref.crop((0, 0, width, height))
    suspect_common = suspect_full.crop((0, 0, width, height))

    # Pillow: tinh hieu tuyet doi tung kenh
    diff = ImageChops.difference(ref_common, suspect_common)
    mask = np.asarray(diff).max(axis=2) > 0

    diff_pixels = int(mask.sum())
    total_pixels = width * height
    percent = (diff_pixels / total_pixels * 100.0) if total_pixels else 0.0

    # Ve khung do quanh cac o co khac biet
    annotated = suspect_common.copy()
    draw = ImageDraw.Draw(annotated)
    box_count = 0
    for y in range(0, height, CELL):
        for x in range(0, width, CELL):
            block = mask[y : y + CELL, x : x + CELL]
            if block.any():
                x2 = x + block.shape[1] - 1
                y2 = y + block.shape[0] - 1
                draw.rectangle([x, y, x2, y2], outline=RED, width=BOX_WIDTH)
                box_count += 1

    token = uuid.uuid4().hex
    annotated_name = f"{token}_mark.png"
    suspect_name = f"{token}.png"
    annotated.save(out_dir / annotated_name, "PNG")
    suspect_full.save(out_dir / suspect_name, "PNG")

    return CompareResult(
        ref_size=ref.size,
        suspect_size=suspect_full.size,
        same_size=same_size,
        diff_pixels=diff_pixels,
        total_pixels=total_pixels,
        percent=percent,
        box_count=box_count,
        annotated_name=annotated_name,
        suspect_name=suspect_name,
    )
