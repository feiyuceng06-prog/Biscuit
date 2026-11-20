"""Run via the isolated stage-D runner with an actual freshly frozen binary."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.mcp_compat_probe import smoke

smoke(str(Path(sys.argv[1]).resolve()))

# Also exercise the production parent entry's own sys.frozen selection, with no
# patch of sys.executable/_worker_args and no model request.
import json
import os
import subprocess
import tempfile
from tests.mcp_http_server import Fake

with tempfile.TemporaryDirectory(prefix='feiyu-frozen-http-parent-') as directory:
    root = Path(directory)
    config = root / 'config' / 'feiyu'
    config.mkdir(parents=True)
    f = Fake()
    env = dict(os.environ, HOME=directory, XDG_CONFIG_HOME=str(root/'config'),
               XDG_STATE_HOME=str(root/'state'), XDG_DATA_HOME=str(root/'data'),
               XDG_CACHE_HOME=str(root/'cache'), PATH='/no-external-python')
    if os.name == 'nt':
        env['USERPROFILE'] = directory
    (config/'mcp.json').write_text(json.dumps({'mcpServers':{'loopback':{'url':f.url}}}))
    try:
        result = subprocess.run([str(Path(sys.argv[1]).resolve()), '--serve', '--own-window',
                                 '-w', directory], input='{"op":"status"}\n',
                                text=True, encoding='utf-8', capture_output=True, env=env, timeout=25)
        assert result.returncode == 0, result.stderr
        assert len(f.seen) >= 3, (f.seen, result.stdout, result.stderr)
        assert any(h.get('mcp-session-id') for h in f.seen), f.seen
        assert f.deleted, (result.stdout, result.stderr)
        assert any(event.get('what') == 'mcp' and 'loopback（2 个工具）' in event.get('text', '')
                   for event in map(json.loads, result.stdout.splitlines())), result.stdout
        print('PASS production frozen --serve parent HTTP initialize/list/session DELETE')
    finally:
        f.close()
