"""Ky va xac minh chu ky so (FR-2, FR-3).

Thuat toan: RSA-2048, RSA-PSS, MGF1(SHA-256), salt_length = MAX, hash SHA-256.
Chu ky tinh tren toan bo byte cua file PNG. Sidecar dinh dang theo ARCHITECTURE.md 4.2.
"""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

import config
from imgsign import keys as keys_mod

ALGORITHM = "RSA-PSS-SHA256"


@dataclass
class VerifyResult:
    """Ket qua xac minh chu ky."""

    valid: bool
    reason: str
    sha256: str
    sidecar: dict | None


def _pss_padding() -> padding.PSS:
    """Padding PSS dung chung cho ky va xac minh."""
    return padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH)


def default_sidecar_path(png_path: Path) -> Path:
    """Duong dan sidecar mac dinh: <file>.png.sig.json."""
    return Path(str(png_path) + ".sig.json")


def sign_file(png_path: Path, asset_id: str) -> Path:
    """Ky file PNG bang khoa rieng, ghi sidecar <png_path>.sig.json."""
    png_path = Path(png_path)
    data = png_path.read_bytes()

    private_key = keys_mod.load_private_key()
    signature = private_key.sign(data, _pss_padding(), hashes.SHA256())

    sidecar = {
        "version": 1,
        "asset_id": asset_id,
        "file_name": png_path.name,
        "sha256": hashlib.sha256(data).hexdigest(),
        "signature_b64": base64.b64encode(signature).decode("ascii"),
        "algorithm": ALGORITHM,
        "key_fingerprint": keys_mod.key_fingerprint(keys_mod.load_public_key()),
        "signed_at": datetime.now().astimezone().isoformat(),
        "owner": config.OWNER_NAME,
    }

    sidecar_path = default_sidecar_path(png_path)
    sidecar_path.write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return sidecar_path


def verify_file(png_path: Path, sidecar_path: Path | None = None) -> VerifyResult:
    """Xac minh chu ky cua file PNG theo sidecar.

    Thu tu kiem tra: (1) SHA-256 file, (2) van tay khoa, (3) chu ky so.
    Sai bat ky buoc nao -> valid=False voi ly do tieng Viet neu dung buoc sai.
    """
    png_path = Path(png_path)
    data = png_path.read_bytes()
    file_sha = hashlib.sha256(data).hexdigest()

    if sidecar_path is None:
        sidecar_path = default_sidecar_path(png_path)
    sidecar_path = Path(sidecar_path)

    if not sidecar_path.exists():
        return VerifyResult(
            valid=False,
            reason=f"Thiếu file sidecar '{sidecar_path.name}'. Vui lòng cung cấp file .sig.json.",
            sha256=file_sha,
            sidecar=None,
        )

    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return VerifyResult(
            valid=False,
            reason="File sidecar không đọc được hoặc sai định dạng JSON.",
            sha256=file_sha,
            sidecar=None,
        )

    if not isinstance(sidecar, dict):
        return VerifyResult(
            valid=False,
            reason="File sidecar sai định dạng (không phải đối tượng JSON).",
            sha256=file_sha,
            sidecar=None,
        )

    # Buoc 1: so SHA-256 cua file voi sidecar
    if sidecar.get("sha256") != file_sha:
        return VerifyResult(
            valid=False,
            reason="SHA-256 không khớp: file ảnh đã bị sửa đổi.",
            sha256=file_sha,
            sidecar=sidecar,
        )

    # Buoc 2: so van tay khoa cong khai (phat hien khoa la)
    try:
        public_key = keys_mod.load_public_key()
    except (OSError, ValueError):
        return VerifyResult(
            valid=False,
            reason="Không nạp được khóa công khai để xác minh.",
            sha256=file_sha,
            sidecar=sidecar,
        )

    if sidecar.get("key_fingerprint") != keys_mod.key_fingerprint(public_key):
        return VerifyResult(
            valid=False,
            reason="Vân tay khóa không khớp: ảnh được ký bằng khóa khác (khóa lạ).",
            sha256=file_sha,
            sidecar=sidecar,
        )

    # Buoc 3: xac minh chu ky so
    try:
        signature = base64.b64decode(sidecar.get("signature_b64") or "", validate=True)
    except (ValueError, TypeError):
        return VerifyResult(
            valid=False,
            reason="Chữ ký trong sidecar sai định dạng base64.",
            sha256=file_sha,
            sidecar=sidecar,
        )

    try:
        public_key.verify(signature, data, _pss_padding(), hashes.SHA256())
    except InvalidSignature:
        return VerifyResult(
            valid=False,
            reason="Chữ ký số không hợp lệ: nội dung chữ ký đã bị thay đổi.",
            sha256=file_sha,
            sidecar=sidecar,
        )

    return VerifyResult(
        valid=True,
        reason="Chữ ký hợp lệ: ảnh nguyên bản, chưa bị sửa đổi.",
        sha256=file_sha,
        sidecar=sidecar,
    )
