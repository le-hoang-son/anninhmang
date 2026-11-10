"""Diem vao dong lenh cho he thong ImgSign.

M2: da co cac lenh keygen, sign, verify-sig, tamper. Cac lenh con lai cai dat o milestone sau.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image

import config
from imgsign import assets as assets_mod
from imgsign import docfile
from imgsign import keys as keys_mod
from imgsign import lsb as lsb_mod
from imgsign import pipeline
from imgsign import recover as recover_mod
from imgsign import signer
from imgsign import tamper as tamper_mod
from imgsign import watermark as watermark_mod

# Windows console: dam bao in tieng Viet khong loi
sys.stdout.reconfigure(encoding="utf-8")

# Anh xa moi lenh con sang milestone se cai dat
_MILESTONES: dict[str, str] = {
    "keygen": "M1",
    "sign": "M1",
    "verify-sig": "M1",
    "tamper": "M2",
    "watermark": "M3",
    "lsb-embed": "M4",
    "lsb-read": "M4",
    "protect": "M5/M6",
    "verify": "M5",
    "assets": "M6",
    "recover": "M6",
    "docx-read": "M9",
}


def _now() -> str:
    """Tra ve dong thoi gian YYYY-MM-DD HH:MM:SS de chup anh minh chung."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def build_parser() -> argparse.ArgumentParser:
    """Tao bo phan tich tham so dong lenh voi day du lenh con theo ARCHITECTURE."""
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="ImgSign - Chong gia mao anh bang watermark va chu ky so (NIST CSF 1.1).",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="<lenh>")

    # --- M1: khoa va chu ky ---
    p_keygen = sub.add_parser("keygen", help="Tao cap khoa RSA-2048 (M1)")
    p_keygen.add_argument("--force", action="store_true", help="Ghi de khoa cu neu da ton tai")

    p_sign = sub.add_parser("sign", help="Ky file PNG, tao sidecar .sig.json (M1)")
    p_sign.add_argument("png", help="Duong dan anh PNG")
    p_sign.add_argument("--id", dest="asset_id", default=None, help="Ma tai san, vi du IMG-0001")

    p_vsig = sub.add_parser("verify-sig", help="Xac minh chu ky cua anh (M1)")
    p_vsig.add_argument("png", help="Duong dan anh PNG")
    p_vsig.add_argument("--sig", dest="sig", default=None, help="Duong dan sidecar .sig.json")

    # --- M2: tao anh gia de demo ---
    p_tamper = sub.add_parser("tamper", help="Tao anh gia de demo (M2)")
    p_tamper.add_argument("png", help="Duong dan anh PNG goc")
    p_tamper.add_argument("out", help="Duong dan anh PNG dau ra")
    p_tamper.add_argument("--mode", choices=["text", "crop", "pixel"], required=True,
                          help="Kieu lam gia: text | crop | pixel")

    # --- M3: watermark hien ---
    p_wm = sub.add_parser("watermark", help="Chen watermark hien (M3)")
    p_wm.add_argument("png", help="Duong dan anh PNG goc")
    p_wm.add_argument("out", help="Duong dan anh PNG dau ra")
    p_wm.add_argument("--text", dest="text", default=None, help="Noi dung chu mo")

    # --- M4: watermark an LSB ---
    p_lsb_e = sub.add_parser("lsb-embed", help="Giau watermark an LSB (M4)")
    p_lsb_e.add_argument("png", help="Duong dan anh PNG goc")
    p_lsb_e.add_argument("out", help="Duong dan anh PNG dau ra")
    p_lsb_e.add_argument("--msg", dest="msg", required=True, help="Noi dung can giau")

    p_lsb_r = sub.add_parser("lsb-read", help="Doc watermark an LSB (M4)")
    p_lsb_r.add_argument("png", help="Duong dan anh PNG")

    # --- M5/M6: quy trinh bao ve, xac minh, tai san, khoi phuc ---
    p_protect = sub.add_parser(
        "protect", help="Quy trinh bao ve anh/tai lieu: PNG, DOCX, PDF (M5/M6/M9)"
    )
    p_protect.add_argument("png", help="Duong dan file goc (.png, .docx hoac .pdf)")
    p_protect.add_argument("--name", required=True, help="Ten tai san")
    p_protect.add_argument("--type", dest="asset_type", required=True, help="Loai anh hoac loai tai lieu")
    p_protect.add_argument("--importance", type=int, choices=[1, 2, 3], required=True,
                           help="Muc quan trong: 1 thap | 2 trung binh | 3 cao")
    p_protect.add_argument("--no-visible-watermark", dest="visible_watermark",
                           action="store_false", default=True,
                           help="Bo qua watermark hien (chi ap dung cho PNG; van co watermark an LSB va chu ky)")

    p_verify = sub.add_parser("verify", help="Xac minh day du anh (M5)")
    p_verify.add_argument("png", help="Duong dan anh PNG")
    p_verify.add_argument("--sig", dest="sig", default=None, help="Duong dan sidecar .sig.json")

    sub.add_parser("assets", help="Liet ke bang tai san anh (M6)")

    p_recover = sub.add_parser("recover", help="Khoi phuc ban da ky (M6)")
    p_recover.add_argument("asset_id", help="Ma tai san, vi du IMG-0001")
    p_recover.add_argument("out", help="Duong dan file dau ra")

    # --- M9: doc watermark an trong tai lieu DOCX ---
    p_docx_read = sub.add_parser("docx-read", help="Doc watermark an (metadata) trong DOCX (M9)")
    p_docx_read.add_argument("docx", help="Duong dan file .docx")

    return parser


def cmd_keygen(args: argparse.Namespace) -> int:
    """Lenh keygen: tao cap khoa RSA-2048."""
    print(f"[{_now()}] [PROTECT] Tạo cặp khóa RSA-2048.")
    try:
        fingerprint = keys_mod.generate_keys(force=args.force)
    except FileExistsError:
        print(f"[{_now()}] Khóa đã tồn tại trong 'keys/'. Dùng --force để ghi đè.")
        return 1
    print(f"[{_now()}] Đã tạo: keys/private.pem, keys/public.pem")
    print(f"[{_now()}] Vân tay khóa công khai (fingerprint): {fingerprint}")
    return 0


def cmd_sign(args: argparse.Namespace) -> int:
    """Lenh sign: ky file PNG, ghi sidecar."""
    png = Path(args.png)
    if not png.exists():
        print(f"[{_now()}] Lỗi: không tìm thấy file '{png}'.")
        return 1

    asset_id = args.asset_id or png.stem
    try:
        sidecar_path = signer.sign_file(png, asset_id)
    except FileNotFoundError:
        print(f"[{_now()}] Lỗi: chưa có khóa. Hãy chạy 'python cli.py keygen' trước.")
        return 1

    print(f"[{_now()}] [PROTECT] Đã ký ảnh '{png.name}' (asset_id={asset_id}).")
    print(f"[{_now()}] Sidecar: {sidecar_path}")
    return 0


def cmd_verify_sig(args: argparse.Namespace) -> int:
    """Lenh verify-sig: xac minh chu ky cua anh."""
    png = Path(args.png)
    if not png.exists():
        print(f"[{_now()}] Lỗi: không tìm thấy file '{png}'.")
        return 1

    sig = Path(args.sig) if args.sig else None
    result = signer.verify_file(png, sig)

    status = "HỢP LỆ" if result.valid else "KHÔNG HỢP LỆ"
    print(f"[{_now()}] [DETECT] Xác minh chữ ký ảnh '{png.name}'.")
    print(f"[{_now()}] Kết quả: {status}")
    print(f"[{_now()}] Lý do: {result.reason}")
    print(f"[{_now()}] SHA-256 file: {result.sha256}")
    return 0


def cmd_tamper(args: argparse.Namespace) -> int:
    """Lenh tamper: tao anh gia de demo (text | crop | pixel)."""
    src, dst = Path(args.png), Path(args.out)
    if not src.exists():
        print(f"[{_now()}] Lỗi: không tìm thấy file '{src}'.")
        return 1

    try:
        detail = tamper_mod.apply_tamper(src, dst, args.mode)
    except (ValueError, OSError) as exc:
        print(f"[{_now()}] Lỗi: {exc}")
        return 1

    print(f"[{_now()}] [DETECT] Tạo ảnh giả từ '{src.name}' (mode={args.mode}).")
    print(f"[{_now()}] {detail}")
    print(f"[{_now()}] Đã lưu ảnh giả: {dst}")
    return 0


def cmd_watermark(args: argparse.Namespace) -> int:
    """Lenh watermark: chen watermark hien (chu mo lap cheo)."""
    src, dst = Path(args.png), Path(args.out)
    if not src.exists():
        print(f"[{_now()}] Lỗi: không tìm thấy file '{src}'.")
        return 1

    text = args.text or f"{config.OWNER_NAME} {datetime.now():%Y-%m-%d}"
    try:
        watermark_mod.add_visible_watermark(src, dst, text)
    except (ValueError, OSError) as exc:
        print(f"[{_now()}] Lỗi: {exc}")
        return 1

    print(f"[{_now()}] [PROTECT] Đã chèn watermark hiện (chữ mờ) vào '{src.name}'.")
    print(f"[{_now()}] Nội dung: {text}")
    print(f"[{_now()}] Đã lưu ảnh: {dst}")
    return 0


def cmd_lsb_embed(args: argparse.Namespace) -> int:
    """Lenh lsb-embed: giau payload JSON vao bit thap nhat cua anh."""
    src, dst = Path(args.png), Path(args.out)
    if not src.exists():
        print(f"[{_now()}] Lỗi: không tìm thấy file '{src}'.")
        return 1

    parts = [p.strip() for p in args.msg.split("|") if p.strip()]
    payload = {
        "asset_id": parts[0] if parts else "",
        "owner": parts[1] if len(parts) > 1 else config.OWNER_NAME,
        "date": f"{datetime.now():%Y-%m-%d}",
    }

    try:
        lsb_mod.embed(src, dst, payload)
    except (ValueError, OSError) as exc:
        print(f"[{_now()}] Lỗi: {exc}")
        return 1

    # Thong ke khac biet de chung minh "mat thuong khong thay"
    a = np.array(Image.open(src).convert("RGB"), dtype=np.int16)
    b = np.array(Image.open(dst).convert("RGB"), dtype=np.int16)
    diff = np.abs(a - b)
    if diff.shape == (0,):
        diff_pixels, max_dev = 0, 0
    else:
        diff_pixels = int((diff.max(axis=2) > 0).sum())
        max_dev = int(diff.max())

    print(f"[{_now()}] [PROTECT] Đã giấu watermark ẩn LSB vào '{src.name}'.")
    print(f"[{_now()}] Payload: {payload}")
    print(f"[{_now()}] Số điểm ảnh khác nhau: {diff_pixels}")
    print(f"[{_now()}] Độ lệch tối đa mỗi kênh: {max_dev}")
    print(f"[{_now()}] Đã lưu ảnh: {dst}")
    return 0


def cmd_lsb_read(args: argparse.Namespace) -> int:
    """Lenh lsb-read: doc watermark an LSB tu anh."""
    src = Path(args.png)
    if not src.exists():
        print(f"[{_now()}] Lỗi: không tìm thấy file '{src}'.")
        return 1

    payload = lsb_mod.extract(src)
    if payload is None:
        print(f"[{_now()}] [DETECT] '{src.name}': không tìm thấy watermark ẩn.")
        return 0

    print(f"[{_now()}] [DETECT] '{src.name}': đọc được watermark ẩn.")
    print(f"[{_now()}] Payload: {payload}")
    return 0


VERDICT_LABEL = {
    "HOP_LE": "HỢP LỆ",
    "HOP_LE_CANH_BAO": "HỢP LỆ (CẢNH BÁO)",
    "KHONG_HOP_LE": "KHÔNG HỢP LỆ",
    "KHONG_XAC_MINH_DUOC": "KHÔNG XÁC MINH ĐƯỢC",
}


def cmd_protect(args: argparse.Namespace) -> int:
    """Lenh protect: quy trinh bao ve anh (watermark hien -> LSB -> ky)."""
    src = Path(args.png)
    if not src.exists():
        print(f"[{_now()}] Lỗi: không tìm thấy file '{src}'.")
        return 1

    try:
        result = pipeline.protect(
            src, args.name, args.asset_type, args.importance,
            visible_watermark=args.visible_watermark,
        )
    except (ValueError, OSError) as exc:
        print(f"[{_now()}] Lỗi: {exc}")
        return 1

    label = "Ảnh đã ký" if result.kind == "png" else "Tài liệu đã ký"
    print(f"[{_now()}] [PROTECT] Đã bảo vệ '{src.name}' -> asset {result.asset_id} (định dạng {result.kind}).")
    if result.kind == "png":
        print(
            f"[{_now()}] Watermark hiện: {'CÓ (chữ mờ)' if result.visible_watermark else 'KHÔNG (chỉ watermark ẩn LSB)'}"
        )
    print(f"[{_now()}] Bản gốc lưu: {result.original_path}")
    print(f"[{_now()}] {label}: {result.signed_path}")
    print(f"[{_now()}] Sidecar: {result.sidecar_path}")
    print(f"[{_now()}] SHA-256 file đã ký: {result.sha256_signed}")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    """Lenh verify: xac minh day du (chu ky + watermark an)."""
    src = Path(args.png)
    if not src.exists():
        print(f"[{_now()}] Lỗi: không tìm thấy file '{src}'.")
        return 1

    sig = Path(args.sig) if args.sig else None
    report = pipeline.verify_full(src, sig)

    print(f"[{_now()}] [DETECT] Xác minh đầy đủ ảnh '{src.name}'.")
    print(f"[{_now()}] Kết luận: {VERDICT_LABEL.get(report.verdict, report.verdict)}")
    print(f"[{_now()}] Lý do: {report.sig.reason}")
    print(f"[{_now()}] SHA-256 file: {report.sig.sha256}")
    if report.lsb_payload is not None:
        print(f"[{_now()}] Watermark ẩn: đọc được {report.lsb_payload}")
    else:
        print(f"[{_now()}] Watermark ẩn: không đọc được")
    for note in report.notes:
        print(f"[{_now()}] - {note}")
    return 0


def cmd_assets(args: argparse.Namespace) -> int:
    """Lenh assets: liet ke bang tai san anh (Identify)."""
    rows = assets_mod.list_assets()
    print(f"[{_now()}] [IDENTIFY] Bảng tài sản ảnh ({len(rows)} bản ghi).")
    if not rows:
        print(f"[{_now()}] Chưa có tài sản nào.")
        return 0

    print(f"[{_now()}] {'asset_id':<10} {'mức':<4} {'loại':<12} {'tên':<28} created_at")
    for a in rows:
        print(
            f"[{_now()}] {a.get('asset_id', ''):<10} {a.get('importance', ''):<4} "
            f"{str(a.get('type', '')):<12} {str(a.get('name', '')):<28} {a.get('created_at', '')}"
        )
    return 0


def cmd_recover(args: argparse.Namespace) -> int:
    """Lenh recover: khoi phuc ban da ky va xac minh lai (Recover)."""
    try:
        result = recover_mod.recover(args.asset_id, Path(args.out))
    except (FileNotFoundError, OSError) as exc:
        print(f"[{_now()}] Lỗi: {exc}")
        return 1

    status = "HỢP LỆ" if result.valid else "KHÔNG HỢP LỆ"
    print(f"[{_now()}] [RECOVER] Đã khôi phục '{args.asset_id}' về {args.out}.")
    print(f"[{_now()}] Kết quả xác minh lại: {status}")
    print(f"[{_now()}] Lý do: {result.reason}")
    print(f"[{_now()}] SHA-256 file: {result.sha256}")
    return 0


def cmd_docx_read(args: argparse.Namespace) -> int:
    """Lenh docx-read: doc watermark an (metadata) trong file DOCX."""
    src = Path(args.docx)
    if not src.exists():
        print(f"[{_now()}] Lỗi: không tìm thấy file '{src}'.")
        return 1

    payload = docfile.extract_docx_metadata(src)
    if payload is None:
        print(f"[{_now()}] [DETECT] '{src.name}': không tìm thấy watermark ẩn.")
        return 0

    print(f"[{_now()}] [DETECT] '{src.name}': đọc được watermark ẩn.")
    print(f"[{_now()}] Payload: {payload}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Chay CLI theo lenh con."""
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "keygen": cmd_keygen,
        "sign": cmd_sign,
        "verify-sig": cmd_verify_sig,
        "tamper": cmd_tamper,
        "watermark": cmd_watermark,
        "lsb-embed": cmd_lsb_embed,
        "lsb-read": cmd_lsb_read,
        "protect": cmd_protect,
        "verify": cmd_verify,
        "assets": cmd_assets,
        "recover": cmd_recover,
        "docx-read": cmd_docx_read,
    }

    handler = handlers.get(args.command)
    if handler is None:
        milestone = _MILESTONES.get(args.command, "milestone sau")
        print(f"[{_now()}] Lệnh '{args.command}' chưa được cài đặt (sẽ làm ở {milestone}).")
        return 0

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
