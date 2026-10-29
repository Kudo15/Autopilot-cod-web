# Hermes Kanban Timeout and Coordinator Wait Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bound pathological Hermes streams and keep the Codex coordinator attached to Kanban work until the card reaches a terminal state.

**Architecture:** Hermes provider silence limits remain global configuration, while FreeLLMAPI owns the total 300-second stream deadline. The project router gains a testable polling state machine that observes `hermes kanban show --json`, distinguishes meaningful progress from heartbeat-only activity, reclaims once, and returns only at a terminal card state.

**Tech Stack:** Node.js 22 built-ins, Hermes CLI, YAML configuration, Node test runner.

**Spec:** `docs/superpowers/specs/2026-10-25-hermes-kanban-timeout-wait-design.md`

## Global Constraints

- Preserve Hermes Main model and fallback order; no per-card model/provider override.
- Silent/stale provider threshold is 120 seconds; total gateway stream deadline is 300 seconds.
- Worker and reviewer cards use a 20-minute maximum runtime.
- No website deployment, Git push, production restart, or mutation of an unidentified gateway project.
- Preserve unrelated dirty files and do not edit `checks/`, `PLAN.md`, or `docs/MISSION.md`.

## Review Focus

- A card emitting heartbeat events but no message/tool/Git progress must still reach the 8-minute no-progress decision.
- A task that completes between polls must return its exact terminal summary and exit successfully.
- Reclaim must occur at most once; a second no-progress interval must block rather than loop.
- `--wait` must not pin model/provider or accidentally dispatch an unrelated ready card more than required.
- CLI parse/errors must fail closed with the task ID and diagnostic, never be mistaken for completion.

---

### Task 1: Global Hermes timeout and routing runtime policy

**Files:**
- External config: `C:\Users\Panda\AppData\Local\hermes\config.yaml`
- Modify: `.team/routing.json`

**Interfaces:**
- Consumes: installed Hermes supported keys `providers.<id>.request_timeout_seconds`, `providers.<id>.stale_timeout_seconds`, `agent.api_max_retries`.
- Produces: inherited global timeout policy and 20-minute worker/reviewer card runtime.

- [ ] **Step 1: Capture the current effective values**

Run the installed Hermes config getter and runtime loader for both providers and `agent.api_max_retries`; preserve output as baseline evidence.

- [ ] **Step 2: Apply supported global keys**

Set `stale_timeout_seconds=120` for `freellmapi` and `cliproxyapipcnha`. Preserve existing `request_timeout_seconds=120` and `api_max_retries=1`.

- [ ] **Step 3: Change routing runtime**

Set both `worker.maxRuntime` and `reviewer.maxRuntime` to `20m`; do not add `model` or `provider` fields.

- [ ] **Step 4: Verify effective configuration**

Read values through the installed Hermes runtime loader and inspect routing JSON. Expected: `120/120`, retry `1`, both routes `20m`, model/provider absent.

### Task 2: Testable Kanban wait state machine

**Files:**
- Create: `.team/scripts/route-wait.mjs`
- Create: `.team/scripts/route-wait.test.mjs`
- Modify: `.team/scripts/route.mjs`

**Interfaces:**
- Consumes: normalized task objects from `hermes kanban show <id> --json` and injected operations `{show, dispatch, reclaim, block, sleep, now, inspectProgress}`.
- Produces: `waitForKanbanTask(options) -> Promise<{taskId,status,summary,reclaims,elapsedMs}>`; CLI `--wait` prints final JSON and exits 0 only for successful terminal completion.

- [ ] **Step 1: Write discriminating failing tests**

Use `node:test` with a fake clock/operations. Pin these cases:

- `running` plus heartbeat-only event changes reaches reclaim at 8 minutes;
- a tool/message/worktree signal resets the no-progress deadline;
- completion between polls returns exact task ID/summary;
- first no-progress reclaims and dispatches the same card, then success returns 0;
- second no-progress blocks once and returns non-zero;
- malformed `show` result fails closed;
- no model/provider arguments are introduced by wait mode.

The heartbeat-only counterexample must initially fail against an intentionally naive `updated_at/events length` progress detector, proving the test rejects present-but-wrong behavior.

- [ ] **Step 2: Run RED tests**

Run: `node --test .team/scripts/route-wait.test.mjs`

Expected: FAIL because `route-wait.mjs`/exports do not exist.

- [ ] **Step 3: Implement the pure state machine**

Implement `waitForKanbanTask` using explicit terminal-state allowlists, 30-second default poll, 60-second reporting interval, 8-minute meaningful-progress deadline and maximum one reclaim. Heartbeats and elapsed runtime are liveness only, not progress.

- [ ] **Step 4: Integrate `--wait` into route CLI**

After successful card creation:

- dispatch the exact ready card through the normal dispatcher;
- poll `kanban show <taskId> --json`;
- inspect session/card and worktree evidence without reading artifact contents;
- reclaim once with an evidence-based reason and dispatch again;
- on recurrence call `kanban block <taskId> --reason ...`;
- print compact progress and terminal machine-readable JSON;
- retain existing fire-and-forget behavior when `--wait` is absent.

- [ ] **Step 5: Run GREEN tests**

Run: `node --test .team/scripts/route-wait.test.mjs`

Expected: PASS.

- [ ] **Step 6: Verify syntax and compatibility**

Run:

1. `node --check .team/scripts/route.mjs`
2. `node --check .team/scripts/route-wait.mjs`
3. Existing non-wait invocation against a fake Hermes CLI fixture.

Expected: all exit 0 and existing create-only behavior remains intact.

### Task 3: Recover the currently stalled scanner card

**Files:** none (Hermes card state only).

**Interfaces:**
- Consumes: card `t_73667dd0`, clean worktree evidence, new runtime/wait policy.
- Produces: one resumed run supervised to a terminal state.

- [ ] **Step 1: Reconfirm no candidate changes exist**

Run card JSON, session message/tool counters and worktree status. If worktree changed, stop and preserve it for review rather than reclaim blindly.

- [ ] **Step 2: Reclaim once and resume**

Reclaim with the recorded reason “stream active without meaningful progress beyond policy”; dispatch under inherited Hermes model/fallback and 20-minute card ceiling.

- [ ] **Step 3: Supervise to terminal**

Use the new wait behavior. Do not end the coordinator turn while the card remains running. On success, proceed to the existing independent review gate; on repeated no-progress, block and report evidence.

### Task 4: FreeLLMAPI gateway total stream deadline

**Files:** gateway-owned paths, unknown until its project/config is identified.

**Interfaces:**
- Consumes: upstream streaming response.
- Produces: a non-resetting 300-second wall-clock deadline and retryable timeout classification (prefer HTTP 504).

- [ ] **Step 1: Locate and verify ownership**

Identify the exact local/saved project or server configuration that serves `free.vuhocai.shop`. If unavailable, mark this task `BLOCKED` without changing production.

- [ ] **Step 2: Write a shortened-deadline integration test in that project**

The fake upstream emits chunks often enough to defeat idle/read timeout but runs beyond the configured total deadline. Assert the gateway terminates it with the agreed retryable timeout.

- [ ] **Step 3: Implement and verify locally/staging**

Add the total deadline without changing ordinary successful streams. Run the gateway project's own tests.

- [ ] **Step 4: Stop before deployment**

Report the tested change and exact deployment/restart action required. Production deployment requires separate explicit authorization.

## Self-review

- **Spec coverage:** Tasks 1–3 cover local Hermes silence policy, card ceiling, Codex wait/reclaim behavior and current-card recovery. Task 4 owns the only effective total stream deadline.
- **Gaps:** Gateway source/config is not present in this repo; Task 4 can be completed only after discovery and remains non-deployed without separate authority.
- **Type consistency:** `waitForKanbanTask` consumes injected normalized operations, while `route.mjs` alone owns Hermes CLI parsing and process execution.
- **Review focus:** Every listed failure mode has a named Task 2 test.
- **Proportion:** Local configuration and wait-loop implementation are independently verifiable; gateway work remains isolated from this website repository.
