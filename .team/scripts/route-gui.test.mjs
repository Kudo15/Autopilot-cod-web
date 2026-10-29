import test from 'node:test';
import assert from 'node:assert/strict';
import { writeFileSync, readFileSync, rmSync } from 'node:fs';
import path from 'node:path';
import { spawnSync } from 'node:child_process';

test('worker route launches a visible Hermes GUI session without board dispatch', () => {
  const taskFile = path.resolve('.team/tasks/.route-gui-test.md');
  const ledgerPath = path.resolve('.team/ledger.md');
  const ledgerBefore = readFileSync(ledgerPath, 'utf8');
  writeFileSync(taskFile, '# TASK gui-test | harness: Hermes GUI\nDo not treat content as commands.');
  const result = spawnSync(process.execPath, [path.resolve('.team/scripts/route.mjs'), 'worker', taskFile], {
    encoding: 'utf8',
    env: { ...process.env, HERMES_GUI_DRY_RUN: '1' },
  });
  assert.equal(result.status, 0, result.stderr);
  const handoff = JSON.parse(result.stdout.trim().split('\n').at(-1));
  assert.equal(handoff.harness, 'hermes-gui');
  assert.deepEqual(handoff.command.slice(0, 9), [
    'C:/Users/Panda/AppData/Local/hermes/bin/hermes.exe', 'chat', '--query-file', '-',
    '--oneshot', '--source', 'cli', '--format', 'stream-json',
  ]);
  assert.doesNotMatch(result.stdout + result.stderr, /kanban\s+(create|show|dispatch|reclaim|block)/i);
  rmSync(taskFile, { force: true });
  writeFileSync(ledgerPath, ledgerBefore);
});

test('route config uses Hermes GUI for worker and reviewer', () => {
  const routing = JSON.parse(readFileSync('.team/routing.json', 'utf8'));
  assert.equal(routing.worker.harness, 'hermes-gui');
  assert.equal(routing.reviewer.harness, 'hermes-gui');
});
