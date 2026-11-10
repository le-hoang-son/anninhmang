"""Quy trinh bao ve protect() va xac minh day du verify_full() (FR-6, FR-7).

Thu tu bao ve (BAT BIEN, khong duoc doi):
    anh goc -> (1) luu ban goc -> (2) watermark hien -> (3) watermark an LSB
            -> (4) luu PNG -> (5) KY file PNG cuoi cung (buoc cuoi)
Chu ky luon la buoc cuoi vi no phu len tung byte cua file PNG cuoi cung.

Ket luan theo bang logic SPEC.md muc 7.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from PIL import Image

import config
from imgsign import assets as assets_mod
from imgsign import docfile
from imgsign import keys as keys_mod
from imgsign import logger as logger_mod
from imgsign import lsb as lsb_mod
from imgsign import notifier
from imgsign import signer
from imgsign import watermark as watermark_mod
from imgsign.signer import VerifyResult


@dataclass
class ProtectResult:
    """Ket qua quy trinh bao ve tai san (anh hoac tai lieu)."""

    asset_id: str
    signed_path: Path
    sidecar_path: Path
    original_path: Path
    sha256_signed: str
    kind: str = "png"  # "png" | "docx" | "pdf"
    visible_watermark: bool = True  # True: da chen watermark hien (chi co y nghia voi PNG)


@dataclass
class FullReport:
    """Bao cao xac minh day du."""

    verdict: str
    sig: VerifyResult
    lsb_payload: dict | None
    notes: list[str] = field(default_factory=list)


def validate_png(src: Path) -> None:
    """Kiem tra file la PNG hop le bang Pillow (khong chi nhin duoi file)."""
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


def protect(
    src: Path,
    asset_name: str,
    asset_type: str,
    importance: int,
    visible_watermark: bool = True,
) -> ProtectResult:
    """Bao ve tai san theo dung thu tu. Tra ve ProtectResult.

    PNG : luu goc -> dang ky asset -> (watermark hien tuy chon) -> LSB -> luu PNG -> KY (buoc cuoi) -> log.
    DOCX: luu goc -> dang ky asset -> (watermark hien header tuy chon) -> watermark an metadata -> luu DOCX -> KY -> log.
    PDF : luu goc -> dang ky asset -> (watermark hien text tuy chon) -> luu PDF -> KY -> log.
    visible_watermark: tuy chon cho PNG/DOCX/PDF. Neu False thi bo watermark hien, van giu watermark an (PNG/DOCX) va ky.
    """
    src = Path(src)
    kind = docfile.detect_kind(src)
    if kind == "png":
        validate_png(src)
    elif kind == "docx":
        docfile.validate_docx(src)
    else:
        docfile.validate_pdf(src)

    sha256_original = hashlib.sha256(src.read_bytes()).hexdigest()
    asset = assets_mod.register_asset(asset_name, asset_type, importance, sha256_original)
    asset_id = asset["asset_id"]
    today = f"{datetime.now():%Y-%m-%d}"
    wm_text = f"{config.OWNER_NAME} {today}"

    # (1) Luu ban goc
    config.ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
    original_path = config.ORIGINALS_DIR / f"{asset_id}{src.suffix}"
    original_path.write_bytes(src.read_bytes())

    config.SIGNED_DIR.mkdir(parents=True, exist_ok=True)
    payload = {"asset_id": asset_id, "owner": config.OWNER_NAME, "date": today}

    wm_applied = False
    if kind == "png":
        # (2) Watermark hien (tuy chon) -> file tam
        if visible_watermark:
            temp_visible = config.SIGNED_DIR / f".{asset_id}_visible.png"
            watermark_mod.add_visible_watermark(src, temp_visible, wm_text)
            lsb_src = temp_visible
            wm_applied = True
        else:
            lsb_src = src

        # (3)+(4) Watermark an LSB -> file PNG cuoi cung
        signed_path = config.SIGNED_DIR / f"{asset_id}.png"
        lsb_mod.embed(lsb_src, signed_path, payload)
        if wm_applied:
            temp_visible.unlink(missing_ok=True)
    elif kind == "docx":
        # (2') Watermark hien (header, tuy chon) -> file tam
        if visible_watermark:
            temp_visible = config.SIGNED_DIR / f".{asset_id}_visible.docx"
            docfile.embed_docx_visible_watermark(src, temp_visible, wm_text)
            meta_src = temp_visible
            wm_applied = True
        else:
            meta_src = src

        # (3') Watermark an (metadata) -> file DOCX cuoi cung
        signed_path = config.SIGNED_DIR / f"{asset_id}.docx"
        docfile.embed_docx_metadata(meta_src, signed_path, payload)
        if wm_applied:
            temp_visible.unlink(missing_ok=True)
    else:
        # PDF: watermark hien (text, tuy chon) -> file PDF cuoi cung (khong watermark an)
        signed_path = config.SIGNED_DIR / f"{asset_id}.pdf"
        if visible_watermark:
            docfile.embed_pdf_visible_watermark(src, signed_path, wm_text)
            wm_applied = True
        else:
            signed_path.write_bytes(src.read_bytes())

    # (5) KY file cuoi cung (buoc cuoi)
    sidecar_path = signer.sign_file(signed_path, asset_id)

    result = ProtectResult(
        asset_id=asset_id,
        signed_path=signed_path,
        sidecar_path=sidecar_path,
        original_path=original_path,
        sha256_signed=signer.verify_file(signed_path, sidecar_path).sha256,
        kind=kind,
        visible_watermark=wm_applied,
    )

    # (6) Ghi log bao ve
    logger_mod.log_verify(
        signed_path.name, "BAO_VE", f"asset {asset_id}; loai={asset_type}; muc={importance}"
    )
    return result


def verify_full(
    png_path: Path, sidecar_path: Path | None = None, send_alert: bool = True
) -> FullReport:
    """Xac minh day du: chu ky + watermark an, ket luan theo SPEC.md muc 7.

    Ho tro PNG (watermark LSB), DOCX (watermark metadata), PDF (chi chu ky).
    send_alert=False: khong gui ntfy (dung cho /verify-batch, noi chi gui mot thong bao tom tat).
    """
    png_path = Path(png_path)
    notes: list[str] = []

    # 1. Xac minh chu ky
    sig = signer.verify_file(png_path, sidecar_path)

    # 2. Thieu sidecar -> khong xac minh duoc
    if sig.sidecar is None:
        notes.append("Thiếu file sidecar: không thể xác minh nguồn gốc.")
        logger_mod.log_verify(png_path.name, "KHONG_XAC_MINH_DUOC", "; ".join(notes))
        return FullReport(verdict="KHONG_XAC_MINH_DUOC", sig=sig, lsb_payload=None, notes=notes)

    # 3. Doc watermark an theo loai file
    try:
        kind = docfile.detect_kind(png_path)
    except ValueError:
        kind = None

    if kind == "docx":
        watermark = docfile.extract_docx_metadata(png_path)
        wm_name = "watermark ẩn (metadata DOCX)"
    elif kind == "pdf":
        watermark = None
        wm_name = "watermark ẩn (PDF không có watermark)"
    else:
        try:
            watermark = lsb_mod.extract(png_path)
        except (ValueError, OSError):
            watermark = None
        wm_name = "watermark ẩn (LSB)"

    # 4. Ket luan theo bang logic SPEC.md muc 7
    if sig.valid:
        if kind == "pdf":
            verdict = "HOP_LE"
            notes.append("Chữ ký hợp lệ: tài liệu PDF nguyên bản (PDF chỉ ký, không watermark).")
        elif watermark is None:
            verdict = "HOP_LE_CANH_BAO"
            notes.append(f"Chữ ký hợp lệ nhưng không đọc được {wm_name} (hiếm, ghi log).")
        elif watermark.get("asset_id") != sig.sidecar.get("asset_id"):
            verdict = "HOP_LE_CANH_BAO"
            notes.append(
                f"{wm_name} không khớp asset_id trong sidecar: "
                f"{watermark.get('asset_id')!r} vs {sig.sidecar.get('asset_id')!r}."
            )
        else:
            verdict = "HOP_LE"
            notes.append(f"Chữ ký hợp lệ và {wm_name} khớp sidecar: tài liệu nguyên bản.")
    else:
        verdict = "KHONG_HOP_LE"
        notes.append(f"Chữ ký không hợp lệ: {sig.reason}")
        if watermark is not None:
            notes.append(f"Vẫn đọc được {wm_name}: nhận ra nguồn gốc tài sản.")
        else:
            notes.append("Không đọc được watermark ẩn: tài liệu bị sửa nặng hoặc không phải của hệ thống.")

    report = FullReport(verdict=verdict, sig=sig, lsb_payload=watermark, notes=notes)

    # 5. Ghi log moi lan xac minh
    logger_mod.log_verify(png_path.name, verdict, "; ".join(notes))

    # 6. Gui canh bao ntfy khi KHONG_HOP_LE (loi mang khong lam sap chuong trinh)
    if verdict == "KHONG_HOP_LE" and send_alert:
        asset_id = sig.sidecar.get("asset_id") if sig.sidecar else "?"
        sent = notifier.send_alert(
            "[RESPOND] Phat hien anh gia",
            f"Anh '{png_path.name}' (asset {asset_id}) KHONG HOP LE: {sig.reason}",
        )
        # Ghi su kien ALERT de /nist dem duoc so canh bao da gui
        logger_mod.log_verify(png_path.name, "ALERT", f"ket qua gui ntfy: thanh_cong={sent}")
        if not sent:
            notes.append("Gửi cảnh báo ntfy thất bại hoặc chưa cấu hình topic (bỏ qua).")

    return report


def key_fingerprint() -> str:
    """Van tay khoa cong khai hien tai (tien cho CLI/web hien thi)."""
    return keys_mod.key_fingerprint(keys_mod.load_public_key())
