const SUCCESS_STATES = new Set(['done', 'completed']);
const FAILURE_STATES = new Set(['blocked', 'failed', 'cancelled', 'timed_out']);

export function defaultProgressKey(snapshot) {
  const task = snapshot?.task;
  const events = Array.isArray(snapshot?.events) ? snapshot.events : [];
  const meaningfulEvents = events
    .filter(event => event?.kind !== 'heartbeat')
    .map(event => [event?.kind, event?.run_id, event?.created_at]);
  const runs = Array.isArray(snapshot?.runs) ? snapshot.runs : [];
  return JSON.stringify({
    status: task?.status,
    result: task?.result ?? snapshot?.latest_summary ?? null,
    meaningfulEvents,
    runs: runs.map(run => [run?.id, run?.status, run?.outcome, run?.summary, run?.ended_at]),
    external: snapshot?.progressKey ?? null,
    session: snapshot?.sessionProgress ?? null,
  });
}

function validateSnapshot(snapshot, taskId) {
  if (!snapshot || typeof snapshot !== 'object' || !snapshot.task || snapshot.task.id !== taskId
      || typeof snapshot.task.status !== 'string') {
    throw new Error(`Invalid kanban show result for ${taskId}`);
  }
}

function terminalSummary(snapshot) {
  return snapshot.latest_summary ?? snapshot.task.result ?? null;
}

export async function waitForKanbanTask(options) {
  const {
    taskId,
    show,
    dispatch,
    reclaim,
    block,
    sleep,
    now,
    report = () => {},
    progressKey = defaultProgressKey,
    pollMs = 30_000,
    stallMs = 480_000,
    reportMs = 60_000,
  } = options;
  if (!taskId || !show || !dispatch || !reclaim || !block || !sleep || !now) {
    throw new Error('waitForKanbanTask requires taskId and all Kanban operations');
  }

  const startedAt = now();
  let lastProgressAt = startedAt;
  let lastReportAt = startedAt - reportMs;
  let priorKey;
  let reclaims = 0;

  for (;;) {
    const snapshot = await show(taskId);
    validateSnapshot(snapshot, taskId);
    const status = snapshot.task.status;
    const currentKey = progressKey(snapshot);
    if (priorKey === undefined || currentKey !== priorKey) {
      priorKey = currentKey;
      lastProgressAt = now();
    }

    if (SUCCESS_STATES.has(status)) {
      return {
        taskId,
        status,
        summary: terminalSummary(snapshot),
        reclaims,
        elapsedMs: now() - startedAt,
      };
    }
    if (FAILURE_STATES.has(status)) {
      const error = new Error(`Kanban task ${taskId} ended with ${status}`);
      error.result = { taskId, status, summary: terminalSummary(snapshot), reclaims, elapsedMs: now() - startedAt };
      throw error;
    }

    if (now() - lastReportAt >= reportMs) {
      report({ taskId, status, reclaims, elapsedMs: now() - startedAt, idleMs: now() - lastProgressAt });
      lastReportAt = now();
    }

    if (now() - lastProgressAt >= stallMs) {
      const reason = `No meaningful message/tool/worktree progress for ${Math.round(stallMs / 60_000)} minutes; heartbeat-only activity does not count`;
      if (reclaims === 0) {
        await reclaim(taskId, reason);
        reclaims = 1;
        await dispatch(taskId);
        priorKey = undefined;
        lastProgressAt = now();
      } else {
        await block(taskId, `Repeated no-progress after one reclaim: ${reason}`);
        throw new Error(`Kanban task ${taskId} blocked after repeated no-progress`);
      }
    }

    await sleep(pollMs);
  }
}
