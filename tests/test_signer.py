"""Kiem thu cho khoa va chu ky so (M1).

Dung tmp_path de co lap, khong dung den keys/ that cua du an.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from imgsign import keys as keys_mod
from imgsign import signer


@pytest.fixture()
def temp_keys(tmp_path, monkeypatch):
    """Tro config sang thu muc khoa tam thoi va sinh khoa moi."""
    keys_dir = tmp_path / "keys"
    monkeypatch.setattr(config, "KEYS_DIR", keys_dir)
    monkeypatch.setattr(config, "PRIVATE_KEY_FILE", keys_dir / "private.pem")
    monkeypatch.setattr(config, "PUBLIC_KEY_FILE", keys_dir / "public.pem")
    monkeypatch.setattr(config, "KEY_PASSWORD", "")

    fingerprint = keys_mod.generate_keys(force=True)
    return fingerprint


@pytest.fixture()
def sample_png(tmp_path):
    """Tao mot anh PNG mau de ky."""
    png = tmp_path / "sample.png"
    Image.new("RGB", (64, 64), (200, 30, 30)).save(png)
    return png


def test_generate_keys_returns_fingerprint(temp_keys):
    assert isinstance(temp_keys, str)
    assert len(temp_keys) == 16


def test_generate_keys_twice_without_force_raises(temp_keys):
    with pytest.raises(FileExistsError):
        keys_mod.generate_keys(force=False)


def test_sign_then_verify_valid(temp_keys, sample_png):
    sidecar_path = signer.sign_file(sample_png, "IMG-0001")
    assert sidecar_path.exists()

    result = signer.verify_file(sample_png, sidecar_path)
    assert result.valid is True
    assert result.sidecar is not None
    assert result.sidecar["asset_id"] == "IMG-0001"
    assert result.sidecar["algorithm"] == "RSA-PSS-SHA256"


def test_tamper_one_byte_invalid(temp_keys, sample_png):
    sidecar_path = signer.sign_file(sample_png, "IMG-0001")

    # Doi 1 byte trong file -> sha256 phai khong khop
    data = bytearray(sample_png.read_bytes())
    data[-1] ^= 0xFF
    sample_png.write_bytes(bytes(data))

    result = signer.verify_file(sample_png, sidecar_path)
    assert result.valid is False
    assert "sha256" in result.reason.lower() or "SHA-256" in result.reason


def test_missing_sidecar(temp_keys, sample_png):
    signer.sign_file(sample_png, "IMG-0001")
    missing = sample_png.with_name("khong_ton_tai.png.sig.json")

    result = signer.verify_file(sample_png, missing)
    assert result.valid is False
    assert result.sidecar is None
    assert "sidecar" in result.reason.lower()
