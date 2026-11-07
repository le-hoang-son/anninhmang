# TEST_PLAN.md — Kịch bản kiểm thử và ảnh minh chứng

## 1. Kịch bản kiểm thử

| ID | Kịch bản | Cách làm | Kết quả mong đợi |
|----|----------|----------|------------------|
| T1 | Ký và xác minh ảnh nguyên bản | `protect` rồi `verify` ảnh trong `data/signed/` | HOP_LE, LSB khớp |
| T2 | Sửa 1 điểm ảnh | `tamper --mode pixel` rồi `verify` | KHONG_HOP_LE, lý do sha256 không khớp |
| T3 | Sửa nội dung bằng chữ đè | `tamper --mode text` rồi `verify` | KHONG_HOP_LE, có log, có ntfy |
| T4 | Cắt mép ảnh | `tamper --mode crop` rồi `verify` | KHONG_HOP_LE |
| T5 | Giả mạo chữ ký | Dùng sidecar của ảnh A cho ảnh B | KHONG_HOP_LE |
| T6 | Thiếu sidecar | Xóa `.sig.json` rồi `verify` | KHONG_XAC_MINH_DUOC |
| T7 | Sửa sidecar | Đổi 1 ký tự trong `signature_b64` | KHONG_HOP_LE |
| T8 | Khóa lạ | `keygen --force` tạo khóa mới rồi verify ảnh cũ | KHONG_HOP_LE (fingerprint không khớp) |
| T9 | Ảnh JPG | Đưa file `.jpg` vào `protect` | Từ chối, thông báo rõ |
| T10 | Ảnh quá nhỏ | Ảnh 20x20 vào `protect` | Báo "ảnh quá nhỏ để giấu thông tin", không crash |
| T11 | Khôi phục | `recover IMG-xxxx out.png` | HỢP LỆ |
| T12 | ntfy lỗi mạng | Đặt topic sai hoặc tắt mạng rồi verify ảnh giả | Chương trình vẫn chạy, log ghi "gửi cảnh báo thất bại" |
| T13 | Bảo mật web | Thử path traversal, upload file đổi đuôi, file quá 10 MB | Bị từ chối, không lộ file |
| T14 | LSB không nhìn thấy | So ảnh trước/sau `lsb-embed` | Độ lệch tối đa mỗi kênh = 1 |

Lưu ý T8: sau khi thử phải khôi phục khóa gốc (sao lưu `keys/` trước khi thử).

## 2. Tự động hóa
- `pytest` bao phủ T1, T2, T5, T6, T7, T10, T14 và test riêng cho `lsb.py`, `signer.py`.
- `demo.py` chạy tuần tự T1, T2, T3, T4, T11 có tiêu đề từng bước để người dùng chụp ảnh.
- T9, T12, T13 kiểm bằng tay.

## 3. Danh sách ảnh cần chụp cho báo cáo
Chụp toàn màn hình, thấy rõ giờ và tên máy. Đặt tên file `EV-01.png`, `EV-02.png`, ...

| Ảnh | Nội dung | Mốc |
|-----|----------|-----|
| EV-01 | Cấu trúc thư mục dự án trong Trae | M0 |
| EV-02 | `keygen` + hai file khóa, `sign`, `verify-sig` HỢP LỆ | M1 |
| EV-03 | Ảnh gốc và ảnh bị `tamper` cạnh nhau (khó phân biệt bằng mắt) | M2 |
| EV-04 | `verify-sig` ảnh giả: KHÔNG HỢP LỆ (nhất là ảnh đổi 1 điểm ảnh) | M2 |
| EV-05 | Ảnh trước và sau watermark hiện | M3 |
| EV-06 | `lsb-read` đọc đúng chuỗi từ ảnh đã giấu, và ảnh chưa giấu không đọc được | M4 |
| EV-07 | Thống kê độ lệch pixel LSB (tối đa 1) | M4 |
| EV-08 | `protect` + `verify` HỢP LỆ, kèm nhãn `[PROTECT]`, `[DETECT]` | M5 |
| EV-09 | `verify` ảnh giả: KHÔNG HỢP LỆ, có nhãn `[DETECT]` `[RESPOND]` | M5/M6 |
| EV-10 | `assets` bảng tài sản (Identify) | M6 |
| EV-11 | `verify.log` nhiều dòng | M6 |
| EV-12 | Điện thoại hoặc trình duyệt nhận thông báo ntfy | M6 |
| EV-13 | `recover` HỢP LỆ (Recover) | M6 |
| EV-14 | Web: trang `/protect` kết quả | M7 |
| EV-15 | Web: `/verify` xanh (hợp lệ) | M7 |
| EV-16 | Web: `/verify` đỏ (không hợp lệ) | M7 |
| EV-17 | Web: `/assets` và `/logs` | M7 |
| EV-18 | Kết quả thử bảo mật web T13 bị từ chối | M7 |
| EV-19 | `pytest -q` toàn bộ xanh | M8 |
| EV-20 | `demo.py` chạy trọn vẹn | M8 |

## 4. Sơ đồ nên vẽ (diagrams.net, làm tay)
1. Sơ đồ khối hệ thống: người phát hành, người kiểm tra, các module, thư mục dữ liệu, ntfy.
2. Lưu đồ quy trình bảo vệ 4 bước (nhấn mạnh thứ tự).
3. Lưu đồ xác minh theo bảng logic `SPEC.md` mục 7.
4. Bảng ánh xạ NIST (lấy từ `NIST_MAPPING.md`).
