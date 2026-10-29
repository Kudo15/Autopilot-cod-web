[ĐÃ LÀM]
- Thêm `NormalizedItem` immutable và `normalize_item` pure, không I/O/network/command.
- Chuẩn hóa canonical URL, Unicode title/content, SHA-256 content hash và provenance.
- Thêm 5 focused tests cho URL, Unicode, hash, validation và prompt-injection text.

[BẰNG CHỨNG]
- `python -m unittest backend.tests.test_normalize -v` — exit 0, 5 tests OK.
- `git diff --check` — exit 0.
- `python -m unittest discover -v` — NOT_VERIFIED/exit 1: test cũ không import được vì môi trường thiếu `fastapi`.
- `uv run ...` — BLOCKED: uv cache tại `C:\Users\Panda\AppData\Local\uv\cache` bị Access Denied.

[RULING]
- Tự chủ: giữ implementation nhỏ và deterministic; content được NFC + trim/collapse whitespace trước khi hash để dedup ổn định.

[CÂU HỎI]
- Không có.

[FIX ROUND 1]
- Reviewer P2 đã chỉ ra lỗi mất dấu ngoặc IPv6 và âm thầm loại bỏ user-info khi rebuild authority.
- Đã thêm regression tests cho IPv6 và user-info; implementation giữ ngoặc IPv6 và reject user-info rõ ràng.
- `python -m unittest backend.tests.test_normalize -v` — exit 0, 7 tests OK.
- `git diff --check` — exit 0.
- Commit tiếp tục BLOCKED: `.git/index.lock` không thể tạo do Permission denied.
