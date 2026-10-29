# TASK <id> — <tên ngắn> | harness: ${Harness:codex exec} | worktree: <đường dẫn>

## NGỮ CẢNH (tự chứa — không có hội thoại nào trước đó)

- Repo: <đường dẫn> | Stack: ${Stack:...} | Kế hoạch: `.team/plans/<plan>.md` (đoạn <x–y>)
- File liên quan: <đường dẫn từng file + việc gì đang ở đó>

## TÁC VỤ (một việc duy nhất, 2–5 phút)

<diễn đạt tác vụ; khuôn mẫu chế từ act "<tên>" trong prompts.chat, đã hiện đại hóa: vai + ràng buộc đầu ra + giao thức tương tác + tin nhắn khởi động>

## QUY TẮC BẤT DI BIẾN

- TDD: KHÔNG có code production nếu chưa có test đang fail. Code viết trước test → XÓA, viết lại từ test.
- Không mở rộng phạm vi ngoài tác vụ. Mơ hồ/chồng chéo → tự quyết, ghi `Ruling: ... — why — cost` vào cuối báo cáo, đừng đứng chờ.
- Không tuyên bố thành công khi chưa chạy được bằng chứng (test/lệnh).
- Narrate tối đa 1 dòng giữa các tool call.

## HOÀN THÀNH KHI

Test xanh + đã commit + tự review một lượt + báo cáo đúng mẫu:

```
[ĐÃ LÀM] tóm tắt 3 dòng
[BẰNG CHỨNG] lệnh đã chạy + kết quả
[RULING] <quyết định tự chủ — nếu có>
[CÂU HỎI] <chỉ khi bế tắc hoàn toàn>
```
