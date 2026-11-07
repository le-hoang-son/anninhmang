"""Watermark an LSB (FR-5) dung numpy.

Dinh dang chuoi bit (ARCHITECTURE.md 4.3):
    MAGIC(4 byte "IMGS") + LENGTH(uint32 big-endian) + PAYLOAD(JSON utf-8) + CRC32(uint32)
Ghi tung bit vao bit thap nhat cua cac kenh mau, thu tu phang row-major (R,G,B).
Anh co alpha: giu nguyen kenh alpha, chi ghi vao R,G,B. Luu PNG (lossless).
"""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

MAGIC = b"IMGS"
HEADER_BYTES = 8  # MAGIC(4) + LENGTH(4)
MAX_PAYLOAD_BYTES = 4096


def _load(src: Path) -> tuple[np.ndarray, str]:
    """Mo anh PNG, tra ve (mang uint8, mode). Alpha (neu co) duoc giu thanh kenh thu 4."""
    img = Image.open(src)
    img.load()
    if img.format != "PNG":
        raise ValueError(f"Chỉ chấp nhận ảnh PNG. File '{Path(src).name}' có định dạng {img.format}.")

    has_alpha = img.mode in ("RGBA", "LA") or "transparency" in img.info
    mode = "RGBA" if has_alpha else "RGB"
    return np.array(img.convert(mode), dtype=np.uint8), mode


def _channel_view(arr: np.ndarray, mode: str) -> tuple[np.ndarray, tuple[int, ...]]:
    """Tra ve (mang phang cac kenh mau, hinh dang kenh mau) de ghi/doc LSB.

    Voi anh co alpha, phan mau R,G,B khong lien tuc nen phai copy ra mang rieng.
    """
    if mode == "RGBA":
        return arr[..., :3].reshape(-1).copy(), arr[..., :3].shape
    return arr.reshape(-1), arr.shape


def embed(src: Path, dst: Path, payload: dict) -> Path:
    """Giau payload JSON vao bit thap nhat cua anh, luu ra dst (PNG).

    Nem ValueError neu anh qua nho de chua du lieu.
    """
    src, dst = Path(src), Path(dst)
    arr, mode = _load(src)

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    if len(body) > MAX_PAYLOAD_BYTES:
        raise ValueError("Payload quá lớn để giấu thông tin")

    blob = MAGIC + struct.pack(">I", len(body)) + body + struct.pack(">I", zlib.crc32(body) & 0xFFFFFFFF)
    bits = np.unpackbits(np.frombuffer(blob, dtype=np.uint8))

    flat, color_shape = _channel_view(arr, mode)
    if bits.size > flat.size:
        raise ValueError("Anh qua nho de giau thong tin")

    flat[: bits.size] = (flat[: bits.size] & 0xFE) | bits

    if mode == "RGBA":
        arr[..., :3] = flat.reshape(color_shape)
    else:
        arr = flat.reshape(arr.shape)

    dst.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr, mode=mode).save(dst, "PNG")
    return dst


def extract(src: Path) -> dict | None:
    """Doc payload tu bit thap nhat. Tra None neu khong co/sai MAGIC/sai CRC."""
    src = Path(src)
    try:
        arr, mode = _load(src)
    except (ValueError, OSError):
        return None

    flat, _ = _channel_view(arr, mode)
    lsb = flat & 1

    if lsb.size < HEADER_BYTES * 8:
        return None
    header = np.packbits(lsb[: HEADER_BYTES * 8]).tobytes()
    if header[:4] != MAGIC:
        return None

    length = struct.unpack(">I", header[4:8])[0]
    if length <= 0 or length > MAX_PAYLOAD_BYTES:
        return None

    total = (HEADER_BYTES * 8) + (length * 8) + 32
    if lsb.size < total:
        return None

    body = np.packbits(lsb[HEADER_BYTES * 8 : HEADER_BYTES * 8 + length * 8]).tobytes()
    stored_crc = struct.unpack(">I", np.packbits(lsb[HEADER_BYTES * 8 + length * 8 : total]).tobytes())[0]
    if (zlib.crc32(body) & 0xFFFFFFFF) != stored_crc:
        return None

    try:
        return json.loads(body.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
