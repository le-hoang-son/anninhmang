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
from imgsign import keys as keys_mod
from imgsign import logger as logger_mod
from imgsign import lsb as lsb_mod
from imgsign import notifier
from imgsign import signer
from imgsign import watermark as watermark_mod
from imgsign.signer import VerifyResult


@dataclass
class ProtectResult:
    """Ket qua quy trinh bao ve anh."""

    asset_id: str
    signed_path: Path
    sidecar_path: Path
    original_path: Path
    sha256_signed: str


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


def protect(src: Path, asset_name: str, asset_type: str, importance: int) -> ProtectResult:
    """Bao ve anh theo dung thu tu bat bien. Tra ve ProtectResult.

    Buoc: luu goc -> dang ky asset -> watermark hien -> LSB -> luu PNG -> KY (buoc cuoi) -> log.
    """
    src = Path(src)
    validate_png(src)

    sha256_original = hashlib.sha256(src.read_bytes()).hexdigest()
    asset = assets_mod.register_asset(asset_name, asset_type, importance, sha256_original)
    asset_id = asset["asset_id"]
    today = f"{datetime.now():%Y-%m-%d}"

    # (1) Luu ban goc
    config.ORIGINALS_DIR.mkdir(parents=True, exist_ok=True)
    original_path = config.ORIGINALS_DIR / f"{asset_id}{src.suffix}"
    original_path.write_bytes(src.read_bytes())

    # (2) Watermark hien -> file tam
    config.SIGNED_DIR.mkdir(parents=True, exist_ok=True)
    temp_visible = config.SIGNED_DIR / f".{asset_id}_visible.png"
    watermark_mod.add_visible_watermark(src, temp_visible, f"{config.OWNER_NAME} {today}")

    # (3)+(4) Watermark an LSB -> file PNG cuoi cung
    signed_path = config.SIGNED_DIR / f"{asset_id}.png"
    payload = {"asset_id": asset_id, "owner": config.OWNER_NAME, "date": today}
    lsb_mod.embed(temp_visible, signed_path, payload)
    temp_visible.unlink(missing_ok=True)

    # (5) KY file PNG cuoi cung (buoc cuoi)
    sidecar_path = signer.sign_file(signed_path, asset_id)

    result = ProtectResult(
        asset_id=asset_id,
        signed_path=signed_path,
        sidecar_path=sidecar_path,
        original_path=original_path,
        sha256_signed=signer.verify_file(signed_path, sidecar_path).sha256,
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

    # 3. Doc watermark an LSB
    try:
        lsb_payload = lsb_mod.extract(png_path)
    except (ValueError, OSError):
        lsb_payload = None

    # 4. Ket luan theo bang logic SPEC.md muc 7
    if sig.valid:
        if lsb_payload is None:
            verdict = "HOP_LE_CANH_BAO"
            notes.append("Chữ ký hợp lệ nhưng không đọc được watermark ẩn (hiếm, ghi log).")
        elif lsb_payload.get("asset_id") != sig.sidecar.get("asset_id"):
            verdict = "HOP_LE_CANH_BAO"
            notes.append(
                "Watermark ẩn không khớp asset_id trong sidecar: "
                f"{lsb_payload.get('asset_id')!r} vs {sig.sidecar.get('asset_id')!r}."
            )
        else:
            verdict = "HOP_LE"
            notes.append("Chữ ký hợp lệ và watermark ẩn khớp sidecar: ảnh nguyên bản.")
    else:
        verdict = "KHONG_HOP_LE"
        notes.append(f"Chữ ký không hợp lệ: {sig.reason}")
        if lsb_payload is not None:
            notes.append("Vẫn đọc được watermark ẩn: nhận ra nguồn gốc ảnh.")
        else:
            notes.append("Không đọc được watermark ẩn: ảnh bị sửa nặng hoặc không phải ảnh của hệ thống.")

    report = FullReport(verdict=verdict, sig=sig, lsb_payload=lsb_payload, notes=notes)

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
