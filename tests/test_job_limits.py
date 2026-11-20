"""Offline real supervisors; assertions precede fixture cleanup."""
import unittest
from tests import test_job_lifecycle as lifecycle


class BackgroundLimits(unittest.TestCase):
    run_child = lifecycle.Lifecycle.run_child

    def scenario(self, change, reason, setup='', locked=False):
        self.run_child('''
from feiyu.agent import Feiyu
import threading
agent = Feiyu(root)
box = agent.toolbox
''' + setup + '''
j = start("if read -r value; then touch input_leaked; fi; touch ready; sleep 30; touch forbidden")
until(lambda: (root / 'ready').exists())
assert not (root / 'input_leaked').exists()
c = j.control
''' + ('''
held, release = threading.Event(), threading.Event()
def owner():
    with c.lock:
        held.set()
        release.wait(8)
t = threading.Thread(target=owner)
t.start()
assert held.wait(2)
''' if locked else '') + '''
try:
    ''' + change + '''
    # Never job.wait/running/refresh: the product monitor must act by itself.
    until(lambda: (j.directory / 'receipt.json').exists())
    receipt = json.loads((j.directory / 'receipt.json').read_text())
    assert receipt['state'] == 'cancelled', receipt
    assert receipt['reason'] == ''' + repr(reason) + ''', receipt
    assert receipt['exit_code'] != 0, receipt
    until(lambda: j.proc.poll() is not None)
    assert not (root / 'forbidden').exists()
    assert not __import__('feiyu.jobs', fromlist=['identity']).identity(j.op['process']['pid'])
finally:
''' + ('''    release.set()
    t.join(2)
''' if locked else '') + '''    box.jobs.kill_all()
''')

    def test_no_wait_time_tightening_while_parent_locked(self):
        self.scenario('agent.time_budget = .15', 'deadline_stopped', locked=True)

    def test_no_wait_cost_tightening(self):
        self.scenario("agent.budget = .5", 'budget_stopped',
                      "agent._control().state.budget['cost'] = 1.0\n")

    def test_running_cost_reaches_limit(self):
        self.scenario("c.state.budget['cost'] = 1.0", 'budget_stopped', 'agent.budget = 1.0\n')

    def test_unknown_cost_finite_limit_while_locked(self):
        self.scenario("c.state.budget.update(cost=None, unknown_attempts=1); agent.budget = 1.0",
                      'budget_stopped', locked=True)

    def test_explicit_cancel_without_wait(self):
        self.scenario('c.cancel()', 'cancelled')

    def test_tightening_save_failure_preserves_error_and_cleans(self):
        self.run_child('''
from feiyu.agent import Feiyu
agent = Feiyu(root)
box = agent.toolbox
j = start('touch ready; sleep 30; touch forbidden')
until(lambda: (root / 'ready').exists())
primary = PersistenceError('tighten disk failure')
with patch.object(j.store, 'save', side_effect=primary):
    agent.time_budget = .15
    until(lambda: j.error is not None)
    until(lambda: (j.directory / 'receipt.json').exists())
    until(lambda: j.proc.poll() is not None)
    receipt = json.loads((j.directory / 'receipt.json').read_text())
    assert receipt['state'] == 'cancelled' and receipt['exit_code'] != 0, receipt
    assert receipt['reason'] == 'persistence_error', receipt
    assert j.op['state'] == 'unknown', j.op
    assert j.error is primary
    for action in (j.status, j.wait, j.control.check, j.kill):
        try: action()
        except PersistenceError as exc: assert exc is primary, repr(exc)
        else: raise AssertionError('monitor swallowed primary persistence error')
    assert not (root / 'forbidden').exists()
''')

    def test_first_take_preserves_terminal_save_error(self):
        self.run_child('''
from feiyu.agent import Feiyu
agent = Feiyu(root)
box = agent.toolbox
j = start('touch ready; while ! test -f release; do sleep .01; done; printf terminal; exit 7')
until(lambda: (root / 'ready').exists())
primary = PersistenceError('terminal import disk failure')
# Select foreground-first import without replacing the real monitor or receipt.
with j.lock:
    (root / 'release').touch()
    until(lambda: (j.directory / 'receipt.json').exists())
    j.proc.wait(timeout=2)
    assert j.error is None
    with patch.object(j.store, 'save', side_effect=primary):
        try: j.take()
        except PersistenceError as exc: assert exc is primary
        else: raise AssertionError('first take swallowed terminal persistence error')
    assert j.op['state'] == 'unknown'
''')

    def test_finished_job_retains_real_exit_after_tightening(self):
        self.run_child('''
from feiyu.agent import Feiyu
agent = Feiyu(root)
box = agent.toolbox
j = start('touch ready; exit 7')
until(lambda: (j.directory / 'receipt.json').exists())
before = (j.directory / 'receipt.json').read_bytes()
agent.time_budget = .001
agent.budget = .001
j.control.cancel()
until(lambda: j.proc.poll() is not None)
j.refresh()
assert j.op['state'] == 'failed' and j.code == 7, j.op
assert (j.directory / 'receipt.json').read_bytes() == before
''')

    def test_dead_parent_uses_last_delivered_deadline(self):
        self.run_child('''
import subprocess
script = """
from pathlib import Path
import os, time, json
from feiyu.agent import Feiyu
root = Path(os.environ['HOME']) / 'workspace'
a = Feiyu(root)
a.time_budget = 30
r = a.toolbox.run('bash', dict(command='touch ready; sleep 30; touch forbidden', background=True))
assert not r.is_error, r.content
j = a.toolbox.jobs.all()[0]
while not (root / 'ready').exists(): time.sleep(.01)
a.time_budget = 1.2
# Wait for actual supervisor receipt of the update via its later deadline stop;
# pipe write completion is the delivery boundary, not a journal-only promise.
while not j.sent_deadline or j.sent_deadline > time.time() + 2: time.sleep(.01)
(root / 'directory').write_text(str(j.directory))
os._exit(0)
"""
p = subprocess.run([sys.executable, '-c', script], timeout=5)
assert p.returncode == 0
directory = Path((root / 'directory').read_text())
until(lambda: (directory / 'receipt.json').exists())
r = json.loads((directory / 'receipt.json').read_text())
assert r['reason'] == 'deadline_stopped' and r['exit_code'] != 0, r
assert not (root / 'forbidden').exists()
''')

    def test_pending_attempt_alone_does_not_stop_and_limits_never_refill(self):
        self.run_child('''
from feiyu.agent import Feiyu
import threading
agent = Feiyu(root)
box = agent.toolbox
j = start('touch ready; sleep 30; touch forbidden')
until(lambda: (root / 'ready').exists())
assert not (root / 'input_leaked').exists()
c = j.control
held, release = threading.Event(), threading.Event()
def owner():
    with c.lock:
        c.state.budget['pending_attempts'] = 1
        held.set()
        release.wait(8)
t = threading.Thread(target=owner)
t.start()
assert held.wait(2)
try:
    agent.budget = 1
    until(lambda: c._background_cost == 1)
    assert not (j.directory / 'receipt.json').exists()
    agent.budget = 10
    c.state.budget.update(cost=1, pending_attempts=0)
    until(lambda: (j.directory / 'receipt.json').exists())
    r = json.loads((j.directory / 'receipt.json').read_text())
    assert r['reason'] == 'budget_stopped' and r['exit_code'] != 0, r
finally:
    release.set()
    t.join(2)
from feiyu.runcontrol import RunStopped
try: c.check()
except RunStopped as exc: assert exc.reason == 'budget_stopped'
else: raise AssertionError('allowance refilled after request lock release')
assert c.state.budget['cost_limit'] == 1
box.jobs.kill_all()
''')
