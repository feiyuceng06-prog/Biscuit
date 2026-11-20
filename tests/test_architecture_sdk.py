"""Local HTTP/native SDK integration; synthetic key only."""
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest
from unittest.mock import patch

from evals import architecture as a
from evals.architecture_execution import Ledger, BudgetStop
from evals.architecture_loopback import service
from evals.architecture_sdk import SDKTransport, RemoteBlocked, require_remote_contract

MODEL = a.CONTRACT['model']['version']


def params(stream=True):
    p = dict(model=MODEL, messages=[dict(role='user', content='synthetic')], stream=stream,
             temperature=0, top_p=1, max_tokens=100)
    if stream:
        p['stream_options'] = {'include_usage': True}
    return p


class SDKAdapter(unittest.TestCase):
    def test_execute_cancel_persists_partial_request(self):
        from evals import architecture_execution as x
        out=Path(tempfile.mkdtemp(prefix='eval-cancel-')); self.addCleanup(__import__('shutil').rmtree, out)
        manifests=x.freeze(out,a.CONTRACT)
        adapter=out/'adapter';adapter.mkdir()
        for name in ('architecture_worker.py','architecture_runtime.py'):
            (adapter/name).write_bytes((a.ROOT/'evals'/name).read_bytes())
        seen=[]; captured=[]; saved=[]
        Original=x.Ledger
        class Capture(Original):
            def __init__(self,*args,**kw): super().__init__(*args,**kw); saved.append(self)
        def interrupt(*args): raise KeyboardInterrupt('review synthetic cancellation')
        def reply(h,p):
            seen.append(p)
            h.send_response(200);h.send_header('Content-Type','text/event-stream');h.end_headers()
            v=dict(id='synthetic',created=0,model=MODEL,object='chat.completion.chunk',choices=[],usage=dict(prompt_tokens=8,completion_tokens=2,total_tokens=10))
            h.wfile.write(b'data: '+json.dumps(v).encode()+b'\n\n');h.wfile.flush()
            h.connection.settimeout(4)
            try: h.rfile.read(1)
            except OSError: pass
        class CancelSDK(SDKTransport):
            def invoke(self,*args):
                signal.setitimer(signal.ITIMER_REAL,1.5)
                try: return super().invoke(*args)
                except KeyboardInterrupt as e:
                    captured.append(e.sdk_receipt);raise
                finally: signal.setitimer(signal.ITIMER_REAL,0)
        old=signal.signal(signal.SIGALRM,interrupt); x.Ledger=Capture
        try:
            with service('executor',MODEL,reply) as endpoint:
                try: x.execute(out,manifests,a.CONTRACT,'snapshot','executor',adapter,transport=CancelSDK(endpoint,MODEL))
                except KeyboardInterrupt: pass
        finally: signal.signal(signal.SIGALRM,old);x.Ledger=Original
        entry=next(iter(saved[0].entries.values()))
        assert len(seen)==1 and entry['usage_lower_bound']==dict(prompt_tokens=8,completion_tokens=2)
        assert entry['reaped'] and entry['cost_cny'] is None
        assert json.loads((out/'snapshot-executor/controller.json').read_text())['ledger'] == json.loads(json.dumps(list(saved[0].entries.values())))

    def test_boolean_usage_stops_admission_before_serialization(self):
        for stream, separator, content_type in ((False, b'\n', True), (True, b'\n', True),
                (True, b'\r', True), (True, b'\r\n', True), (True, b'\n', False)):
            for invalid in (False, True):
                def reply(h, p):
                    h.send_response(200)
                    if content_type:
                        h.send_header('Content-Type', 'text/event-stream' if stream else 'application/json')
                    h.end_headers()
                    value = dict(id='synthetic', created=0, model=MODEL,
                        object='chat.completion.chunk' if stream else 'chat.completion',
                        choices=[dict(index=0, finish_reason='stop',
                            **{('delta' if stream else 'message'): dict(role='assistant', content='ok')})],
                        usage=dict(prompt_tokens=invalid, completion_tokens=invalid, total_tokens=invalid))
                    raw = json.dumps(value).encode()
                    h.wfile.write(b'data: '+raw+separator*2+b'data: [DONE]'+separator*2 if stream else raw)
                ledger = Ledger(a.CONTRACT['budget'])
                with service('executor', MODEL, reply) as endpoint:
                    sdk = SDKTransport(endpoint, MODEL)
                    with self.assertRaises(BudgetStop):
                        ledger.invoke('1', 'primary', lambda r, n, role:
                            sdk.invoke(params(stream), r, n, role, time.monotonic()+10))
                self.assertIsNone(ledger.entries[('1', 1)]['cost_cny'])
                self.assertFalse(ledger.entries[('1', 1)]['usage_complete'])
                with self.assertRaises(BudgetStop): ledger.check()

    def test_native_stream_and_auxiliary_estimates_are_not_invoices(self):
        for stream in (True, False):
            with service('executor', MODEL) as endpoint:
                receipt = SDKTransport(endpoint, MODEL).invoke(params(stream), '1', 1,
                    'primary' if stream else 'auxiliary', time.monotonic()+10)
            self.assertEqual(receipt['outcome'], 'ok', receipt)
            self.assertIsNone(receipt['supplier_invoice'])
            self.assertIsNone(receipt['invoice'])
            self.assertEqual(receipt['usage_lower_bound'], dict(prompt_tokens=10, completion_tokens=5))
            self.assertEqual(receipt['returned_models'], [MODEL])
            self.assertTrue(receipt['reaped'])
            self.assertAlmostEqual(receipt['cost_cny'], .00002)
            self.assertTrue(Ledger.accounted(receipt))
            with self.assertRaises(ProcessLookupError): os.kill(receipt['sdk_pid'], 0)
            if stream: self.assertTrue(receipt['response']['calls'])

    def test_http_failure_no_hidden_sdk_retry_unknown_not_zero(self):
        seen = []
        def fail(handler, p):
            seen.append(p)
            handler.send_response(500); handler.end_headers()
            handler.wfile.write(b'{"error":{"message":"synthetic failure"}}')
        ledger = Ledger(a.CONTRACT['budget'])
        with service('executor', MODEL, fail) as endpoint:
            sdk = SDKTransport(endpoint, MODEL)
            with self.assertRaises(BudgetStop):
                ledger.invoke('1', 'auxiliary', lambda r, n, role: sdk.invoke(params(), r, n, role, time.monotonic()+10))
        self.assertEqual(len(seen), 1)
        self.assertEqual(len(ledger.entries), 1)
        e = next(iter(ledger.entries.values()))
        self.assertIsNone(e['cost_cny']); self.assertEqual(e['role'], 'auxiliary')
        self.assertEqual(e['outcome'], 'failed')

    def test_silence_half_sse_and_partial_usage_deadline(self):
        for mode in ('silent', 'half', 'partial'):
            def stall(h, p):
                h.send_response(200); h.send_header('Content-Type', 'text/event-stream'); h.end_headers()
                if mode == 'half': h.wfile.write(b'data: {"id":')
                if mode == 'partial':
                    value = dict(id='synthetic', created=0, model=MODEL, object='chat.completion.chunk', choices=[],
                                 usage=dict(prompt_tokens=8, completion_tokens=2, total_tokens=10))
                    h.wfile.write(b'data: '+json.dumps(value).encode()+b'\n\n')
                h.wfile.flush()
                # Wait for parent cancellation, bounded independently of SDK timeout.
                h.connection.settimeout(3)
                try: h.rfile.read(1)
                except OSError: pass
            with service('executor', MODEL, stall) as endpoint:
                start = time.monotonic()
                receipt = SDKTransport(endpoint, MODEL).invoke(params(), '1', 1, 'primary', start+2)
            self.assertLess(time.monotonic()-start, 4)
            self.assertTrue(receipt.get('deadline_exceeded'), receipt)
            self.assertIsNone(receipt['cost_cny']); self.assertFalse(receipt['usage_complete'])
            self.assertTrue(receipt['reaped'])
            if mode == 'partial': self.assertEqual(receipt['usage_lower_bound']['prompt_tokens'], 8)

    def test_unknown_usage_and_returned_model_drift(self):
        for model, usage in ((MODEL, None), ('unexpected', {'prompt_tokens': 1, 'completion_tokens': 1})):
            def reply(h, p):
                h.send_response(200); h.end_headers()
                h.wfile.write(json.dumps(dict(id='synthetic', created=0, model=model,
                    object='chat.completion', usage=usage,
                    choices=[dict(index=0, finish_reason='stop', message=dict(role='assistant', content='ok'))])).encode())
            with service('executor', MODEL, reply) as endpoint:
                receipt = SDKTransport(endpoint, MODEL).invoke(params(False), '1', 1, 'primary', time.monotonic()+10)
            self.assertEqual(receipt['outcome'], 'failed', receipt)
            self.assertIsNone(receipt['cost_cny'])

    def test_exception_cancel_and_physical_retry_reservations(self):
        for exc in (RuntimeError('save failed'), KeyboardInterrupt()):
            ledger = Ledger(a.CONTRACT['budget'])
            def fail(*args): raise exc
            with self.assertRaises(type(exc)): ledger.invoke('1', 'primary', fail)
            self.assertIsNone(ledger.entries[('1', 1)]['cost_cny'])
            self.assertEqual(ledger.entries[('1', 1)]['outcome'], 'failed')
            self.assertTrue(ledger.stopped)
        ledger = Ledger(a.CONTRACT['budget'])
        def retry(r, n, role):
            return dict(cost_cny=.1, invoice=None, supplier_invoice=None, synthetic=True,
                        usage_complete=True, accounting_basis='usage_fixed_price_estimate',
                        outcome='failed' if n == 1 else 'ok')
        ledger.invoke('1', 'auxiliary', retry)
        self.assertEqual(len(ledger.entries), 2)
        self.assertAlmostEqual(sum(e['cost_cny'] for e in ledger.entries.values()), .2)

    def test_authorization_missing_and_remote_always_disabled(self):
        with patch('subprocess.Popen', side_effect=AssertionError('must not spawn')):
            for endpoint in ('https://api.openai.com/v1', 'http://localhost:8000/v1',
                             'http://127.0.0.1:8000/v1?remote=1', 'http://key@127.0.0.1:80/v1'):
                with self.assertRaises(RemoteBlocked): SDKTransport(endpoint, MODEL)
            for contract in (None, {}, {'fee_authorization': True}):
                with self.assertRaisesRegex(RemoteBlocked, 'missing'): require_remote_contract(contract)
            with self.assertRaises(RemoteBlocked):
                require_remote_contract(dict.fromkeys(('fee_authorization', 'endpoint', 'model',
                    'dedicated_credential_file', 'source_lock', 'runtime_lock', 'prompt_lock', 'budget', 'billing_policy'), True))
        p = subprocess.run([os.sys.executable, '-m', 'evals.architecture', 'live'], capture_output=True)
        self.assertEqual(p.returncode, 2); self.assertIn(b'BLOCKED', p.stderr)

    def test_sdk_process_cancel_cleanup(self):
        def stall(h, p):
            h.connection.settimeout(3)
            try: h.rfile.read(1)
            except OSError: pass
        with service('executor', MODEL, stall) as endpoint:
            children = []
            original = subprocess.Popen
            def spawn(*args, **kwargs):
                child = original(*args, **kwargs); children.append(child); return child
            def cancel(*args): raise KeyboardInterrupt()
            old = signal.signal(signal.SIGALRM, cancel)
            signal.setitimer(signal.ITIMER_REAL, 1)
            try:
                with patch('subprocess.Popen', spawn), self.assertRaises(KeyboardInterrupt):
                    SDKTransport(endpoint, MODEL).invoke(params(), '1', 1, 'primary', time.monotonic()+10)
            finally:
                signal.setitimer(signal.ITIMER_REAL, 0); signal.signal(signal.SIGALRM, old)
            self.assertEqual(len(children), 1)
            self.assertIsNotNone(children[0].poll())
            self.assertTrue(children[0].stdout.closed)

    def test_callback_ipc_half_frame_and_request_backpressure(self):
        original = subprocess.Popen
        for program, payload in (("import sys,time;sys.stdout.write('{');sys.stdout.flush();time.sleep(30)", params()),
                                 ('import time;time.sleep(30)', dict(params(), messages=[{'role': 'user', 'content': 'x'*1000000}]))):
            children = []
            def spawn(argv, **kwargs):
                child = original([os.sys.executable, '-c', program], **kwargs)
                children.append(child); return child
            with patch('subprocess.Popen', spawn):
                start = time.monotonic()
                receipt = SDKTransport('http://127.0.0.1:1/v1', MODEL).invoke(payload, '1', 1, 'primary', start+.2)
            self.assertLess(time.monotonic()-start, 2)
            self.assertTrue(receipt.get('deadline_exceeded'), receipt)
            self.assertTrue(receipt['reaped']); self.assertIsNotNone(children[0].poll())

    def test_real_product_save_failure_retained(self):
        from evals import architecture_execution as x
        if not Path('/usr/bin/bwrap').exists(): self.skipTest('bubblewrap required')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifests = x.freeze(root, a.CONTRACT)
            adapter = root/'adapter'; adapter.mkdir()
            for name in ('architecture_worker.py', 'architecture_runtime.py'):
                data = (a.ROOT/'evals'/name).read_text()
                if name == 'architecture_worker.py':
                    data = data.replace('        session.save(Path(\'/work\'), agent)\n    rpc(\'done\'',
                        "        raise OSError('synthetic session save failure')\n    rpc('done'")
                (adapter/name).write_text(data)
                # This test deliberately freezes a fault-injected worker; the
                # adapter must still match that synthetic source inventory.
                frozen = root/'snapshot'/'evals'/name
                frozen.write_bytes((adapter/name).read_bytes())
                manifests['snapshot']['evals/'+name] = hashlib.sha256(frozen.read_bytes()).hexdigest()
            with service('executor', MODEL) as endpoint:
                result = x.execute(root, manifests, a.CONTRACT, 'snapshot', 'executor', adapter,
                                   transport=SDKTransport(endpoint, MODEL))
            self.assertEqual(result['status'], 'environment_failure')
            receipt = json.loads((root/'snapshot-executor/controller.json').read_text())
            self.assertGreater(len(receipt['ledger']), 0)
            self.assertIn('synthetic session save failure', (root/'snapshot-executor/worker-0.log').read_text())
            self.assertTrue(all(e['cost_cny'] is not None for e in receipt['ledger']))

    def test_redirect_does_not_escape_endpoint_binding(self):
        redirected = []
        def target(h, p):
            redirected.append(p); h.send_response(500); h.end_headers()
        with service('executor', MODEL, target) as other:
            def redirect(h, p):
                h.send_response(307); h.send_header('Location', other+'/chat/completions'); h.end_headers()
            with service('executor', MODEL, redirect) as endpoint:
                receipt = SDKTransport(endpoint, MODEL).invoke(params(), '1', 1, 'primary', time.monotonic()+10)
        self.assertEqual(redirected, [])
        self.assertEqual(receipt['outcome'], 'failed')
        self.assertIsNone(receipt['cost_cny'])

    def test_invalid_receipt_retains_attempt_reservation(self):
        ledger = Ledger(a.CONTRACT['budget'])
        with self.assertRaises(ValueError):
            ledger.invoke('1', 'primary', lambda *args: dict(cost_cny=float('nan'), invoice='synthetic'))
        self.assertIsNone(ledger.entries[('1', 1)]['cost_cny'])
        self.assertEqual(ledger.entries[('1', 1)]['outcome'], 'failed')
        self.assertTrue(ledger.stopped)
