# sri-001c — safe scheduled inbox scanner

[ĐÃ LÀM]

- Thêm scanner inbox JSON an toàn và persistence SQLite quyết định.
- Thêm projection ledger allowlist và bộ đếm kết quả scan.
- Thêm 11 test cho idempotency, quarantine, transaction isolation, SQL rollback, injection text và DRAFT-only persistence.
- Sửa transaction thành công phải commit/release trước khi trả `_Outcome`.

[BẰNG CHỨNG]

- Commit ứng viên: `8e516af778c2c360a890f9d42af34afc3c766140`.
- `uv run python -m unittest backend.tests.test_scheduled_inbox -v`: 11/11 OK, exit 0.
- Regression schema + migration + importers: 40/40 OK, exit 0.
- `git diff 829de5c..8e516af --check`: exit 0.
- Review độc lập card `t_6219bd07`: `APPROVED`, không có finding chặn.

[RULING]

- Đủ điều kiện tích hợp vào nhánh chính cục bộ.
- Không deploy và không publish tự động.

[CÂU HỎI]

- Không còn câu hỏi chặn. Tối ưu dedup cho file không đọc được là follow-up không bắt buộc.
