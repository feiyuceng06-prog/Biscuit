import test from 'node:test';
import { EOL } from 'node:os';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createInterface } from 'node:readline';
import { fileURLToPath } from 'node:url';

import { existsSync } from 'node:fs';
const localPython = fileURLToPath(new URL(process.platform === 'win32'
  ? '../../.venv/Scripts/python.exe' : '../../.venv/bin/python', import.meta.url));
const python = process.env.FEIYU_STDIO_TEST_PYTHON || (existsSync(localPython) ? localPython
  : process.platform === 'win32' ? 'python' : 'python3');
const fixture = fileURLToPath(new URL('./stdio-echo-fixture.py', import.meta.url));
const text = '中文 简繁體 😀 𠮷 e\u0301';
for (const mode of ['cli', 'frozen-entry']) {
  for (const encoding of ['cp936', 'cp1252']) {
    test(`UTF-8 actual Protocol through ${mode}, inherited ${encoding}`, { timeout: 15000 }, async () => {
      const child = spawn(python, [fixture, mode, '--serve'], {
        env: { ...process.env, PYTHONIOENCODING: `${encoding}:strict`, PYTHONUTF8: '1' },
        stdio: ['pipe', 'pipe', 'pipe'],
      });
      const rows = [];
      const lines = createInterface({ input: child.stdout }); // same decoder as AgentProcess
      lines.on('line', line => rows.push(JSON.parse(line)));
      let diagnostic = '';
      child.stderr.setEncoding('utf8');
      child.stderr.on('data', data => diagnostic += data);
      child.stdin.on('error', () => {});
      const done = new Promise((resolve, reject) => {
        child.once('error', reject);
        child.once('exit', (code, signal) => resolve({ code, signal }));
      });
      try {
        // Byte-at-a-time writes force split UTF-8 codepoints on input. A large
        // response also spans pipe chunks; readline must preserve each value.
        const messages = [text, text.repeat(12000)];
        for (const byte of Buffer.from(JSON.stringify({ text }) + '\n')) {
          child.stdin.write(Buffer.from([byte]));
        }
        child.stdin.end(JSON.stringify({ text: messages[1] }) + '\n');
        assert.deepEqual(await done, { code: 0, signal: null }, diagnostic);
        assert.deepEqual(rows, messages.map(text => ({ kind: 'echo', text })));
        assert.equal(diagnostic, `合成诊断 😀 𠮷${EOL}`);
      } finally {
        lines.close();
        if (child.exitCode === null) child.kill('SIGKILL');
      }
    });
  }
}

test('Node readline preserves codepoints split across every output byte', async () => {
  const { Readable } = await import('node:stream');
  const bytes = Buffer.from(JSON.stringify({ text }) + '\n');
  const lines = createInterface({ input: Readable.from([...bytes].map(b => Buffer.from([b]))) });
  const rows = [];
  for await (const line of lines) rows.push(JSON.parse(line));
  assert.deepEqual(rows, [{ text }]);
});
