# Independent review — Task 001

## 1. Tuân thủ spec

- Proxy Vite `/api` trỏ `http://127.0.0.1:8000` và server vẫn bind localhost: đạt theo diff.
- Frontend gọi `/api/articles`, có loading, empty, error và retry được dùng thật: đạt theo diff.
- Test focused cho public feed có mặt và kiểm tra PUBLISHED/SAMPLE cùng allowlist field: đạt.
- Phạm vi file trong review package phù hợp task pack; không thấy sửa `checks/`, `PLAN.md` hoặc `docs/MISSION.md`.

### Findings

- [P2] `backend/app/main.py:45` — Điều kiện `data_origin != ?` loại luôn các hàng có `data_origin IS NULL` vì biểu thức SQL đó trả `NULL`, không phải true. Task pack chỉ yêu cầu loại `SAMPLE`; các bài thật từ database/migration cũ chưa điền `data_origin` sẽ biến mất khỏi public feed. Đổi điều kiện thành `(data_origin IS NULL OR data_origin != ?)` và thêm regression fixture có bài `PUBLISHED` với `data_origin` NULL.

## 2. Chất lượng code / bảo mật

- Truy vấn dùng placeholders cho các giá trị lọc; tên cột được lấy từ hằng số nội bộ và schema introspection, nên diff không cho thấy SQL injection mới.
- AbortController ngăn một request bị hủy chuyển UI sang error state; HTTP lỗi, network lỗi và JSON không phải mảng đều đi vào error state.
- Không có key/secret hoặc request ngoài localhost được thêm trong diff.

## Xác minh độc lập

- `uv run python -m unittest discover -v` — exit 0; 1 test passed.
- `npm run build` — exit 0; build hoàn tất (có warning Node 22.11.0 thấp hơn mức Vite khuyến nghị).
- `PYTHONIOENCODING=utf-8 python checks/p5.py` — exit 0; `PASS (11/11)` với backend và Vite localhost thật.

VERDICT: CHANGES_REQUESTED — [P2] sửa điều kiện `data_origin` để không loại các bài public có giá trị NULL, rồi bổ sung regression test.
