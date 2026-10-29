# TASK 008 — P7 Explorer responsive UI | harness: hermes-kanban | worktree: D:\\anhvuxd_2026\\VUHOCAI\\Project\\Autopilot cod web

## NGỮ CẢNH

P7 public `GET /api/models` is integrated and independently approved. Build the dependent frontend view without embedding provider/model claims. The live database may correctly return an empty list because only SAMPLE provider rows exist; the UI must explain that state rather than inventing cards.

Use the frontend implementation/test pattern: preserve loading/empty/error behavior, render untrusted API text as React text nodes, and keep compare selection local to the session. Do not introduce a new UI dependency or a test runner.

## CONTRACT

When the active group is `free-model-explorer`, call `/api/models` and render:

- model name + provider name, API model id when present;
- free status, quota/rate limit, context and capability values as returned;
- verification status with `UNKNOWN`/`UNVERIFIED`/NULL visibly labeled, never upgraded to a fact;
- official URL as a safe external CTA (`target="_blank"`, `rel="noreferrer"`) when present;
- filter controls for free status/provider/card requirement/capability and a local compare toggle;
- loading, empty and error/retry states matching the existing shell.

Do not put provider/model seed data in `src/`; do not render `raw_content`, provenance, API base URLs, admin notes or secrets. Non-Explorer groups keep the article feed behavior.

## FILES_ALLOWED

- `src/App.jsx`
- `src/components/GroupView.jsx`
- `src/components/ExplorerView.jsx` (new) and narrowly related `src/components/**` only.
- `src/styles.css`
- `src/data/groups.js` only if the existing group id/name is insufficient.
- No changes to `checks/`, `PLAN.md`, `docs/MISSION.md`, backend files or package dependencies.

## VERIFY

- Exercise static/source checks for `/api/models`, loading/empty/error, unverified labeling, compare selection and safe CTA.
- `npm run build` → exit 0.
- Verify bundle has no API key/secret/provenance/registry strings and no embedded provider/model claims.
- `git diff --check` → exit 0.
- Commit only task-scoped files and report exact commands and exit codes; browser DOM smoke is NOT_VERIFIED if browser tooling is unavailable.

## REPORT

```
[ĐÃ LÀM]
[BẰNG CHỨNG]
[RULING]
[CÂU HỎI]
```
