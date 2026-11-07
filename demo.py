"""Kich ban demo tu dong cho ImgSign (M8).

Chay tuan tu cac kich ban T1, T2, T3, T4, T11 trong TEST_PLAN.md:
    protect (bao ve) -> verify hop le -> tamper 3 kieu -> verify -> recover.

Moi buoc in tieu de ro rang va dong thoi gian YYYY-MM-DD HH:MM:SS de chup anh minh chung.

Chay:
    python demo.py
"""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path

# Windows console: dam bao in tieng Viet khong loi
sys.stdout.reconfigure(encoding="utf-8")

# Cho phep chay 'python demo.py' tu thu muc goc du an
PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config
from imgsign import keys as keys_mod
from imgsign import pipeline
from imgsign import recover as recover_mod
from imgsign import tamper as tamper_mod

SAMPLE = PROJECT_ROOT / "samples" / "goc.png"

VERDICT_LABEL = {
    "HOP_LE": "HỢP LỆ",
    "HOP_LE_CANH_BAO": "HỢP LỆ (CẢNH BÁO)",
    "KHONG_HOP_LE": "KHÔNG HỢP LỆ",
    "KHONG_XAC_MINH_DUOC": "KHÔNG XÁC MINH ĐƯỢC",
}

_step = 0
_failures = 0


def now() -> str:
    """Dong thoi gian de chup anh minh chung."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def banner(title: str, nist: str = "") -> None:
    """In tieu de buoc demo."""
    global _step
    _step += 1
    label = f"  {nist}" if nist else ""
    print()
    print("=" * 72)
    print(f"BƯỚC {_step}: {title}{label}")
    print(f"Thời gian: {now()}")
    print("=" * 72)


def line(msg: str) -> None:
    """In mot dong co thoi gian."""
    print(f"[{now()}] {msg}")


def expect(condition: bool, msg: str) -> None:
    """Kiem tra ket qua mong doi, tang bo dem loi neu sai."""
    global _failures
    if condition:
        line(f"ĐẠT: {msg}")
    else:
        _failures += 1
        line(f"KHÔNG ĐẠT: {msg}")


def ensure_keys() -> None:
    """Tao khoa RSA neu chua co (FR-1)."""
    if config.PRIVATE_KEY_FILE.exists() and config.PUBLIC_KEY_FILE.exists():
        line("Đã có khóa RSA, bỏ qua bước tạo khóa.")
        return
    fp = keys_mod.generate_keys()
    line(f"Đã tạo cặp khóa RSA-2048, fingerprint = {fp}")


def run() -> int:
    """Chay toan bo kich ban demo. Tra ve ma thoat (0 = thanh cong)."""
    print("KỊCH BẢN DEMO IMGSIGN (chống giả mạo ảnh - NIST CSF 1.1)")
    print(f"Thư mục dự án: {PROJECT_ROOT}")
    print(f"Ảnh mẫu: {SAMPLE}")

    if not SAMPLE.exists():
        print(f"[{now()}] Lỗi: không tìm thấy ảnh mẫu '{SAMPLE}'. Hãy đặt ảnh PNG vào samples/goc.png.")
        return 1

    # --- Bước 1: T1 - Bảo vệ ảnh ---
    banner("T1 - Bảo vệ ảnh (protect): watermark hiện -> watermark ẩn LSB -> lưu PNG -> KÝ", "[PROTECT]")
    ensure_keys()
    try:
        result = pipeline.protect(SAMPLE, "Bảng tốt nghiệp A (demo)", "văn bằng", 3)
    except ValueError as exc:
        print(f"[{now()}] Lỗi: {exc}")
        return 1

    line(f"asset_id: {result.asset_id}")
    line(f"Bản gốc lưu: {result.original_path}")
    line(f"Ảnh đã ký: {result.signed_path}")
    line(f"Sidecar: {result.sidecar_path}")
    line(f"SHA-256 ảnh đã ký: {result.sha256_signed}")

    # --- Bước 2: T1 - Xác minh ảnh nguyên bản ---
    banner("T1 - Xác minh ảnh đã ký (mong đợi: HỢP LỆ)", "[DETECT]")
    report = pipeline.verify_full(result.signed_path, result.sidecar_path)
    line(f"Kết luận: {VERDICT_LABEL.get(report.verdict, report.verdict)}")
    line(f"Lý do: {report.sig.reason}")
    line(f"Watermark ẩn: {'đọc được ' + str(report.lsb_payload) if report.lsb_payload else 'không đọc được'}")
    expect(report.verdict == "HOP_LE" and report.lsb_payload is not None,
           "Ảnh nguyên bản được kết luận HỢP LỆ và đọc được watermark ẩn")

    # --- Bước 3-4-5: T2, T3, T4 - Làm giả 3 kiểu rồi xác minh ---
    modes = [("pixel", "T2 - Sửa 1 điểm ảnh"), ("text", "T3 - Sửa nội dung bằng chữ đè"),
             ("crop", "T4 - Cắt 5% mép ảnh")]
    for mode, title in modes:
        banner(f"{title}, sau đó xác minh (mong đợi: KHÔNG HỢP LỆ)", "[DETECT] [RESPOND]")
        fake_path = PROJECT_ROOT / "samples" / f"demo_fake_{mode}.png"
        detail = tamper_mod.apply_tamper(result.signed_path, fake_path, mode)
        line(f"{detail}")
        line(f"Ảnh giả lưu: {fake_path}")

        fake_report = pipeline.verify_full(fake_path, result.sidecar_path)
        line(f"Kết luận: {VERDICT_LABEL.get(fake_report.verdict, fake_report.verdict)}")
        line(f"Lý do: {fake_report.sig.reason}")
        expect(fake_report.verdict == "KHONG_HOP_LE",
               f"Ảnh giả kiểu '{mode}' bị phát hiện KHÔNG HỢP LỆ")

    # --- Bước 6: T11 - Khôi phục bản đã ký ---
    banner("T11 - Khôi phục bản đã ký (recover) và xác minh lại (mong đợi: HỢP LỆ)", "[RECOVER]")
    recovered = PROJECT_ROOT / "samples" / "demo_recovered.png"
    try:
        rec = recover_mod.recover(result.asset_id, recovered)
    except (FileNotFoundError, OSError) as exc:
        print(f"[{now()}] Lỗi: {exc}")
        return 1
    line(f"Đã khôi phục về: {recovered}")
    line(f"Kết quả xác minh lại: {'HỢP LỆ' if rec.valid else 'KHÔNG HỢP LỆ'}")
    line(f"Lý do: {rec.reason}")
    expect(rec.valid, "Bản khôi phục xác minh HỢP LỆ")

    # --- Tong ket ---
    print()
    print("=" * 72)
    print(f"TỔNG KẾT ({now()})")
    print("=" * 72)
    if _failures == 0:
        print("Toàn bộ kịch bản chạy thành công, không có bước nào KHÔNG ĐẠT.")
        print("Kết quả đúng với TEST_PLAN.md (T1, T2, T3, T4, T11).")
        print("Xem log tại: data/logs/verify.log")
        return 0

    print(f"Có {_failures} bước KHÔNG ĐẠT. Xem chi tiết ở trên.")
    return 1


if __name__ == "__main__":
    raise SystemExit(run())
