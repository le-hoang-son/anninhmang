# ImgSign — Chống giả mạo và làm giả hình ảnh bằng watermark và chữ ký số

Đồ án môn **An ninh mạng**. Hệ thống giúp chứng minh một **ảnh hoặc tài liệu** (`.png`, `.docx`, `.pdf`) là **nguyên bản, chưa bị sửa**, và **phát hiện file bị làm giả**. Ánh xạ theo **NIST CSF 1.1** (Identify, Protect, Detect, Respond, Recover).

Ý tưởng: một đơn vị (ví dụ trường học) phát hành ảnh bằng tốt nghiệp hoặc hợp đồng. Hệ thống dán watermark hiện, giấu watermark ẩn (LSB ở PNG, metadata ở DOCX), rồi **ký số** file cuối cùng. Nếu ai sửa file (đổi tên, cắt mép, đổi 1 điểm ảnh, sửa 1 byte tài liệu), hệ thống báo **KHÔNG HỢP LỆ** và gửi cảnh báo. PDF chỉ được ký để bảo vệ toàn vẹn (không watermark).

---

## 1. Yêu cầu môi trường

- **Python 3.10+** (đã chạy thử với Python 3.13).
- Windows hoặc Ubuntu. Trên Windows dùng **PowerShell**.
- Không cần Internet, trừ khi muốn nhận cảnh báo ntfy.

Cài đặt (Windows PowerShell):

```powershell
cd d:\doananninhmang
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Kiểm tra nhanh:

```powershell
.\.venv\Scripts\python.exe -c "import PIL, numpy, cryptography, flask, requests; print('OK')"
```

---

## 2. Chạy dòng lệnh (CLI)

Đặt ảnh PNG mẫu vào `samples/goc.png` trước.

```powershell
# M1 - Tạo khóa RSA-2048 (không ghi đè nếu đã có; thêm --force để tạo lại)
.\.venv\Scripts\python.exe cli.py keygen

# M1 - Ký thô một file PNG và xác minh chữ ký
.\.venv\Scripts\python.exe cli.py sign samples/goc.png --id IMG-0001
.\.venv\Scripts\python.exe cli.py verify-sig samples/goc.png --sig samples/goc.png.sig.json

# M2 - Tạo ảnh giả để demo (text | crop | pixel)
.\.venv\Scripts\python.exe cli.py tamper samples/goc.png samples/fake.png --mode text

# M3 - Watermark hiện
.\.venv\Scripts\python.exe cli.py watermark samples/goc.png samples/wm.png --text "Truong Demo 2026"

# M4 - Watermark ẩn LSB
.\.venv\Scripts\python.exe cli.py lsb-embed samples/wm.png samples/hidden.png --msg "IMG-0001|Truong Demo"
.\.venv\Scripts\python.exe cli.py lsb-read samples/hidden.png

# M5/M6 - Quy trình bảo vệ đầy đủ + xác minh + tài sản + khôi phục
.\.venv\Scripts\python.exe cli.py protect samples/goc.png --name "Bang tot nghiep A" --type "van bang" --importance 3
# Bỏ watermark hiện (chỉ giữ watermark ẩn LSB + chữ ký), áp dụng cho PNG:
.\.venv\Scripts\python.exe cli.py protect samples/goc.png --name "Bang tot nghiep A" --type "van bang" --importance 3 --no-visible-watermark
.\.venv\Scripts\python.exe cli.py verify data/signed/IMG-0001.png
.\.venv\Scripts\python.exe cli.py assets
.\.venv\Scripts\python.exe cli.py recover IMG-0001 samples/recovered.png

# M9 - Bảo vệ tài liệu DOCX (watermark ẩn metadata) và PDF (chỉ ký)
.\.venv\Scripts\python.exe cli.py protect samples/goc.docx --name "Hop dong A" --type "hop dong" --importance 3
.\.venv\Scripts\python.exe cli.py docx-read data/signed/IMG-0002.docx
.\.venv\Scripts\python.exe cli.py verify data/signed/IMG-0002.docx
.\.venv\Scripts\python.exe cli.py protect samples/goc.pdf --name "Bao cao B" --type "bao cao" --importance 2
.\.venv\Scripts\python.exe cli.py verify data/signed/IMG-0003.pdf --sig data/signed/IMG-0003.pdf.sig.json

# M8 - Kịch bản demo tự động (T1, T2, T3, T4, T11)
.\.venv\Scripts\python.exe demo.py
```

Chạy kiểm thử tự động:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

---

## 3. Chạy giao diện web (Flask)

```powershell
.\.venv\Scripts\python.exe web/app.py
```

Mở trình duyệt: <http://127.0.0.1:5000>

Các trang:

| Trang | Việc |
|-------|------|
| `/` | Bảng điều khiển: thẻ số liệu (tài sản, lần xác minh, hợp lệ, không hợp lệ), biểu đồ cột CSS, 5 sự kiện gần nhất có màu |
| `/protect` | Upload file (PNG/DOCX/PDF) + tên + loại + mức quan trọng → bảo vệ file, tải file đã ký và sidecar |
| `/verify` | Upload file (PNG/DOCX/PDF) (kèm sidecar tùy chọn) → kết luận HỢP LỆ / KHÔNG HỢP LỆ / cảnh báo |
| `/verify-batch` | Xác minh lô: chọn tối đa 10 ảnh PNG, mỗi ảnh tự tìm sidecar theo LSB; bảng kết quả; ntfy tối đa 1 thông báo tóm tắt |
| `/compare` | So sánh ảnh nghi giả với bản đã ký: vẽ khung đỏ vùng khác biệt, hiện 3 ảnh + số điểm ảnh khác, tỷ lệ % |
| `/assets` | Bảng tài sản; bấm vào `asset_id` để xem chi tiết |
| `/assets/<id>` | Chi tiết tài sản: ảnh đã ký, lịch sử xác minh riêng, nút tải ảnh/sidecar, nút Khôi phục |
| `/nist` | Bảng 5 ô NIST CSF 1.1 kèm số liệu thật tính từ `data/` và `verify.log` |
| `/keys` | Khóa công khai: vân tay, ngày tạo, tải `public.pem` (không bao giờ trả khóa riêng) |
| `/logs` | Nhật ký: lọc theo kết luận, tìm theo tên ảnh, phân trang 50 dòng, nút Xuất CSV |
| `/alert-test` | Trạng thái ntfy (chỉ 3 ký tự đầu tên kênh) + nút gửi thử cảnh báo |
| `/demo-tamper` | **Chỉ dùng cho demo**: tạo ảnh giả trong `data/tampered/` để đưa sang `/verify` |

Lưu ý bảo mật (đã áp dụng): giới hạn upload 10 MB, tên file lưu bằng `uuid4`, chỉ nhận PNG/DOCX/PDF (PNG kiểm bằng Pillow; DOCX kiểm cấu trúc ZIP OOXML; PDF kiểm header `%PDF-`), không cho nhập đường dẫn tùy ý, `debug=False`, khóa phiên đọc từ biến môi trường (không hardcode), giới hạn tần suất POST 20 lần/phút mỗi IP (vượt quá trả 429), chống CSV injection khi xuất log.

---

## 4. Cấu hình cảnh báo ntfy (tùy chọn)

ntfy gửi thông báo khi phát hiện ảnh **KHÔNG HỢP LỆ** (Respond - RS.AN/RS.CO).

```powershell
# PowerShell: đặt topic (chọn tên khó đoán, ví dụ imgsign-<tên bạn>)
$env:IMGSIGN_NTFY_TOPIC = "imgsign-truong-demo-123"

# Xem thông báo: mở https://ntfy.sh/imgsign-truong-demo-123 trên điện thoại/trình duyệt
```

Biến môi trường khác:

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `IMGSIGN_NTFY_TOPIC` | rỗng (tắt cảnh báo) | Kênh ntfy nhận cảnh báo |
| `IMGSIGN_KEY_PASSWORD` | rỗng (không mã hóa) | Mật khẩu bảo vệ khóa riêng |
| `IMGSIGN_SECRET_KEY` | sinh ngẫu nhiên mỗi lần khởi động | Khóa phiên Flask (nên đặt cố định khi chạy thật) |

Nếu để topic rỗng hoặc lỗi mạng: chương trình **vẫn chạy bình thường**, chỉ ghi log "gửi cảnh báo thất bại".

---

## 5. Cấu trúc thư mục

```text
doananninhmang/
├─ AGENTS.md  SPEC.md  ARCHITECTURE.md  TASKS.md  NIST_MAPPING.md  TEST_PLAN.md
├─ README.md  EVIDENCE_CHECKLIST.md
├─ requirements.txt  .gitignore
├─ config.py                 # cấu hình đường dẫn, tên đơn vị, ntfy topic
├─ cli.py                    # điểm vào dòng lệnh
├─ demo.py                   # kịch bản demo tự động
├─ imgsign/
│  ├─ keys.py                # tạo/nạp khóa RSA
│  ├─ signer.py              # ký + xác minh chữ ký, đọc/ghi sidecar
│  ├─ watermark.py           # watermark hiện (Pillow)
│  ├─ lsb.py                 # watermark ẩn LSB (numpy)
│  ├─ tamper.py              # tạo ảnh giả cho demo (text/crop/pixel)
│  ├─ pipeline.py            # protect() và verify_full()
│  ├─ docfile.py             # watermark ẩn DOCX + xử lý tài liệu docx/pdf
│  ├─ compare.py             # so sánh ảnh bằng ImageChops.difference (web /compare)
│  ├─ assets.py              # bảng tài sản (data/assets.json)
│  ├─ logger.py              # ghi data/logs/verify.log
│  ├─ notifier.py            # gửi ntfy
│  └─ recover.py             # khôi phục bản đã ký
├─ web/
│  ├─ app.py                 # Flask
│  ├─ templates/             # base, index, protect, verify, verify_batch, compare, assets,
│  │                         #   asset_detail, nist, keys, logs, alert_test, demo_tamper, 404, 429
│  └─ static/style.css
├─ tests/                    # test_signer.py, test_lsb.py, test_pipeline.py, test_docfile.py, test_web.py
├─ samples/                  # file mẫu (goc.png, goc.docx, goc.pdf)
├─ keys/                     # private.pem, public.pem  (KHÔNG commit)
└─ data/                     # KHÔNG commit
   ├─ originals/             # <asset_id>.<ext>  bản gốc trước khi bảo vệ
   ├─ signed/                # <asset_id>.png|.docx|.pdf + <asset_id>.<ext>.sig.json
   ├─ tampered/              # ảnh giả tạo từ trang /demo-tamper
   ├─ compare/               # ảnh nghi giả + ảnh đánh dấu vùng khác biệt (trang /compare)
   ├─ recovered/             # bản khôi phục từ trang chi tiết tài sản
   ├─ logs/verify.log
   └─ assets.json
```

**Quy trình bảo vệ (thứ tự bất biến - KÝ luôn là bước cuối):**

```text
ảnh gốc (PNG) → (1) watermark hiện → (2) watermark ẩn LSB → (3) lưu PNG → (4) KÝ file PNG cuối cùng
DOCX          → (1) watermark ẩn metadata → (2) lưu DOCX          → (3) KÝ file DOCX cuối cùng
PDF           → (1) lưu PDF                                       → (2) KÝ file PDF cuối cùng (không watermark)
```

Chữ ký luôn là bước cuối vì nó phủ lên **từng byte** của file cuối cùng.

---

## 6. Giới hạn trung thực (phải ghi vào báo cáo)

- **Chữ ký số là bằng chứng chính** về toàn vẹn: đổi 1 byte là chữ ký hỏng.
- **Watermark ẩn LSB rất mong manh**: lưu lại JPG, đổi kích thước, chụp màn hình đều có thể làm mất. Vai trò của nó là **chứng cứ nguồn gốc bổ sung**, không thay thế chữ ký.
- Ảnh bị sửa nhẹ vùng nhỏ có thể vẫn còn watermark ẩn đọc được nhưng chữ ký vẫn báo **KHÔNG HỢP LỆ**. Đây là hành vi đúng, hệ thống kết luận theo chữ ký.
- Chữ ký chứng minh "file này do người giữ khóa riêng phát hành, chưa bị đổi", **không** chứng minh nội dung ảnh là sự thật.
- Hệ thống **không** chống được nén JPG, cắt xén, phóng to thu nhỏ ở mức watermark ẩn (ngoài phạm vi đồ án).
- **Tài liệu DOCX/PDF**: chữ ký phủ lên toàn bộ byte file. Với DOCX, mở rồi lưu lại bằng Word (dù không sửa nội dung) cũng làm đổi byte file ZIP nên báo **KHÔNG HỢP LỆ** — đúng với mục tiêu "toàn vẹn byte". PDF chỉ được ký, không có watermark ẩn.

---

## 7. Ánh xạ NIST CSF 1.1 (tóm tắt)

| Chức năng | NIST | Module |
|-----------|------|--------|
| Bảng tài sản ảnh | IDENTIFY (ID.AM) | `assets.py`, `cli.py assets`, `/assets` |
| Watermark + ký số | PROTECT (PR.DS) | `watermark.py`, `lsb.py`, `docfile.py`, `signer.py`, `pipeline.py` |
| Phát hiện sửa đổi | DETECT (DE.CM) | `pipeline.verify_full()`, `/verify` |
| Ghi log + cảnh báo | RESPOND (RS.AN, RS.CO) | `logger.py`, `notifier.py` |
| Khôi phục bản gốc | RECOVER (RC.RP) | `recover.py`, `cli.py recover` |

Chi tiết đầy đủ xem `NIST_MAPPING.md`.
