"""Real installed Anthropic SDK, synthetic local HTTP only."""
import json
import os
import signal
import tempfile
import time
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from evals import architecture as a
from evals.architecture_anthropic import AnthropicTransport, validate_usage
from evals.architecture_execution import Ledger, BudgetStop
from evals.architecture_loopback import service
from tests import test_architecture_sdk as shared

MODEL = a.ANTHROPIC_MODEL


def params(stream=True):
    return dict(model=MODEL, max_tokens=100, messages=[dict(role='user', content='synthetic')], stream=stream)


def message(usage):
    return dict(id='synthetic', type='message', role='assistant', model=MODEL,
        content=[dict(type='text', text='ok')], stop_reason='end_turn', stop_sequence=None, usage=usage)


class AnthropicSDK(unittest.TestCase):
    def test_truncated_stream_cannot_complete_accounting(self):
        for mode in ('normal', 'missing_stop', 'missing_delta', 'start_claims_done'):
            def reply(h, p):
                h.send_response(200); h.end_headers()
                initial = message(dict(input_tokens=10, output_tokens=1))
                initial['stop_reason'] = 'end_turn' if mode == 'start_claims_done' else None
                events = [dict(type='message_start', message=initial)]
                if mode not in ('missing_delta', 'start_claims_done'):
                    events.append(dict(type='message_delta', delta=dict(stop_reason='end_turn', stop_sequence=None),
                                       usage=dict(output_tokens=5)))
                if mode != 'missing_stop':
                    events.append(dict(type='message_stop'))
                for event in events:
                    h.wfile.write(('event: '+event['type']+'\ndata: '+json.dumps(event)+'\n\n').encode())
            receipt = self.invoke(params(), reply)
            self.assertTrue(receipt['reaped'])
            if mode == 'normal':
                self.assertTrue(receipt['usage_complete'], receipt)
            else:
                self.assertEqual(receipt['outcome'], 'failed', receipt)
                self.assertFalse(receipt['usage_complete'])
                self.assertIsNone(receipt['cost_cny'])
                self.assertEqual(receipt['usage_lower_bound']['input_tokens'], 10)
                ledger = Ledger(a.CONTRACT['budget'])
                with self.assertRaises(BudgetStop): ledger.invoke('1', 'primary', lambda *args: receipt)
                with self.assertRaises(BudgetStop): ledger.check()

    def invoke(self, p, responder=None, deadline=10):
        with service('executor', MODEL, responder, provider='anthropic') as endpoint:
            return AnthropicTransport(endpoint, MODEL).invoke(p, '1', 1, 'primary', time.monotonic()+deadline)

    def test_stream_nonstream_and_cache_not_double_counted(self):
        for stream in (True, False):
            r = self.invoke(params(stream))
            self.assertEqual(r['outcome'], 'ok', r)
            self.assertEqual(r['sdk_version'], '2.8.0')
            self.assertEqual(r['usage_lower_bound'], dict(input_tokens=10, output_tokens=5, cache_read_input_tokens=3, cache_creation_input_tokens=2))
            self.assertAlmostEqual(r['cost_cny'], .0000228)
            self.assertIsNone(r['invoice']); self.assertIsNone(r['supplier_invoice'])
            self.assertTrue(r['reaped'])
            with self.assertRaises(ProcessLookupError): os.kill(r['sdk_pid'], 0)
            if stream: self.assertEqual(r['response']['calls'][0]['name'], 'read_file')

    def test_raw_usage_fail_closed_before_sdk_coercion(self):
        for stream, sep in ((False,b'\n'), (True,b'\n'), (True,b'\r'), (True,b'\r\n')):
            for bad in (False, True, -1, '5', 1.5, None, 'missing', 'unknown'):
                seen = []
                def reply(h, p):
                    seen.append(p)
                    h.send_response(200); h.end_headers()  # no content-type dependency
                    u = dict(input_tokens=10, output_tokens=bad)
                    if bad == 'missing': u.pop('output_tokens')
                    if bad == 'unknown': u['future_tokens'] = 1
                    v = message(u)
                    if stream: v = dict(type='message_start', message=v)
                    raw = json.dumps(v).encode()
                    h.wfile.write(b'event: message_start'+sep+b'data: '+raw+sep*2 if stream else raw)
                r = self.invoke(params(stream), reply)
                self.assertEqual(r['outcome'], 'failed', r)
                self.assertIsNone(r['cost_cny']); self.assertFalse(r['usage_complete'])
                self.assertEqual(len(seen), 1)
                ledger=Ledger(a.CONTRACT['budget'])
                with self.assertRaises(BudgetStop): ledger.invoke('1','primary',lambda *args:r)
                with self.assertRaises(BudgetStop): ledger.check()

    def test_nested_cache_usage_and_unknown_event(self):
        usage=dict(input_tokens=10,output_tokens=5,cache_creation_input_tokens=3,
                   cache_creation=dict(ephemeral_5m_input_tokens=1,ephemeral_1h_input_tokens=2))
        validate_usage(message(usage))
        for n in (False, None, -1, '1'):
            with self.assertRaises(ValueError):
                validate_usage(message(dict(usage,cache_creation=dict(ephemeral_5m_input_tokens=n,ephemeral_1h_input_tokens=2))))
        with self.assertRaises(ValueError): validate_usage(dict(type='future_event'))

    def test_partial_usage_deadline(self):
        def reply(h,p):
            h.send_response(200);h.end_headers()
            v=dict(type='message_start',message=dict(message(dict(input_tokens=8,output_tokens=2)),content=[],stop_reason=None))
            h.wfile.write(b'event: message_start\ndata: '+json.dumps(v).encode()+b'\n\n');h.wfile.flush()
            h.connection.settimeout(4)
            try:h.rfile.read(1)
            except OSError:pass
        r=self.invoke(params(),reply,2)
        self.assertTrue(r['deadline_exceeded'],r)
        self.assertEqual(r['usage_lower_bound']['input_tokens'],8)
        self.assertFalse(r['usage_complete']);self.assertIsNone(r['cost_cny']);self.assertTrue(r['reaped'])

    def test_shared_supervision_and_remote_boundaries(self):
        # Exercise the same native child through existing failure/cancel/backpressure assertions.
        original=shared.service
        def native_service(group,model,responder=None):
            return original(group,model,responder,provider='anthropic')
        with patch.multiple(shared,MODEL=MODEL,params=params,SDKTransport=AnthropicTransport,service=native_service):
            for name in ('test_http_failure_no_hidden_sdk_retry_unknown_not_zero',
                         'test_sdk_process_cancel_cleanup','test_callback_ipc_half_frame_and_request_backpressure',
                         'test_authorization_missing_and_remote_always_disabled'):
                getattr(shared.SDKAdapter(name),name)()

    def test_native_execute_cancel_persistence_and_original_exception(self):
        self.cancel_execute(False)
        self.cancel_execute(True)

    def test_native_execute_cancel_before_first_usage(self):
        self.cancel_execute(False, before_usage=True)

    def cancel_execute(self, save_failure, before_usage=False):
        from evals import architecture_execution as x
        with tempfile.TemporaryDirectory(prefix='anthropic-cancel-') as tmp:
            out=Path(tmp);config=a.anthropic_config();manifests=x.freeze(out,config)
            adapter=out/'adapter';adapter.mkdir()
            for name in ('architecture_worker.py','architecture_runtime.py'):
                (adapter/name).write_bytes((a.ROOT/'evals'/name).read_bytes())
            exc=KeyboardInterrupt('synthetic cancellation')
            def interrupt(*args):raise exc
            released = threading.Event()
            self.addCleanup(released.set)
            def reply(h,p):
                if before_usage:
                    os.kill(os.getpid(), signal.SIGALRM)
                    released.wait(10)
                    return
                h.send_response(200);h.end_headers()
                v=dict(type='message_start',message=dict(message(dict(input_tokens=8,output_tokens=2)),content=[],stop_reason=None))
                h.wfile.write(b'event: message_start\ndata: '+json.dumps(v).encode()+b'\n\n');h.wfile.flush()
                released.wait(10)
            class Cancel(AnthropicTransport):
                def observe(self,value,receipt):
                    super().observe(value,receipt)
                    if receipt['usage_lower_bound']:
                        signal.raise_signal(signal.SIGALRM)
            old=signal.signal(signal.SIGALRM,interrupt)
            original_write=x.write
            failure=OSError('synthetic controller write failure')
            def write(path,obj):
                if save_failure and path.name=='controller.json':raise failure
                return original_write(path,obj)
            x.write=write
            try:
                with service('executor',MODEL,reply,provider='anthropic') as endpoint:
                    with self.assertRaises(KeyboardInterrupt) as caught:
                        try:
                            x.execute(out,manifests,config,'snapshot','executor',adapter,transport=Cancel(endpoint,MODEL))
                        finally:
                            released.set()
                self.assertIs(caught.exception,exc)
            finally:
                signal.signal(signal.SIGALRM,old)
                x.write=original_write
            self.assertTrue(exc.sdk_receipt['reaped'])
            self.assertFalse(exc.sdk_receipt['usage_complete'])
            self.assertIsNone(exc.sdk_receipt['cost_cny'])
            with self.assertRaises(ProcessLookupError): os.kill(exc.sdk_receipt['sdk_pid'], 0)
            self.assertEqual(exc.sdk_receipt['usage_lower_bound'], {} if before_usage else dict(input_tokens=8,output_tokens=2))
            if save_failure:
                self.assertIs(exc.controller_persistence_error,failure)
                self.assertTrue(exc.sdk_receipt['reaped'])
                return
            c=json.loads((out/'snapshot-executor/controller.json').read_text())
            self.assertTrue(c['requests']);self.assertTrue(c['events'])
            self.assertEqual(c['ledger'][0]['usage_lower_bound'],{} if before_usage else dict(input_tokens=8,output_tokens=2))
            self.assertIsNone(c['ledger'][0]['cost_cny']);self.assertTrue(c['ledger'][0]['reaped'])

    def test_cumulative_delta_and_raw_framing(self):
        for sep in (b'\n',b'\r',b'\r\n'):
            def reply(h,p):
                h.send_response(200);h.end_headers()
                values=[dict(type='message_start',message=dict(message(dict(input_tokens=10,output_tokens=1,
                    cache_read_input_tokens=3,cache_creation_input_tokens=2)),content=[],stop_reason=None)),
                    dict(type='message_delta',delta=dict(stop_reason=None,stop_sequence=None),usage=dict(output_tokens=2)),
                    dict(type='message_delta',delta=dict(stop_reason='end_turn',stop_sequence=None),usage=dict(output_tokens=5)),
                    dict(type='message_stop')]
                for v in values:
                    raw=json.dumps(v).encode()
                    frame=b'event: '+v['type'].encode()+sep+b'data: {'+sep+b'data: '+raw[1:]+sep*2
                    for b in frame:
                        h.wfile.write(bytes([b]));h.wfile.flush()
            r=self.invoke(params(),reply)
            self.assertEqual(r['outcome'],'ok',r)
            self.assertAlmostEqual(r['cost_cny'],.0000228)

    def test_native_config_and_source_drift(self):
        import copy
        from evals import architecture_execution as x
        a.validate(a.anthropic_config())
        c=a.anthropic_config();c['model']['version']='other'
        with self.assertRaises(AssertionError):a.validate(c)
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp);c=a.anthropic_config();m=x.freeze(out,c)
            (out/'snapshot/feiyu/providers.py').write_text('substituted copy')
            adapter=out/'adapter';adapter.mkdir()
            with self.assertRaisesRegex(RuntimeError,'inventory/bytes'):
                x.execute(out,m,c,'snapshot','executor',adapter)
