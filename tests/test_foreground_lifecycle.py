"""Bounded, isolated real Shell/hook cancellation and evidence regressions."""
import unittest
from tests import test_job_lifecycle


class Foreground(unittest.TestCase):
    run_child = test_job_lifecycle.Lifecycle.run_child

    def exercise(self, body):
        self.run_child('''
import threading, signal, contextlib, io
from feiyu.agent import Feiyu
from feiyu import hooks, sandbox, session
from feiyu.runcontrol import RunStopped, RunControl
session.DIR = str(Path(os.environ['XDG_STATE_HOME']) / 'sessions')
a = Feiyu(root)
a.mode = 'auto'
a._ensure_task_storage()
c = a._control()
# Synthetic local commands explicitly use the unboxed path; existing bwrap
# regressions run separately and continue to exercise product defaults.
patcher = patch.object(sandbox, 'wrap', return_value=None)
patcher.start()
def hook(command, timeout=5):
    return hooks.Hook('PostToolUse', dict(command=command, timeout=timeout), 'verify:')
def stopped(fn, reason):
    try: fn()
    except RunStopped as exc: assert exc.reason == reason, exc.reason
    else: raise AssertionError('ignored parent stop')
def clean():
    time.sleep(.7)
    assert not (root / 'late').exists(), 'descendant survived'
    if (root / 'pid').exists():
        pid = int((root / 'pid').read_text())
        stat = Path('/proc') / str(pid) / 'stat'
        assert not stat.exists() or stat.read_text().split()[2] == 'Z', 'live descendant'
command = "echo started > started; sh -c 'echo $$ > pid; sleep .5; echo late > late' & sleep 30"
try:
''' + '\n'.join('    ' + line for line in body.splitlines()) + '''
finally:
    c.cancel()
    a.toolbox.jobs.kill_all()
    a.toolbox.lsp.close()
    a._task_store.close()
    patcher.stop()
''')

    def test_shell_cancel_has_real_exit_and_unknown_journal(self):
        self.exercise('''
threading.Timer(.15, a.cancel).start()
stopped(lambda: a.toolbox.run('bash', dict(command=command)), 'cancelled')
record = a.toolbox.execution.records[-1]
assert record['exit_code'] == -signal.SIGKILL, record
assert record['state'] == 'unknown', record
op = a.task_state.operations[-1]
assert op['exit_code'] == record['exit_code'] and op['state'] == 'unknown', op
assert op['execution_started'] and op['stop_reason'] == 'cancelled', op
assert (root / 'started').exists()
clean()
''')

    def test_deadline_survives_control_recreation_and_shell_wait(self):
        self.exercise('''
origin = time.time()
a.task_state.budget.update(started_at=origin, deadline=origin+.2, time_limit=.2)
a._task_store.save(a.task_state)
loaded = a._task_store.load(a.task_id)
restored = RunControl(a._task_store, loaded, time_limit=600)
assert restored.state.budget['deadline'] == a.task_state.budget['deadline']
a.task_state = loaded
a.toolbox.execution.durable = (a._task_store, loaded)
a.toolbox.execution.control = restored
stopped(lambda: a.toolbox.run('bash', dict(command=command)), 'deadline_stopped')
assert a.toolbox.execution.records[-1]['exit_code'] == -signal.SIGKILL
clean()
''')

    def test_shell_timeout_and_normal_exit_clean_descendants(self):
        for tail in ('sleep 30', 'exit 7'):
            self.exercise('''
result = a.toolbox.run('bash', dict(command="echo started; sh -c 'echo $$ > pid; sleep 2; echo late > late' & " + %r, timeout=1))
assert result.is_error
assert result.exit_code == %s, result.content
clean()
''' % (tail, '-signal.SIGKILL' if tail == 'sleep 30' else '7'))

    def test_standalone_hook_parent_cancel_and_deadline(self):
        for reason in ('cancelled', 'deadline_stopped'):
            self.exercise('''
if %r == 'cancelled': threading.Timer(.15, c.cancel).start()
else:
    a.task_state.budget['deadline'] = time.time()+.2
    c.monotonic_deadline = time.monotonic()+.2
out = hooks.run(hook(command), {}, root, control=c)
assert out.stop_reason == %r and out.execution_started, vars(out)
assert out.code == -signal.SIGKILL and out.execution_unknown
assert Path(out.log).exists()
clean()
''' % (reason, reason))

    def test_pre_post_and_verification_cancel(self):
        for event in ('PreToolUse', 'PostToolUse', 'verify'):
            self.exercise('''
h = hook(command)
h.event = %r
if h.event != 'verify': h.source = 'test'
threading.Timer(.15, a.cancel).start()
if %r == 'verify':
    a.verify = command
    stopped(lambda: a._run_verification(h, {}, 'post_change'), 'cancelled')
    row = a.verifications.records[-1]
    assert row['execution'] == 'unknown' and row['exit_code'] == -signal.SIGKILL, row
    assert a.verified_ok is None
else:
    a.hooks = [h]
    stopped(lambda: a._fire(%r, 'bash', dict(command='true')), 'cancelled')
assert a.task_state.operations[-1]['state'] == 'unknown'
clean()
''' % (event, event, event))

    def test_hook_timeout_and_normal_exit_clean_descendants(self):
        for tail in ('sleep 30', 'exit 7'):
            self.exercise('''
out = hooks.run(hook("sh -c 'echo $$ > pid; sleep 2; echo late > late' & " + %r, timeout=1), {}, root, control=c)
assert out.code == %s and out.execution_started, vars(out)
assert out.timed_out == %r, vars(out)
clean()
''' % (tail, '-signal.SIGKILL' if tail == 'sleep 30' else '7', tail == 'sleep 30'))

    def test_terminal_save_failure_preserves_exit_and_cleans_group(self):
        self.exercise('''
original = a._task_store.save
def fail_terminal(state):
    if any(op.get('ended') for op in state.operations): raise PersistenceError('injected terminal write')
    return original(state)
threading.Timer(.15, a.cancel).start()
with patch.object(a._task_store, 'save', side_effect=fail_terminal):
    try: a.toolbox.run('bash', dict(command=command))
    except PersistenceError: pass
    else: raise AssertionError('swallowed persistence failure')
record = a.toolbox.execution.records[-1]
assert record['state'] == 'unknown' and record['exit_code'] == -signal.SIGKILL, record
assert a.task_state.operations[-1]['state'] == 'unknown'
clean()
''')

    def test_prepare_failure_and_cancel_before_launch_have_no_effect(self):
        self.exercise('''
with patch.object(a._task_store, 'prepare', side_effect=PersistenceError('injected prepare')):
    try: a.toolbox.run('bash', dict(command='touch forbidden'))
    except PersistenceError: pass
    else: raise AssertionError('prepare failure ignored')
with patch('feiyu.permissions.verdict', return_value='deny'):
    out = hooks.run(hook('touch forbidden'), {}, root, control=c)
    assert out.rejected and not out.execution_started, vars(out)
c.cancel()
stopped(lambda: a.toolbox.run('bash', dict(command='touch forbidden')), 'cancelled')
stopped(lambda: hooks.run(hook('touch forbidden'), {}, root, control=c), 'cancelled')
assert not (root / 'forbidden').exists()
''')

    def test_hook_log_failure_retains_exit_and_unknown_evidence(self):
        self.exercise('''
a.verify = 'echo executed > started; exit 7'
from types import SimpleNamespace
from unittest.mock import Mock
log_os = SimpleNamespace(**dict(vars(os), fsync=Mock(side_effect=OSError('injected log fsync'))))
with patch.object(hooks, 'os', log_os):
    out = a._run_verification(hook(a.verify), {}, 'post_change')
row = a.verifications.records[-1]
assert (root / 'started').exists()
assert row['execution'] == 'failed' and row['exit_code'] == 7, row
assert row['evidence_error'] and not row['environment_error'], row
assert a.verified_ok is None
''')

    def test_sigint_during_launch_and_repeated_cleanup(self):
        for entry in ('shell', 'verify'):
            for phase in ('launch', 'kill', 'wait'):
                with self.subTest(entry=entry, phase=phase):
                    self.exercise("""
import sys, inspect, subprocess
from feiyu import processwait
entry, phase = %r, %r
fired = []
processes = []
old_handler = signal.getsignal(signal.SIGINT)
def tracer(frame, event, arg):
    if (event == 'return' and frame.f_code is subprocess.Popen.__init__.__code__
            and frame.f_back.f_code is processwait._run.__code__
            and not fired and getattr(frame.f_locals['self'], 'pid', None)):
        processes.append(frame.f_locals['self'])
        # Real SIGINT before ownership assignment in processwait's caller.
        time.sleep(.08)
        fired.append('launch')
        os.kill(os.getpid(), signal.SIGINT)
    if event == 'line' and frame.f_code is processwait._cleanup.__code__:
        line = inspect.getframeinfo(frame).code_context[0].strip()
        if len(fired) == 1 and ((phase == 'kill' and 'os.killpg(' in line)
                              or (phase == 'wait' and 'proc.wait()' in line)):
            fired.append(phase)
            os.kill(os.getpid(), signal.SIGINT)
    return tracer
try:
    sys.settrace(tracer)
    if entry == 'shell':
        stopped(lambda: a.toolbox.run('bash', dict(command=command)), 'cancelled')
    else:
        a.verify = command
        stopped(lambda: a._run_verification(hook(command), {}, 'post_change'), 'cancelled')
finally:
    sys.settrace(None)
    product_reaped = bool(processes) and all(proc.returncode is not None for proc in processes)
    # Failure cleanup never signals an already reaped/reused process ID.
    for proc in processes:
        if proc.returncode is None:
            try: os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            proc.wait(timeout=2)
assert product_reaped, 'product did not reap child'
assert fired == (['launch'] if phase == 'launch' else ['launch', phase]), fired
assert signal.getsignal(signal.SIGINT) == old_handler
assert processes[0].returncode == -signal.SIGKILL
op = a.task_state.operations[-1]
assert op['execution_started'] and op['exit_code'] == -signal.SIGKILL, op
assert op['stop_reason'] == 'cancelled' and op['state'] == 'unknown', op
if entry == 'verify':
    row = a.verifications.records[-1]
    assert row['execution'] == 'unknown' and row['exit_code'] == -signal.SIGKILL, row
clean()
""" % (entry, phase))
