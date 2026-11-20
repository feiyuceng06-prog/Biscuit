"""UTF-8 over the actual frozen service pipes, under legacy code pages.

Read-only path completion deliberately isolates wire encoding from model access.
This does not prove that a model turn or persistence works.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

TEXT = '中文 简繁體 😀 𠮷 e\u0301'
binary = str(Path(sys.argv[1]).resolve())
for encoding in ('cp936', 'cp1252'):
    with tempfile.TemporaryDirectory(prefix='feiyu-frozen-stdio-') as temporary:
        root = Path(temporary)
        config = root / 'config' / 'feiyu'
        config.mkdir(parents=True)
        (config / 'models.json').write_text(json.dumps({'synthetic': {
            'kind': 'openai', 'model': 'synthetic', 'key': 'test-only-not-a-key',
            'limit': 32000}}), encoding='utf-8')
        env = dict(os.environ, HOME=temporary, USERPROFILE=temporary,
                   XDG_CONFIG_HOME=str(root / 'config'), XDG_STATE_HOME=str(root / 'state'),
                   XDG_DATA_HOME=str(root / 'data'), XDG_CACHE_HOME=str(root / 'cache'),
                   PYTHONIOENCODING=encoding + ':strict', PYTHONUTF8='0')
        payload = (json.dumps({'op': 'paths', 'prefix': TEXT}, ensure_ascii=False) + '\n').encode('utf-8')
        result = subprocess.run([binary, '--serve', '--own-window', '-w', temporary,
                                 '-m', 'synthetic'], input=payload, capture_output=True,
                                env=env, timeout=30)
        assert result.returncode == 0, (result.returncode, result.stderr.decode('utf-8'))
        rows = [json.loads(line) for line in result.stdout.decode('utf-8', errors='strict').splitlines()]
        assert any(row.get('kind') == 'paths' and row['prefix'] == TEXT for row in rows), rows
        assert any(row.get('kind') == 'hello' for row in rows), rows
        print(encoding, 'frozen serve UTF-8 pipe input/output PASS')
