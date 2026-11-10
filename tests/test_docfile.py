"""Kiem thu bao ve tai lieu .docx/.pdf (M9, FR-21, FR-22).

Bao gom: phat hien loai file, kiem tra hop le, watermark an metadata DOCX,
quy trinh protect/verify cho DOCX (hop le + bi sua) va PDF (chi ky).
"""

from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from imgsign import docfile
from imgsign import keys as keys_mod
from imgsign import pipeline

_CORE_NS = "http://schemas.openxmlformats.org/package/2006/metadata/core-properties"
_CONTENT_TYPES = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
    '<Default Extension="xml" ContentType="application/xml"/></Types>'
)


def _make_docx(path: Path, keywords: str = "") -> Path:
    """Tao mot file .docx toi thieu (ZIP OOXML) de kiem thu."""
    core = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<cp:coreProperties xmlns:cp="{_CORE_NS}" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:title>Tai lieu demo</dc:title>"
        f"<cp:keywords>{keywords}</cp:keywords>"
        "</cp:coreProperties>"
    )
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"/>'
    )
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _CONTENT_TYPES)
        z.writestr("word/document.xml", document)
        z.writestr("docProps/core.xml", core)
    return path


def _make_pdf(path: Path) -> Path:
    """Tao mot file .pdf toi thieu (chi can header %PDF-)."""
    path.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    return path


def _rewrite_docx(src: Path, dst: Path, note: bytes = b"<!-- tampered -->") -> Path:
    """Ghi lai DOCX voi noi dung khac nhung van la ZIP hop le (gia lap bi sua)."""
    with zipfile.ZipFile(src) as zin:
        parts = {n: zin.read(n) for n in zin.namelist()}
    parts["word/document.xml"] = parts["word/document.xml"] + note
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for n, data in parts.items():
            zout.writestr(n, data)
    return dst


@pytest.fixture()
def workspace(tmp_path, monkeypatch):
    """Co lap data/keys sang tmp_path va sinh khoa moi."""
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
    return tmp_path


def test_detect_kind_valid_and_rejected(tmp_path):
    assert docfile.detect_kind(tmp_path / "a.png") == "png"
    assert docfile.detect_kind(tmp_path / "a.docx") == "docx"
    assert docfile.detect_kind(tmp_path / "a.pdf") == "pdf"
    with pytest.raises(ValueError):
        docfile.detect_kind(tmp_path / "a.jpg")


def test_validate_docx_rejects_non_zip(tmp_path):
    bad = tmp_path / "bad.docx"
    bad.write_bytes(b"day khong phai file zip")
    with pytest.raises(ValueError):
        docfile.validate_docx(bad)


def test_validate_pdf_rejects_non_pdf(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"khong phai pdf")
    with pytest.raises(ValueError):
        docfile.validate_pdf(bad)


def test_docx_embed_extract_roundtrip(tmp_path):
    """Watermark an phai doc lai dung payload va giu keywords cu cua nguoi dung."""
    src = _make_docx(tmp_path / "in.docx", keywords="bao-mat")
    dst = tmp_path / "out.docx"
    payload = {"asset_id": "IMG-0042", "owner": "Truong Demo", "date": "2026-11-10"}

    docfile.embed_docx_metadata(src, dst, payload)
    got = docfile.extract_docx_metadata(dst)

    assert got == payload
    # keywords cu van con (khong bi xoa)
    with zipfile.ZipFile(dst) as z:
        core = z.read("docProps/core.xml").decode("utf-8")
    assert "bao-mat" in core
    assert "IMGSIGN-B64:" in core


def test_extract_returns_none_without_watermark(tmp_path):
    src = _make_docx(tmp_path / "plain.docx", keywords="chi la keyword")
    assert docfile.extract_docx_metadata(src) is None


def test_protect_docx_then_verify_valid(workspace):
    src = _make_docx(workspace / "goc.docx", keywords="hop dong")
    result = pipeline.protect(src, "Hop dong A", "hop dong", 3)

    assert result.kind == "docx"
    assert result.signed_path.suffix == ".docx"
    assert result.signed_path.exists() and result.sidecar_path.exists()

    report = pipeline.verify_full(result.signed_path)
    assert report.verdict == "HOP_LE"
    assert report.lsb_payload is not None  # metadata DOCX
    assert report.lsb_payload["asset_id"] == result.asset_id


def test_protect_docx_tampered_invalid(workspace):
    src = _make_docx(workspace / "goc.docx")
    result = pipeline.protect(src, "Hop dong A", "hop dong", 3)

    tampered = _rewrite_docx(result.signed_path, workspace / "sua.docx")
    report = pipeline.verify_full(tampered, result.sidecar_path)

    assert report.verdict == "KHONG_HOP_LE"
    assert report.sig.valid is False


def test_protect_pdf_then_verify_valid(workspace):
    src = _make_pdf(workspace / "goc.pdf")
    result = pipeline.protect(src, "Bao cao PDF", "bao cao", 2)

    assert result.kind == "pdf"
    assert result.signed_path.suffix == ".pdf"

    report = pipeline.verify_full(result.signed_path)
    assert report.verdict == "HOP_LE"
    assert report.lsb_payload is None  # PDF khong co watermark


def test_verify_pdf_missing_sidecar_not_verifiable(workspace):
    src = _make_pdf(workspace / "goc.pdf")
    pipeline.protect(src, "Bao cao PDF", "bao cao", 2)

    # Ban sao khong kem sidecar o mot thu muc khac
    copy = workspace / "no_sidecar.pdf"
    copy.write_bytes(src.read_bytes())
    report = pipeline.verify_full(copy)

    assert report.verdict == "KHONG_XAC_MINH_DUOC"
    assert report.sig.sidecar is None


def test_find_signed_by_extension(workspace):
    src = _make_docx(workspace / "goc.docx")
    result = pipeline.protect(src, "Hop dong A", "hop dong", 3)

    found = docfile.find_signed(config.SIGNED_DIR, result.asset_id)
    assert found is not None
    assert found.suffix == ".docx"
    assert docfile.find_signed(config.SIGNED_DIR, "IMG-9999") is None
