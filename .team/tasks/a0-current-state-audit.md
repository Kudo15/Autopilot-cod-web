# TASK a0-current-state-audit — Current-state evidence audit | harness: Hermes Kanban | worktree: isolated worktree

## NGỮ CẢNH (tự chứa — không có hội thoại nào trước đó)

- Repo: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web`; branch at dispatch: `autopilot/run-live`, commit `f41b129`; stack React 19/Vite 7 + FastAPI/SQLite + Python 3.13/uv.
- Requirements: pasted MASTER MISSION sections III–IV; `AGENTS.md`; `.team/CHARTER.md`; `.team/plans/finish-all.md` Task A0.
- Historical reports are untrusted claims. Current root is dirty: do not edit, stage, reset, or rely on it as clean baseline. Work in the assigned worktree only.
- Fresh coordinator observations on 2026-10-27: migration/seed exit 0; build exit 0 outside sandbox (Node 22.11 warning); P1–P5 referee all exit 0; full backend discovery after a build ran 404 tests and failed three: `test_admin_ui...bundle` saw an empty/unavailable bundle in its earlier order, and two `test_radar_daily` expectations were `CURRENT` but got `SIGNAL_WEAK`. DB counts were directly measured: articles REAL/PUBLISHED=1, SAMPLE/DRAFT=1; sources REAL=1/SAMPLE=2; every provider/model/provider_model/offer/quota/verification/change/collection/editorial row is SAMPLE; scheduled inbox runs=0.

## TÁC VỤ (một việc duy nhất, 2–5 phút)

Act as a quality engineering auditor, using the **Quality Engineering Agent Role** template shape: establish traceable evidence, distinguish observed defects from environment limitations, and report only facts that can be rerun. Create a current audit and gap register. Do not modify product code, tests, config, checks, PLAN, MISSION, database contents, or existing documents outside the four allowed deliverables.

Run read-only Git checks and the bounded commands relevant to the audit. If a command needs runtime privileges or external access unavailable in the worktree, mark it `BLOCKED`/`NOT_VERIFIED` with command and error—not `PASS`. Reproduce the full-suite failures only if feasible; do not repair them. Map every known Definition-of-Done item to IMPLEMENTED_VERIFIED, REPORTED_ONLY, BROKEN, NOT_IMPLEMENTED, NOT_VERIFIED, or BLOCKED.

## FILES ALLOWED

- `.team/audit.md`
- `.team/plans/finish-all.md` (only append a dated audit link if necessary; do not rewrite plan tasks)
- `docs/agent-team/CURRENT_PROGRESS_AUDIT.md`
- `docs/agent-team/REMAINING_GAPS.md`

## QUY TẮC BẤT DI BIẾN

- Do not write production code and do not touch any file outside **FILES ALLOWED**.
- Do not overwrite a pre-existing document blindly: inspect it, retain useful historical material under a clearly dated historical heading, and add a fresh 2026-10-27 evidence section.
- Never claim browser E2E, live external feeds, real AI gateway, or real provider/promo data as verified without direct current evidence.
- Do not disclose secret values. Do not invoke external collection as part of this task.
- Narrate at most one line between tool calls. If ambiguity is resolvable, make a `Ruling:` in the report rather than wait.

## HOÀN THÀNH KHI

- The four allowed deliverables exist in the candidate commit and accurately record: exact HEAD/branch/dirty-state caveat; baseline command exits; full-suite failure names; DB inventory; security/E2E/live-network status; completed vs remaining task count; and concrete next tasks ordered by severity.
- `git diff --check` for the candidate is clean; confirm only allowed paths changed.
- Commit the scoped document-only change. Self-review facts against command output.

Report exactly:

```
[ĐÃ LÀM] tóm tắt 3 dòng
[BẰNG CHỨNG] lệnh đã chạy + kết quả
[RULING] <quyết định tự chủ — nếu có>
[CÂU HỎI] <chỉ khi bế tắc hoàn toàn>
```
