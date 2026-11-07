"""Ghi va doc log xac minh (FR-9, Detect) tai data/logs/verify.log.

Dinh dang moi dong (ARCHITECTURE.md 4.5):
    YYYY-MM-DD HH:MM:SS | <ten file> | <verdict> | <chi tiet>

Ngoai cac ket luan xac minh con co su kien:
    BAO_VE  - da bao ve mot anh (Protect)
    RECOVER - da khoi phuc mot tai san (Recover)
    ALERT   - da thu gui canh bao ntfy (Respond), chi tiet co thanh_cong=True/False
"""

from __future__ import annotations

from datetime import datetime

import config


def log_verify(file_name: str, verdict: str, detail: str) -> None:
    """Ghi mot dong log. Loi ghi file khong lam sap chuong trinh."""
    line = f"{datetime.now():%Y-%m-%d %H:%M:%S} | {file_name} | {verdict} | {detail}\n"
    try:
        config.VERIFY_LOG.parent.mkdir(parents=True, exist_ok=True)
        with config.VERIFY_LOG.open("a", encoding="utf-8") as handle:
            handle.write(line)
    except OSError:
        pass


def read_log_lines() -> list[str]:
    """Doc toan bo dong log, tra ve [] neu file chua co hoac loi doc."""
    if not config.VERIFY_LOG.exists():
        return []
    try:
        return config.VERIFY_LOG.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []


def parse_line(line: str) -> tuple[str, str, str, str] | None:
    """Tach mot dong log thanh (thoi_gian, ten_file, verdict, chi_tiet). None neu sai dinh dang."""
    parts = line.split(" | ")
    if len(parts) < 4:
        return None
    return parts[0], parts[1], parts[2], " | ".join(parts[3:])


def summarize() -> dict:
    """Thong ke so lieu tu verify.log de hien thi tren trang /nist."""
    counts = {
        "bao_ve": 0,
        "hop_le": 0,
        "hop_le_canh_bao": 0,
        "khong_hop_le": 0,
        "khong_xac_minh": 0,
        "total_verify": 0,
        "alerts_sent": 0,
        "alerts_failed": 0,
        "recovers": 0,
    }
    for line in read_log_lines():
        parsed = parse_line(line)
        if parsed is None:
            continue
        _, _, verdict, detail = parsed
        if verdict == "BAO_VE":
            counts["bao_ve"] += 1
        elif verdict == "HOP_LE":
            counts["hop_le"] += 1
        elif verdict == "HOP_LE_CANH_BAO":
            counts["hop_le_canh_bao"] += 1
        elif verdict == "KHONG_HOP_LE":
            counts["khong_hop_le"] += 1
        elif verdict == "KHONG_XAC_MINH_DUOC":
            counts["khong_xac_minh"] += 1
        elif verdict == "RECOVER":
            counts["recovers"] += 1
        elif verdict == "ALERT":
            if "thanh_cong=True" in detail:
                counts["alerts_sent"] += 1
            else:
                counts["alerts_failed"] += 1

    counts["total_verify"] = (
        counts["hop_le"]
        + counts["hop_le_canh_bao"]
        + counts["khong_hop_le"]
        + counts["khong_xac_minh"]
    )
    counts["total_hop_le"] = counts["hop_le"] + counts["hop_le_canh_bao"]
    return counts
