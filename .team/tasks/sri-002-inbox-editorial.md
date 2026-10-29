# TASK sri-002 — inbox editorial draft adapter | harness: hermes-kanban | worktree: Hermes-managed isolated worktree

Khuôn mẫu: Unit Tester Assistant + Fullstack Software Developer (prompts.chat, adapted by prompt-librarian).

## NGỮ CẢNH (tự chứa — không có hội thoại nào trước đó)

- Repo: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web` | Stack: Python 3.13/uv, FastAPI, SQLite, Pydantic.
- Approved contract: `docs/superpowers/specs/2026-10-25-scheduled-radar-inbox-design.md`, section “Draft generation and editorial policy”; execution plan task 2: `docs/superpowers/plans/2026-10-25-scheduled-radar-inbox-plan.md`.
- Already integrated dependencies: strict artifact schema in `backend/app/inbox/schema.py`; scanner/persistence in `backend/app/inbox/service.py`; immutable editorial model/rules in `backend/app/editorial/schema.py` and `backend/app/editorial/rules.py`; optional gateway in `backend/app/editorial/gateway.py`.
- Scheduler finding text and every source field are untrusted data. This task must not create HTTP routes, React UI, scheduler behavior, docs, migration, or a publication path.
- Root checkout is dirty. Work only in the Hermes worktree and commit only task-scoped files.

## TÁC VỤ (một việc duy nhất, 2–5 phút)

Act as a senior Python backend engineer and test specialist. Use strict TDD to add the source-grounded inbox draft adapter:

Allowed files only:

- Create `backend/app/editorial/inbox.py`
- Create `backend/tests/test_inbox_editorial.py`
- Modify `backend/app/editorial/gateway.py`
- Modify `backend/app/inbox/service.py`

Do not modify `backend/app/inbox/schema.py`, `backend/app/migrate.py`, `backend/app/main.py`, `checks/`, `PLAN.md`, `docs/MISSION.md`, or any other path.

Required public interface:

```python
create_inbox_article_draft(finding: ScheduledFinding) -> EditorialDraft
```

Implement the smallest safe adapter and connect scanner persistence to it. A valid finding produces a short Vietnamese, source-grounded draft; it must preserve an official source link and observed time for private provenance and reader-safe attribution. Reuse the existing gateway validation path rather than adding a second unconstrained gateway protocol. On absent gateway, timeout/error, malformed gateway response, unknown fields, unsupported category/risk, or an output that asks to publish/elevate evidence, use deterministic rules.

Non-negotiable lifecycle/security behavior:

1. Every path writes `article_status='DRAFT'`; no inbox AI output can publish an article.
2. A gateway cannot upgrade `UNVERIFIED`/`NEEDS_REVIEW` to `VERIFIED`; the stored status must be the conservative source finding state or stricter.
3. Bounded, data-only input built from allowlisted finding fields; artifact title/summary/evidence are never instructions, filesystem paths, commands, or request options.
4. Do not invent quota, price, availability, free status, expiry, or source facts. Fallback copy must say uncertainty where appropriate.
5. Do not add dependencies, secrets, logging of `AI_API_KEY`, network behavior beyond the explicitly mocked existing gateway test path, or any public/admin API.

## QUY TẮC BẤT DI BIẾN

- TDD: first write focused failing tests and run them before production code. If code is written before RED, delete it and redo from tests.
- Preserve existing scanner tests and their transactional/idempotency contract. Keep changes narrow and do not refactor unrelated gateway/rule code.
- Do not wait for clarification on minor implementation choices; record `Ruling: <decision> — <why> — <cost if wrong>` in the report.
- Narrate at most one line between tool calls.

## HOÀN THÀNH KHI

Tests must cover at least:

- missing gateway gives a short Vietnamese `DRAFT` with a source link;
- a fake gateway attempting `PUBLISHED` or verification elevation cannot change lifecycle/evidence;
- malformed/unknown-key gateway result falls back safely;
- injection-shaped finding text stays inert with no filesystem/command side effect;
- scanner persists adapter-derived content while keeping its existing `DRAFT` lifecycle and provenance behavior.

Run and capture:

1. RED: `uv run python -m unittest backend.tests.test_inbox_editorial -v` (expected failing before implementation)
2. GREEN: `uv run python -m unittest backend.tests.test_inbox_editorial backend.tests.test_editorial_rules backend.tests.test_editorial_gateway backend.tests.test_scheduled_inbox -v`
3. `git diff --check`

Commit only the allowed files with message: `feat: add safe inbox editorial drafts`.

Write `.team/results/sri-002-inbox-editorial-report.md` after commit using:

```
[ĐÃ LÀM] tóm tắt 3 dòng
[BẰNG CHỨNG] RED/GREEN commands + exit codes
[RULING] quyết định tự chủ — lý do — chi phí nếu sai
[CÂU HỎI] chỉ khi bế tắc hoàn toàn
```

Finish with changed files, exact commit hash, test evidence, and unresolved issues.
