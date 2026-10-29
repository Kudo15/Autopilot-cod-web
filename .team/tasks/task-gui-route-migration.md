# TASK gui-route-migration — route workers through Hermes GUI | harness: Hermes GUI | worktree: current project worktree

## NGỮ CẢNH

- Project: `D:\anhvuxd_2026\VUHOCAI\Project\Autopilot cod web`.
- Current dispatch is `.team/scripts/route.mjs`; it creates and waits on `hermes kanban` cards for `worker` and `reviewer`.
- Reference only: `D:\anhvuxd_2026\VUHOCAI\Project\Vu-Agent-Room-PC` demonstrates the GUI-visible Hermes invocation `hermes chat --query-file - --oneshot --source cli --format stream-json`.
- The user explicitly requires: workers in this project must launch Hermes GUI sessions directly, never through Kanban and without modifying the reference project.
- The root checkout is dirty. Change only the allowed route/config/test files and keep all existing product changes untouched.

## TÁC VỤ

Act as an IT Architect and senior test automation engineer. Design and implement the smallest maintainable adapter that makes `.team/scripts/route.mjs worker|reviewer <task-pack>` launch a GUI-visible Hermes session and never call `hermes kanban`. Use the architectural integration pattern from the IT Architect prompt and the explicit-evidence/test discipline from the Unit Tester Assistant and Code Review Agent patterns.

The adapter must:

1. Launch Hermes with `chat --query-file - --oneshot --source cli --format stream-json`, passing the task pack through stdin and using the current project as cwd. Do not expose secrets in arguments/logs.
2. Keep the process detached so the session is visible in Hermes GUI while the coordinator receives an immediate handoff; capture JSONL output under `.team/results/`.
3. Return a stable JSON/text handoff containing task id, PID, GUI source, workspace and output path; append a ledger line with `harness:hermes-gui`.
5. Remove the Kanban execution path from this route. `route.mjs`, its helper modules and routing configuration must contain no executable `kanban create/show/dispatch/reclaim/block` calls. Historical ledger/task text may mention old runs, but the new route must not.
6. Preserve a clearly documented `--direct` diagnostic only if it invokes Hermes CLI directly and is never selected by default; it must not silently fall back to Kanban.

Use TDD: first add a focused test that fails because the current route calls Kanban, then implement the adapter, then test success/error paths with a temporary Room fixture or mocked subprocess. Do not run real product workers from the test. Keep the GUI startup bounded and localhost-only.

## FILES_ALLOWED

- `.team/routing.json`
- `.team/scripts/route.mjs`
- `.team/scripts/route-gui.test.mjs` (new focused test)
- `.team/tasks/task-gui-route-migration.md` only for a factual test-command correction
- `.team/ledger.md` only for the completion line
- Do not edit `checks/`, `PLAN.md`, `docs/MISSION.md`, frontend/backend product code, or the reference project.

## VERIFY

- Focused RED test fails on the pre-change Kanban route and passes after the change.
- `node --test .team/scripts/route-gui.test.mjs` and any Python helper test pass with exact counts.
- A dry-run proves the exact GUI Hermes command and never invokes a command containing `kanban`.
- `node .team/scripts/route.mjs worker .team/tasks/task-gui-route-migration.md` (or an equivalent safe smoke with `HERMES_BIN`) returns a GUI session handoff; do not claim completion unless the Hermes process is launched.
- `git diff --check` passes and only allowed paths changed.

## BÁO CÁO

```
[ĐÃ LÀM] tóm tắt 3 dòng
[BẰNG CHỨNG] lệnh + exit code + Room task id/GUI URL nếu có
[RULING] quyết định tự chủ — nếu có
[CÂU HỎI] chỉ khi bế tắc hoàn toàn
```
