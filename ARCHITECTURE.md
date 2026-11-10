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
│  ├─ docfile.py              # watermark ẩn DOCX + ký tài liệu (docx/pdf)
│  ├─ assets.py               # bảng tài sản ảnh (assets.json)
│  ├─ logger.py               # ghi verify.log
│  ├─ notifier.py             # gửi ntfy
│  └─ recover.py              # lưu gốc + khôi phục
├─ web/
│  ├─ app.py                  # Flask
│  └─ templates/              # base.html index.html protect.html verify.html assets.html logs.html
├─ tests/
│  ├─ test_signer.py  test_lsb.py  test_pipeline.py  test_docfile.py
├─ samples/                   # ảnh PNG mẫu của người dùng (goc.png)
├─ keys/                      # private.pem public.pem  (KHÔNG commit)
└─ data/                      # KHÔNG commit
   ├─ originals/              # <asset_id>.<ext>  bản gốc trước khi bảo vệ
   ├─ signed/                 # <asset_id>.png|.docx|.pdf + <asset_id>.<ext>.sig.json
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
| `SECRET_KEY` | đọc env `IMGSIGN_SECRET_KEY`, không có thì `secrets.token_hex(32)` mỗi lần khởi động | Khóa phiên Flask (không hardcode) |
| `RATE_LIMIT_MAX` | `20` | Số lần POST tối đa mỗi IP trong một cửa sổ |
| `RATE_LIMIT_WINDOW` | `60.0` | Độ dài cửa sổ giới hạn tần suất (giây) |
| `BATCH_MAX` | `10` | Số ảnh tối đa cho một lần xác minh theo lô (`/verify-batch`) |

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
def protect(src: Path, asset_name: str, asset_type: str, importance: int,
            visible_watermark: bool = True) -> ProtectResult
# Thứ tự theo loại file (KÝ luôn là bước cuối):
#   PNG : lưu gốc -> đăng ký asset -> (watermark hiện nếu visible_watermark=True) -> LSB -> lưu <id>.png -> ký -> log
#   DOCX: lưu gốc -> đăng ký asset -> watermark ẩn (metadata) -> lưu <id>.docx -> ký -> log
#   PDF : lưu gốc -> đăng ký asset -> lưu <id>.pdf -> ký -> log
# visible_watermark: chỉ có ý nghĩa với PNG. False = bỏ watermark hiện, vẫn giữ LSB + ký.
def verify_full(png_path: Path, sidecar_path: Path | None) -> FullReport
# ProtectResult: dataclass(asset_id, signed_path, sidecar_path, original_path, sha256_signed,
#                        kind: str = "png", visible_watermark: bool = True)
# FullReport: dataclass(verdict: str, sig: VerifyResult, lsb_payload: dict | None, notes: list[str])
# verdict ∈ {"HOP_LE", "HOP_LE_CANH_BAO", "KHONG_HOP_LE", "KHONG_XAC_MINH_DUOC"}

# docfile.py (FR-21, FR-22) - chỉ dùng thư viện chuẩn
def detect_kind(path: Path) -> str                        # 'png' | 'docx' | 'pdf'; raise ValueError nếu khác
def validate_docx(path: Path) -> None                     # raise ValueError nếu không phải ZIP OOXML
def validate_pdf(path: Path) -> None                      # raise ValueError nếu thiếu header %PDF-
def embed_docx_metadata(src: Path, dst: Path, payload: dict) -> Path  # ghi watermark ẩn vào docProps/core.xml
def extract_docx_metadata(path: Path) -> dict | None      # None nếu không có/sai định dạng
def find_signed(signed_dir: Path, asset_id: str) -> Path | None       # tìm <id>.png|.docx|.pdf

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

### 4.7 Watermark ẩn trong DOCX (FR-21)
- DOCX là file ZIP (OOXML). Chỉ sửa part `docProps/core.xml`, các part khác giữ nguyên byte.
- Token giấu trong thẻ `<cp:keywords>`: `IMGSIGN-B64:<base64(JSON)>` với `JSON = {"asset_id","owner","date"}`.
- Khi chèn: giữ lại các keyword cũ của người dùng, chỉ nối thêm token; nếu chưa có thẻ `<cp:keywords>` thì tạo mới trước `</cp:coreProperties>`.
- `extract`: tìm token bằng regex `IMGSIGN-B64:([A-Za-z0-9+/]+={0,2})`, base64-decode, parse JSON; sai bước nào trả `None`.
- PDF không có watermark: chỉ ký toàn vẹn byte.

### 4.8 Tài liệu đã ký trong `data/signed/`
- `<asset_id>.png` (ảnh), `<asset_id>.docx` (tài liệu Word), `<asset_id>.pdf` (PDF).
- Sidecar luôn là `<asset_id>.<ext>.sig.json` (ví dụ `IMG-0001.docx.sig.json`).
- `docfile.find_signed` dò theo thứ tự `.png` -> `.docx` -> `.pdf` để hỗ trợ `/download`, khôi phục và chi tiết tài sản.

## 5. CLI (`cli.py`)

```
python cli.py keygen [--force]
python cli.py sign <anh.png> [--id IMG-xxxx]            # ký thô (M1)
python cli.py verify-sig <anh.png> [--sig file.json]    # chỉ chữ ký (M1)
python cli.py watermark <anh.png> <out.png> [--text ...]# M3
python cli.py lsb-embed <anh.png> <out.png> --msg ...   # M4
python cli.py lsb-read <anh.png>                        # M4
python cli.py protect <file> --name ... --type ... --importance 1|2|3   # M5/M6/M9 (file: .png/.docx/.pdf)
python cli.py verify <file> [--sig file.json]           # verify_full (M5/M9)
python cli.py assets                                    # liệt kê tài sản (M6)
python cli.py recover <asset_id> <out>                  # M6 (out có đuôi theo tài sản)
python cli.py docx-read <file.docx>                     # đọc watermark ẩn metadata DOCX (M9)
python cli.py tamper <anh.png> <out.png> --mode text|crop|pixel   # tạo ảnh giả để demo (M2)
```
Mỗi lệnh in kết quả có dòng thời gian đầu tiên.

## 6. Web (Flask) — routes

| Route | Method | Việc |
|-------|--------|------|
| `/` | GET | (FR-15) Bảng điều khiển: thẻ số liệu (tài sản, lần xác minh, hợp lệ, không hợp lệ), biểu đồ cột CSS, 5 sự kiện gần nhất có màu |
| `/protect` | GET/POST | Upload file (PNG/DOCX/PDF) + tên + loại + mức quan trọng -> chạy `protect` -> hiện kết quả, link tải file đã ký và sidecar |
| `/verify` | GET/POST | Upload file (PNG/DOCX/PDF) (+ sidecar tùy chọn) -> `verify_full` -> hiện kết luận màu xanh/đỏ/vàng |
| `/assets` | GET | Bảng tài sản |
| `/logs` | GET | (FR-18) Lọc theo kết luận (`verdict`), tìm theo tên ảnh (`q`), phân trang 50 dòng (`page`) |
| `/download/<asset_id>/<kind>` | GET | `kind` nhận `png`, `doc` hoặc `sig`; `doc` trả file `.docx`/`.pdf` với MIME tương ứng; kiểm `asset_id` khớp regex `^IMG-\d{4}$` |
| `/compare` | GET/POST | (FR-12) Chọn asset + upload ảnh nghi giả; so bằng `ImageChops.difference`; hiện 3 ảnh, số điểm ảnh khác, tỷ lệ % |
| `/nist` | GET | (FR-13) Bảng 5 ô NIST kèm số liệu thật tính từ `assets.json`, `data/signed`, `verify.log` |
| `/assets/<asset_id>` | GET/POST | (FR-14) Chi tiết tài sản, lịch sử xác minh riêng; POST = khôi phục |
| `/verify-batch` | GET/POST | (FR-16) Xác minh tối đa 10 ảnh cùng lúc; ntfy tối đa 1 thông báo tóm tắt |
| `/keys` | GET | (FR-17) Fingerprint, ngày tạo khóa công khai, tải `public.pem` |
| `/keys/public.pem` | GET | (FR-17) Chỉ phục vụ `public.pem`; không bao giờ trả khóa riêng |
| `/logs/export.csv` | GET | (FR-18) Xuất log theo bộ lọc hiện tại, chống CSV injection |
| `/alert-test` | GET/POST | (FR-19) Trạng thái ntfy (ẩn topic) + gửi thử cảnh báo |

Giới hạn tần suất: mọi request **POST** bị đếm theo IP; vượt `RATE_LIMIT_MAX` trong `RATE_LIMIT_WINDOW` giây trả **429** kèm thông báo tiếng Việt. Ghi thêm sự kiện `RECOVER` và `ALERT` vào `verify.log` theo định dạng cũ (mục 4.5) để đếm số liệu cho `/nist`.

Giao diện: HTML thuần + một file CSS nhỏ, nền sáng, kết luận HỢP LỆ màu xanh, KHÔNG HỢP LỆ màu đỏ, cảnh báo màu vàng. Không dùng framework JS. Biểu đồ vẽ bằng HTML/CSS thuần.
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
