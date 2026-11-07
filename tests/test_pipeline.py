"""Kiem thu quy trinh bao ve va xac minh day du (M5)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from imgsign import assets as assets_mod
from imgsign import keys as keys_mod
from imgsign import pipeline
from imgsign import recover as recover_mod
from imgsign import tamper as tamper_mod


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    """Co lap toan bo thu muc data/keys sang tmp_path va sinh khoa moi."""
    keys_dir = tmp_path / "keys"
    data_dir = tmp_path / "data"
    monkeypatch.setattr(config, "KEYS_DIR", keys_dir)
    monkeypatch.setattr(config, "PRIVATE_KEY_FILE", keys_dir / "private.pem")
    monkeypatch.setattr(config, "PUBLIC_KEY_FILE", keys_dir / "public.pem")
    monkeypatch.setattr(config, "KEY_PASSWORD", "")
    monkeypatch.setattr(config, "DATA_DIR", data_dir)
    monkeypatch.setattr(config, "ORIGINALS_DIR", data_dir / "originals")
    monkeypatch.setattr(config, "SIGNED_DIR", data_dir / "signed")
    monkeypatch.setattr(config, "LOGS_DIR", data_dir / "logs")
    monkeypatch.setattr(config, "ASSETS_FILE", data_dir / "assets.json")
    monkeypatch.setattr(config, "VERIFY_LOG", data_dir / "logs" / "verify.log")
    monkeypatch.setattr(config, "NTFY_TOPIC", "")

    keys_mod.generate_keys(force=True)

    src = tmp_path / "goc.png"
    rng = np.random.default_rng(7)
    Image.fromarray(rng.integers(0, 256, (120, 120, 3), dtype=np.uint8), "RGB").save(src)
    return src


def test_protect_then_verify_valid(workspace):
    result = pipeline.protect(workspace, "Bang A", "van bang", 3)
    assert result.signed_path.exists()
    assert result.sidecar_path.exists()

    report = pipeline.verify_full(result.signed_path)
    assert report.verdict == "HOP_LE"
    assert report.lsb_payload is not None
    assert report.lsb_payload["asset_id"] == result.asset_id


def test_tamper_pixel_then_verify_invalid(workspace):
    result = pipeline.protect(workspace, "Bang A", "van bang", 3)

    arr = np.array(Image.open(result.signed_path).convert("RGB"))
    arr[60, 60, 0] ^= 0xFF
    Image.fromarray(arr, "RGB").save(result.signed_path)

    report = pipeline.verify_full(result.signed_path, result.sidecar_path)
    assert report.verdict == "KHONG_HOP_LE"
    assert report.sig.valid is False


def test_missing_sidecar_not_verifiable(workspace):
    result = pipeline.protect(workspace, "Bang A", "van bang", 3)
    result.sidecar_path.unlink()

    report = pipeline.verify_full(result.signed_path)
    assert report.verdict == "KHONG_XAC_MINH_DUOC"
    assert report.sig.sidecar is None


def test_reject_non_png(workspace, tmp_path):
    jpg = tmp_path / "fake.png"
    Image.new("RGB", (50, 50), (1, 2, 3)).save(jpg, "JPEG")

    with pytest.raises(ValueError):
        pipeline.protect(jpg, "Bang A", "van bang", 3)


def test_asset_registered_and_logged(workspace):
    result = pipeline.protect(workspace, "Bang A", "van bang", 3)

    asset = assets_mod.get_asset(result.asset_id)
    assert asset is not None
    assert asset["name"] == "Bang A"
    assert asset["importance"] == 3
    assert asset["sha256_original"]

    log_text = config.VERIFY_LOG.read_text(encoding="utf-8")
    assert "BAO_VE" in log_text
    assert result.asset_id in log_text


def test_verify_writes_log_and_alert_offline_ok(workspace):
    result = pipeline.protect(workspace, "Bang A", "van bang", 3)

    arr = np.array(Image.open(result.signed_path).convert("RGB"))
    arr[10, 10, 0] ^= 0xFF
    Image.fromarray(arr, "RGB").save(result.signed_path)

    report = pipeline.verify_full(result.signed_path, result.sidecar_path)
    assert report.verdict == "KHONG_HOP_LE"

    log_text = config.VERIFY_LOG.read_text(encoding="utf-8")
    assert "KHONG_HOP_LE" in log_text
    # topic rong -> khong gui duoc, phai co note, khong crash
    assert any("ntfy" in n for n in report.notes)


def test_recover_returns_valid(workspace, tmp_path):
    result = pipeline.protect(workspace, "Bang A", "van bang", 3)
    dst = tmp_path / "recovered.png"

    verify = recover_mod.recover(result.asset_id, dst)
    assert verify.valid is True
    assert dst.exists()


def test_T3_tamper_text_then_verify_invalid(workspace, tmp_path):
    """T3: sua noi dung bang chu de -> KHONG_HOP_LE."""
    result = pipeline.protect(workspace, "Bang A", "van bang", 3)

    fake = tmp_path / "fake_text.png"
    tamper_mod.apply_tamper(result.signed_path, fake, "text")

    report = pipeline.verify_full(fake, result.sidecar_path)
    assert report.verdict == "KHONG_HOP_LE"
    assert report.sig.valid is False


def test_T4_tamper_crop_then_verify_invalid(workspace, tmp_path):
    """T4: cat 5% mep duoi -> KHONG_HOP_LE."""
    result = pipeline.protect(workspace, "Bang A", "van bang", 3)

    fake = tmp_path / "fake_crop.png"
    tamper_mod.apply_tamper(result.signed_path, fake, "crop")

    report = pipeline.verify_full(fake, result.sidecar_path)
    assert report.verdict == "KHONG_HOP_LE"
    assert report.sig.valid is False


def test_T5_sidecar_of_other_image_invalid(workspace):
    """T5: dung sidecar cua anh A cho anh B -> KHONG_HOP_LE (sha256 khong khop)."""
    asset_a = pipeline.protect(workspace, "Bang A", "van bang", 3)
    asset_b = pipeline.protect(workspace, "Bang B", "van bang", 2)
    assert asset_a.asset_id != asset_b.asset_id

    # Xac minh anh B bang sidecar cua anh A
    report = pipeline.verify_full(asset_b.signed_path, asset_a.sidecar_path)
    assert report.verdict == "KHONG_HOP_LE"
    assert report.sig.valid is False
    assert "sha-256" in report.sig.reason.lower()


def test_T7_modified_sidecar_invalid(workspace):
    """T7: sua 1 ky tu trong signature_b64 -> KHONG_HOP_LE (chu ky hong)."""
    result = pipeline.protect(workspace, "Bang A", "van bang", 3)

    sidecar = json.loads(result.sidecar_path.read_text(encoding="utf-8"))
    sig = sidecar["signature_b64"]
    # Doi ky tu dau: 'A' <-> 'B' de chac chan khac
    first = "B" if sig[0] == "A" else "A"
    sidecar["signature_b64"] = first + sig[1:]
    result.sidecar_path.write_text(json.dumps(sidecar, ensure_ascii=False), encoding="utf-8")

    report = pipeline.verify_full(result.signed_path, result.sidecar_path)
    assert report.verdict == "KHONG_HOP_LE"
    assert report.sig.valid is False
