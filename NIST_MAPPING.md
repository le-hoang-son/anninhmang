# NIST_MAPPING.md — Ánh xạ hệ thống ImgSign sang NIST CSF 1.1

Dùng làm khung cho mục "Cơ sở lý thuyết và ánh xạ" trong báo cáo. Agent dùng file này để đảm bảo mọi chức năng có chỗ đứng trong 5 chức năng NIST, và để đặt tên log/báo cáo cho nhất quán.

## 1. Bảng ánh xạ chính

| Chức năng | Danh mục NIST CSF 1.1 | Việc hệ thống làm | Module / lệnh | Minh chứng |
|-----------|----------------------|--------------------|----------------|-----------|
| **Identify** | ID.AM (Quản lý tài sản) | Đăng ký mỗi ảnh vào bảng tài sản, có loại ảnh và mức quan trọng 1-3 | `assets.py`, lệnh `assets`, trang `/assets` | Bảng tài sản |
| **Identify** | ID.RA (Đánh giá rủi ro) | Mức quan trọng 3 được ghi nhận là rủi ro cao nếu bị làm giả; nêu trong báo cáo | `assets.json` trường `importance` | Mô tả trong báo cáo |
| **Protect** | PR.DS (Bảo mật dữ liệu) | Chữ ký số RSA-PSS bảo vệ toàn vẹn; watermark hiện và ẩn bảo vệ nguồn gốc | `signer.py`, `watermark.py`, `lsb.py` | Ảnh ký, ảnh watermark |
| **Protect** | PR.AC (Kiểm soát truy cập) | Khóa riêng chỉ người phát hành giữ, có thể đặt mật khẩu; người kiểm tra chỉ cần khóa công khai | `keys.py` | Mô tả quản lý khóa |
| **Protect** | PR.IP (Quy trình bảo vệ thông tin) | Quy trình bảo vệ cố định 4 bước, lưu bản gốc | `pipeline.protect()` | Lưu đồ quy trình |
| **Detect** | DE.CM (Giám sát liên tục) | Mỗi ảnh đưa vào đều được xác minh, ghi log | `pipeline.verify_full()`, `logger.py` | `verify.log` |
| **Detect** | DE.AE (Phân tích bất thường) | Phân loại bốn kết luận theo chữ ký và watermark ẩn, phát hiện sửa 1 điểm ảnh | `verify_full()` | Ảnh KHÔNG HỢP LỆ |
| **Respond** | RS.CO (Truyền thông ứng phó) | Gửi cảnh báo ntfy tới người phụ trách khi phát hiện ảnh giả | `notifier.py` | Ảnh điện thoại nhận thông báo |
| **Respond** | RS.AN (Phân tích) | Báo cáo chỉ rõ nguyên nhân: hash sai, chữ ký sai, thiếu sidecar, khóa lạ | `FullReport.notes` | Nội dung báo cáo xác minh |
| **Recover** | RC.RP (Kế hoạch phục hồi) | Lưu bản gốc và bản đã ký, lệnh `recover` khôi phục và kiểm tra lại | `recover.py` | Ảnh kết quả recover |

## 2. Quy ước đặt tên để báo cáo khớp NIST
- Log và báo cáo dùng nhãn: `[IDENTIFY]`, `[PROTECT]`, `[DETECT]`, `[RESPOND]`, `[RECOVER]` đầu dòng tương ứng khi in ra CLI (ví dụ `[PROTECT] Da ky anh IMG-0001`, `[DETECT] Phat hien anh bi sua`, `[RESPOND] Da gui canh bao ntfy`, `[RECOVER] Da khoi phuc IMG-0001`).
- Trong `verify.log` giữ nguyên định dạng ở `ARCHITECTURE.md` mục 4.5, thêm nhãn NIST chỉ ở phần in CLI.

## 3. Điểm mạnh và điểm yếu (nói thật trong báo cáo)
- Mạnh: Protect (toàn vẹn dữ liệu) và Detect (phát hiện sửa đổi) khớp trực tiếp, có chứng cứ rõ.
- Mỏng hơn: Respond và Recover ở mức cơ bản (cảnh báo, ghi log, khôi phục từ bản lưu). Đề xuất mở rộng ở phần "Hướng phát triển": tích hợp ticketing, ký thời gian (timestamp) bên thứ ba, sao lưu bản gốc mã hóa ra nơi khác.

## 4. Rủi ro và biện pháp (gợi ý cho mục Identify trong báo cáo)

| Rủi ro | Mức | Biện pháp trong hệ thống |
|--------|-----|--------------------------|
| Ảnh bị sửa nội dung (đổi tên, số liệu) | Cao | Chữ ký số + xác minh |
| Ảnh bị mạo danh nguồn gốc | Cao | Chữ ký bằng khóa riêng + watermark hiện/ẩn |
| Lộ khóa riêng | Rất cao | Không commit, đặt mật khẩu khóa, `.gitignore` |
| Ảnh giả bị phát tán không ai biết | Trung bình | Log và cảnh báo ntfy khi xác minh thất bại |
| Mất bản gốc | Trung bình | Lưu `data/originals/`, lệnh `recover` |
| Watermark ẩn bị xóa do nén JPG | Thấp (đã biết) | Chữ ký vẫn là bằng chứng chính; ghi giới hạn |
