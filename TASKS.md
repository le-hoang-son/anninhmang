# TASKS.md — Các milestone (làm lần lượt, mỗi lần MỘT mốc)

Quy tắc: làm xong mốc -> chạy lệnh nghiệm thu -> in kết quả -> đánh `[x]` -> DỪNG chờ người dùng xác nhận.
Ảnh mẫu của người dùng: `samples/goc.png` (PNG, nên rộng từ 600 px trở lên). Nếu chưa có, hãy dừng và nhắc người dùng đặt vào, không tự tải ảnh lạ.

---

## [x] M0 — Khởi tạo dự án
**Làm:**
- Tạo cấu trúc thư mục theo `ARCHITECTURE.md` (file rỗng hoặc khung tối thiểu).
- `requirements.txt`, `.gitignore` (keys/, data/, __pycache__/, .env, *.pyc), `config.py`.
- Tạo venv và cài thư viện (hướng dẫn lệnh cho Windows PowerShell).

**Nghiệm thu:**
```
python -c "import PIL, numpy, cryptography, flask, requests; print('OK')"
python cli.py --help
```
Mong đợi: in `OK` và hiện danh sách lệnh con.

---

## [x] M1 — Tạo khóa, ký, xác minh chữ ký (FR-1, FR-2, FR-3)
**Làm:** `keys.py`, `signer.py`, lệnh `keygen`, `sign`, `verify-sig`. Dùng RSA-PSS theo `ARCHITECTURE.md` mục 4.1 và sidecar mục 4.2.
Có `tests/test_signer.py`: ký rồi verify đúng; sửa 1 byte thì sai; sidecar thiếu thì báo đúng lý do.

**Nghiệm thu:**
```
python cli.py keygen
python cli.py sign samples/goc.png --id IMG-0001
python cli.py verify-sig samples/goc.png --sig samples/goc.png.sig.json
pytest tests/test_signer.py -q
```
Mong đợi: tạo `keys/private.pem`, `keys/public.pem`, sidecar JSON; lệnh verify in `HỢP LỆ`; pytest xanh.
Chạy `keygen` lần 2 không `--force` phải báo "khóa đã tồn tại" và không ghi đè.

---

## [ ] M2 — Tạo ảnh giả và phát hiện (FR-3 mở rộng)
**Làm:** lệnh `tamper` với 3 chế độ:
- `text`: vẽ thêm một dòng chữ đè lên ảnh (giả lập sửa tên)
- `crop`: cắt bỏ 5% mép dưới
- `pixel`: đổi đúng 1 điểm ảnh
Lưu kết quả bằng PNG.

**Nghiệm thu:**
```
python cli.py tamper samples/goc.png samples/fake_text.png --mode text
python cli.py tamper samples/goc.png samples/fake_pixel.png --mode pixel
python cli.py verify-sig samples/fake_text.png --sig samples/goc.png.sig.json
python cli.py verify-sig samples/fake_pixel.png --sig samples/goc.png.sig.json
```
Mong đợi: cả hai báo `KHÔNG HỢP LỆ` với lý do "sha256 không khớp". Đây là ảnh minh chứng quan trọng: đổi **một** điểm ảnh vẫn bị phát hiện.

---

## [ ] M3 — Watermark hiện (FR-4)
**Làm:** `watermark.py`. Chữ mờ gồm `OWNER_NAME` và ngày, lặp chéo toàn ảnh với độ trong suốt thấp, vẫn đọc được. Dùng font mặc định của Pillow hoặc font hệ thống có sẵn, có xử lý khi không tìm thấy font. Ảnh có alpha vẫn chạy được.

**Nghiệm thu:**
```
python cli.py watermark samples/goc.png samples/wm.png --text "Truong Demo 2026"
```
Mong đợi: tạo `samples/wm.png`, mở ra thấy chữ mờ, ảnh gốc không bị ghi đè.

---

## [ ] M4 — Watermark ẩn LSB (FR-5)
**Làm:** `lsb.py` đúng định dạng `ARCHITECTURE.md` mục 4.3. Test: embed rồi extract ra đúng payload; ảnh chưa embed trả `None`; ảnh quá nhỏ báo lỗi; sửa ngẫu nhiên vài điểm ảnh vùng chứa dữ liệu thì CRC sai trả `None`.

**Nghiệm thu:**
```
python cli.py lsb-embed samples/wm.png samples/hidden.png --msg "IMG-0001|Truong Demo"
python cli.py lsb-read samples/hidden.png
python cli.py lsb-read samples/goc.png
pytest tests/test_lsb.py -q
```
Mong đợi: lệnh đọc thứ nhất in đúng chuỗi; lệnh đọc thứ hai in "không tìm thấy watermark ẩn"; hai ảnh nhìn bằng mắt giống nhau. In thêm số điểm ảnh khác nhau và độ lệch tối đa của mỗi kênh (phải là 1) để chụp minh chứng "mắt thường không thấy".

---

## [ ] M5 — Quy trình bảo vệ + xác minh đầy đủ (FR-6, FR-7)
**Làm:** `pipeline.py` với `protect()` (phiên bản chưa có asset/log/ntfy, các phần đó để M6) và `verify_full()` theo bảng logic `SPEC.md` mục 7. Thứ tự quy trình theo `AGENTS.md` mục 6, KHÔNG đổi.
`tests/test_pipeline.py`: protect rồi verify = HOP_LE; sửa pixel rồi verify = KHONG_HOP_LE; xóa sidecar = KHONG_XAC_MINH_DUOC.

**Nghiệm thu:**
```
python cli.py protect samples/goc.png --name "Bang tot nghiep A" --type "van bang" --importance 3
python cli.py verify data/signed/IMG-0001.png
python cli.py tamper data/signed/IMG-0001.png samples/fake.png --mode text
python cli.py verify samples/fake.png --sig data/signed/IMG-0001.png.sig.json
pytest -q
```
Mong đợi: lần verify đầu `HỢP LỆ`, lần sau `KHÔNG HỢP LỆ` và vẫn đọc được watermark ẩn nếu vùng LSB chưa bị phá. pytest xanh toàn bộ.

---

## [ ] M6 — Lớp NIST: tài sản, log, ntfy, lưu gốc, khôi phục (FR-8, FR-9, FR-10)
**Làm:** `assets.py`, `logger.py`, `notifier.py`, `recover.py`, nối vào `protect()` và `verify_full()`. Thêm lệnh `assets`, `recover`.
- `protect` đăng ký tài sản, lưu bản gốc vào `data/originals/`, ghi log "BAO_VE".
- Mỗi lần `verify` ghi một dòng `verify.log`.
- `KHONG_HOP_LE` thì gọi `send_alert`. Tắt mạng hoặc sai topic: chương trình vẫn chạy bình thường.
- `recover` chép bản đã ký về đích và chạy `verify_file`, in kết quả.

**Nghiệm thu:**
```
set IMGSIGN_NTFY_TOPIC=<topic-cua-ban>        (PowerShell: $env:IMGSIGN_NTFY_TOPIC="...")
python cli.py protect samples/goc.png --name "Bang tot nghiep A" --type "van bang" --importance 3
python cli.py assets
python cli.py verify samples/fake.png --sig data/signed/IMG-0002.png.sig.json
type data\logs\verify.log
python cli.py recover IMG-0002 samples/recovered.png
```
Mong đợi: bảng tài sản có dòng mới; log có dòng `KHONG_HOP_LE`; điện thoại nhận thông báo ntfy; `recover` in `HỢP LỆ`. Thử với topic rỗng: không lỗi.

---

## [ ] M7 — Giao diện web Flask (FR-11)
**Làm:** `web/app.py` và templates theo `ARCHITECTURE.md` mục 6, áp dụng đủ các quy tắc an toàn ở `AGENTS.md` mục 5. Dùng lại hàm trong `pipeline.py`, không viết lại logic.

**Nghiệm thu:**
```
python web/app.py
```
Mở `http://127.0.0.1:5000` rồi thử bằng tay:
1. `/protect`: upload `goc.png`, thấy kết quả và link tải ảnh đã ký + sidecar.
2. `/verify`: upload ảnh đã ký -> màu xanh HỢP LỆ.
3. `/verify`: upload `fake.png` -> màu đỏ KHÔNG HỢP LỆ.
4. Upload file `.jpg` hoặc `.txt` đổi đuôi thành `.png` -> bị từ chối thông báo rõ.
5. Thử `/download/..%2f..%2fkeys%2fprivate.pem/png` và `/download/IMG-0001/xyz` -> phải 404 hoặc 400, tuyệt đối không lộ file.
6. `/assets` và `/logs` hiển thị đúng.

---

## [ ] M8 — Kịch bản demo và tài liệu minh chứng
**Làm:**
- `demo.py`: chạy tự động toàn bộ kịch bản `TEST_PLAN.md` (protect, verify hợp lệ, tamper 3 kiểu, verify, recover), in từng bước có dòng thời gian và tiêu đề rõ để chụp ảnh.
- `README.md`: cách cài, chạy CLI, chạy web, cấu hình ntfy, cấu trúc thư mục, giới hạn trung thực (lấy từ `SPEC.md` mục 6).
- Tạo `EVIDENCE_CHECKLIST.md` từ danh sách ảnh trong `TEST_PLAN.md` mục 3 (tích khi chụp xong).

**Nghiệm thu:**
```
python demo.py
pytest -q
```
Mong đợi: demo chạy trơn từ đầu đến cuối, không lỗi, kết quả đúng với `TEST_PLAN.md`.
