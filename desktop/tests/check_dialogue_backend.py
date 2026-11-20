"""Head-frozen synthetic UTF-8 streaming turns and durable resume; loopback only."""
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.test_sdk_worker import SDKWorkerTests

binary = str(Path(sys.argv[1]).resolve())
TEXT = '中文 简繁體 😀 𠮷'
for encoding in ('cp936', 'cp1252'):
    for anthropic in (False, True):
        with tempfile.TemporaryDirectory(prefix='feiyu-dialogue-') as directory, SDKWorkerTests().server('complete', anthropic) as (url, ready, requests):
            root = Path(directory)
            config = root / 'config/feiyu'
            config.mkdir(parents=True)
            (config / 'models.json').write_text(json.dumps({'offline': dict(
                kind='anthropic' if anthropic else 'openai', model='offline',
                key='offline-not-a-real-key', base_url=url)}), encoding='utf-8')
            env = dict(os.environ, HOME=directory, USERPROFILE=directory,
                       XDG_CONFIG_HOME=str(root/'config'), XDG_STATE_HOME=str(root/'state'),
                       XDG_DATA_HOME=str(root/'data'), XDG_CACHE_HOME=str(root/'cache'),
                       PYTHONIOENCODING=encoding+':strict', PYTHONUTF8='0')
            for resume in (False, True):
                args = [binary, '--serve', '--own-window', '-w', directory, '-m', 'offline']
                if resume:
                    args.append('--resume')
                proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, env=env)
                rows, errors = queue.Queue(), []
                def reader():
                    for line in proc.stdout:
                        try:
                            rows.put(json.loads(line.decode('utf-8', 'strict')))
                        except Exception as exc:
                            errors.append(repr(exc))
                    rows.put(None)
                thread = threading.Thread(target=reader, daemon=True)
                thread.start()
                received = []
                try:
                    while True:
                        row = rows.get(timeout=30)
                        assert row is not None, received
                        received.append(row)
                        if row.get('kind') == 'hello':
                            break
                    if resume:
                        assert any(r.get('kind') == 'resumed' for r in received), received
                    proc.stdin.write((json.dumps({'op':'prompt', 'text':TEXT}, ensure_ascii=False)+'\n').encode('utf-8'))
                    proc.stdin.flush()
                    while True:
                        row = rows.get(timeout=30)
                        assert row is not None, received
                        received.append(row)
                        if row.get('kind') == 'turn_end':
                            break
                    assert not [r for r in received if r.get('kind') == 'note' and r.get('level') == 'error'], received
                    assert 'answer' in json.dumps(received), received
                    assert TEXT in json.dumps(received, ensure_ascii=False), received
                    proc.stdin.close()
                    assert proc.wait(timeout=15) == 0, proc.stderr.read().decode('utf-8')
                    thread.join(timeout=5)
                    assert not errors, errors
                finally:
                    if proc.poll() is None:
                        proc.kill()
                        proc.wait(timeout=10)
                    proc.stdout.close()
                    proc.stderr.close()
            assert len(requests) == 2, requests
            journals = list((root/'state/feiyu/sessions').rglob('*.task.json'))
            assert journals, 'no durable task journal'
            payloads = [json.loads(p.read_text(encoding='utf-8'))['payload'] for p in journals]
            assert sum(p['budget']['attempts'] for p in payloads) == 2, payloads
            assert all(p['budget']['pending_attempts'] == 0 for p in payloads), payloads
            print(encoding, 'anthropic' if anthropic else 'openai', 'actual frozen dialogue/resume PASS')
