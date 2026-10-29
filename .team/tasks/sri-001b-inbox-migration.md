# TASK sri-001b-inbox-migration — add idempotent scheduled inbox run ledger | harness: hermes-kanban | worktree: Hermes-managed

Act as a Python/SQLite backend engineer using strict TDD. This is one narrow migration task; do not implement scanning, persistence services, APIs, UI, AI, docs, scheduler, or publication.

## Context

- Repo: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web`
- Base commit includes the approved schema package at root commit `6bfa3bc`.
- Existing migration conventions live in `backend/app/migrate.py`; tests commonly monkeypatch `backend.app.database.DB_PATH` and `backend.app.migrate.DB_PATH` to a temporary SQLite file.
- External report data is untrusted text. This task only creates a constrained ledger table; it does not execute or interpret report fields.

## STEP 1 — RED

Create `backend/tests/test_scheduled_inbox_migration.py` with `unittest`. First test a fresh temporary database after `apply_migration()` and assert the table `scheduled_inbox_runs` exists with these exact columns:

- `run_id TEXT PRIMARY KEY`
- `report_kind TEXT NOT NULL`
- `content_hash TEXT NOT NULL`
- `observed_at TEXT NOT NULL`
- `status TEXT NOT NULL` restricted to `IMPORTED|QUARANTINED`
- `finding_count INTEGER NOT NULL DEFAULT 0` and non-negative
- `accepted_count INTEGER NOT NULL DEFAULT 0` and non-negative
- `skipped_count INTEGER NOT NULL DEFAULT 0` and non-negative
- `error_message TEXT`
- `processed_at TEXT NOT NULL`
- `data_origin TEXT NOT NULL DEFAULT 'REAL'` restricted to `REAL|SAMPLE`

Run `uv run python -m unittest backend.tests.test_scheduled_inbox_migration -v` and capture the expected failure because the table is absent.

## STEP 2 — GREEN

Modify only `backend/app/migrate.py` to add the table and indexes justified by planned queries:

- index on `processed_at`;
- index on `status`.

Use existing `CREATE TABLE IF NOT EXISTS` / `CREATE INDEX IF NOT EXISTS` conventions. Do not change or drop any existing table/column/index. Add focused tests proving:

- migration run twice succeeds and preserves a previously inserted ledger row;
- invalid status, negative counts, and invalid `data_origin` are rejected by SQLite constraints;
- a valid row can be inserted and read back;
- all pre-existing business tables remain present.

## STEP 3 — VERIFY + COMMIT

Run:

1. `uv run python -m unittest backend.tests.test_scheduled_inbox_migration -v`
2. `uv run python -m unittest backend.tests.test_importers backend.tests.test_scheduled_inbox_schema -v`
3. `uv run python -m backend.app.migrate` twice, both exit 0
4. `git diff --check`

Commit exactly these two files:

- `backend/app/migrate.py`
- `backend/tests/test_scheduled_inbox_migration.py`

Commit message: `feat: add scheduled inbox run ledger`

Write `.team/results/sri-001b-inbox-migration-report.md` after the commit with `[ĐÃ LÀM]`, `[BẰNG CHỨNG]`, `[RULING]`, `[CÂU HỎI]`. Report exact commands and exit codes.

## Invariants

- Never edit `checks/`, `PLAN.md`, `docs/MISSION.md`, or unrelated dirty files.
- No destructive migration, no fabricated records, no secret, no network, no auto-publish.
- Preserve all existing rows and schema behavior.
- If a command cannot run, mark it `BLOCKED`/`NOT_VERIFIED`; do not claim PASS.
- Narrate at most one line between tool calls.

## Output contract

Finish with changed files, RED evidence, GREEN/regression evidence, migration-twice evidence, commit hash, and unresolved issues.
