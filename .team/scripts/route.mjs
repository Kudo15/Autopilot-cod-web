#!/usr/bin/env node
// route.mjs — định tuyến task pack tới harness/model theo .team/routing.json.
// Worker/reviewer tasks launch visible Hermes GUI sessions directly.
//
// Dùng (coordinator gọi từ thư mục dự án):
//   node .team/scripts/route.mjs <role> .team/tasks/<id>.md           # launch visible Hermes GUI session
//   node .team/scripts/route.mjs <role> .team/tasks/<id>.md --wait    # launch GUI session and return handoff
//   node .team/scripts/route.mjs <role> .team/tasks/<id>.md --direct  # one-shot hermes -z tại chỗ (diagnostic)
//
// routing.json là bảng vai → harness/model/provider/profile. Xem references/routing.json của skill agent-team.

import { readFileSync, writeFileSync, mkdirSync, appendFileSync, existsSync, openSync } from 'node:fs';
import { spawn, spawnSync } from 'node:child_process';
import path from 'node:path';

const argv = process.argv.slice(2);
const direct = argv.includes('--direct');
const wait = argv.includes('--wait');
const pos = argv.filter(a => !a.startsWith('--'));
const [role, taskFile] = pos;
if (!role || !taskFile) {
  console.error('Dùng: node route.mjs <role> <task-pack.md> [--direct|--wait]');
  process.exit(2);
}
if (!existsSync(taskFile)) {
  console.error('Không thấy task pack: ' + taskFile);
  process.exit(2);
}

const teamRoot = path.dirname(path.dirname(path.resolve(taskFile))); // .../.team
const routingPath = path.join(teamRoot, 'routing.json');
if (!existsSync(routingPath)) {
  console.error('Thiếu ' + routingPath + ' — copy template từ skill agent-team rồi điền model.');
  process.exit(2);
}
const routing = JSON.parse(readFileSync(routingPath, 'utf8'));
const roleRoute = (routing.roles || routing)[role];
if (!roleRoute) {
  console.error(`routing.json chưa định nghĩa role "${role}".`);
  process.exit(2);
}
const codexDefaults = routing.codex || {};
const isCodex = (roleRoute.harness || 'hermes-gui') === 'codex-internal';
const r = isCodex
  ? {
      ...roleRoute,
      model: roleRoute.model || codexDefaults.model,
      effort: roleRoute.effort || codexDefaults.effort,
      reasoning: roleRoute.reasoning || codexDefaults.effort,
    }
  : roleRoute;

if (isCodex && (!r.model || !r.effort)) {
  console.error('routing.json thiếu codex.model hoặc codex.effort cho role Codex.');
  process.exit(2);
}

const body = readFileSync(taskFile, 'utf8');
const id = (body.match(/^#\s*TASK\s+(\S+)/m) || [, path.basename(taskFile, '.md')])[1];
const title = (body.match(/^#\s*TASK\s+(.+?)(?:\s*\||$)/m) || [, id])[1].trim();
const ledger = path.join(teamRoot, 'ledger.md');
if (!existsSync(ledger)) writeFileSync(ledger, '# Ledger\n');
const stamp = new Date().toISOString();

function runHermes(args) {
  const candidates = [
    process.env.HERMES_BIN,
    'hermes',
    'C:/Users/Panda/AppData/Local/hermes/hermes-agent/venv/Scripts/hermes.exe',
  ].filter(Boolean);
  let lastErr;
  for (const bin of candidates) {
    const res = spawnSync(bin, args, { encoding: 'utf8', windowsHide: true });
    if (res.error && res.error.code === 'ENOENT') { lastErr = res.error; continue; }
    return { bin, ...res };
  }
  throw lastErr || new Error('Không tìm thấy hermes CLI (đặt HERMES_BIN để override)');
}

function runCodex(args) {
  const candidates = [
    process.env.CODEX_BIN,
    'codex',
  ].filter(Boolean);
  let lastErr;
  for (const bin of candidates) {
    const res = spawnSync(bin, args, { encoding: 'utf8', windowsHide: true });
    if (res.error && res.error.code === 'ENOENT') { lastErr = res.error; continue; }
    return { bin, ...res };
  }
  throw lastErr || new Error('Không tìm thấy codex CLI (đặt CODEX_BIN để override)');
}

function hermesBinary() {
  return process.env.HERMES_BIN || 'C:/Users/Panda/AppData/Local/hermes/bin/hermes.exe';
}

function launchHermesGui() {
  const resultsDir = path.join(teamRoot, 'results');
  mkdirSync(resultsDir, { recursive: true });
  const outputFile = path.join(resultsDir, `${id}.hermes-gui.jsonl`);
  const args = [
    'chat', '--query-file', '-', '--oneshot', '--source', 'cli', '--format', 'stream-json',
  ];
  if (r.model) args.push('--model', r.model);
  if (r.toolsets) args.push('--toolsets', r.toolsets);
  if (process.env.HERMES_GUI_DRY_RUN === '1') {
    return { ok: true, harness: 'hermes-gui', role, task: id, command: [hermesBinary(), ...args], workspace: process.cwd(), output: outputFile, dry_run: true };
  }
  const output = openSync(outputFile, 'a');
  const child = spawn(hermesBinary(), args, {
    cwd: process.cwd(), detached: true, windowsHide: false,
    stdio: ['pipe', output, output],
  });
  const prompt = `[Vũ Học AI | task=${id} | role=${role} | title=${title}]\n${body}`;
  child.stdin.end(prompt, 'utf8');
  child.unref();
  return {
    ok: true, harness: 'hermes-gui', role, task: id, pid: child.pid,
    gui_source: 'Hermes GUI session (source=cli)', workspace: process.cwd(), output: outputFile,
  };
}

if (!direct && (r.harness || 'hermes-gui') === 'hermes-gui') {
  const handoff = launchHermesGui();
  appendFileSync(ledger, `\nTask ${id} — role:${role} — harness:hermes-gui — source:cli — pid:${handoff.pid ?? 'dry-run'} — ${stamp}\n`);
  console.log(JSON.stringify(handoff));
} else if (isCodex) {
  // Codex route: GUI dùng cùng routing.json, CLI chạy codex exec với cùng model/effort.
  mkdirSync(path.join(teamRoot, 'results'), { recursive: true });
  const resultFile = path.join(teamRoot, 'results', `${id}.md`);
  const args = [
    'exec',
    '--model', r.model,
    '--config', `model_reasoning_effort="${r.effort}"`,
    '--cd', process.cwd(),
    '--output-last-message', resultFile,
    body,
  ];
  const res = runCodex(args);
  appendFileSync(ledger, `\nTask ${id} — role:${role} — harness:codex-exec — model:${r.model} — effort:${r.effort} — ${stamp}\n`);
  console.log(res.stdout || res.stderr);
  if (res.status !== 0) process.exit(res.status ?? 1);
} else {
  // Nhánh direct: one-shot hermes -z — chạy ngay, ghi kết quả + báo cáo usage (token/tiền).
  mkdirSync(path.join(teamRoot, 'results'), { recursive: true });
  mkdirSync(path.join(teamRoot, 'usage'), { recursive: true });
  const usageFile = path.join(teamRoot, 'usage', `${id}.json`);
  const args = ['-z', body, '--in', process.cwd(), '--usage-file', usageFile];
  if (r.model) args.push('-m', r.model);
  if (r.provider) args.push('--provider', r.provider);
  if (r.reasoning) args.push('--reasoning', r.reasoning);
  if (r.toolsets) args.push('-t', r.toolsets);
  const res = runHermes(args);
  writeFileSync(path.join(teamRoot, 'results', `${id}.md`), res.stdout || '');
  appendFileSync(ledger, `\nTask ${id} — role:${role} — harness:hermes-oneshot — usage:${usageFile} — exit:${res.status} — ${stamp}\n`);
  console.log(res.stdout || res.stderr);
  if (res.status !== 0) process.exit(res.status ?? 1);
}
