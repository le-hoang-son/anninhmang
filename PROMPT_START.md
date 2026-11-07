# PROMPT_START.md — Prompt để dán vào Trae Solo

## Chuẩn bị (làm một lần)
1. Tạo thư mục dự án `imgsign` trên máy.
2. Chép 6 file `.md` vào thư mục gốc: `AGENTS.md`, `SPEC.md`, `ARCHITECTURE.md`, `TASKS.md`, `NIST_MAPPING.md`, `TEST_PLAN.md`.
3. Tạo thư mục `samples/` và đặt ảnh PNG của bạn vào, đặt tên `goc.png` (ảnh rộng từ 600 px trở lên, nên là PNG, không dùng JPG).
4. (Tùy chọn) Chép `AGENTS.md` thêm một bản vào `.trae/rules/project_rules.md` để Trae luôn nạp luật này.
5. Mở thư mục `imgsign` trong Trae, bật chế độ Solo.

## Prompt 1 — Khởi động (dán nguyên văn)

```
Hãy đọc lần lượt các file trong thư mục dự án: AGENTS.md, SPEC.md, ARCHITECTURE.md, TASKS.md, NIST_MAPPING.md, TEST_PLAN.md.
Sau đó chỉ thực hiện milestone M0 trong TASKS.md.
Tuân thủ nghiêm AGENTS.md: làm một milestone, chạy lệnh nghiệm thu, báo cáo theo mẫu ở mục 8 của AGENTS.md rồi DỪNG chờ tôi xác nhận. Không làm trước milestone sau.
Nếu có điểm nào trong tài liệu mâu thuẫn hoặc thiếu, hãy hỏi tôi trước khi code.
```

## Prompt 2 — Sang milestone kế (dán sau khi bạn đã kiểm tra kết quả)

```
Milestone trước đã đạt. Hãy làm milestone <MX> trong TASKS.md.
Đọc lại phần liên quan trong ARCHITECTURE.md trước khi code. Chạy lệnh nghiệm thu và dán nguyên văn kết quả. Sau đó dừng.
```
(Thay `<MX>` bằng M1, M2, ... M8.)

## Prompt 3 — Khi có lỗi

```
Lệnh nghiệm thu bị lỗi. Dưới đây là thông báo lỗi nguyên văn:
<dán lỗi>
Hãy nêu nguyên nhân trong 1-2 câu, sửa tối thiểu, chạy lại nghiệm thu. Không đổi hợp đồng trong ARCHITECTURE.md nếu không cần.
```

## Prompt 4 — Khi agent làm lan man hoặc làm trước

```
Bạn đang làm vượt phạm vi. Hãy dừng, hoàn tác phần ngoài milestone hiện tại, và đọc lại AGENTS.md mục 2. Chỉ làm đúng <MX>.
```

## Prompt 5 — Kiểm tra chất lượng cuối (sau M8)

```
Hãy rà soát toàn bộ dự án theo 4 ý, chỉ báo cáo, chưa sửa:
1. Có chỗ nào vi phạm quy tắc an toàn ở AGENTS.md mục 5 không (khóa riêng bị in/commit, path traversal, upload không kiểm tra)?
2. Thứ tự quy trình bảo vệ (watermark hiện, LSB, lưu, ký) có đúng ở mọi nơi gọi không?
3. Mọi chức năng FR-1 đến FR-11 trong SPEC.md đã có chưa, mỗi chức năng nằm ở file nào?
4. Test T1 đến T14 trong TEST_PLAN.md cái nào chưa có kiểm thử?
Liệt kê vấn đề kèm đường dẫn file và số dòng.
```

## Mẹo dùng Trae Solo
- Mỗi lần chỉ một milestone. Agent làm nhiều mốc cùng lúc rất dễ sai thứ tự quy trình ký.
- Sau mỗi mốc, tự chạy lại lệnh nghiệm thu trong terminal của bạn rồi **chụp ảnh ngay** theo `TEST_PLAN.md` mục 3.
- Chụp xong mốc nào thì ghi vài dòng vào `notes.txt` như đã làm với đề cũ.
- Nếu agent đề xuất thêm thư viện hoặc tính năng, trả lời "ghi vào IDEAS.md, không làm".
- Trước khi nộp, sao lưu thư mục `keys/` ra nơi khác, nhưng **không** đưa vào báo cáo hay GitHub.
