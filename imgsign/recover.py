"""Luu ban goc va khoi phuc ban da ky (FR-10, Recover - RC.RP).

recover(): chep ban da ky (data/signed/<asset_id>.<ext>) ve dst va xac minh lai.
Ho tro .png, .docx, .pdf.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import config
from imgsign import docfile
from imgsign import logger as logger_mod
from imgsign import signer
from imgsign.signer import VerifyResult


def recover(asset_id: str, dst: Path) -> VerifyResult:
    """Chep ban da ky cua asset ve dst roi xac minh lai chinh file do.

    Nem FileNotFoundError neu khong co ban da ky.
    """
    dst = Path(dst)
    source = docfile.find_signed(config.SIGNED_DIR, asset_id)
    sidecar = Path(str(source) + ".sig.json") if source is not None else None

    if source is None or sidecar is None or not sidecar.exists():
        raise FileNotFoundError(
            f"Không tìm thấy bản đã ký cho asset '{asset_id}' trong data/signed/."
        )

    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, dst)

    # Ho tro sidecar di kem ban da chep (them duoi .sig.json)
    dst_sidecar = Path(str(dst) + ".sig.json")
    shutil.copyfile(sidecar, dst_sidecar)

    result = signer.verify_file(dst, dst_sidecar)

    # Ghi su kien RECOVER de /nist dem duoc so lan khoi phuc
    logger_mod.log_verify(
        dst.name, "RECOVER", f"asset {asset_id}; ket qua xac minh lai: {'hop le' if result.valid else 'khong hop le'}"
    )
    return result
