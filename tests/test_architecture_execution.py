"""Offline controller contract boundaries; no product state or remote providers."""
import tempfile
from pathlib import Path
import unittest
from evals import architecture as a
from evals.architecture_execution import Ledger, BudgetStop, verify_package


class ExecutionContracts(unittest.TestCase):
    def ledger(self, now=lambda: 0):
        return Ledger(a.CONTRACT['budget'], now)

    def test_zero_unknown_missing_and_duplicates(self):
        ledger = self.ledger()
        ledger.charge('main', 1, 'primary', 0.0, 'fake-zero')
        ledger.check()
        with self.assertRaisesRegex(RuntimeError, 'duplicate'):
            ledger.charge('main', 1, 'failed', 0.0, 'fake-zero')
        for cost, invoice in ((None, 'unknown-price'), (0.0, None)):
            ledger = self.ledger()
            ledger.charge('helper', 1, 'auxiliary', cost, invoice, 'failed')
            with self.assertRaises(BudgetStop):
                ledger.check()

    def test_retry_exhaustion_no_double_charge(self):
        ledger = self.ledger()
        with self.assertRaisesRegex(BudgetStop, 'exhausted'):
            ledger.invoke('request', 'auxiliary', lambda *args: dict(cost_cny=.2, invoice='fake', outcome='failed'))
        self.assertEqual(len(ledger.entries), 2)
        self.assertAlmostEqual(sum(e['cost_cny'] for e in ledger.entries.values()), .4)
        self.assertTrue(all(e['role'] == 'auxiliary' for e in ledger.entries.values()))
        with self.assertRaises(BudgetStop):
            ledger.check()  # parent ledger reused across a restarted worker

    def test_rounds_wall_money_limits(self):
        ledger = self.ledger()
        for round_number in range(30):
            ledger.invoke(str(round_number), 'primary', lambda *args: dict(cost_cny=0, invoice='synthetic'))
            ledger.rounds += 1
        self.assertEqual(len(ledger.entries), 30)
        with self.assertRaises(BudgetStop): ledger.check()
        clock = [0]
        ledger = self.ledger(lambda: clock[0])
        clock[0] = 120
        with self.assertRaises(BudgetStop): ledger.check()
        ledger = self.ledger()
        ledger.charge('cost', 1, 'primary', 3.0, 'fake')
        with self.assertRaises(BudgetStop): ledger.check()
        for invalid in (-1, float('nan'), float('inf'), True):
            with self.assertRaises(ValueError): self.ledger().charge('bad', 1, 'primary', invalid, 'fake')

    def test_source_inventory_and_byte_substitution_rejected(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root/'module.py').write_bytes(b'original')
            manifest = {'module.py': hashlib.sha256(b'original').hexdigest()}
            verify_package(root, manifest)
            (root/'extra.py').write_bytes(b'extra')
            with self.assertRaisesRegex(RuntimeError, 'inventory'): verify_package(root, manifest)
            (root/'extra.py').unlink()
            (root/'module.py').write_bytes(b'substituted')
            with self.assertRaisesRegex(RuntimeError, 'bytes'): verify_package(root, manifest)

    def test_transport_retry_receipts_and_budget_stop_precede_success(self):
        for receipt in (dict(cost_cny=None, invoice='unknown'), dict(cost_cny=0, invoice=None),
                        dict(cost_cny=3.1, invoice='over-budget')):
            ledger = self.ledger()
            with self.assertRaises(BudgetStop):
                ledger.invoke('main', 'primary', lambda *args: receipt)
            self.assertTrue(ledger.stopped)
            self.assertEqual(len(ledger.entries), 1)
        ledger = self.ledger()
        calls = []
        def transport(request, attempt, role):
            calls.append((request, attempt, role))
            return dict(cost_cny=.1, invoice='synthetic', outcome='failed' if attempt == 1 else 'ok')
        ledger.invoke('logical-request', 'primary', transport)
        self.assertEqual(calls, [('logical-request', 1, 'primary'), ('logical-request', 2, 'primary')])
        self.assertAlmostEqual(sum(e['cost_cny'] for e in ledger.entries.values()), .2)


class FrameDeadlines(unittest.TestCase):
    def test_partial_frame_actual_worker_deadline_and_eof(self):
        import copy
        import hashlib
        import json
        import signal
        import time
        from evals import architecture_execution as x
        if not Path('/usr/bin/bwrap').exists():
            self.skipTest('bubblewrap required')
        for suffix in ('\nimport time; time.sleep(30)\n', '\n'):
            with self.subTest(suffix=suffix), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                source = root/'snapshot/feiyu'
                source.mkdir(parents=True)
                (source/'__init__.py').write_text('')
                manifest = {'feiyu/__init__.py': hashlib.sha256(b'').hexdigest()}
                adapter = root/'adapter'; adapter.mkdir()
                (adapter/'architecture_worker.py').write_text(
                    "import sys\nsys.stdout.write('{\\\"kind\\\":');sys.stdout.flush()" + suffix)
                (adapter/'architecture_runtime.py').write_text('')
                (root/'snapshot/evals').mkdir()
                for name in ('architecture_worker.py', 'architecture_runtime.py'):
                    data = (adapter/name).read_bytes()
                    (root/'snapshot/evals'/name).write_bytes(data)
                    manifest['evals/'+name] = hashlib.sha256(data).hexdigest()
                config = copy.deepcopy(a.CONTRACT)
                config['budget']['seconds'] = 1
                def guard(*args):
                    raise RuntimeError('external test timeout')
                old = signal.signal(signal.SIGALRM, guard)
                signal.setitimer(signal.ITIMER_REAL, 4)
                started = time.monotonic()
                try:
                    result = x.execute(root, {'snapshot': manifest}, config, 'snapshot', 'executor', adapter)
                finally:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    signal.signal(signal.SIGALRM, old)
                self.assertLess(time.monotonic()-started, 3)
                receipt = json.loads((root/'snapshot-executor/controller.json').read_text())
                errors = [e.get('error', '') for e in receipt['events']]
                if 'sleep' in suffix:
                    self.assertEqual(result['status'], 'budget_stop', errors)
                    self.assertIn('parent wall deadline', errors)
                else:
                    self.assertEqual(result['status'], 'environment_failure', errors)
                    self.assertTrue(any('incomplete frame' in e for e in errors), errors)

    def test_reply_backpressure_obeys_same_deadline(self):
        import os
        import time
        from evals.architecture_execution import send_frame
        read_fd, write_fd = os.pipe()
        with os.fdopen(read_fd, 'rb', buffering=0), os.fdopen(write_fd, 'wb', buffering=0) as writer:
            os.set_blocking(write_fd, False)
            while True:
                try:
                    os.write(write_fd, b'x'*65536)
                except BlockingIOError:
                    break
            started = time.monotonic()
            with self.assertRaisesRegex(BudgetStop, 'wall deadline'):
                send_frame(writer, {'reply': 'not consumed'}, started+.05)
            self.assertLess(time.monotonic()-started, 1)
