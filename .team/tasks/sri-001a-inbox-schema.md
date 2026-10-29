# TASK sri-001a-inbox-schema — schema-v1 and additive inbox-run migration | harness: hermes-kanban | worktree: Hermes-managed

## NGỮ CẢNH (tự chứa — không có hội thoại nào trước đó)

- Repo: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web`; Python 3.13/FastAPI/SQLite/`unittest`.
- Approved contract: `docs/superpowers/specs/2026-10-25-scheduled-radar-inbox-design.md`; implementation plan Task 1 at `docs/superpowers/plans/2026-10-25-scheduled-radar-inbox-plan.md`.
- This is the first half of original Task 1, intentionally split after an analysis-only worker made no code changes. Do not implement file scanning or article persistence here.
- Use current patterns in `backend/app/migrate.py`, `backend/app/ingest/normalize.py`, and tests under `backend/tests/`.
- The root checkout is dirty. Work only in the Hermes worktree; commit only files you change.

## TÁC VỤ (một việc duy nhất, 2–5 phút)

Act as an expert test engineer and backend developer. Using the **Unit Tester Assistant** template, first write a small failing `unittest` module for strict scheduled-report schema v1 and the additive `scheduled_inbox_runs` migration, run RED, then write the minimum code to pass.

Create `backend/app/inbox/schema.py` with strict (unknown field rejected) Pydantic models for exactly:

- top-level fields `schema_version`, `run_id`, `report_kind`, `observed_at`, `timezone`, `findings`;
- `schema_version == "1"`; report kinds exactly `provider_harness_radar|tip_trick_radar`;
- finding fields exactly `external_id`, `title`, `category`, `summary`, `canonical_urls`, `source_type`, `verification_status`, `evidence_note`, `valid_until`, `risk_note`;
- non-empty canonical URL list, syntactically safe HTTP(S) URLs (no credential userinfo), parseable offset timestamp(s), and allowlisted source/verification states from the approved design.

Add only the additive `scheduled_inbox_runs` table/indexes to the existing migration. It must preserve the mission’s existing 12-table contract; do not alter `BUSINESS_TABLES` unless a failing test demonstrates it is required. The table must use the exact plan fields and `IMPORTED|QUARANTINED` status allowlist. Create `backend/app/inbox/__init__.py` as package marker if required.

Do not add scanner/service, API routes, UI, AI behavior, scheduled prompts, source creation, or deployment.

## QUY TẮC BẤT DI BIẾN

- Only create/modify `backend/app/inbox/__init__.py`, `backend/app/inbox/schema.py`, `backend/app/migrate.py`, `backend/tests/test_scheduled_inbox_schema.py`.
- TDD strictly: show focused test failing before production code; no production code before RED.
- Artifact text stays data; no subprocess, network, shell, file write derived from input, secret or auto-publish logic.
- No new dependency; no edits to `checks/`, `PLAN.md`, `docs/MISSION.md` or unrelated tests.
- Commit only scoped changes in your worktree as `feat: add inbox schema and run migration`.

## HOÀN THÀNH KHI

1. Tests prove valid provider/tip reports parse; unknown fields/invalid run status/timestamp/URL/empty source link reject.
2. Tests prove a fresh migration contains `scheduled_inbox_runs` with the planned fields and second migration run succeeds.
3. Run and record:
   - `uv run python -m unittest backend.tests.test_scheduled_inbox_schema -v`
   - `uv run python -m unittest backend.tests.test_importers -v`
   - `uv run python -m backend.app.migrate` twice
4. Write `.team/results/sri-001a-inbox-schema-report.md` in your worktree:

```
[ĐÃ LÀM]
[BẰNG CHỨNG]
[RULING]
[CÂU HỎI]
```
