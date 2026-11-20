"""Real local LSP fixtures; each scenario has a fresh whitelist environment and hard timeout."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

SERVER = r'''
import json, os, subprocess, sys, time
from pathlib import Path
mode = sys.argv[1]
child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
Path('pids').write_text(json.dumps([os.getpid(), child.pid]))
def send(msg):
 body=json.dumps(msg).encode(); sys.stdout.buffer.write(b'Content-Length: %d\r\n\r\n'%len(body)+body);sys.stdout.buffer.flush()
while True:
 head=b''
 while not head.endswith(b'\r\n\r\n'):
  c=sys.stdin.buffer.read(1)
  if not c: sys.exit(0)
  head+=c
 length=int(head.split(b':',1)[1].strip())
 msg=json.loads(sys.stdin.buffer.read(length))
 if msg.get('method')=='initialize':
  if mode=='init-hang': time.sleep(60)
  if mode=='init-fail': send({'id':msg['id'],'error':{'message':'synthetic failure'}});continue
  send({'id':msg['id'],'result':{}})
  if mode=='backpressure': time.sleep(60)
 elif 'id' in msg:
  if mode=='output-hang': time.sleep(60)
  if mode.startswith('exit'): sys.exit(int(mode[4:]))
  send({'id':msg['id'],'result':[]})
'''


def scenario(mode, root):
    from feiyu import lsp, session
    from feiyu.tools import Toolbox
    from feiyu.taskstate import TaskStore, TaskState, PersistenceError, workspace_id
    from feiyu.runcontrol import RunControl, RunStopped
    from feiyu.jobs import identity
    root = Path(root)
    (root/'server.py').write_text(SERVER)
    (root/'x.py').write_text('needle = 1\n')
    session.DIR = str(root/'sessions')
    store = TaskStore(root, 'lsp-session')
    state = TaskState('lsp-session', 'lsp-task', workspace_id(root))
    store.save(state)
    control = RunControl(store, state)
    box = Toolbox(root)
    box.execution.durable = (store, state)
    box.execution.control = control
    servermode = {'init-timeout':'init-hang', 'cancel-init':'init-hang', 'deadline-init':'init-hang',
                  'output-cancel':'output-hang','output-timeout':'output-hang',
                  'stdin-cancel':'backpressure'}.get(mode, mode)
    argv = [sys.executable, str(root/'server.py'), servermode]
    lsp.FIRST_TIMEOUT = .35 if mode=='init-timeout' else 3
    lsp.REQUEST_TIMEOUT = .3 if mode=='output-timeout' else 3
    timers=[]
    created=[]
    popen=lsp.subprocess.Popen
    def spawn(*a,**kw):
        proc=popen(*a,**kw)
        if a and a[0] == argv:
            created.append(proc)
        return proc
    spawn_patch=patch.object(lsp.subprocess,'Popen',side_effect=spawn)
    spawn_patch.start()
    def later(fn, delay=.2):
        t=threading.Timer(delay, fn);timers.append(t);t.start()
    def symbol():
        return box.run('symbol', dict(action='definition', path='x.py', name='needle'))
    try:
        with patch.object(lsp, 'server_for', return_value=argv):
            if mode=='close-init':
                errors=[]
                def get():
                    try: box.lsp.get(root/'x.py')
                    except RuntimeError as exc: errors.append(exc)
                argv[-1]='init-hang'
                worker=threading.Thread(target=get);worker.start()
                end=time.monotonic()+2
                while not (root/'pids').exists() and time.monotonic()<end: time.sleep(.01)
                box.lsp.close();worker.join(3)
                assert not worker.is_alive() and errors
            elif mode in ('cancel-init','output-cancel','stdin-cancel'):
                later(control.cancel)
            if mode=='deadline-init':
                state.budget['deadline']=time.time()+.2
                store.save(state)
                state=store.load(state.task_id)
                control=RunControl(store,state)
                box.execution.durable=(store,state)
                box.execution.control=control
            if mode=='close-init':
                pass
            elif mode in ('pool-lock','client-lock'):
                if mode=='client-lock':
                    client=box.lsp.get(root/'x.py');lock=client.lock
                else: lock=box.lsp.lock
                lock.acquire()
                later(control.cancel)
                try:
                    try: symbol();raise AssertionError('cancel ignored')
                    except RunStopped: pass
                finally: lock.release()
            elif mode=='stdin-cancel':
                client=box.lsp.get(root/'x.py')
                try: client.open(root/'x.py', 'x'*2000000);raise AssertionError('backpressure ignored')
                except RunStopped: pass
            elif mode=='prepare-fail':
                with patch.object(store, 'prepare_service', side_effect=PersistenceError('injected prepare')):
                    try: symbol();raise AssertionError('save ignored')
                    except PersistenceError: pass
                assert not (root/'pids').exists()
            elif mode in ('identity-save-fail','ready-save-fail','finish-save-fail'):
                original=store.save
                def save(s):
                    services=[o for o in s.operations if o.get('kind')=='lsp-service']
                    service=services[-1] if services else {}
                    hit=(mode=='identity-save-fail' and service.get('service_status')=='initializing' or
                         mode=='ready-save-fail' and service.get('service_status')=='ready' or
                         mode=='finish-save-fail' and any(o['name']=='symbol' and o['state']=='completed' for o in s.operations))
                    if hit:
                        store.blocked=True
                        raise PersistenceError('injected critical save')
                    return original(s)
                with patch.object(store,'save', side_effect=save):
                    try: symbol();raise AssertionError('save ignored')
                    except PersistenceError: pass
            elif mode=='recovery':
                assert not symbol().is_error
                assert not store.pending(), state.operations
                op=next(o for o in state.operations if o.get('kind')=='lsp-service')
                # Observe a copied task in another session directory; no live owner state mutation.
                from dataclasses import asdict
                recovered=TaskState.read(asdict(state))
                recovered.task_id='recovered'
                store.save(recovered)
                with patch('os.killpg', side_effect=AssertionError('restore signalled old pid')):
                    loaded=store.load('recovered');store.reconcile(loaded)
                    assert next(o for o in loaded.operations if o.get('kind')=='lsp-service')['state']=='unknown'
                    assert 'recovered' in store.pending()
                    try: store.resolve(loaded,op['id'],'fixture observation');raise AssertionError('live resolve')
                    except PersistenceError: pass
                    try: symbol();raise AssertionError('other task pending bypassed')
                    except PersistenceError: pass
                    lost=next(o for o in loaded.operations if o.get('kind')=='lsp-service')
                    lost['process']['start']='0'
                    store.save(loaded)
                    store.reconcile(loaded)
                    assert lost['observation']['process']=='absent-or-different; not success'
                    store.resolve(loaded,op['id'],'synthetic stale identity; acknowledge unknown only')
                    assert lost['state']=='resolved' and loaded.result=='unfinished'
                # Never auto restart after a lost/old process identity.
                assert len(json.loads((root/'pids').read_text()))==2
            elif mode=='task-select':
                assert not symbol().is_error
                from feiyu.agent import Feiyu
                agent=object.__new__(Feiyu)
                from feiyu.verification import Ledger
                agent.verifications=Ledger()
                agent.toolbox=box;agent.task_state=state;agent.task_id=state.task_id
                agent._task_store=store;agent._refresh_system=lambda:None
                selected=TaskState(store.sid,'next-task',state.workspace_id)
                store.save(selected)
                agent.task_control(dict(action='select',task_id=selected.task_id))
                assert not box.lsp.clients and box.execution.durable[1] is selected
                service=next(o for o in state.operations if o.get('kind')=='lsp-service')
                assert service['state']=='completed' and service['service_status']=='stopped'
            elif mode=='idle-save-fail':
                assert not symbol().is_error
                with patch('feiyu.taskstate.atomic_json', side_effect=PersistenceError('synthetic disk failure')):
                    try: store.save(state);raise AssertionError('save failure ignored')
                    except PersistenceError: pass
                    assert store.blocked
                    client=next(iter(box.lsp.clients.values()))
                    assert client.stopped.wait(2)
            elif mode=='idle-cancel':
                assert not symbol().is_error
                control.cancel()
                client=next(iter(box.lsp.clients.values()))
                assert client.stopped.wait(2)
            elif mode=='normal':
                assert not symbol().is_error
                assert not symbol().is_error
                assert not store.pending(),state.operations
                assert getattr(box,'_unisolated_lsp',False)
                box.lsp.close()
                op=next(o for o in state.operations if o.get('kind')=='lsp-service')
                assert op['state']=='completed' and op['lifecycle_only']
            else:
                try:
                    out=symbol()
                    assert mode not in ('cancel-init','deadline-init','output-cancel'), 'parent stop became ordinary error'
                    assert out.is_error and out.execution_unknown,(mode,out)
                    assert any(o['state']=='unknown' for o in state.operations)
                except RunStopped:
                    assert mode in ('cancel-init','deadline-init','output-cancel')
        # Product must clean up before fixture fallback.
        if mode not in ('recovery','normal','pool-lock'):
            p=root/'pids'
            pids=json.loads(p.read_text()) if p.exists() else []
            end=time.monotonic()+3
            while (any(identity(pid) for pid in pids) or any(p.returncode is None or not p.stdin.closed or not p.stdout.closed for p in created)) and time.monotonic()<end:
                time.sleep(.02)
            assert not any(identity(pid) for pid in pids), ('product leak',pids)
            for proc in created:
                assert proc.returncode is not None
                assert proc.stdin.closed and proc.stdout.closed
    finally:
        for t in timers:t.cancel();t.join()
        try: box.lsp.close()
        except PersistenceError: pass
        spawn_patch.stop()
        for proc in created:
            if proc.returncode is None:
                try: os.killpg(proc.pid,signal.SIGKILL)
                except ProcessLookupError: pass
                proc.wait(timeout=2)
            proc.stdin.close();proc.stdout.close()
        store.close()
        p=root/'pids'
        if p.exists():
            for pid in json.loads(p.read_text()):
                if identity(pid):
                    try: os.kill(pid,signal.SIGKILL)
                    except ProcessLookupError: pass


class TestLifecycle(unittest.TestCase):
    def run_scenario(self, mode):
        with tempfile.TemporaryDirectory(prefix='lsp-fixture-') as tmp:
            env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1'}
            for name in ('HOME','XDG_CONFIG_HOME','XDG_STATE_HOME','XDG_CACHE_HOME','XDG_DATA_HOME'):
                p=Path(tmp)/name;p.mkdir();env[name]=str(p)
            code='from tests.test_lsp_lifecycle import scenario; scenario(%r,%r)'%(mode,tmp)
            proc=subprocess.Popen([sys.executable,'-c',code],env=env,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,start_new_session=True)
            try:
                out=proc.communicate(timeout=15)[0].decode()
                self.assertEqual(proc.returncode,0,out)
            finally:
                if proc.returncode is None:
                    os.killpg(proc.pid,signal.SIGKILL);proc.communicate()
                # Full fixture fallback even if scenario was interrupted before finally.
                p=Path(tmp)/'pids'
                if p.exists():
                    from feiyu.jobs import identity
                    for pid in json.loads(p.read_text()):
                        if identity(pid):
                            try: os.killpg(pid,signal.SIGKILL)
                            except ProcessLookupError:
                                try: os.kill(pid,signal.SIGKILL)
                                except ProcessLookupError: pass

for _mode in ('init-timeout','init-fail','cancel-init','deadline-init','output-cancel','output-timeout',
              'stdin-cancel','pool-lock','client-lock','exit0','exit7','normal','idle-cancel','idle-save-fail','task-select',
              'close-init','prepare-fail','identity-save-fail','ready-save-fail','finish-save-fail','recovery'):
    setattr(TestLifecycle,'test_'+_mode.replace('-','_'),lambda self, mode=_mode:self.run_scenario(mode))
