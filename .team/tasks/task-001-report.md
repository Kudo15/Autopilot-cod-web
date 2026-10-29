[ĐÃ LÀM]
- Thêm Vite proxy `/api` tới `http://127.0.0.1:8000`, vẫn chỉ bind `127.0.0.1`.
- Frontend fetch `/api/articles`, dùng thật các trạng thái loading/empty/error và nút thử lại; feed chỉ render dữ liệu API theo nhóm.
- Public API chỉ chọn các trường public hiện có và loại bài `article_status != PUBLISHED` hoặc `data_origin = SAMPLE` khi các cột schema đó tồn tại.

[BẰNG CHỨNG]
- RED: `uv run python -m unittest backend.tests.test_public_articles -v` — exit 1; assertion nhận `['Sample', 'Draft', 'Published']` thay vì chỉ `['Published']`.
- GREEN: `uv run python -m unittest discover -v` — exit 0; `Ran 1 test ... OK`.
- `npm run build` — exit 0; Vite tạo `dist/index.html` và bundle JS. Có cảnh báo Node 22.11.0 thấp hơn mức Vite khuyến nghị 22.12+, nhưng build hoàn tất.
- `PYTHONIOENCODING=utf-8 python checks/p5.py` (ngoài sandbox, backend/Vite localhost thật) — exit 0; `== ket qua phase: PASS (11/11) ==`.
- `git diff --check` — exit 0.

[RULING]
- Khi migration cũ chưa có `article_status`/`data_origin`, endpoint chỉ áp điều kiện mà `PRAGMA table_info` xác nhận có; schema hiện tại có cả hai nên feed công khai bắt buộc `PUBLISHED` và khác `SAMPLE`. Chi phí nếu sai: database cũ chưa migration có thể chưa có ranh giới public hoàn chỉnh, nhưng sẽ không lỗi truy vấn và lifespan migration cập nhật schema trước khi server phục vụ.

[CÂU HỎI]
- Không có.

## Fix round 1 — legacy NULL data_origin

[ĐÃ LÀM]
- Giữ bài `PUBLISHED` có `data_origin = NULL` trong public feed, đồng thời tiếp tục loại `data_origin = SAMPLE`.
- Bổ sung fixture regression cho một bài legacy `PUBLISHED` với `data_origin` NULL.

[BẰNG CHỨNG]
- RED: `uv run python -m unittest backend.tests.test_public_articles -v` — exit 1; nhận `['Published']` thay vì `['Legacy published', 'Published']`.
- GREEN: `uv run python -m unittest discover -v` — exit 0; `Ran 1 test ... OK`.
- `npm run build` — exit 0; Vite build hoàn tất (vẫn cảnh báo Node 22.11.0 thấp hơn 22.12+ khuyến nghị).
- `PYTHONIOENCODING=utf-8 python checks/p5.py` — exit 0; `== ket qua phase: PASS (11/11) ==`.
- `git diff --check` — exit 0.

[RULING]
- SQL dùng `(data_origin IS NULL OR data_origin != ?)` với parameter `SAMPLE`: bảo toàn record legacy không gắn origin nhưng không công khai dữ liệu SAMPLE.

[CÂU HỎI]
- Không có.
