import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';

test('Desktop runtime facts map once to status notes and tolerate unknown kinds', () => {
  const src = fs.readFileSync(new URL('../ui/app.js', import.meta.url), 'utf8');
  const handler = src.slice(src.indexOf('function handle(ev) {'), src.indexOf('\nlet pendingPreview', src.indexOf('function handle(ev) {')));
  const rows = [];
  const pending = {};
  const context = vm.createContext({toolBlocks: new Map([["c", {querySelector: () => pending}]]), atBottom: () => true, keepBottom: () => {}, esc: x => x,
    block: () => {const row = {}; rows.push(row); return row;}});
  vm.runInContext(handler, context);
  for (const kind of ['execution_start', 'execution_end', 'run_end', 'future_kind'])
    context.handle({kind, session_id: 's', run_id: 'r', seq: 1});
  assert.equal(rows.length, 0);
  context.handle({kind: 'execution_start', call_id: 'c', name: 'read_file'});
  assert.match(pending.textContent, /read_file · running/);
  context.handle({kind: 'execution_end', call_id: 'c', name: 'read_file', state: 'completed'});
  assert.match(pending.textContent, /read_file · completed/);
  context.handle({kind: 'task_stopped', state: 'interrupted'});
  context.handle({kind: 'task_resumed', previous_state: 'interrupted'});
  context.handle({kind: 'verification_invalidated', verification_refs: ['v']});
  assert.equal(rows.length, 3);
  assert.match(rows[0].innerHTML, /warn.*任务停止 · interrupted/);
  assert.match(rows[1].innerHTML, /notice.*任务继续 · interrupted/);
  assert.match(rows[2].innerHTML, /验证已失效 · 1/);
  context.handle({kind: 'note', level: 'error', text: 'legacy'});
  assert.match(rows[3].innerHTML, /error.*legacy/);
});
