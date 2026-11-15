"""Verify frozen SDK imports/initialization without making API requests."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory(prefix="feiyu-payload-test-") as temporary:
    root = Path(temporary)
    config = root / "config" / "feiyu"
    config.mkdir(parents=True)
    env = dict(os.environ, HOME=temporary, XDG_CONFIG_HOME=str(root / "config"),
               XDG_STATE_HOME=str(root / "state"), XDG_DATA_HOME=str(root / "data"))
    for kind in ("openai", "anthropic"):
        (config / "models.json").write_text(json.dumps({"smoke": {
            "kind": kind, "model": "smoke-model", "key": "test-only-not-a-key",
            "base_url": "http://127.0.0.1:1", "limit": 32000,
        }}))
        result = subprocess.run([sys.argv[1], "--serve", "--own-window", "-w", temporary, "-m", "smoke"],
                                input='{"op":"status"}\n', text=True, capture_output=True,
                                env=env, timeout=30)
        assert result.returncode == 0, f"{kind} backend failed: {result.stderr}"
        events = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        assert any(event.get("kind") == "status" for event in events), f"{kind}: no status received"
        print(f"PASS: frozen {kind} backend initializes without system Python")

# Exercise the frozen entry point, not imports from the development interpreter.
if sys.platform.startswith('linux'):
    import http.server
    import queue
    import shutil
    import ssl
    import threading

    with tempfile.TemporaryDirectory(prefix='feiyu-frozen-runtime-') as directory:
        root = Path(directory)
        cert, key = root / 'ca.pem', root / 'ca.key'
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                        '-keyout', str(key), '-out', str(cert), '-days', '1',
                        '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"data":[{"id":"local-tls-test"}]}')

            def log_message(self, *args):
                pass

        server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert, key)
        server.socket = context.wrap_socket(server.socket, server_side=True)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        config = root / 'config' / 'feiyu'
        config.mkdir(parents=True)
        probe = root / 'probe.py'
        result_path = root / 'child.json'
        probe.write_text('''import json, os, subprocess, sys
r = subprocess.run(['bash', '-c', 'printf frozen-shell-ok'], capture_output=True, text=True)
with open(sys.argv[1], 'w') as f:
    json.dump({'code': r.returncode, 'stdout': r.stdout, 'stderr': r.stderr,
               'libs': os.environ.get('LD_LIBRARY_PATH', '')}, f)
for line in sys.stdin:
    message = json.loads(line)
    if 'id' not in message: continue
    result = {'protocolVersion':'2024-11-05','capabilities':{},'serverInfo':{'name':'probe','version':'1'}} if message['method']=='initialize' else {'tools':[]}
    print(json.dumps({'jsonrpc':'2.0','id':message['id'],'result':result}), flush=True)
''')
        (config / 'mcp.json').write_text(json.dumps({'mcpServers': {'probe': {
            'command': sys.executable, 'args': ['-I', str(probe), str(result_path)]}}}))
        env = dict(os.environ, HOME=directory, XDG_CONFIG_HOME=str(root / 'config'),
                   XDG_STATE_HOME=str(root / 'state'), XDG_DATA_HOME=str(root / 'data'),
                   SSL_CERT_FILE=str(cert), NO_PROXY='localhost,127.0.0.1', no_proxy='localhost,127.0.0.1')
        process = subprocess.Popen([sys.argv[1], '--serve', '--own-window', '-w', directory],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, env=env)
        events = queue.Queue()
        def read_events():
            for line in process.stdout:
                try: events.put(json.loads(line))
                except ValueError: pass
        threading.Thread(target=read_events, daemon=True).start()
        try:
            request = {'op': 'model_list', 'ticket': 701, 'kind': 'openai', 'key': '',
                       'base_url': 'https://localhost:%d/v1' % server.server_port}
            process.stdin.write(json.dumps(request) + '\n'); process.stdin.flush()
            import time
            deadline = time.monotonic() + 30
            while True:
                event = events.get(timeout=max(0.1, deadline - time.monotonic()))
                if event.get('kind') == 'model_list':
                    assert event.get('ok'), event
                    break
                assert time.monotonic() < deadline, 'no model list response'
            while not result_path.exists() and time.monotonic() < deadline:
                time.sleep(0.05)
            result = json.loads(result_path.read_text())
            assert result['code'] == 0 and result['stdout'] == 'frozen-shell-ok', result
            assert str(Path(sys.argv[1]).resolve().parent) not in result['libs'], result
            print('PASS: frozen MCP child launches host bash; HTTPS honors custom CA')
        finally:
            process.stdin.close()
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill(); process.wait()
            server.shutdown(); server.server_close(); thread.join()
