"""Real installed SDKs against loopback only; product owns process cleanup."""
import contextlib
import json
import os
import subprocess
import sys
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import patch

from feiyu import providers, sdk_worker
from feiyu.runcontrol import RunControl, RunStopped, active_control
from feiyu.taskstate import PersistenceError
from tests import test_runcontrol


class SDKWorkerTests(unittest.TestCase):
    setUp = test_runcontrol.ParentControlTests.setUp

    @contextlib.contextmanager
    def server(self, mode='silent', anthropic=False, errors=(), error_text='cache unsupported'):
        received, stop = threading.Event(), threading.Event()
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(body)
                received.set()
                try:
                    status = errors[len(requests)-1] if len(requests) <= len(errors) else 200
                    if status != 200:
                        data = json.dumps({'error': {'message': error_text, 'type': 'invalid_request_error'}}).encode()
                        self.send_response(status); self.send_header('Content-Type', 'application/json')
                        self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)
                        return
                    if mode == 'silent':
                        stop.wait(8)
                        return
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream' if body.get('stream') else 'application/json')
                    self.end_headers()
                    if not body.get('stream'):
                        value = ({'id':'m', 'type':'message','role':'assistant','model':'offline',
                            'content':[{'type':'text','text':'answer'}], 'stop_reason':'end_turn',
                            'usage':{'input_tokens':10,'output_tokens':2}} if anthropic else {
                            'id':'c','object':'chat.completion','created':0,'model':'offline',
                            'choices':[{'index':0,'message':{'role':'assistant','content':'answer'},'finish_reason':'stop'}],
                            'usage':{'prompt_tokens':10,'completion_tokens':2,'total_tokens':12}})
                        self.wfile.write(json.dumps(value).encode()); return
                    if anthropic:
                        events = [dict(type='message_start', message=dict(id='m', type='message', role='assistant',
                            model='offline', content=[], stop_reason=None, usage=dict(input_tokens=10,output_tokens=0))),
                            dict(type='content_block_start',index=0,content_block=dict(type='text',text='')),
                            dict(type='content_block_delta',index=0,delta=dict(type='text_delta',text='answer'))]
                        if mode == 'complete':
                            events += [dict(type='content_block_stop',index=0), dict(type='message_delta',
                                delta=dict(stop_reason='end_turn',stop_sequence=None),usage=dict(output_tokens=2)),
                                dict(type='message_stop')]
                        for event in events:
                            self.wfile.write(('event: '+event['type']+'\ndata: '+json.dumps(event)+'\n\n').encode())
                    else:
                        value = dict(id='c',object='chat.completion.chunk',created=0,model='offline',
                            choices=[dict(index=0,delta=dict(content='answer',reasoning_content='thought'),
                                          finish_reason='stop' if mode == 'complete' else None)],
                            usage=dict(prompt_tokens=10,completion_tokens=2,total_tokens=12))
                        self.wfile.write(('data: '+json.dumps(value)+'\n\n').encode())
                        if mode == 'complete':
                            self.wfile.write(b'data: [DONE]\n\n')
                    self.wfile.flush()
                    if mode != 'complete':
                        stop.wait(8)
                except (BrokenPipeError, ConnectionResetError):
                    pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            yield 'http://127.0.0.1:%d/v1' % server.server_port, received, requests
        finally:
            stop.set(); server.shutdown(); server.server_close(); thread.join(2)

    def backend(self, url, anthropic=False):
        cls = providers.AnthropicBackend if anthropic else providers.OpenAICompatBackend
        b = cls(system='system', tools=[], model='offline', api_key='offline-not-a-real-key', base_url=url)
        self.addCleanup(b.client.close)
        b.rates = (1,1,1); b.cache = False
        b.add_user_message('hello')
        return b

    @contextlib.contextmanager
    def processes(self):
        procs = []
        real = subprocess.Popen
        def spawn(*args, **kw):
            proc = real(*args, **kw); procs.append(proc); return proc
        with patch('feiyu.sdk_worker.subprocess.Popen', side_effect=spawn):
            yield procs
        # Assert before fixture cleanup: product, not this test, must reap and close.
        self.assertTrue(procs)
        for proc in procs:
            self.assertIsNotNone(proc.returncode)
            self.assertTrue(proc.stdin.closed); self.assertTrue(proc.stdout.closed)
            if os.name == 'posix':
                with self.assertRaises(ChildProcessError):
                    os.waitpid(proc.pid, os.WNOHANG)

    def invoke(self, b, stream=False):
        return self.agent._model_call(b, 'run_turn', on_text=lambda t: None) if stream else self.agent._model_call(b, 'ask', 'hello')

    def test_cancel_at_wait_boundary(self):
        for anth in (False,True):
            for stream in (False,True):
                with self.subTest(anth=anth,stream=stream), self.server('complete',anth) as (url,_,_):
                    b=self.backend(url,anth); c=self.agent._control(); c.cancelled.clear()
                    old=len(b.messages); real=subprocess.Popen; procs=[]
                    def spawn(*a,**kw):
                        p=real(*a,**kw); procs.append(p); wait=p.wait
                        def stop_wait(*a,**kw):
                            result=wait(*a,**kw); c.cancel(); return result
                        p.wait=stop_wait
                        return p
                    with active(c), patch('feiyu.sdk_worker.subprocess.Popen',side_effect=spawn), self.assertRaises(RunStopped):
                        b.run_turn(lambda _:None) if stream else b.ask('hi')
                    for p in procs:
                        self.assertIsNotNone(p.returncode); self.assertTrue(p.stdin.closed and p.stdout.closed)
                        with self.assertRaises(ChildProcessError): os.waitpid(p.pid,os.WNOHANG)
                    row=c.state.budget['attempt_records'][-1]
                    self.assertNotEqual(row['usage_status'],'complete','stop during product wait must remain partial')
                    self.assertEqual(len(b.messages),old)

    def test_cleanup_unknown_blocks_retry_and_cache_fallback(self):
        for anth in (False, True):
            for status in (503, 400):
                with self.subTest(anth=anth, status=status), self.server('complete', anth, errors=(status,)) as (url, _, requests):
                    b = self.backend(url, anth)
                    b.cache = True
                    real = subprocess.Popen
                    procs = []
                    def spawn(*args, **kwargs):
                        proc = real(*args, **kwargs)
                        procs.append(proc)
                        wait = proc.wait
                        def failed_wait(*args, **kwargs):
                            wait(*args, **kwargs)
                            raise OSError('synthetic cleanup confirmation failure')
                        proc.wait = failed_wait
                        return proc
                    with patch('feiyu.sdk_worker.subprocess.Popen', side_effect=spawn):
                        with self.assertRaises(Exception) as caught:
                            self.invoke(b, stream=True)
                    self.assertIn('unknown', caught.exception.sdk_cleanup_error)
                    self.assertEqual(len(requests), 1)
                    self.assertEqual(len(procs), 1)
                    from feiyu.agent import transient, overflow, rejected
                    self.assertFalse(transient(caught.exception))
                    self.assertFalse(overflow(caught.exception))
                    self.assertFalse(rejected(caught.exception))
                    for proc in procs:
                        self.assertIsNotNone(proc.returncode)
                        self.assertTrue(proc.stdin.closed and proc.stdout.closed)
                        if os.name == 'posix':
                            with self.assertRaises(ChildProcessError):
                                os.waitpid(proc.pid, os.WNOHANG)

    @unittest.skipUnless(sys.platform == 'linux', 'Linux supervisor receipt')
    def test_receipt_failure_blocks_retry(self):
        with self.server('complete', errors=(503,)) as (url, _, requests):
            b = self.backend(url)
            with patch('feiyu.sdk_lifecycle.read_receipt', side_effect=ValueError('synthetic lost receipt')):
                with self.assertRaises(Exception) as caught:
                    self.invoke(b)
            self.assertEqual(caught.exception.status_code, 503)
            self.assertIn('unknown', caught.exception.sdk_cleanup_error)
            self.assertEqual(len(requests), 1)

    def test_silent_cancel_both_sdks_ask_and_stream(self):
        for anthropic in (False, True):
            for stream in (False, True):
                with self.subTest(anthropic=anthropic, stream=stream), self.server(anthropic=anthropic) as (url, ready, _):
                    b = self.backend(url, anthropic)
                    # Fresh task/control per case, preserving previous unknown facts separately.
                    self.agent._run_control = None
                    control = RunControl(self.agent._task_store, self.agent.task_state) if self.agent._task_store else None
                    if control is None:
                        self.agent._ensure_task_storage()
                        control = self.agent._control()
                    def cancel():
                        if ready.wait(4): control.cancel()
                    t = threading.Thread(target=cancel); t.start()
                    start = time.monotonic()
                    with self.processes(), active(control), self.assertRaises(RunStopped):
                        b.run_turn(lambda t: None) if stream else b.ask('hello')
                    t.join(4)
                    self.assertLess(time.monotonic()-start, 5)
                    self.assertEqual(control.state.budget['attempt_records'][-1]['usage_status'], 'unknown')

    def test_real_success_usage_and_native_history(self):
        for anthropic in (False, True):
            with self.subTest(anthropic=anthropic), self.server('complete', anthropic) as (url, _, requests):
                b = self.backend(url, anthropic)
                if anthropic:
                    b.messages[0]['content'] = [{'type':'image','source':{'type':'base64','media_type':'image/png','data':'YWJj'}}, {'type':'text','text':'hello'}]
                else:
                    b.messages[0]['content'] = [{'type':'image_url','image_url':{'url':'data:image/png;base64,YWJj'}}]
                with self.processes():
                    self.assertEqual(self.invoke(b), 'answer')
                    turn = self.invoke(b, True)
                self.assertEqual(turn.text, 'answer')
                self.assertEqual(b.tokens_total, 24)
                self.assertIn('YWJj', json.dumps(requests[-1]))
                self.assertEqual(self.agent.task_state.budget['attempt_records'][-1]['usage_status'], 'complete')
                if not anthropic: self.assertEqual(b.messages[-1]['reasoning_content'], 'thought')

    def test_partial_usage_cancel(self):
        for anthropic in (False, True):
            with self.subTest(anthropic=anthropic), self.server('partial', anthropic) as (url, ready, _):
                b = self.backend(url, anthropic)
                self.agent._ensure_task_storage(); control = self.agent._control()
                control.cancelled.clear()
                timers = []
                def text(_):
                    timer = threading.Timer(.15, control.cancel)
                    timers.append(timer); timer.start()
                try:
                    with self.processes(), active(control), self.assertRaises(RunStopped):
                        b.run_turn(text)
                finally:
                    for timer in timers: timer.join(2)
                row = control.state.budget['attempt_records'][-1]
                self.assertEqual(row['usage_status'], 'partial')
                self.assertGreater(row['tokens'], 0)
                self.assertIsNone(control.state.budget['cost'])

    def test_dynamic_deadline_during_silent_read(self):
        for anthropic in (False, True):
            for stream in (False, True):
                with self.subTest(anthropic=anthropic, stream=stream), self.server() as (url, ready, _):
                    b = self.backend(url, anthropic)
                    control = self.agent._control(); control.cancelled.clear()
                    control.state.budget.pop('deadline', None)
                    control.state.budget['time_limit'] = 0
                    control.state.budget['started_at'] = time.time()
                    control.monotonic_deadline = None
                    control._background_time = 0
                    control._background_deadline = control._background_mono = None
                    def tighten():
                        if ready.wait(4): control.tighten(time_limit=.2)
                    t = threading.Thread(target=tighten); t.start()
                    start = time.monotonic()
                    with self.processes(), active(control), self.assertRaises(RunStopped) as caught:
                        b.run_turn(lambda t: None) if stream else b.ask('hello')
                    t.join(3)
                    self.assertFalse(t.is_alive())
                    self.assertEqual(caught.exception.reason, 'deadline_stopped')
                    self.assertLess(time.monotonic()-start, 5)

    def test_request_lock_wait_is_cancellable_without_admission(self):
        control = self.agent._control()
        acquired, release = threading.Event(), threading.Event()
        def owner():
            with control.lock:
                acquired.set(); release.wait(4)
        t = threading.Thread(target=owner); t.start(); self.assertTrue(acquired.wait(1))
        timer = threading.Timer(.1, control.cancel); timer.start()
        try:
            with self.assertRaises(RunStopped):
                with control.attempt(self.agent.backend, report={}):
                    self.fail('must not admit')
            self.assertEqual(control.state.budget['attempts'], 0)
        finally:
            release.set(); t.join(2); timer.join(2)

    def test_worker_death_unknown_and_reaped(self):
        with self.server() as (url, _, _):
            b = self.backend(url)
            real = subprocess.Popen
            dead = []
            def killed(*args, **kw):
                proc = real(*args, **kw); dead.append(proc); proc.kill(); return proc
            with patch('feiyu.sdk_worker.subprocess.Popen', side_effect=killed), self.assertRaises((sdk_worker.WorkerError, BrokenPipeError)):
                self.invoke(b)
            self.assertIsNone(self.agent.task_state.budget['cost'])
            self.assertIsNotNone(dead[0].returncode)
            self.assertTrue(dead[0].stdin.closed)
            self.assertTrue(dead[0].stdout.closed)

    def test_backpressured_request_cancel_and_product_reaps(self):
        control = self.agent._control()
        real = subprocess.Popen
        procs = []
        def silent(*args, **kw):
            proc = real([sys.executable, '-c', 'import time; time.sleep(20)'], **kw)
            procs.append(proc); return proc
        timer = threading.Timer(.15, control.cancel); timer.start()
        try:
            with patch('feiyu.sdk_worker.subprocess.Popen', side_effect=silent), self.assertRaises(RunStopped):
                with sdk_worker.Exchange('openai', {}, 'ask', {'text':'x'*2000000}, control):
                    self.fail('request must remain blocked')
            self.assertIsNotNone(procs[0].returncode)
            self.assertTrue(procs[0].stdin.closed)
            self.assertTrue(procs[0].stdout.closed)
        finally:
            timer.join(2)

    def test_retry_and_cache_fallback_remain_parent_attempts(self):
        for anthropic in (False, True):
            with self.subTest(anthropic=anthropic), self.server('complete', anthropic, (503,)) as (url, _, requests):
                b = self.backend(url, anthropic)
                with self.processes(): self.assertEqual(self.invoke(b), 'answer')
                self.assertEqual(len(requests), 2)
            with self.server('complete', anthropic, (400,)) as (url, _, requests):
                b = self.backend(url, anthropic); b.cache = True
                with self.processes(): self.assertEqual(self.invoke(b, True).text, 'answer')
                self.assertEqual(len(requests), 2); self.assertFalse(b.cache)

    def test_save_failure_during_stream_preserves_error_and_reaps(self):
        with self.server('partial') as (url, _, _):
            b = self.backend(url)
            control = self.agent._control()
            error = PersistenceError('synthetic durable failure')
            def fail(_):
                control.blocked = True
                raise error
            with self.processes(), active(control), self.assertRaises(PersistenceError) as caught:
                b.run_turn(fail)
            self.assertIs(caught.exception, error)
            self.assertEqual(control.state.budget['attempt_records'][-1]['usage_status'], 'partial')

    def test_terminal_result_cancel_keeps_usage_lower_bound(self):
        with self.server('complete') as (url, _, _):
            b = self.backend(url)
            control = self.agent._control()
            observe = b._observe
            def cancel(usage, anthropic=False):
                observe(usage, anthropic)
                control.cancel()
            with self.processes(), active(control), patch.object(b, '_observe', side_effect=cancel), self.assertRaises(RunStopped):
                b.ask('hello')
            row = control.state.budget['attempt_records'][-1]
            self.assertEqual(row['usage_status'], 'partial')
            self.assertEqual(row['tokens'], 12)

    def test_source_internal_route_does_not_load_app_configuration(self):
        proc = subprocess.run([sys.executable, '-m', 'feiyu', '--_sdk-worker'], input=b'',
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn(b'Traceback', proc.stderr)

    def test_native_codec_keeps_thinking_signature_tools_and_extensions(self):
        from anthropic.types import Message
        value = dict(id='m',type='message',role='assistant',model='offline',stop_reason='tool_use',
            usage=dict(input_tokens=1,output_tokens=2),content=[
                dict(type='thinking',thinking='reason',signature='signed'),
                dict(type='tool_use',id='t',name='tool',input={'image':['data']})])
        result = sdk_worker.restore('anthropic','result',value)
        self.assertIsInstance(result, Message)
        for original, restored in zip(value['content'], sdk_worker.plain(result)['content']):
            for key, item in original.items():
                self.assertEqual(restored[key], item)
        value = dict(id='c',object='chat.completion.chunk',created=0,model='offline',choices=[dict(index=0,
            delta=dict(reasoning_content='reason', tool_calls=[dict(index=0,id='t',type='function',
                function=dict(name='tool',arguments='{"x":'))], extension={'keep':True}),finish_reason=None)])
        result = sdk_worker.restore('openai','event',value)
        self.assertEqual(sdk_worker.plain(result)['choices'][0]['delta']['extension'], {'keep':True})
        self.assertEqual(result.choices[0].delta.tool_calls[0].function.arguments, '{"x":')

    def test_pending_finite_budget_does_not_stop_own_worker(self):
        self.agent.budget = 1
        with self.server('complete') as (url, _, _), self.processes():
            self.assertEqual(self.invoke(self.backend(url)), 'answer')
        self.assertEqual(self.agent.task_state.budget['unknown_attempts'], 0)

    def test_sigint_during_spawn_handoff_reaps_worker(self):
        if os.name != 'posix': self.skipTest('POSIX signal injection')
        import signal
        with self.server() as (url, _, _), self.processes():
            b = self.backend(url)
            # Wrap the recording Popen to retain assertions in processes().
            recorded = sdk_worker.subprocess.Popen
            def spawn(*args, **kwargs):
                proc = recorded(*args, **kwargs)
                os.kill(os.getpid(), signal.SIGINT)
                return proc
            with patch('feiyu.sdk_worker.subprocess.Popen', side_effect=spawn), self.assertRaises(RunStopped):
                self.invoke(b)

    def test_structured_error_preserves_overflow_without_echoing_body(self):
        from feiyu.agent import overflow, limit_in_error
        with self.server('complete', errors=(400,), error_text='maximum context length is 65536 tokens PRIVATE') as (url, _, _):
            b = self.backend(url)
            with self.processes(), self.assertRaises(sdk_worker.WorkerError) as caught:
                self.invoke(b)
            self.assertTrue(overflow(caught.exception))
            self.assertEqual(limit_in_error(caught.exception), 65536)
            self.assertNotIn('PRIVATE', str(caught.exception))


@contextlib.contextmanager
def active(control):
    token = active_control.set(control)
    try: yield
    finally: active_control.reset(token)
