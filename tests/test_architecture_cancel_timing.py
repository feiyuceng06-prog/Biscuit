"""Controlled real native HTTP cancellation; synthetic registries, no remote calls."""
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

from evals import architecture as a, architecture_authorization as auth, architecture_durable as d
from evals.architecture_anthropic import AnthropicTransport
from evals.architecture_sdk import SDKTransport
from evals.architecture_loopback import service
from tests.test_architecture_authorization import fixture
from tests.test_architecture_anthropic import message


class CancelTiming(unittest.TestCase):
    def test_durable_native_cancel_order(self):
        for provider in ('anthropic', 'openai'):
            for observed, broken in ((False, False), (False, True), (True, False), (True, True)):
                with self.subTest(provider=provider, observed=observed, broken=broken):
                    self.check_order(provider, observed, broken)

    def check_order(self, provider, observed, broken):
        evidence = os.environ.get('CANCEL_TIMING_EVIDENCE')
        name = provider+'-'+str(observed)+'-'+str(broken)
        if evidence:
            root = Path(evidence)/name
            root.mkdir(parents=True)
        else:
            tmp = tempfile.TemporaryDirectory()
            self.addCleanup(tmp.cleanup)
            root = Path(tmp.name)
        events = []
        lock = threading.Lock()
        def event(kind, **fields):
            with lock:
                events.append(dict(t_ns=time.monotonic_ns(), kind=kind, **fields))
                (root/'timeline.json').write_text(json.dumps(events, indent=2))
        config = a.anthropic_config() if provider == 'anthropic' else a.CONTRACT
        p = fixture(provider)['plan']
        p['model']['version'] = config['model']['version']
        p.update(issued_at=time.time()-60, expires_at=time.time()+3600, schema_version=2,
                 prompt_semantics='initial_constructor_and_system_not_full_requests')
        static = dict(runtime=d.environment(), config=config)
        p['measurement_lock'] = auth.digest(static)
        p['source_lock']['snapshot'] = auth.digest(a.source_lock())
        approval = dict(approved=True, approver='SYNTHETIC', record_id='timing',
                        plan_sha256=auth.digest(p), granted_at=time.time()-1, expires_at=time.time()+1800)
        receipt = auth.require_remote_contract(dict(plan=p, fee_authorization=approval), p)
        receipt.update(measurement_lock=p['measurement_lock'], trust='local_remeasurement_not_host_attestation')
        released = threading.Event()
        original = KeyboardInterrupt('controlled native cancellation')
        failure = OSError('synthetic atomic save failure')
        def interrupt(*args):
            event('parent_cancel')
            raise original
        old = signal.signal(signal.SIGALRM, interrupt)
        self.addCleanup(signal.signal, signal.SIGALRM, old)
        def reply(h, params):
            event('http_request')
            if not observed:
                event('http_withheld_first_usage')
                os.kill(os.getpid(), signal.SIGALRM)
            else:
                h.send_response(200); h.end_headers()
                if provider == 'anthropic':
                    v = dict(type='message_start', message=dict(message(dict(input_tokens=8, output_tokens=2)), content=[], stop_reason=None))
                    raw = 'event: message_start\ndata: '+json.dumps(v)+'\n\n'
                else:
                    v = dict(id='synthetic', object='chat.completion.chunk', model=p['model']['version'], choices=[], usage=dict(prompt_tokens=8, completion_tokens=2, total_tokens=10))
                    raw = 'data: '+json.dumps(v)+'\n\n'
                event('http_write_first_usage')
                h.wfile.write(raw.encode()); h.wfile.flush()
                event('http_flushed_first_usage')
            released.wait(10)
        cls = AnthropicTransport if provider == 'anthropic' else SDKTransport
        with d.Controller(root/'registry') as c:
            c._consume(p, approval, receipt, dict(static=static))
            real_save = d.atomic_json
            def save(path, value):
                state = c.run['entries'][-1]['state'] if c.run['entries'] else None
                event('save_attempt', state=state)
                if broken and state == 'unknown':
                    event('save_failed')
                    raise failure
                real_save(path, value)
                event('save_committed', state=state)
            with service('executor', p['model']['version'], reply, provider=provider) as endpoint:
                t = cls(endpoint, p['model']['version'])
                real_observe = t.observe
                def observe(value, receipt):
                    event('parent_value_received')
                    real_observe(value, receipt)
                    event('parent_observed', usage=dict(receipt['usage_lower_bound']))
                    signal.raise_signal(signal.SIGALRM)
                parameters = dict(model=p['model']['version'], messages=[dict(role='user', content='synthetic')], stream=True)
                if provider == 'anthropic': parameters['max_tokens'] = 100
                try:
                    with patch.object(t, 'observe', observe), patch.object(d, 'atomic_json', save):
                        with self.assertRaises(KeyboardInterrupt) as caught:
                            c.invoke_sdk('snapshot/executor/development/0', 'one', 1, 'primary', parameters, 'synthetic system', t)
                    self.assertIs(caught.exception, original)
                finally:
                    released.set()
            kinds = [e['kind'] for e in events]
            self.assertEqual(kinds.count('http_request'), 1)
            self.assertLess(kinds.index('save_committed'), kinds.index('http_request'))
            if observed:
                self.assertLess(kinds.index('parent_observed'), kinds.index('parent_cancel'))
            else:
                self.assertNotIn('parent_observed', kinds)
                self.assertNotIn('http_write_first_usage', kinds)
            expected = dict(input=8, output=2) if observed else {}
            self.assertEqual(original.durable_attempt['usage_lower_bound'], expected)
            self.assertEqual(original.durable_attempt['state'], 'unknown')
            self.assertIsNone(original.durable_attempt['cost_cny'])
            self.assertIsNone(original.durable_attempt['supplier_invoice'])
            self.assertTrue(original.sdk_receipt['reaped'])
            with self.assertRaises(ProcessLookupError): os.kill(original.sdk_receipt['sdk_pid'], 0)
            event('child_reaped_exception_preserved', pid=original.sdk_receipt['sdk_pid'], usage=expected)
            disk = auth.load(c.path)['runs'][p['run_id']]
            self.assertEqual(disk['entries'][0]['state'], 'reserved' if broken else 'unknown')
            if broken:
                self.assertIsInstance(original.persistence_error, d.PersistenceFailure)
                self.assertIs(original.persistence_error.__cause__, failure)
                self.assertTrue(c.poisoned)
            else:
                self.assertEqual(disk['entries'][0]['usage_lower_bound'], expected)
            with self.assertRaises(d.Blocked): c._check()
            (root/'exception-facts.json').write_text(json.dumps(original.durable_attempt, indent=2))
            (root/'before-resume.json').write_text(json.dumps(disk, indent=2))
        code = """import json,sys
from evals.architecture_durable import Controller,Blocked
with Controller(sys.argv[1]) as c:
 r=c.resume(sys.argv[2]);assert len(r['entries'])==1
 e=r['entries'][0];assert e['state']=='unknown' and e['cost_cny'] is None
 assert r['limits']==json.loads(sys.argv[3]) and r['deadline']==float(sys.argv[4])
 try:c._check()
 except Blocked:pass
 else:raise AssertionError('unknown replenished')
 print(json.dumps(r))
"""
        argv = [sys.executable, '-c', code, str(root/'registry'), p['run_id'], json.dumps(disk['limits']), str(disk['deadline'])]
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        (root/'resume-command.json').write_text(json.dumps(dict(argv=argv, exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr), indent=2))
        self.assertEqual(result.returncode, 0, result.stderr)
        resumed = json.loads(result.stdout)
        self.assertEqual(resumed['entries'][0]['usage_lower_bound'], {} if broken else expected)
        event('fresh_process_resume_unknown_blocked')
