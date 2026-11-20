"""Offline MCP regressions through the real Toolbox; private, bounded children."""
import unittest
from tests import test_job_lifecycle


class MCP(unittest.TestCase):
    run_child = test_job_lifecycle.Lifecycle.run_child

    def exercise(self, body):
        self.run_child('''
import threading, contextlib, io
from feiyu import mcp, session
from feiyu.agent import Feiyu
from feiyu.runcontrol import RunControl, RunStopped
from tests.fakes import FakeBackend, call, unpaired
from tests.mcp_http_server import Fake
session.DIR = str(Path(os.environ['XDG_STATE_HOME']) / 'sessions')
a = Feiyu(root)
a.mode = 'auto'
a._ensure_task_storage()
c = a._control()
box = a.toolbox
fixture = root / 'server.py'
fixture.write_text("""import json, sys, time
from pathlib import Path
for line in sys.stdin:
 m=json.loads(line)
 if 'id' not in m: continue
 method=m['method']
 if method=='initialize':
  if Path('init-slow').exists(): time.sleep(5)
  r={}
 elif method=='tools/list': r={'tools':[{'name':'echo','inputSchema':{'type':'object','properties':{}}}]}
 else:
  Path('sent').write_text(str(m['id']))
  time.sleep(m['params']['arguments'].get('delay',0))
  r={'content':[{'type':'text','text':str(m['id'])}]}
 print(json.dumps({'jsonrpc':'2.0','id':m['id'],'result':r}),flush=True)
""")
def stdio(control=None):
 s=mcp.Server('s',dict(command=sys.executable,args=[str(fixture)]),root,dict(os.environ),control)
 box.mcp.servers['s']=s
 box.mcp._index()
 return s
def http():
 f=Fake()
 f.httpd.handle_error=lambda *args:None
 original=f.result
 def result(msg):
  if msg['method']=='tools/call':
   (root/'sent').write_text(str(msg['id']))
   time.sleep(msg['params']['arguments'].get('delay',0))
  return original(msg)
 f.result=result
 s=mcp.Server('s',dict(url=f.url),root,dict(os.environ))
 box.mcp.servers['s']=s
 box.mcp._index()
 return s,f
def stopped(fn,reason):
 try: fn()
 except RunStopped as e: assert e.reason==reason, e.reason
 else: raise AssertionError('stop not propagated')
def facts(started,state):
 r=box.execution.records[-1]; op=a.task_state.operations[-1]
 assert r['execution_started'] is started and r['state']==state,r
 assert op['execution_started'] is started and op['state']==state,op
 # The newly persisted fact must be readable, including not_run.
 loaded=a._task_store.load(a.task_id)
 assert loaded.operations[-1]['state']==state
try:
''' + '\n'.join(' '+line for line in body.splitlines()) + '''
finally:
 box.mcp.close()
 box.lsp.close()
 a._task_store.close()
''')

    def test_continuous_stdio_toolbox_results_and_close(self):
        self.exercise('''
s=stdio()
for i in range(2):
 r=box.run('mcp_s_echo',dict(text='ok'))
 assert not r.is_error and str(3+i) in r.content,r.content
s.close()
r=box.run('mcp_s_echo',dict(text='ok'))
assert r.is_error
facts(False,'not_run')
assert s.io.proc.poll() is not None
''')

    def test_continuous_http_toolbox_and_close(self):
        self.exercise('''
s,f=http()
# Worker receives already expanded values; literal dollar braces stay literal.
s.io.headers={'x-api-key':'${MCP_LITERAL}'}
f.api_key='${MCP_LITERAL}'
try:
 for text in ('one','two'):
  r=box.run('mcp_s_echo',dict(text=text))
  assert not r.is_error and text in r.content,r.content
 s.close()
 r=box.run('mcp_s_echo',dict(text='ok'))
 facts(False,'not_run')
 assert f.deleted
finally: f.close()
''')

    def test_before_send_cancel_is_not_run(self):
        self.exercise('''
s=stdio()
box.on_mutation=lambda _: c.cancel()
stopped(lambda:box.run('mcp_s_echo',dict(text='ok')),'cancelled')
facts(False,'not_run')
assert not (root/'sent').exists()
''')

    def test_lock_wait_cancel_does_not_close_owner(self):
        self.exercise('''
s=stdio()
s.lock.acquire()
t=threading.Timer(.1,c.cancel);t.start()
try: stopped(lambda:box.run('mcp_s_echo',dict(text='ok')),'cancelled')
finally: s.lock.release();t.join()
facts(False,'not_run')
assert s.alive() and not (root/'sent').exists()
''')

    def test_lock_wait_uses_request_timeout(self):
        self.exercise('''
s=stdio();s.lock.acquire()
try:
 with patch.object(mcp,'CALL_TIMEOUT',.1): r=box.run('mcp_s_echo',dict(text='ok'))
finally:s.lock.release()
facts(False,'not_run')
assert s.alive()
''')

    def test_after_send_stdio_cancel_is_unknown_no_reuse(self):
        self.exercise('''
s=stdio()
t=threading.Thread(target=lambda:(until(lambda:(root/'sent').exists()),c.cancel()))
t.start()
stopped(lambda:box.run('mcp_s_echo',dict(text='ok',delay=1)),'cancelled');t.join()
facts(True,'unknown')
assert not s.alive() and s.io.proc.poll() is not None
c.cancelled.clear()
try:box.run('mcp_s_echo',dict(text='ok'))
except PersistenceError:pass
else:raise AssertionError('unresolved request replayed')
''')

    def test_after_send_http_cancel_is_unknown_remote_can_finish(self):
        self.exercise('''
s,f=http()
t=threading.Thread(target=lambda:(until(lambda:(root/'sent').exists()),c.cancel()))
t.start()
try:
 stopped(lambda:box.run('mcp_s_echo',dict(text='ok',delay=.3)),'cancelled');t.join()
 facts(True,'unknown')
 assert not s.alive()
 time.sleep(.4)
 assert len(f.seen)==4, f.seen # one call only; remote receives despite local stop
finally:f.close()
''')

    def test_deadline_restored_stdio_and_http(self):
        for transport in ('stdio','http'):
            self.exercise('''
s=stdio() if %r=='stdio' else None
f=None
if s is None:s,f=http()
try:
 a.task_state.budget.update(started_at=time.time(),deadline=time.time()+.2,time_limit=.2)
 a._task_store.save(a.task_state)
 restored=a._task_store.load(a.task_id)
 c=RunControl(a._task_store,restored,time_limit=100)
 a.task_state=restored
 box.execution.durable=(a._task_store,restored);box.execution.control=c
 stopped(lambda:box.run('mcp_s_echo',dict(text='ok',delay=.5)),'deadline_stopped')
 facts(True,'unknown')
 assert not s.alive()
finally:
 if f:f.close()
''' % transport)

    def test_timeout_late_stdio_response_cannot_be_reused(self):
        self.exercise('''
s=stdio()
with patch.object(mcp,'CALL_TIMEOUT',.1):r=box.run('mcp_s_echo',dict(text='ok',delay=.5))
assert r.is_error
facts(True,'unknown')
assert not s.alive() and s.io.proc.poll() is not None
# Exercise registry directly too: no stale response or automatic restart.
text,failed=box.mcp.call('mcp_s_echo',{})
assert failed and '关闭' in text
''')

    def test_http_missing_response_is_bounded(self):
        self.exercise('''
s,f=http()
try:
 with patch.object(mcp,'CALL_TIMEOUT',.15):r=box.run('mcp_s_echo',dict(text='ok',delay=.5))
 assert r.is_error
 facts(True,'unknown')
 assert not s.alive()
finally:f.close()
''')

    def test_initialization_timeout_and_parent_stop_cleanup(self):
        for cancel in (False,True):
            self.exercise('''
(root/'init-slow').touch()
real=mcp.subprocess.Popen
procs=[]
def capture(*args,**kw):
 p=real(*args,**kw);procs.append(p);return p
with patch.object(mcp.subprocess,'Popen',side_effect=capture),patch.object(mcp,'INIT_TIMEOUT',.15):
 t=threading.Timer(.05,c.cancel) if %r else None
 if t:t.start()
 try:
  try:stdio(c)
  except mcp.RequestFailure as e:assert e.stop_reason==('cancelled' if t else ''),vars(e)
  else:raise AssertionError('initialization survived')
 finally:
  if t:t.join()
assert procs and all(p.poll() is not None and p.stdin.closed and p.stdout.closed for p in procs)
''' % cancel)

    def test_critical_prepare_and_finish_failures(self):
        for stage in ('prepare','finish'):
            self.exercise('''
s=stdio()
real_close=box.mcp.close
def cleanup_failure():
 real_close()
 raise RuntimeError('synthetic cleanup failure')
with patch.object(a._task_store,%r,side_effect=PersistenceError('synthetic disk failure')),patch.object(box.mcp,'close',side_effect=cleanup_failure):
 try:box.run('mcp_s_echo',dict(text='ok'))
 except PersistenceError:pass
 else:raise AssertionError('critical error swallowed')
assert (root/'sent').exists() is %r
if %r=='finish':assert box.execution.records[-1]['state']=='unknown'
''' % (stage,stage=='finish',stage))

    def test_agent_cancel_pairs_protocol_result_once(self):
        self.exercise('''
s=stdio()
a.backend=FakeBackend([('',[call('mcp-id','mcp_s_echo',delay=.5)])])
t=threading.Thread(target=lambda:(until(lambda:(root/'sent').exists()),c.cancel()))
t.start()
with contextlib.redirect_stdout(io.StringIO()):stopped(lambda:a.send('synthetic MCP call'),'cancelled')
t.join()
assert not unpaired(a.backend.messages),a.backend.messages
rows=[m for m in a.backend.messages if m.get('role')=='tool' and m.get('tool_call_id')=='mcp-id']
assert len(rows)==1,rows
facts(True,'unknown')
''')

    def test_stdio_blocked_send_is_cancellable_without_writer_thread(self):
        self.exercise('''
# Complete the handshake, then deliberately stop consuming stdin.
s=stdio()
s.io.proc.send_signal(__import__('signal').SIGSTOP)
t=threading.Timer(.1,c.cancel);t.start()
try:stopped(lambda:box.run('mcp_s_echo',dict(text='x'*1000000)),'cancelled')
finally:t.join()
facts(True,'unknown')
assert s.io.proc.poll() is not None
''')

    def test_parent_critical_check_failure_closes_inflight_connection(self):
        self.exercise('''
s=stdio()
original=c.check
def check(**kw):
 if (root/'sent').exists():
  c.blocked=True
  raise PersistenceError('synthetic critical save failure')
 original(**kw)
with patch.object(c,'check',side_effect=check):
 try:box.run('mcp_s_echo',dict(delay=.5))
 except PersistenceError:pass
 else:raise AssertionError('critical wait failure swallowed')
assert not s.alive() and s.io.proc.poll() is not None
assert a.task_state.operations[-1]['state']=='unknown'
''')

    def test_http_initialization_timeout_reaps_io_worker(self):
        self.exercise('''
f=Fake()
original=f.result
def result(msg):
 if msg['method']=='initialize':time.sleep(.4)
 return original(msg)
f.result=result
real=mcp.subprocess.Popen
procs=[]
def capture(*args,**kw):
 p=real(*args,**kw);procs.append(p);return p
try:
 with patch.object(mcp.subprocess,'Popen',side_effect=capture),patch.object(mcp,'INIT_TIMEOUT',.15):
  try:mcp.Server('s',dict(url=f.url),root,dict(os.environ),c)
  except mcp.RequestFailure:pass
  else:raise AssertionError('HTTP init timeout ignored')
 assert procs and all(p.poll() is not None and p.stdin.closed and p.stdout.closed for p in procs)
finally:f.close()
''')

    def test_cancelled_admission_records_not_run(self):
        self.exercise('''
s=stdio();c.cancel()
stopped(lambda:box.run('mcp_s_echo',dict(text='ok')),'cancelled')
facts(False,'not_run')
assert not (root/'sent').exists()
''')

    def test_http_trickling_body_obeys_total_deadline(self):
        self.exercise('''
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_POST(self):
  self.rfile.read(int(self.headers['Content-Length']))
  self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
  try:
   for _ in range(30):self.wfile.write(b': still waiting\\n');self.wfile.flush();time.sleep(.02)
  except OSError:pass
h=ThreadingHTTPServer(('127.0.0.1',0),Handler)
t=threading.Thread(target=h.serve_forever);t.start()
# Use a real initialized server, then redirect its next call to the local slow body.
s,f=http()
s.io.url='http://127.0.0.1:%d/mcp'%h.server_address[1]
try:
 start=time.monotonic()
 with patch.object(mcp,'CALL_TIMEOUT',.15):r=box.run('mcp_s_echo',dict(text='ok'))
 assert time.monotonic()-start<2
 facts(True,'unknown')
 assert not s.alive()
finally:h.shutdown();h.server_close();t.join();f.close()
''')

    def test_close_http_inflight_reaps_and_discards_reply(self):
        self.exercise('''
s,f=http();rows=[];procs=[];real=mcp.subprocess.Popen
def capture(*args,**kw):
 p=real(*args,**kw);procs.append(p);return p
def invoke():
 try: rows.append(('returned',s.call('echo',dict(text='slow',delay=.4))))
 except BaseException as e: rows.append((type(e).__name__,str(e)))
try:
 with patch.object(mcp.subprocess,'Popen',side_effect=capture):
  t=threading.Thread(target=invoke);t.start();until(lambda:(root/'sent').exists());s.close()
  assert all(p.returncode is not None for p in procs), 'close did not reap'
  t.join(3)
 assert not t.is_alive() and rows[0][0]!='returned', rows
 assert s.closed and not s.io.session and not s.io.inbox
finally: f.close()
''')

    def test_primary_wait_error_survives_cleanup_failure(self):
        for cancel in (False, True):
            self.exercise('''
s=stdio();real=s.io.close;original=c.check
def check(**kw):
 if (root/'sent').exists():
  if %r: raise RunStopped('cancelled')
  raise PersistenceError('PRIMARY_SAVE_FAILURE')
 original(**kw)
def bad_close():
 real();raise RuntimeError('SECONDARY_CLOSE_FAILURE')
with patch.object(c,'check',side_effect=check),patch.object(s.io,'close',side_effect=bad_close):
 try: box.run('mcp_s_echo',dict(delay=.3))
 except PersistenceError as e:
  assert not %r and 'PRIMARY_SAVE_FAILURE' in str(e)
  assert 'SECONDARY_CLOSE_FAILURE' in str(e.cleanup_errors)
 except RunStopped as e:
  assert %r and e.reason=='cancelled'
 else: raise AssertionError('primary failure swallowed')
assert s.io.proc.returncode is not None
''' % (cancel, cancel, cancel))

    def test_close_after_http_import_stops_request_without_delete(self):
        self.exercise('''
s,f=http();ready=threading.Event();resume=threading.Event();rows=[]
original=s.io.read
def paused_read(deadline):
 ready.set()
 assert resume.wait(3)
 return original(deadline)
def invoke():
 try: rows.append(('ok',s.request('tools/call',dict(name='echo',arguments={}),2)))
 except mcp.RequestFailure as e: rows.append(('error',e))
try:
 with patch.object(s.io,'read',side_effect=paused_read):
  t=threading.Thread(target=invoke);t.start();assert ready.wait(3)
  assert s.io._worker is None and s.io.inbox
  s.close();resume.set();t.join(.5)
  assert not t.is_alive(), 'closed request kept waiting for original timeout'
 assert rows[0][0]=='error' and rows[0][1].started,rows
 assert not s.io.session and not s.io.inbox and not f.deleted
finally:
 resume.set();t.join(3);f.close()
''')
