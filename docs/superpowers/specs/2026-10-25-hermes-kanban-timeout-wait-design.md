# Hermes Kanban timeout and coordinator wait design

## Intent

Prevent a Hermes Kanban card from appearing healthy indefinitely while an upstream model emits a never-ending trickle stream, and prevent the Codex coordinator from ending its turn immediately after dispatch. The policy must be global for Hermes-routed workers/reviewers; individual task packs do not pin models or timeout values.

## Goals

- A silent provider stream becomes an error after 120 seconds and can enter the configured Hermes fallback chain.
- Any single FreeLLMAPI streaming request has a 300-second wall-clock ceiling even if chunks continue arriving.
- A Kanban card has a 20-minute final runtime ceiling.
- Codex waits for the dispatched card to reach a terminal state and reports useful progress, rather than treating `running` as completion.
- Heartbeats alone do not count as implementation progress.

## Non-goals

- Do not change the configured main model or fallback order.
- Do not pin a model/provider on individual cards.
- Do not deploy the Vũ Học AI website or expose a local port publicly.
- Do not patch installed Hermes source unless the gateway cannot provide a total stream deadline and the user separately approves that fallback approach.

## Selected approach

### 1. Hermes provider policy

Set the supported provider-level values globally:

```yaml
providers:
  freellmapi:
    request_timeout_seconds: 120
    stale_timeout_seconds: 120
  cliproxyapipcnha:
    request_timeout_seconds: 120
    stale_timeout_seconds: 120
agent:
  api_max_retries: 1
```

`request_timeout_seconds` limits socket read silence; `stale_timeout_seconds` explicitly overrides context/reasoning timeout floors when no real chunk arrives. Neither is treated as a total inference deadline.

### 2. FreeLLMAPI total stream deadline

At the owner-controlled `free.vuhocai.shop` gateway, enforce a 300-second deadline from upstream request start to terminal completion. The deadline must not reset on chunk receipt. On expiry, abort the upstream stream and return/propagate a timeout classified as HTTP 504 (or the gateway's equivalent retryable timeout) so Hermes can activate its existing fallback providers.

This repository does not contain or identify the production gateway source/config. Implementation of this item requires the exact gateway project or runtime configuration. No production mutation is authorized by this design alone; configure and verify it in its own project, then deploy only after explicit deployment approval.

### 3. Kanban runtime policy

Change the worker and reviewer routing defaults from `2h`/unbounded to `20m`, while preserving Hermes Main + Fallback inheritance. Card timeout is the final safety boundary; it is not a substitute for provider fallback.

### 4. Coordinator wait mode

Extend `.team/scripts/route.mjs` with an explicit `--wait` mode used by project dispatches:

- Dispatch the created card, then poll it every 30 seconds.
- Keep the command/session alive until `done`, `blocked`, `failed`, `cancelled`, or `timed_out`.
- Emit a compact update no more than once per 60 seconds.
- Track meaningful progress using card events/session message count/tool-call count and worktree HEAD/status changes. A heartbeat by itself is not progress.
- If there is no meaningful progress for 8 minutes, reclaim once with an evidence-based reason.
- If the same no-progress condition recurs after reclaim, block the card and return a non-zero result; do not create unlimited replacement runs.
- Preserve the created task ID and terminal summary in machine-readable output so Codex can review/integrate the exact result.
- `--wait` must remain optional for manual fire-and-forget use, but project coordinator task packs use it by default.

## Failure handling

```text
provider silent >120s
        -> Hermes timeout/retry policy
provider emits chunks but exceeds 300s total
        -> gateway aborts with retryable timeout
        -> Hermes activates fallback
card still non-terminal at 20m
        -> Kanban runtime timeout
no tools/messages/files for 8m
        -> coordinator reclaims once
same condition repeats
        -> BLOCKED with evidence
```

## Verification

- Read back Hermes runtime timeout values through the installed Hermes loader.
- Add route-script tests using a fake Hermes executable/card-state sequence: normal completion, fallback-like delayed completion, one reclaim then success, repeated no-progress block, and terminal failure propagation.
- Verify `--wait` does not return while the fake card is `running`.
- Verify heartbeat-only fixtures do not reset the meaningful-progress timer.
- Verify routing-created cards contain no model/provider override and a 20-minute max runtime.
- Gateway project: add an integration test with an upstream stream that emits periodic chunks beyond 300 seconds (using a shortened test deadline) and assert the gateway terminates it with the agreed timeout classification.

## Approaches considered

- **Operational card timeout only:** cheapest, but does not trigger provider fallback and can discard useful work.
- **Gateway total deadline + coordinator wait (selected):** works with existing Hermes fallback semantics and avoids per-task configuration.
- **Patch Hermes with a total-stream watchdog:** technically direct but creates a locally maintained fork and update risk; reserved only if gateway enforcement is unavailable.

## Constraints and rollout

- First apply and test Hermes config and local routing changes.
- The currently stalled card is reclaimed only after the local wait/runtime safeguards are ready.
- Gateway changes happen in the gateway's own project and are tested before any production deployment.
- No website deployment, Git push, remote configuration change, or production restart is included without separate authorization.
