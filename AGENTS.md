# AGENTS.md — Luật làm việc cho agent

Dự án: **ImgSign** — Xây dựng hệ thống chống giả mạo và làm giả hình ảnh bằng watermark và chữ ký số theo tiêu chuẩn NIST CSF 1.1.
Đây là đồ án môn An ninh mạng của sinh viên. Mục tiêu: chạy được thật, dễ demo, dễ chụp ảnh cho báo cáo. Không cần hoàn hảo, cần ĐƠN GIẢN và ĐÚNG.

## 1. Đọc theo thứ tự trước khi code
1. `SPEC.md` — hệ thống làm gì
2. `ARCHITECTURE.md` — cấu trúc thư mục, hàm, định dạng dữ liệu (đây là hợp đồng, không tự ý đổi)
3. `TASKS.md` — danh sách mốc (milestone) làm lần lượt
4. `NIST_MAPPING.md` — ánh xạ NIST CSF
5. `TEST_PLAN.md` — kịch bản kiểm thử và ảnh minh chứng

## 2. Quy tắc làm việc (bắt buộc)
- Làm **MỘT milestone mỗi lần**. Xong thì chạy lệnh nghiệm thu ghi trong `TASKS.md`, in kết quả ra, rồi **DỪNG** và chờ người dùng xác nhận. Không tự làm trước milestone sau.
- Trước khi sửa file đã có, đọc lại file đó. Sửa nhỏ, không viết lại cả file nếu không cần.
- Gặp lỗi: nêu nguyên nhân bằng 1 đến 2 câu, sửa tối thiểu, chạy lại. Không đoán mò hàng loạt.
- Không thêm thư viện ngoài danh sách ở mục 3. Cần thêm thì hỏi trước.
- Không làm thêm tính năng ngoài `SPEC.md` (mục "Ngoài phạm vi"). Gặp ý hay thì ghi vào `IDEAS.md`, không code.

## 3. Công nghệ
- Python 3.10+, chạy được trên **Windows** (dùng `pathlib`, không dùng lệnh chỉ có trên bash).
- Thư viện cho phép: `pillow`, `numpy`, `cryptography`, `flask`, `requests`, `pytest`.
- Không dùng: Docker, database server, framework JS, AI/ML.
- Lưu trữ: file JSON và thư mục thường. Không SQLite trừ khi người dùng yêu cầu.

## 4. Quy ước code
- Tên hàm, biến, file: tiếng Anh. Chú thích ngắn: tiếng Việt. Thông báo cho người dùng (CLI, web): tiếng Việt có dấu.
- Có type hints. Hàm ngắn (dưới 40 dòng). Mỗi module một trách nhiệm theo `ARCHITECTURE.md`.
- Lỗi người dùng (file sai định dạng, thiếu khóa...) phải ra thông báo rõ ràng, không in traceback.
- Mọi lệnh CLI in kết quả có **dòng thời gian** `YYYY-MM-DD HH:MM:SS` để người dùng chụp ảnh làm minh chứng.
- Windows console: đặt `sys.stdout.reconfigure(encoding="utf-8")` ở đầu `cli.py` để không lỗi tiếng Việt.

## 5. Quy tắc an toàn (đề tài về bảo mật nên phải làm đúng)
- **Không bao giờ** commit hoặc in ra khóa riêng. `keys/` và `data/` phải nằm trong `.gitignore`.
- Khóa riêng lưu `keys/private.pem`. Cho phép đặt mật khẩu bảo vệ qua biến môi trường `IMGSIGN_KEY_PASSWORD` (tùy chọn).
- Flask:
  - `MAX_CONTENT_LENGTH` = 10 MB
  - Dùng `secure_filename`, lưu file với tên `uuid4`, không dùng tên gốc làm đường dẫn
  - Kiểm tra file là PNG hợp lệ bằng Pillow (không chỉ nhìn đuôi)
  - `debug=False` mặc định
  - Không để route nào nhận đường dẫn tùy ý từ người dùng (chống path traversal)
- Chấp nhận **PNG, DOCX, PDF**. PNG: watermark hiện + watermark ẩn LSB. DOCX: giữ nguyên nội dung, giấu watermark ẩn trong metadata (`docProps/core.xml`). PDF: chỉ ký toàn vẹn, không watermark. JPG và định dạng khác bị từ chối kèm giải thích (nén có mất mát phá watermark ẩn).
- So sánh hash/chữ ký dùng hàm của thư viện `cryptography`, không tự so sánh chuỗi.

## 6. Bất biến quan trọng nhất (KHÔNG được đổi thứ tự)
Quy trình bảo vệ luôn kết thúc bằng bước KÝ, tùy theo loại file:

```
ảnh gốc (PNG) -> (1) [watermark hiện] (tùy chọn, mặc định bật) -> (2) watermark ẩn LSB -> (3) lưu PNG -> (4) KÝ file PNG cuối cùng
DOCX          -> (1) watermark ẩn trong metadata -> (2) lưu DOCX          -> (3) KÝ file DOCX cuối cùng
PDF           -> (1) lưu PDF                                             -> (2) KÝ file PDF cuối cùng (không watermark)
```

Lý do: ký phải là bước cuối vì chữ ký phủ lên từng byte của file. Watermark hiện làm đổi điểm ảnh nên phải làm TRƯỚC watermark ẩn, nếu không sẽ phá LSB. Sai thứ tự = hỏng hệ thống.
Lưu ý: watermark hiện là **tùy chọn** (mặc định bật). Nếu tắt thì bỏ qua bước (1), vẫn giữ LSB + ký. Tùy chọn này chỉ có ý nghĩa cho PNG.

## 7. Định nghĩa "xong"
Một milestone xong khi: (a) lệnh nghiệm thu chạy ra đúng kết quả mong đợi, (b) không có lỗi, (c) đã in kết quả cho người dùng xem, (d) cập nhật dấu `[x]` trong `TASKS.md`.

## 8. Cách báo cáo sau mỗi milestone
Trả lời ngắn theo mẫu:
```
Milestone: <tên>
Đã làm: <1-3 gạch đầu dòng>
Lệnh đã chạy + kết quả: <dán nguyên văn>
Ảnh nên chụp: <theo TEST_PLAN.md>
Tiếp theo: <milestone kế>, chờ xác nhận.
```
