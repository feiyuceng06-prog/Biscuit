"""Real process boundaries; each child has private HOME/XDG and a hard timeout."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from feiyu.jobs import identity, signal_identity


class Lifecycle(unittest.TestCase):
    def run_child(self, body):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'SHELL': '/bin/bash',
                   'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': '/dev/null'}
            for key in ('HOME', 'XDG_CONFIG_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME', 'XDG_DATA_HOME'):
                path = root / key
                path.mkdir()
                env[key] = str(path)
            prelude = '''
import os, time, json, sys
from pathlib import Path
from feiyu.tools import Toolbox
from feiyu.taskstate import TaskStore, PersistenceError
from feiyu.jobs import restore_jobs
from unittest.mock import patch
root = Path(os.environ['HOME']) / 'workspace'
root.mkdir(exist_ok=True)
box = Toolbox(root)
def start(command):
    result = box.run('bash', dict(command=command, background=True))
    assert not result.is_error, result.content
    return box.jobs.all()[-1]
def until(check):
    end = time.monotonic() + 5
    while time.monotonic() < end:
        if check(): return
        time.sleep(.02)
    raise AssertionError('condition timed out')
'''
            proc = subprocess.Popen([sys.executable, '-c', prelude + body], env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    start_new_session=True, text=True)
            try:
                output, _ = proc.communicate(timeout=18)
            except subprocess.TimeoutExpired:
                import signal
                os.killpg(proc.pid, signal.SIGKILL)
                output, _ = proc.communicate()
                self.fail('hard timeout: ' + output)
            self.assertEqual(proc.returncode, 0, output)

    def test_running_then_real_exit_and_durable_output(self):
        self.run_child('''
j = start('printf ready; sleep .2; exit 7')
try:
    assert j.op['state'] == 'running', j.op
    assert j.op['session_id'] == j.state.session_id
    until(lambda: not j.running)
    assert j.op['state'] == 'failed', j.op
    assert j.code == 7
    assert 'ready' in j.take()[0]
    assert (j.store.directory / j.op['output_ref']).exists()
finally: box.jobs.kill_all()
''')

    def test_cancel_kills_descendants_and_allows_control_under_write_guard(self):
        self.run_child('''
j = start("sh -c 'sleep .5; echo late > late' & sleep 30")
try:
    with __import__('contextlib').nullcontext():
        try: box.run('write_file', dict(path='bad', content='bad'))
        except PersistenceError: pass
        else: raise AssertionError('write protection bypassed')
    box.run('job', dict(action='status', id=j.id))
    box.run('job', dict(action='output', id=j.id))
    box.run('job', dict(action='kill', id=j.id))
    assert j.op['state'] == 'cancelled', j.op
    time.sleep(.7)
    assert not (root / 'late').exists()
finally: box.jobs.kill_all()
''')

    def test_parent_cancel_and_job_wait_are_cancellable(self):
        self.run_child('''
from feiyu.runcontrol import RunControl, RunStopped
import threading
j = start('sleep 30')
c = RunControl(j.store, j.state)
j.control = c
box.execution.control = c
threading.Timer(.1, c.cancel).start()
try:
    box.run('job', dict(action='wait', id=j.id))
except RunStopped: pass
else: raise AssertionError('wait ignored cancellation')
until(lambda: j.op['state'] == 'cancelled')
box.jobs.kill_all()
''')

    def test_deadline_wait_and_newtask_reset_guard(self):
        self.run_child('''
from feiyu.agent import Feiyu
from feiyu.runcontrol import RunStopped
agent = Feiyu(root)
agent.time_budget = .4
box = agent.toolbox
j = start('sleep 30')
try:
    for method in (agent.new_task, agent.reset):
        try: method()
        except PersistenceError: pass
        else: raise AssertionError('lost active job')
    try: box.run('job', dict(action='wait', id=j.id))
    except RunStopped: pass
    until(lambda: not j.running)
    assert j.op['state'] == 'cancelled', j.op
    assert json.loads((j.directory / 'receipt.json').read_text())['reason'] == 'deadline'
finally: box.jobs.kill_all()
''')

    def test_missing_log_and_finish_storage_failure_unknown(self):
        self.run_child('''
j = start('sleep .1; echo done')
until(lambda: not j.running)
(j.directory / 'output').unlink()
j.refresh()
assert j.op['state'] == 'unknown'
try: j.kill()
except PersistenceError: pass
else: raise AssertionError('unknown was reported killed')
# Explicit acknowledgement is not success and never replays.
j.store.resolve(j.state, j.op['id'], 'checked missing output; uncertainty retained')
assert j.op['state'] == 'resolved'
''')

    def test_finish_write_failure_still_cleans(self):
        self.run_child('''
j = start("sh -c 'sleep .6; touch late' & sleep 30")
with patch.object(j.store, 'save', side_effect=PersistenceError('disk full')):
    try: j.kill()
    except PersistenceError: pass
    until(lambda: (j.directory / 'receipt.json').exists())
    assert j.op['state'] == 'unknown', j.op
time.sleep(.7)
assert not (root / 'late').exists()
''')

    def test_running_cannot_be_manually_resolved(self):
        self.run_child('''
j = start('sleep 30')
try:
    j.op['state'] = 'unknown'
    try: j.store.resolve(j.state, j.op['id'], 'pretend no effects')
    except PersistenceError: pass
    else: raise AssertionError('running resolve accepted')
    box.run('job', dict(action='kill', id=j.id))
finally: box.jobs.kill_all()
''')


    def test_running_recovery_old_pointer_pending_select_and_kill(self):
        self.run_child('''
from feiyu.agent import Feiyu
from feiyu.taskstate import TaskState, workspace_id
from feiyu import session
# Old session points at an earlier completed task, while a newer job is live.
a = Feiyu(root)
a._ensure_task_storage()
old = a.task_id
sid = a.session_id
a.new_task()
box = a.toolbox
j = start('sleep 30')
store = a._task_store
# Simulate a separate recovery reader; the supervisor survives writer close.
store.close()
b = Feiyu(root)
try:
    b.restore(dict(session_id=sid, task_ref=old, journal_only=True))
    assert j.state.task_id in b.task_control(dict(action='pending'))['pending']
    restored = b.toolbox.jobs.all()[0]
    assert restored.running
    try: b.new_task()
    except PersistenceError: pass
    else: raise AssertionError('hidden pending job')
    b.task_control(dict(action='select', task_id=j.state.task_id))
    try: b.task_control(dict(action='resolve', operation_id=j.op['id'], acknowledgement='no effects'))
    except PersistenceError: pass
    else: raise AssertionError('running job manually resolved')
    restored.op['state'] = 'unknown'
    b.toolbox.run('job', dict(action='kill', id=restored.id))
    assert restored.op['state'] == 'cancelled', restored.op
finally:
    # The old object has a deliberately closed writer; only the recovered owner cleans up.
    b.toolbox.jobs.kill_all()
''')

    def test_journal_running_write_failure_never_opens_gate(self):
        self.run_child('''
from feiyu.agent import Feiyu
a = Feiyu(root)
a._control()
box = a.toolbox
store = a._task_store
save = store.save
def fail_running(state):
    if any(op['state'] == 'running' for op in state.operations):
        raise PersistenceError('running write failed')
    return save(state)
with patch.object(store, 'save', side_effect=fail_running):
    try: start('touch must_not_run')
    except PersistenceError: pass
    else: raise AssertionError('storage failure swallowed')
time.sleep(.2)
assert not (root / 'must_not_run').exists()
assert not box.jobs.all()[0].proc.poll() is None
''')

    def test_parent_cancel_api_cleans_even_without_wait(self):
        self.run_child('''
from feiyu.agent import Feiyu
a = Feiyu(root)
box = a.toolbox
j = start("sh -c 'sleep .5; touch late' & sleep 30")
a.cancel()
assert j.op['state'] == 'cancelled'
time.sleep(.7)
assert not (root / 'late').exists()
''')

    def test_exit_without_receipt_does_not_become_success(self):
        self.run_child('''
j = start('true')
until(lambda: not j.running)
(j.directory / 'receipt.json').unlink()
until(lambda: j.proc.poll() is not None)
j.refresh()
assert j.op['state'] == 'unknown', j.op
assert j.code is None
''')

    def test_checkpoint_storage_failure_still_cleans_live_job(self):
        self.run_child('''
from feiyu.agent import Feiyu
a = Feiyu(root)
box = a.toolbox
j = start("sh -c 'sleep .5; touch late' & sleep 30")
with patch.object(a._task_store, 'save', side_effect=PersistenceError('disk failed')):
    try: a._task_checkpoint()
    except PersistenceError: pass
    else: raise AssertionError('critical failure swallowed')
until(lambda: j.proc.poll() is not None)
time.sleep(.7)
assert not (root / 'late').exists()
''')

    def test_identity_mismatch_never_signals(self):
        expected = identity(os.getpid())
        self.assertIsNotNone(expected)
        expected['start'] = 'wrong'
        with patch('feiyu.jobs._pidfd_send') as send:
            self.assertFalse(signal_identity(expected))
            send.assert_not_called()
        with patch('feiyu.jobs.identity', return_value=None), patch('feiyu.jobs._pidfd_send') as send:
            self.assertFalse(signal_identity(expected))
            send.assert_not_called()

    def test_crash_windows_recovery_never_replays(self):
        for window in ('prepared', 'spawn', 'running', 'finished-before-parent'):
            with self.subTest(window=window):
                self.run_child('''
# A separate writer dies at an exact durable boundary; same session is reopened.
import subprocess
crash = """
import os, sys, time
from pathlib import Path
from feiyu.tools import Toolbox
from feiyu import session
from feiyu.taskstate import TaskStore, TaskState, workspace_id
root = Path(os.environ['HOME']) / 'workspace'
box = Toolbox(root)
store = TaskStore(root, session.new_id())
state = TaskState(store.sid, 'task', workspace_id(root))
store.activate(state)
box.execution.durable = (store, state)
(root / 'sid').write_text(store.sid)
window = sys.argv[1]
original = store.save
def save(s):
    if window == 'finished-before-parent' and s.operations and s.operations[-1]['state'] in ('completed', 'failed', 'cancelled'):
        os._exit(74)  # output and receipt durable; terminal journal write not performed
    original(s)
    if s.operations:
        op = s.operations[-1]
        if window == 'prepared' and op['state'] == 'prepared' and 'kind' not in op: os._exit(71)
        if window == 'running' and op['state'] == 'running': os._exit(72)
store.save = save
if window == 'spawn':
    import feiyu.tools as t
    popen = t.subprocess.Popen
    def spawn(*a, **kw):
        proc = popen(*a, **kw)
        if 'jobrunner.py' in str(a): os._exit(73)
        return proc
    t.subprocess.Popen = spawn
box.run('bash', dict(command='echo once >> count; sleep .1; echo done', background=True))
# The monitor attempts terminal journal save after real command output/receipt.
end = time.monotonic() + 5
while time.monotonic() < end: time.sleep(.02)
os._exit(75)
"""
window = ''' + repr(window) + '''
p = subprocess.run([sys.executable, '-c', crash, window], timeout=7)
assert p.returncode in (71,72,73,74), p.returncode
time.sleep(.4)
sid = (root / 'sid').read_text()
store = TaskStore(root, sid)
state = store.recover()
assert state is not None
restore_jobs(box.jobs, store)
if window == 'finished-before-parent':
    j = box.jobs.all()[0]
    until(lambda: not j.running)
    assert j.op['state'] == 'completed', j.op
    assert (root / 'count').read_text().splitlines() == ['once']
else:
    assert state.operations[0]['state'] == 'unknown', state.operations
    assert not (root / 'count').exists()
# Repeated recovery observations cannot execute anything.
store.reconcile(state)
assert not (root / 'count').exists() or window == 'finished-before-parent'
''')

    def test_replaced_output_is_unknown_before_and_after_restore(self):
        self.run_child('''
from feiyu.jobs import Jobs
j = start('printf ORIGINAL_LOG')
until(lambda: not j.running)
assert j.op['state'] == 'completed', j.op
(j.directory / 'output').write_text('REPLACED_LOG')
result = box.run('job', dict(action='output', id=j.id))
assert 'REPLACED_LOG' not in result.content, result.content
assert j.op['state'] == 'unknown', j.op
sid = j.state.session_id
j.store.close()
store = TaskStore(root, sid)
try:
    state = store.recover()
    pool = Jobs()
    restore_jobs(pool, store)
    assert pool.all()[0].op['state'] == 'unknown'
    assert store.pending()
finally: store.close()
''')

    def test_output_directory_symlink_never_returns_external_content(self):
        self.run_child('''
j = start('printf ORIGINAL_LOG')
until(lambda: not j.running)
external = Path(os.environ['HOME']) / 'private-fixture'
external.mkdir()
(external / 'output').write_text('EXTERNAL_PRIVATE_FIXTURE')
j.directory.rename(j.directory.with_name(j.directory.name + '-original'))
j.directory.symlink_to(external, target_is_directory=True)
result = box.run('job', dict(action='output', id=j.id))
assert 'EXTERNAL_PRIVATE_FIXTURE' not in result.content, result.content
assert j.op['state'] == 'unknown', j.op
assert j.take() == ('', False)
''')
