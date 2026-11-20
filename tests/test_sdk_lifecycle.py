"""SIGKILL probes use only disposable parents, loopback SDKs and synthetic journals."""
import ctypes
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from feiyu import sdk_lifecycle
from tests import test_sdk_worker

PARENT = r'''
import json, os, signal, subprocess, sys, time
from pathlib import Path
from feiyu import providers, sdk_worker
from feiyu.taskstate import TaskStore, TaskState, workspace_id
from feiyu.runcontrol import RunControl, active_control
root=Path(sys.argv[1]); mode=sys.argv[2]; url=sys.argv[3]
store=TaskStore(root,'session'); state=TaskState('session','task',workspace_id(root)); state.revise('synthetic')
control=RunControl(store,state,cost_limit=1,time_limit=60)
if mode=='startup':
 from feiyu import sdk_lifecycle
 reserve=sdk_lifecycle.reserve
 def paused_reserve():
  value=reserve()
  (root/'startup').write_text('reserved, no child')
  time.sleep(30)
  return value
 sdk_lifecycle.reserve=paused_reserve
real=subprocess.Popen
def spawn(*a,**kw):
 p=real(*a,**kw)
 if mode=='handoff': os.kill(p.pid,signal.SIGSTOP)
 (root/'spawn').write_text(str(p.pid))
 if mode=='handoff': time.sleep(30)
 return p
sdk_worker.subprocess.Popen=spawn
if mode=='complete':
 cleanup=sdk_worker.Exchange._cleanup
 def pause(self,exc):
  (root/'complete').write_text('protocol done')
  time.sleep(30)
  cleanup(self,exc)
 sdk_worker.Exchange._cleanup=pause
b=providers.OpenAICompatBackend(system='synthetic',tools=[],model='offline',api_key='offline-not-a-real-key',base_url=url)
b.rates=(1,1,1); b.cache=False
active_control.set(control)
def text(t):
 (root/'partial').write_text(t)
b.run_turn(on_text=text) if mode=='partial' else b.ask('synthetic')
'''
RECOVER = r'''
import sys, json
from pathlib import Path
from feiyu.taskstate import TaskStore
from feiyu.runcontrol import RunControl, RunStopped
store=TaskStore(Path(sys.argv[1]),'session'); state=store.load('task')
c=RunControl(store,state,cost_limit=100,time_limit=600)
assert state.budget['pending_attempts']==1
assert state.budget['cost'] is None and state.budget['cost_limit']==1
assert state.budget['attempts']==1
try: c.check()
except RunStopped as e: assert e.reason=='budget_stopped'
else: raise AssertionError('refilled/replayed')
print(json.dumps(state.budget))
store.close()
'''


def until(predicate, seconds=12):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        value = predicate()
        if value:
            return value
        time.sleep(.02)
    raise AssertionError('probe hard timeout')


@unittest.skipUnless(sys.platform == 'linux', 'Linux direct-child supervisor')
class LifecycleTests(unittest.TestCase):
    def test_parent_sigkill_handoff_silent_partial_and_complete(self):
        # Adopt only our disposable probe descendants, so even container PID1
        # cannot leave supervisor zombies behind. Product reaps the SDK child.
        libc = ctypes.CDLL(None, use_errno=True)
        old = ctypes.c_int()
        self.assertEqual(libc.prctl(37, ctypes.byref(old), 0, 0, 0), 0)
        self.assertEqual(libc.prctl(36, 1, 0, 0, 0), 0)
        try:
            for mode in ('handoff', 'silent', 'partial', 'complete'):
                with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp, test_sdk_worker.SDKWorkerTests().server(
                        'complete' if mode == 'complete' else 'partial' if mode == 'partial' else 'silent') as (url, received, requests):
                    root = Path(tmp)
                    env = dict(os.environ)
                    for key in ('HOME', 'XDG_STATE_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
                        path = root / key; path.mkdir(); env[key] = str(path)
                    parent = subprocess.Popen([sys.executable, '-c', PARENT, tmp, mode, url], env=env,
                                              stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    supervisor = worker = None
                    try:
                        supervisor = int(until(lambda: (root/'spawn').read_text() if (root/'spawn').exists() else None))
                        if mode == 'silent':
                            self.assertTrue(received.wait(12))
                        if mode in ('partial', 'complete'):
                            until(lambda: (root/mode).exists())
                        parent.kill(); parent.wait(timeout=3)
                        self.assertEqual(parent.returncode, -signal.SIGKILL)
                        if mode == 'handoff':
                            os.kill(supervisor, signal.SIGCONT)
                        slots = root/'XDG_STATE_HOME/feiyu/sdk-lifecycle'
                        def receipt():
                            for path in slots.iterdir():
                                try:
                                    row = json.loads(path.read_text())
                                    if row.get('state') == 'reaped': return row
                                except (ValueError, OSError): pass
                        row = until(receipt)
                        worker = row['worker']
                        self.assertEqual(row['supervisor'], supervisor)
                        self.assertEqual(row['parent'], parent.pid)
                        self.assertEqual(row['source'], 'sdk-supervisor')
                        # Completion can win the race; either way waitpid is a fact.
                        self.assertIn(row['reason'], ('exited', 'owner_pipe_closed'))
                        self.assertFalse(Path('/proc/%d' % worker).exists(), row)
                        def exited():
                            found = os.waitpid(supervisor, os.WNOHANG)
                            return found if found[0] else None
                        status = until(exited)
                        self.assertEqual(status, (supervisor, 0))
                        supervisor = None
                        if mode == 'handoff': self.assertEqual(len(requests), 0)
                        else: self.assertEqual(len(requests), 1)
                        # Correlation survives parent crash; final usage does not.
                        for lost in (False, True):
                            if lost:
                                for path in slots.iterdir(): path.write_text('{broken')
                            recovered = subprocess.run([sys.executable, '-c', RECOVER, tmp], env=env,
                                                       capture_output=True, timeout=10)
                            self.assertEqual(recovered.returncode, 0, recovered.stderr)
                            budget = json.loads(recovered.stdout)
                            self.assertEqual(budget['attempt_records'][0]['local_worker']['token'], row['token'])
                            print(json.dumps(dict(probe=mode, receipt=row, lost_receipt=lost, budget=budget)))
                            self.assertLessEqual(len(requests), 1)
                    finally:
                        if parent.poll() is None: parent.kill()
                        parent.wait(timeout=3); parent.stderr.close()
                        if supervisor:
                            children = Path('/proc/%d/task/%d/children' % (supervisor, supervisor))
                            if children.exists():
                                owned = children.read_text().split()
                                if owned: worker = int(owned[0])
                            try: os.kill(supervisor, signal.SIGCONT); os.kill(supervisor, signal.SIGKILL)
                            except ProcessLookupError: pass
                            try: os.waitpid(supervisor, 0)
                            except ChildProcessError: pass
                        if worker and Path('/proc/%d' % worker).exists():
                            os.kill(worker, signal.SIGKILL)
                            try: os.waitpid(worker, 0)
                            except ChildProcessError: pass
        finally:
            libc.prctl(36, old.value, 0, 0, 0)

    def test_parent_dies_before_spawn(self):
        with tempfile.TemporaryDirectory() as tmp, test_sdk_worker.SDKWorkerTests().server() as (url, _, requests):
            root = Path(tmp); env = dict(os.environ)
            for key in ('HOME', 'XDG_STATE_HOME', 'XDG_CONFIG_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
                path = root/key; path.mkdir(); env[key] = str(path)
            proc = subprocess.Popen([sys.executable, '-c', PARENT, tmp, 'startup', url], env=env,
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            try:
                until(lambda: (root/'startup').exists())
                proc.kill(); proc.wait(timeout=3)
                self.assertFalse((root/'spawn').exists())
                self.assertEqual(requests, [])
                recovery = subprocess.run([sys.executable, '-c', RECOVER, tmp], env=env,
                                          capture_output=True, timeout=10)
                self.assertEqual(recovery.returncode, 0, recovery.stderr)
                self.assertEqual(requests, [])
            finally:
                if proc.poll() is None: proc.kill()
                proc.wait(timeout=3); proc.stderr.close()

    def test_receipts_bounded_locked_and_conservative(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, XDG_STATE_HOME=tmp):
            fds = []
            try:
                for _ in range(sdk_lifecycle.SLOTS):
                    fd, ref = sdk_lifecycle.reserve(); fds.append(fd)
                    with self.assertRaises(ValueError): sdk_lifecycle.read_receipt(fd, ref['token'])
                with self.assertRaisesRegex(OSError, 'busy'): sdk_lifecycle.reserve()
                self.assertEqual(len(list(Path(ref['directory']).iterdir())), sdk_lifecycle.SLOTS)
                sdk_lifecycle.record(fds[0], dict(v=1, state='reaped', source='sdk-supervisor', token='other'))
                with self.assertRaises(ValueError): sdk_lifecycle.read_receipt(fds[0], ref['token'])
            finally:
                for fd in fds: os.close(fd)

    def test_failed_receipt_does_not_leave_sdk_child(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'receipt'; path.write_text('')
            reader, writer = os.pipe(); fd = os.open(path, os.O_RDONLY)
            argv = [sys.executable, '-m', 'feiyu', '--_sdk-supervisor', str(reader), str(fd), 'synthetic', str(os.getpid())]
            proc = subprocess.Popen(argv, pass_fds=(reader, fd), stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            try:
                self.assertEqual(proc.wait(timeout=4), 3)
                self.assertEqual(path.read_text(), '')
            finally:
                os.close(reader); os.close(writer); os.close(fd)
                if proc.poll() is None: proc.kill()
                proc.wait(timeout=3); proc.stdin.close(); proc.stdout.close()
