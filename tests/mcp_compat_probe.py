"""Loopback protocol smoke shared by source and actual frozen-worker checks."""
import contextlib
from pathlib import Path
import os
import sys
import threading
import time
from unittest.mock import patch
from feiyu import mcp
from feiyu.runcontrol import RunControl
from tests.mcp_http_server import Fake


def smoke(binary=None):
    f = Fake(api_key='synthetic-${literal}')
    f.httpd.handle_error = lambda *args: None
    procs = []
    original = mcp.subprocess.Popen
    def spawn(*args, **kwargs):
        p = original(*args, **kwargs)
        procs.append(p)
        if binary:
            assert p.args == [binary, '--_mcp-http-worker'], p.args
        assert 'synthetic-' not in repr(p.args), p.args
        return p
    def server():
        return mcp.Server('compat', dict(url=f.url, headers={'x-api-key':'synthetic-${literal}'}),
                          Path.cwd(), dict(os.environ))
    # Expansion happens once, then the literal braces must survive worker IPC.
    with contextlib.ExitStack() as stack:
        stack.enter_context(patch.dict(os.environ, literal='${literal}'))
        if binary:
            stack.enter_context(patch.object(mcp.sys, 'executable', binary))
            stack.enter_context(patch.object(mcp, '_worker_args', return_value=['--_mcp-http-worker']))
            stack.enter_context(patch.dict(os.environ, PATH='/no-external-python'))
        stack.enter_context(patch.object(mcp.subprocess, 'Popen', side_effect=spawn))
        try:
            s = server()
            try:
                assert s.call('echo', dict(text='actual-worker')) == ('actual-worker', False)
            finally:
                s.close()
            assert f.deleted and s.io.release_confirmed, s.io.release_error
            f.deleted = False
            s = server()
            sent = threading.Event()
            result = f.result
            def slow(msg):
                if msg['method'] == 'tools/call':
                    sent.set()
                    time.sleep(1)
                return result(msg)
            f.result = slow
            from types import SimpleNamespace
            from feiyu.taskstate import TaskState
            c = RunControl(SimpleNamespace(save=lambda state:None), TaskState('smoke','smoke','smoke'))
            def cancel():
                assert sent.wait(5)
                c.cancel()
            t = threading.Thread(target=cancel)
            t.start()
            start = time.monotonic()
            try:
                try:
                    s.call('echo', dict(text='cancel'), c)
                except mcp.RequestFailure as exc:
                    assert exc.started and exc.stop_reason == 'cancelled', vars(exc)
                else:
                    raise AssertionError('cancel did not propagate')
                assert time.monotonic()-start < 4
                assert s.closed and not s.io.session and not s.io.inbox
                assert not f.deleted and s.io.release_error
            finally:
                s.close()
                t.join(6)
            assert all(p.poll() is not None for p in procs)
            assert all(p.stdin.closed and p.stdout.closed for p in procs)
        finally:
            f.close()
    print('PASS MCP initialize/tool/DELETE/cancel, workers reaped', binary or 'source')
