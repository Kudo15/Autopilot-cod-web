# TASK s2-windows-scheduler — Daily Radar Windows Task Scheduler runner | harness: hermes-gui | worktree: repository root

## NGỮ CẢNH (tự chứa — không có hội thoại nào trước đó)

- Repo: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web`; stack: Python 3.13 via uv, SQLite, FastAPI.
- Existing durable scheduling logic: `backend/app/radar/scheduler.py`. It is explicitly request-driven today; `run_daily_radar_once(conn, owner, now, window="today", ...)` owns a SQLite lease, bounded retries, and does not publish/network.
- Existing tests: `backend/tests/test_radar_scheduler.py`; current full suite is 454 passing tests. `scripts/dev.ps1` runs only localhost development servers and is not a scheduled runner.
- User explicitly authorized a local Windows Task Scheduler task at 07:00 Asia/Ho_Chi_Minh and waived the independent-review-verdict requirement. Do not create a cloud task, service, remote connection, or production publication.

## TÁC VỤ (một việc duy nhất, 2–5 phút)

Khuôn mẫu: `Devops Engineer` + `Test Automation Expert`, hiện đại hóa cho a local-only Python/SQLite scheduled job. Implement a minimal, testable one-shot scheduler entrypoint and an idempotent PowerShell registration script:

1. Add a Python module runnable by `uv run python -m ...` that opens the configured local database, calls `run_daily_radar_once` with the actual current time and a deterministic owner, prints a non-secret JSON/text status, and exits non-zero on an unexpected job failure. It must not make network requests or publish content.
2. Add a PowerShell script that can register and query a per-user task named `VuHocAIRadar-Daily` at 07:00 daily, using an absolute repo path and the project's `uv` executable. Registration must be idempotent, localhost/worktree only, and return a clear error if prerequisites are absent. Include an explicit query/status mode. Do not unregister/delete an existing task as part of normal registration.
3. TDD is mandatory. First add focused tests proving the CLI/runner invokes the durable lease logic exactly once and propagates job failure; run them RED before production code, then GREEN. Add a safe script-content/command-construction test if that is the established repository pattern.

## FILES ĐƯỢC PHÉP

- `backend/app/radar/**`
- `backend/tests/test_radar_scheduler.py` (or a new focused backend test file)
- `scripts/**`
- `README_LOCAL.md`

## QUY TẮC BẤT DI BIẾN

- Do not modify `checks/`, `PLAN.md`, `docs/MISSION.md`, frontend files, source registry, or existing database data.
- No hardcoded secrets; do not log environment values or database contents.
- Use only `127.0.0.1` resources; no background server/thread, external source fetch, account creation, or auto-publish.
- Do not register, alter, delete, or run Windows Task Scheduler yourself. That external action is reserved for the coordinator after code verification.
- Preserve any pre-existing root changes. TDD: no production code before a focused test demonstrably fails.
- Commit only the allowed files; report the commit hash and exact commands/exit codes.

## HOÀN THÀNH KHI

```
[ĐÃ LÀM] runner, registration/query script, docs, focused tests
[BẰNG CHỨNG] RED command/result; GREEN focused test; full backend suite; script syntax/status check
[RULING] <nếu có>
[CÂU HỎI] <chỉ khi hoàn toàn bế tắc>
```
