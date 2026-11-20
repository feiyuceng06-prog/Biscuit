"""Offline SDK smoke for a freshly frozen backend, including same-exe parent."""
from pathlib import Path
import json
import os
import signal
import struct
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from tests.test_sdk_worker import SDKWorkerTests
from feiyu.sdk_worker import frame, decode

binary = str(Path(sys.argv[1]).resolve())
for anthropic in (False, True):
    provider = 'anthropic' if anthropic else 'openai'
    for stream in (False, True):
        with SDKWorkerTests().server('complete', anthropic) as (url, _, requests):
            kwargs = dict(model='offline', max_tokens=100, messages=[dict(role='user',content='hello')])
            if stream and not anthropic:
                kwargs.update(stream=True, stream_options={'include_usage':True})
            payload = frame('request', provider=provider, operation='stream' if stream else 'ask',
                client=dict(api_key='offline-not-a-real-key', base_url=url, timeout=10), kwargs=kwargs)
            proc = subprocess.run([binary, '--_sdk-worker'], input=payload, capture_output=True, timeout=15)
            assert proc.returncode == 0, proc.stderr
            raw, kinds = proc.stdout, []
            while raw:
                n = struct.unpack('!I',raw[:4])[0]; kinds.append(decode(raw[4:4+n])['kind']); raw=raw[4+n:]
            assert kinds[-1] == 'done', kinds
            assert ('event' if stream else 'result') in kinds, kinds
            assert len(requests) == 1
    for mode in ('complete', 'silent'):
        with tempfile.TemporaryDirectory(prefix='sdk-frozen-') as directory, SDKWorkerTests().server(mode, anthropic) as (url, ready, requests):
            root = Path(directory)
            config = root/'config/feiyu'; config.mkdir(parents=True)
            (config/'models.json').write_text(json.dumps({'offline':dict(kind=provider,model='offline',key='offline-not-a-real-key',base_url=url)}))
            env = dict(os.environ, HOME=directory, XDG_CONFIG_HOME=str(root/'config'), XDG_STATE_HOME=str(root/'state'),
                       XDG_DATA_HOME=str(root/'data'), XDG_CACHE_HOME=str(root/'cache'), PATH='/no-external-python')
            proc = subprocess.Popen([binary,'-w',directory,'-m','offline','hello'], stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
            try:
                assert ready.wait(8), 'parent did not reach local SDK'
                childfile = Path('/proc')/str(proc.pid)/'task'/str(proc.pid)/'children'
                children = childfile.read_text().split() if childfile.exists() else []
                if mode == 'silent': proc.send_signal(signal.SIGINT)
                out, err = proc.communicate(timeout=10)
                assert len(requests) == 1
                if mode == 'complete': assert b'answer' in out, (out,err)
                for pid in children:
                    assert not Path('/proc',pid).exists(), 'worker not reaped by product'
            finally:
                if proc.poll() is None:
                    proc.kill(); proc.wait()
                proc.stdout.close(); proc.stderr.close()
print('PASS two SDKs frozen direct ask/stream and same-exe parent success/cancel; no external Python')

if sys.platform == 'linux':
    import ctypes
    libc = ctypes.CDLL(None, use_errno=True)
    old = ctypes.c_int()
    assert libc.prctl(37, ctypes.byref(old), 0, 0, 0) == 0
    assert libc.prctl(36, 1, 0, 0, 0) == 0
    try:
        for anthropic in (False, True):
            with tempfile.TemporaryDirectory(prefix='sdk-frozen-hard-death-') as directory, SDKWorkerTests().server('silent', anthropic) as (url, ready, requests):
                root = Path(directory); config = root/'config/feiyu'; config.mkdir(parents=True)
                (config/'models.json').write_text(json.dumps({'offline':dict(kind='anthropic' if anthropic else 'openai',
                    model='offline',key='offline-not-a-real-key',base_url=url)}))
                env = dict(os.environ, HOME=directory, XDG_CONFIG_HOME=str(root/'config'), XDG_STATE_HOME=str(root/'state'),
                           XDG_DATA_HOME=str(root/'data'), XDG_CACHE_HOME=str(root/'cache'), PATH='/no-external-python')
                proc = subprocess.Popen([binary,'-w',directory,'-m','offline','hello'], stdin=subprocess.DEVNULL,
                                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
                supervisors = []
                try:
                    assert ready.wait(10), 'frozen parent did not reach SDK'
                    supervisors = [int(p) for p in (Path('/proc')/str(proc.pid)/'task'/str(proc.pid)/'children').read_text().split()]
                    assert len(supervisors) == 1, supervisors
                    proc.kill(); proc.communicate(timeout=5)
                    end = time.monotonic() + 5; receipt = None
                    while time.monotonic() < end:
                        for path in (root/'state/feiyu/sdk-lifecycle').iterdir():
                            try:
                                value = json.loads(path.read_text())
                                if value.get('state') == 'reaped': receipt = value
                            except (ValueError, OSError): pass
                        if receipt: break
                        time.sleep(.02)
                    assert receipt and receipt['parent'] == proc.pid, receipt
                    assert receipt['supervisor'] == supervisors[0] and receipt['wait_status'] == 9, receipt
                    assert not Path('/proc', str(receipt['worker'])).exists(), receipt
                    while time.monotonic() < end:
                        found, status = os.waitpid(supervisors[0], os.WNOHANG)
                        if found:
                            assert status == 0, status
                            supervisors.clear(); break
                        time.sleep(.02)
                    assert not supervisors, 'supervisor did not exit'
                    assert len(requests) == 1
                    print('PASS frozen parent SIGKILL', json.dumps(receipt, sort_keys=True))
                finally:
                    if proc.poll() is None: proc.kill()
                    proc.wait(timeout=3); proc.stdout.close(); proc.stderr.close()
                    for pid in supervisors:
                        children = Path('/proc/%d/task/%d/children' % (pid, pid))
                        workers = [int(p) for p in children.read_text().split()] if children.exists() else []
                        try: os.kill(pid, signal.SIGKILL)
                        except ProcessLookupError: pass
                        try: os.waitpid(pid, 0)
                        except ChildProcessError: pass
                        for worker in workers:
                            try: os.kill(worker, signal.SIGKILL)
                            except ProcessLookupError: pass
                            try: os.waitpid(worker, 0)
                            except ChildProcessError: pass
    finally:
        libc.prctl(36, old.value, 0, 0, 0)
