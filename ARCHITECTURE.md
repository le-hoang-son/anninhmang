# ARCHITECTURE.md — Kiến trúc và hợp đồng kỹ thuật

> Đây là "hợp đồng". Agent không tự ý đổi tên hàm, định dạng file, thứ tự quy trình. Muốn đổi phải hỏi người dùng.

## 1. Cấu trúc thư mục

```
imgsign/
├─ AGENTS.md  SPEC.md  ARCHITECTURE.md  TASKS.md  NIST_MAPPING.md  TEST_PLAN.md
├─ requirements.txt
├─ .gitignore                 # keys/ data/ __pycache__/ .env
├─ config.py                  # đường dẫn, tên đơn vị, ntfy topic (đọc từ biến môi trường)
├─ cli.py                     # điểm vào dòng lệnh (argparse)
├─ imgsign/
│  ├─ __init__.py
│  ├─ keys.py                 # tạo/nạp khóa RSA
│  ├─ signer.py               # ký + xác minh chữ ký, đọc/ghi sidecar
│  ├─ watermark.py            # watermark hiện (Pillow)
│  ├─ lsb.py                  # watermark ẩn (numpy)
│  ├─ pipeline.py             # protect() và verify_full()
│  ├─ assets.py               # bảng tài sản ảnh (assets.json)
│  ├─ logger.py               # ghi verify.log
│  ├─ notifier.py             # gửi ntfy
│  └─ recover.py              # lưu gốc + khôi phục
├─ web/
│  ├─ app.py                  # Flask
│  └─ templates/              # base.html index.html protect.html verify.html assets.html logs.html
├─ tests/
│  ├─ test_signer.py  test_lsb.py  test_pipeline.py
├─ samples/                   # ảnh PNG mẫu của người dùng (goc.png)
├─ keys/                      # private.pem public.pem  (KHÔNG commit)
└─ data/                      # KHÔNG commit
   ├─ originals/              # <asset_id>.png  bản gốc trước khi bảo vệ
   ├─ signed/                 # <asset_id>.png + <asset_id>.png.sig.json
   ├─ logs/verify.log
   └─ assets.json
```

## 2. config.py (biến cấu hình)

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `OWNER_NAME` | `"Truong Demo"` | Tên đơn vị phát hành, dùng cho watermark |
| `NTFY_URL` | `"https://ntfy.sh"` | Máy chủ ntfy |
| `NTFY_TOPIC` | đọc env `IMGSIGN_NTFY_TOPIC`, rỗng = tắt cảnh báo | Kênh cảnh báo |
| `KEY_PASSWORD` | đọc env `IMGSIGN_KEY_PASSWORD`, rỗng = không mã hóa khóa | Mật khẩu khóa riêng |
| `MAX_UPLOAD_MB` | `10` | Giới hạn upload |

Dùng `pathlib.Path` cho mọi đường dẫn, gốc là thư mục chứa `config.py`.

## 3. Hợp đồng hàm (chữ ký hàm cố định)

```python
# keys.py
def generate_keys(force: bool = False) -> str            # trả fingerprint (SHA-256 hex của public key DER, 16 ký tự đầu)
def load_private_key() -> RSAPrivateKey
def load_public_key() -> RSAPublicKey
def key_fingerprint(public_key) -> str

# signer.py
def sign_file(png_path: Path, asset_id: str) -> Path      # ghi <png_path>.sig.json, trả đường dẫn sidecar
def verify_file(png_path: Path, sidecar_path: Path | None = None) -> VerifyResult
# VerifyResult: dataclass(valid: bool, reason: str, sha256: str, sidecar: dict | None)

# watermark.py
def add_visible_watermark(src: Path, dst: Path, text: str, opacity: int = 90) -> Path

# lsb.py
def embed(src: Path, dst: Path, payload: dict) -> Path    # raise ValueError nếu ảnh quá nhỏ
def extract(src: Path) -> dict | None                      # None nếu không có/sai magic/sai CRC

# pipeline.py
def protect(src: Path, asset_name: str, asset_type: str, importance: int) -> ProtectResult
# Làm đúng thứ tự: lưu gốc -> đăng ký asset -> watermark hiện -> LSB -> lưu data/signed -> ký -> ghi log
def verify_full(png_path: Path, sidecar_path: Path | None) -> FullReport
# FullReport: dataclass(verdict: str, sig: VerifyResult, lsb_payload: dict | None, notes: list[str])
# verdict ∈ {"HOP_LE", "HOP_LE_CANH_BAO", "KHONG_HOP_LE", "KHONG_XAC_MINH_DUOC"}

# assets.py
def register_asset(name, asset_type, importance, sha256_original) -> dict   # sinh asset_id dạng "IMG-0001"
def list_assets() -> list[dict]
def get_asset(asset_id: str) -> dict | None

# logger.py
def log_verify(file_name: str, verdict: str, detail: str) -> None

# notifier.py
def send_alert(title: str, message: str) -> bool          # False nếu lỗi mạng, KHÔNG raise

# recover.py
def recover(asset_id: str, dst: Path) -> VerifyResult     # chép bản đã ký về dst và xác minh lại
```

## 4. Định dạng dữ liệu

### 4.1 Chữ ký
- Thuật toán: **RSA-2048, RSA-PSS, MGF1(SHA-256), salt_length = MAX, hash SHA-256**.
- Chữ ký tính trên **toàn bộ byte của file PNG cuối cùng** (sau khi đã watermark hiện + ẩn).
- (Lưu ý: `step1.py` cũ dùng PKCS1v15 chỉ để thử, bản chính thức dùng PSS.)

### 4.2 Sidecar `<file>.png.sig.json`
```json
{
  "version": 1,
  "asset_id": "IMG-0001",
  "file_name": "IMG-0001.png",
  "sha256": "hex 64 ký tự",
  "signature_b64": "base64",
  "algorithm": "RSA-PSS-SHA256",
  "key_fingerprint": "16 ký tự hex",
  "signed_at": "2026-11-08T10:00:00+07:00",
  "owner": "Truong Demo"
}
```
Xác minh: (1) tính SHA-256 file, so với `sha256` trong sidecar; (2) verify chữ ký bằng public key; (3) so `key_fingerprint`. Sai bất kỳ bước nào -> `valid=False`, `reason` tiếng Việt nêu đúng bước sai.

### 4.3 Watermark ẩn LSB
- Mở ảnh, chuyển về `RGB` (nếu có alpha: giữ nguyên kênh alpha, chỉ ghi vào R,G,B).
- Chuỗi bit cần ghi = `MAGIC(4 byte "IMGS") + LENGTH(uint32 big-endian) + PAYLOAD(JSON utf-8) + CRC32(uint32 của PAYLOAD)`.
- Ghi từng bit vào bit thấp nhất của các giá trị kênh, theo thứ tự phẳng (row-major, R,G,B lần lượt).
- Dung lượng = `width * height * 3` bit. Nếu chuỗi bit dài hơn dung lượng: `ValueError("Anh qua nho de giau thong tin")`.
- Lưu **PNG** (lossless). Không lưu JPG.
- `extract`: đọc 8 byte đầu, kiểm MAGIC, đọc LENGTH (giới hạn hợp lý, tối đa 4096 byte), đọc payload, kiểm CRC. Sai bước nào trả `None`.
- Payload: `{"asset_id": "...", "owner": "...", "date": "YYYY-MM-DD"}`.

### 4.4 assets.json
```json
[
  {"asset_id":"IMG-0001","name":"Bang tot nghiep A","type":"van bang","importance":3,
   "sha256_original":"...","created_at":"..."}
]
```
`importance`: 1 thấp, 2 trung bình, 3 cao.

### 4.5 verify.log (mỗi lần xác minh một dòng)
```
2026-11-08 10:05:12 | IMG-0001.png | HOP_LE | chu ky dung; LSB khop
2026-11-08 10:07:40 | IMG-0001_fake.png | KHONG_HOP_LE | sha256 khong khop
```

### 4.6 ntfy
`POST {NTFY_URL}/{NTFY_TOPIC}`, body là thông điệp tiếng Việt không dấu hoặc UTF-8, header `Title`, `Priority: high`, `Tags: warning`. Timeout 5 giây, bắt mọi lỗi.
Chỉ gửi khi verdict = `KHONG_HOP_LE`.

## 5. CLI (`cli.py`)

```
python cli.py keygen [--force]
python cli.py sign <anh.png> [--id IMG-xxxx]            # ký thô (M1)
python cli.py verify-sig <anh.png> [--sig file.json]    # chỉ chữ ký (M1)
python cli.py watermark <anh.png> <out.png> [--text ...]# M3
python cli.py lsb-embed <anh.png> <out.png> --msg ...   # M4
python cli.py lsb-read <anh.png>                        # M4
python cli.py protect <anh.png> --name ... --type ... --importance 1|2|3   # M5/M6
python cli.py verify <anh.png> [--sig file.json]        # verify_full (M5)
python cli.py assets                                    # liệt kê tài sản (M6)
python cli.py recover <asset_id> <out.png>              # M6
python cli.py tamper <anh.png> <out.png> --mode text|crop|pixel   # tạo ảnh giả để demo (M2)
```
Mỗi lệnh in kết quả có dòng thời gian đầu tiên.

## 6. Web (Flask) — routes

| Route | Method | Việc |
|-------|--------|------|
| `/` | GET | Trang chủ: tóm tắt, số tài sản, 5 sự kiện log gần nhất |
| `/protect` | GET/POST | Upload PNG + tên + loại + mức quan trọng -> chạy `protect` -> hiện kết quả, link tải ảnh đã ký và sidecar |
| `/verify` | GET/POST | Upload PNG (+ sidecar tùy chọn) -> `verify_full` -> hiện kết luận màu xanh/đỏ/vàng |
| `/assets` | GET | Bảng tài sản |
| `/logs` | GET | 50 dòng log mới nhất |
| `/download/<asset_id>/<kind>` | GET | `kind` chỉ nhận `png` hoặc `sig`; kiểm `asset_id` khớp regex `^IMG-\d{4}$` |

Giao diện: HTML thuần + một file CSS nhỏ, nền sáng, kết luận HỢP LỆ màu xanh, KHÔNG HỢP LỆ màu đỏ, cảnh báo màu vàng. Không dùng framework JS.
Trên trang `/verify` nếu người dùng tải ảnh lên không kèm sidecar, tự tìm sidecar theo `asset_id` đọc từ LSB trong `data/signed/`; nếu không có thì kết luận `KHONG_XAC_MINH_DUOC`.

## 7. Phụ thuộc (`requirements.txt`)
```
pillow
numpy
cryptography
flask
requests
pytest
```
