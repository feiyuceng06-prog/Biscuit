"""Compatibility regressions using bounded, isolated local fixtures only."""
import unittest
from tests import test_job_lifecycle


class Compatibility(unittest.TestCase):
    run_child = test_job_lifecycle.Lifecycle.run_child

    def test_source_worker_protocol_and_cancel(self):
        self.run_child('''
from tests.mcp_compat_probe import smoke
smoke()
''')

    def test_release_failure_is_explicit_and_bounded(self):
        self.run_child('''
import threading
from feiyu import mcp
from tests.mcp_http_server import Fake
f=Fake()
s=mcp.Server('release',dict(url=f.url),root,dict(os.environ))
# A DELETE response that never arrives must not retain the local process.
handler=f.httpd.RequestHandlerClass
handler.do_DELETE=lambda self:time.sleep(2)
start=time.monotonic()
try:
 s.close()
 assert time.monotonic()-start<2
 assert not s.io.release_confirmed and '未确认' in s.io.release_error
 s.close()
finally:f.close()
''')

    def test_cleanup_without_primary_is_reported(self):
        self.run_child('''
from feiyu.mcp import _close_preserving
def fail():raise RuntimeError('cleanup-only')
try:_close_preserving(fail)
except RuntimeError as e:assert str(e)=='cleanup-only'
else:raise AssertionError('cleanup swallowed')
''')

    @unittest.skipUnless(__import__('os').name == 'nt', 'requires actual Windows pipes')
    def test_windows_backpressure_cancel_and_reap(self):
        self.run_child('''
import threading
from feiyu import mcp
from feiyu.runcontrol import RunControl
p=root/'blocked.py';p.write_text('import time;time.sleep(30)')
s=mcp._Stdio('blocked',dict(command=sys.executable,args=[str(p)]),root,dict(os.environ))
from types import SimpleNamespace
from feiyu.taskstate import TaskState
c=RunControl(SimpleNamespace(save=lambda state:None),TaskState('smoke','smoke','smoke'));s.wait=mcp._Wait(2,c)
t=threading.Timer(.1,c.cancel);t.start()
try:
 try:s.send({'data':'x'*2000000},2)
 except BaseException:pass
 else:raise AssertionError('blocked write completed')
finally:s.close();t.join()
assert s.proc.poll() is not None
assert not s.windows.writer.is_alive()
''')
