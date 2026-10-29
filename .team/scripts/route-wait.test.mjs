import test from 'node:test';
import assert from 'node:assert/strict';

import { defaultProgressKey, waitForKanbanTask } from './route-wait.mjs';

function harness(states, { stallMs = 480_000 } = {}) {
  let now = 0;
  let index = 0;
  const calls = [];
  return {
    calls,
    options: {
      taskId: 't_test',
      pollMs: 60_000,
      stallMs,
      reportMs: 60_000,
      now: () => now,
      sleep: async ms => { now += ms; },
      show: async () => states[Math.min(index++, states.length - 1)],
      dispatch: async id => calls.push(['dispatch', id]),
      reclaim: async (id, reason) => calls.push(['reclaim', id, reason]),
      block: async (id, reason) => calls.push(['block', id, reason]),
      report: info => calls.push(['report', info.status]),
    },
  };
}

const running = (progressKey = 'base', heartbeat = 0) => ({
  task: { id: 't_test', status: 'running' },
  latest_summary: null,
  progressKey,
  events: [{ kind: 'heartbeat', created_at: heartbeat }],
});

test('heartbeat-only activity reclaims once after the meaningful-progress deadline', async () => {
  const states = Array.from({ length: 10 }, (_, i) => running('base', i));
  states.push({ task: { id: 't_test', status: 'done', result: 'ok' }, latest_summary: 'ok', progressKey: 'done' });
  const h = harness(states);

  const result = await waitForKanbanTask(h.options);

  assert.equal(result.status, 'done');
  assert.equal(result.reclaims, 1);
  assert.equal(h.calls.filter(([name]) => name === 'reclaim').length, 1);
});

test('meaningful tool or worktree progress resets the no-progress deadline', async () => {
  const states = [
    ...Array.from({ length: 7 }, (_, i) => running('base', i)),
    running('tool-call-1', 7),
    ...Array.from({ length: 3 }, (_, i) => running('tool-call-1', i + 8)),
    { task: { id: 't_test', status: 'done', result: 'finished' }, latest_summary: 'finished', progressKey: 'done' },
  ];
  const h = harness(states);

  const result = await waitForKanbanTask(h.options);

  assert.equal(result.status, 'done');
  assert.equal(result.reclaims, 0);
});

test('session message or tool activity is meaningful progress', () => {
  const before = running('same-worktree', 1);
  const after = running('same-worktree', 2);
  before.sessionProgress = { messageId: 10, timestamp: 100 };
  after.sessionProgress = { messageId: 11, timestamp: 101 };

  assert.notEqual(defaultProgressKey(before), defaultProgressKey(after));
});

test('completion returns the exact task id and summary', async () => {
  const h = harness([{ task: { id: 't_test', status: 'done', result: 'exact result' }, latest_summary: 'exact summary', progressKey: 'done' }]);
  const result = await waitForKanbanTask(h.options);
  assert.deepEqual({ taskId: result.taskId, status: result.status, summary: result.summary }, {
    taskId: 't_test', status: 'done', summary: 'exact summary',
  });
});

test('one reclaim can resume and complete the same card', async () => {
  const states = [
    ...Array.from({ length: 10 }, (_, i) => running('base', i)),
    { task: { id: 't_test', status: 'ready' }, progressKey: 'reclaimed' },
    running('new-run', 11),
    { task: { id: 't_test', status: 'done', result: 'recovered' }, latest_summary: 'recovered', progressKey: 'done' },
  ];
  const h = harness(states);
  const result = await waitForKanbanTask(h.options);
  assert.equal(result.status, 'done');
  assert.equal(result.reclaims, 1);
  assert.deepEqual(h.calls.filter(([name]) => name === 'dispatch'), [['dispatch', 't_test']]);
});

test('a second no-progress interval blocks instead of reclaiming forever', async () => {
  const states = Array.from({ length: 20 }, (_, i) => running(i < 10 ? 'run-1' : 'run-2', i));
  const h = harness(states);

  await assert.rejects(waitForKanbanTask(h.options), /blocked after repeated no-progress/i);
  assert.equal(h.calls.filter(([name]) => name === 'reclaim').length, 1);
  assert.equal(h.calls.filter(([name]) => name === 'block').length, 1);
});

test('malformed show output fails closed', async () => {
  const h = harness([{ nope: true }]);
  await assert.rejects(waitForKanbanTask(h.options), /invalid kanban show result/i);
  assert.equal(h.calls.some(([name]) => name === 'reclaim'), false);
});
