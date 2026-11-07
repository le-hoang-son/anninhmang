"""Diem vao dong lenh cho he thong ImgSign.

M1: da co cac lenh keygen, sign, verify-sig. Cac lenh con lai cai dat o milestone sau.
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from imgsign import keys as keys_mod
from imgsign import signer

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
    p_protect = sub.add_parser("protect", help="Quy trinh bao ve anh (M5/M6)")
    p_protect.add_argument("png", help="Duong dan anh PNG goc")
    p_protect.add_argument("--name", required=True, help="Ten tai san")
    p_protect.add_argument("--type", dest="asset_type", required=True, help="Loai anh")
    p_protect.add_argument("--importance", type=int, choices=[1, 2, 3], required=True,
                           help="Muc quan trong: 1 thap | 2 trung binh | 3 cao")

    p_verify = sub.add_parser("verify", help="Xac minh day du anh (M5)")
    p_verify.add_argument("png", help="Duong dan anh PNG")
    p_verify.add_argument("--sig", dest="sig", default=None, help="Duong dan sidecar .sig.json")

    sub.add_parser("assets", help="Liet ke bang tai san anh (M6)")

    p_recover = sub.add_parser("recover", help="Khoi phuc ban da ky (M6)")
    p_recover.add_argument("asset_id", help="Ma tai san, vi du IMG-0001")
    p_recover.add_argument("out", help="Duong dan file dau ra")

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


def main(argv: list[str] | None = None) -> int:
    """Chay CLI theo lenh con."""
    parser = build_parser()
    args = parser.parse_args(argv)

    handlers = {
        "keygen": cmd_keygen,
        "sign": cmd_sign,
        "verify-sig": cmd_verify_sig,
    }

    handler = handlers.get(args.command)
    if handler is None:
        milestone = _MILESTONES.get(args.command, "milestone sau")
        print(f"[{_now()}] Lệnh '{args.command}' chưa được cài đặt (sẽ làm ở {milestone}).")
        return 0

    return handler(args)


if __name__ == "__main__":
    raise SystemExit(main())
