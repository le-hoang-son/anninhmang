# SPEC.md — Đặc tả hệ thống ImgSign

## 1. Mục tiêu
Hệ thống giúp **chứng minh một tấm ảnh là nguyên bản và chưa bị sửa**, và **phát hiện ảnh bị làm giả**.
Ví dụ: một trường phát hành ảnh bằng tốt nghiệp. Hệ thống ký ảnh và đóng dấu. Nếu ai sửa tên trong ảnh, hệ thống báo KHÔNG HỢP LỆ và gửi cảnh báo.

## 2. Người dùng
- **Người phát hành** (giữ khóa riêng): đăng ký tài sản ảnh, bảo vệ (watermark + ký), khôi phục bản gốc.
- **Người kiểm tra** (chỉ cần khóa công khai): xác minh ảnh.

## 3. Yêu cầu chức năng

| ID | Chức năng | Mô tả ngắn | Mốc |
|----|-----------|------------|-----|
| FR-1 | Tạo khóa | Sinh cặp khóa RSA-2048, lưu `keys/private.pem` và `keys/public.pem`. Không ghi đè khóa cũ nếu chưa có cờ `--force`. | M1 |
| FR-2 | Ký ảnh | Ký file PNG bằng khóa riêng, ghi file sidecar `.sig.json`. | M1 |
| FR-3 | Xác minh chữ ký | Nhận ảnh + sidecar, trả HỢP LỆ hoặc KHÔNG HỢP LỆ (kèm lý do). Chỉ cần khóa công khai. | M1 |
| FR-4 | Watermark hiện | Chèn chữ mờ (tên đơn vị, ngày) lên ảnh, vị trí lặp chéo hoặc góc dưới. | M3 |
| FR-5 | Watermark ẩn | Giấu payload JSON (asset_id, owner, ngày) vào bit thấp nhất (LSB) của điểm ảnh, đọc lại được. | M4 |
| FR-6 | Quy trình bảo vệ | Lệnh một bước: watermark hiện -> watermark ẩn -> lưu -> ký. | M5 |
| FR-7 | Xác minh đầy đủ | Báo cáo gồm: kết quả chữ ký, watermark ẩn đọc được hay không, payload có khớp sidecar không. | M5 |
| FR-8 | Bảng tài sản ảnh (Identify) | Đăng ký ảnh vào `data/assets.json`: asset_id, tên, loại ảnh, mức quan trọng (1-3), hash, thời gian. | M6 |
| FR-9 | Ghi log + cảnh báo (Respond) | Mỗi lần xác minh ghi một dòng vào `data/logs/verify.log`. Nếu KHÔNG HỢP LỆ thì gửi ntfy. | M6 |
| FR-10 | Lưu gốc + khôi phục (Recover) | Khi bảo vệ, lưu bản gốc vào `data/originals/`. Lệnh `recover` đưa bản đã ký trở lại và kiểm tra lại chữ ký. | M6 |
| FR-11 | Giao diện web | Flask: trang chủ, đăng ký + bảo vệ ảnh, xác minh ảnh, xem log, danh sách tài sản. | M7 |
| FR-12 | So sánh ảnh (web) | Chọn asset trong `data/signed`, upload ảnh nghi giả, so bằng `ImageChops.difference`, vẽ khung đỏ vùng khác biệt, hiện 3 ảnh + số điểm ảnh khác và tỷ lệ %. Xử lý ảnh khác kích thước. | W2 |
| FR-13 | Bảng NIST động (web) | 5 ô Identify / Protect / Detect / Respond / Recover: danh mục NIST, việc hệ thống làm, số liệu thật (số tài sản, ảnh đã ký, lần xác minh, lần phát hiện giả, cảnh báo đã gửi, lần khôi phục). | W2 |
| FR-14 | Chi tiết tài sản (web) | `/assets/<id>`: thông tin, ảnh đã ký, lịch sử xác minh riêng, nút tải + nút Khôi phục (POST, dùng `recover.recover`). | W2 |
| FR-15 | Bảng điều khiển (web) | Trang chủ thành dashboard: thẻ số liệu, biểu đồ cột CSS hợp lệ/không hợp lệ, 5 sự kiện gần nhất có màu. | W3 |
| FR-16 | Xác minh theo lô (web) | `/verify-batch`: upload tối đa 10 ảnh PNG, mỗi ảnh tự tìm sidecar theo LSB; bảng kết quả; ghi log từng ảnh; gửi ntfy tối đa một thông báo tóm tắt. | W3 |
| FR-17 | Quản lý khóa công khai (web) | `/keys`: fingerprint, ngày tạo, tải `public.pem`. Tuyệt đối không có route trả khóa riêng. | W4 |
| FR-18 | Nhật ký nâng cao (web) | `/logs`: lọc theo kết luận, tìm theo tên ảnh, phân trang 50 dòng, xuất CSV (chống CSV injection). | W4 |
| FR-19 | Thử cảnh báo (web) | `/alert-test`: hiện trạng thái ntfy (chỉ 3 ký tự đầu của topic) và nút gửi thử cảnh báo. | W4 |
| FR-20 | Bảo mật web nâng cao | `secret_key` đọc từ `IMGSIGN_SECRET_KEY` (không hardcode); giới hạn tần suất POST theo IP (20 lần/phút), vượt quá trả 429 kèm thông báo tiếng Việt. | W1 |

## 4. Phi chức năng
- Chạy trên Windows và Ubuntu. Không cần Internet, trừ gửi ntfy (lỗi mạng ntfy không được làm sập chương trình, chỉ ghi log).
- Ảnh PNG, tối đa 10 MB. Từ chối định dạng khác với thông báo rõ.
- Xác minh một ảnh dưới 2 giây với ảnh khoảng 2 MB.
- Mọi thông báo cho người dùng bằng tiếng Việt có dấu.

## 5. Ngoài phạm vi (KHÔNG làm)
- Watermark chịu nén JPG, chịu cắt xén, chịu phóng to thu nhỏ (cần kỹ thuật tần số, quá nặng).
- Đăng nhập người dùng, phân quyền, database server.
- Blockchain, timestamp server bên ngoài, chứng chỉ X.509.
- Hỗ trợ video hoặc PDF.
- Triển khai lên Internet.

## 6. Giới hạn trung thực (phải ghi vào báo cáo)
- **Chữ ký số là bằng chứng chính** về toàn vẹn: đổi 1 byte là chữ ký hỏng.
- **Watermark ẩn LSB rất mong manh**: lưu lại JPG, đổi kích thước, chụp màn hình đều có thể làm mất. Vai trò của nó là chứng cứ nguồn gốc bổ sung, không thay thế chữ ký.
- Ảnh bị sửa nhẹ vùng nhỏ có thể vẫn còn watermark ẩn đọc được nhưng chữ ký vẫn báo KHÔNG HỢP LỆ. Đây là hành vi đúng, hệ thống kết luận theo chữ ký.
- Chữ ký chứng minh "file này do người giữ khóa riêng phát hành, chưa bị đổi", không chứng minh nội dung ảnh là sự thật.

## 7. Logic kết luận khi xác minh

| Chữ ký | Watermark ẩn | Kết luận |
|--------|--------------|----------|
| Hợp lệ | Đọc được, khớp sidecar | **HỢP LỆ** — nguyên bản |
| Hợp lệ | Không đọc được | **HỢP LỆ (cảnh báo)** — hiếm, ghi log |
| Không hợp lệ | Đọc được | **KHÔNG HỢP LỆ** — ảnh bị sửa, nguồn gốc nhận ra |
| Không hợp lệ | Không đọc được | **KHÔNG HỢP LỆ** — ảnh bị sửa nặng hoặc không phải ảnh của hệ thống |
| Thiếu file sidecar | — | **KHÔNG XÁC MINH ĐƯỢC** — yêu cầu cung cấp `.sig.json` |
