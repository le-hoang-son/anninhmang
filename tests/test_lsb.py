"""Kiem thu cho watermark an LSB (M4)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from imgsign import lsb


@pytest.fixture()
def sample_png(tmp_path):
    png = tmp_path / "sample.png"
    rng = np.random.default_rng(42)
    arr = rng.integers(0, 256, size=(80, 80, 3), dtype=np.uint8)
    Image.fromarray(arr, "RGB").save(png)
    return png


def _payload() -> dict:
    return {"asset_id": "IMG-0001", "owner": "Truong Demo", "date": "2026-11-07"}


def test_embed_then_extract_roundtrip(sample_png, tmp_path):
    dst = tmp_path / "hidden.png"
    lsb.embed(sample_png, dst, _payload())
    assert lsb.extract(dst) == _payload()


def test_extract_from_clean_image_returns_none(sample_png):
    assert lsb.extract(sample_png) is None


def test_image_too_small_raises(tmp_path):
    tiny = tmp_path / "tiny.png"
    Image.new("RGB", (4, 4), (10, 20, 30)).save(tiny)
    with pytest.raises(ValueError):
        lsb.embed(tiny, tmp_path / "out.png", _payload())


def test_max_channel_deviation_is_one(sample_png, tmp_path):
    dst = tmp_path / "hidden.png"
    lsb.embed(sample_png, dst, _payload())

    a = np.array(Image.open(sample_png).convert("RGB"), dtype=np.int16)
    b = np.array(Image.open(dst).convert("RGB"), dtype=np.int16)
    assert int(np.abs(a - b).max()) == 1


def test_corrupt_payload_fails_crc(sample_png, tmp_path):
    dst = tmp_path / "hidden.png"
    lsb.embed(sample_png, dst, _payload())

    arr = np.array(Image.open(dst).convert("RGB"), dtype=np.uint8)
    flat = arr.reshape(-1)
    # Dao bit LSB cua mot byte nam trong phan payload (sau 8 byte header)
    pos = 8 * 8 + 5
    for i in range(8):
        flat[pos + i] ^= 1
    Image.fromarray(flat.reshape(arr.shape), "RGB").save(dst)

    assert lsb.extract(dst) is None


def test_rgba_image_keeps_alpha(tmp_path):
    rgba = tmp_path / "alpha.png"
    arr = np.zeros((60, 60, 4), dtype=np.uint8)
    arr[..., :3] = 120
    arr[..., 3] = 200
    Image.fromarray(arr, "RGBA").save(rgba)

    dst = tmp_path / "alpha_hidden.png"
    lsb.embed(rgba, dst, _payload())

    out = np.array(Image.open(dst))
    assert out.shape[2] == 4
    assert (out[..., 3] == 200).all()
    assert lsb.extract(dst) == _payload()
