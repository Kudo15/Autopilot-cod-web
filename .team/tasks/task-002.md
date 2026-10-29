# TASK 002 — Chuẩn hóa canonical URL, title và content hash | harness: Codex local task | worktree: D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web

## NGỮ CẢNH

- Repo: `D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web` | Stack: Python 3.13 qua uv, FastAPI, SQLite.
- Plan: `.team/plans/remaining.md`, Task 2 (PLAN phase 6.1); audit: `.team/audit.md`.
- Chỉ được tạo/sửa `backend/app/ingest/normalize.py`, `backend/app/ingest/__init__.py` và `backend/tests/**` cho focused tests. Không sửa `checks/`, `PLAN.md`, `docs/MISSION.md`, frontend hay public data.
- Task 001 đã nối public article feed; importer Task 3 và dedup Task 4 sẽ consume normalized result.

## TÁC VỤ

Tạo pure normalization module cho imported items. Khuôn mẫu: Bug Risk Analyst. Biến thể: dùng phân tích input/risk để khóa các edge cases, nhưng implementation phải là code nhỏ, deterministic, không đọc/ghi file, không network, không thực thi text nhập vào.

## INTERFACES

- `normalize_item(payload: dict, source_id: str, fetched_at: str) -> NormalizedItem`.
- `NormalizedItem` phải expose `source_id`, `fetched_at`, `title`, `url`, `canonical_url`, `normalized_title`, `content`, `content_hash`, `provenance` và các field public tối thiểu cần cho importer.
- Canonical URL phải bỏ fragment, normalize scheme/host case và trailing slash an toàn; không đổi query semantics.
- Normalized title phải Unicode-normalize, trim và collapse whitespace.
- Content hash là SHA-256 deterministic trên content normalized; provenance phải chứa source + fetched timestamp.
- Input thiếu title/content hoặc source_id/fetched_at không hợp lệ phải raise lỗi rõ ràng, không bịa giá trị.

## QUY TẮC BẤT DI BIẾN

- TDD: test fail trước implementation, gồm URL fragment/trailing slash, Unicode title, hash ổn định, missing fields và prompt-injection text được giữ nguyên như data.
- Không thêm dependency nặng, không log input secrets, không thao tác file/command/network.
- Worker không dispatch subagent/reviewer; ghi report `.team/tasks/task-002-report.md`, commit local, trả status/commit/tests/concerns.

## VERIFY

- `uv run python -m unittest discover -v` hoặc lệnh focused tương đương phải exit 0.
- Có test chứng minh cùng input cho cùng canonical/hash và input khác hash khác.
- `git diff --check` exit 0; không sửa ngoài scope.

## REPORT

Ghi vào `.team/tasks/task-002-report.md`:

```
[ĐÃ LÀM] tóm tắt 3 dòng
[BẰNG CHỨNG] lệnh + exit code/output chính
[RULING] quyết định tự chủ — nếu có
[CÂU HỎI] chỉ khi bế tắc hoàn toàn
```
