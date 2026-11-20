"""Eval-only OpenAI SDK transport. Literal loopback and synthetic credentials only."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import time
from urllib.parse import urlsplit

from evals.architecture_execution import BudgetStop, MAX_FRAME, remaining_time, send_frame


from evals.architecture_authorization import RemoteBlocked, require_remote_contract

class SDKTransport:
    usage_keys = ('prompt_tokens', 'completion_tokens')

    def observe(self, value, receipt):
        model = value.get('model')
        if model and model not in receipt['returned_models']:
            receipt['returned_models'].append(model)
        for key in self.usage_keys:
            n = (value.get('usage') or {}).get(key)
            if type(n) is int and n >= 0:
                receipt['usage_lower_bound'][key] = max(n, receipt['usage_lower_bound'].get(key, 0))

    def complete(self, chunks, receipt, params):
        usage = receipt['usage_lower_bound']
        final = chunks[-1].get('usage') or {} if chunks else {}
        if len(usage) != 2 or any(type(final.get(k)) is not int or final[k] != usage[k] for k in usage):
            raise RuntimeError('unknown usage')
        return normalize(chunks, self.model, params.get('stream', False))

    def __init__(self, endpoint, model, rates=(1.0, 2.0), child_path=None):
        url = urlsplit(endpoint)
        if (url.scheme != 'http' or url.hostname != '127.0.0.1' or not url.port or
                url.username or url.password or url.query or url.fragment or url.path != '/v1'):
            raise RemoteBlocked('only literal 127.0.0.1 synthetic HTTP endpoint allowed')
        if len(rates) != len(self.usage_keys) or any(type(r) not in (float, int) or not 0 <= r < float('inf') for r in rates):
            raise ValueError('invalid fixed CNY per million rates')
        self.endpoint, self.model, self.rates = endpoint, model, rates
        self.child_path = child_path or Path(__file__).with_name('architecture_sdk_child.py')

    def invoke(self, params, request, attempt, role, deadline):
        receipt = dict(outcome='failed', cost_cny=None, invoice=None,
                       accounting_basis='usage_fixed_price_estimate', supplier_invoice=None,
                       endpoint=self.endpoint, requested_model=self.model, returned_models=[],
                       usage_lower_bound={}, usage_complete=False, rates_cny_per_million=self.rates,
                       synthetic=True, rate_source='synthetic_fixture_not_supplier_quote',
                       semantics_sha256=hashlib.sha256(Path(sys.modules[type(self).__module__].__file__).read_bytes()).hexdigest(), request_sha256=hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest(),
                       adapter_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                       child_sha256=hashlib.sha256(self.child_path.read_bytes()).hexdigest(),
                       interpreter_sha256=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest())
        if params.get('model') != self.model:
            receipt['error'] = 'request model drift'
            return receipt
        env = {k: os.environ[k] for k in ('HOME', 'XDG_CONFIG_HOME', 'XDG_STATE_HOME',
               'XDG_CACHE_HOME', 'XDG_DATA_HOME', 'PATH', 'LANG') if k in os.environ}
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        p = subprocess.Popen([sys.executable, str(self.child_path)],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             env=env, bufsize=0, start_new_session=True)
        receipt['sdk_pid'] = p.pid
        buf = bytearray()
        chunks = []
        done = False
        try:
            os.set_blocking(p.stdin.fileno(), False)
            os.set_blocking(p.stdout.fileno(), False)
            send_frame(p.stdin, dict(endpoint=self.endpoint, params=params), deadline)
            p.stdin.close()
            with selectors.DefaultSelector() as sel:
                sel.register(p.stdout, selectors.EVENT_READ)
                while not done:
                    if not sel.select(remaining_time(deadline)):
                        remaining_time(deadline)
                    remaining_time(deadline)
                    try:
                        raw = os.read(p.stdout.fileno(), 65536)
                    except BlockingIOError:
                        continue
                    if not raw:
                        raise RuntimeError('SDK EOF/incomplete frame')
                    buf.extend(raw)
                    if len(buf) > MAX_FRAME:
                        raise RuntimeError('SDK frame too large')
                    while b'\n' in buf:
                        remaining_time(deadline)
                        line, _, tail = buf.partition(b'\n'); buf = bytearray(tail)
                        msg = json.loads(line)
                        if msg['kind'] == 'sdk':
                            receipt['sdk_version'] = msg['version']
                        elif msg['kind'] == 'value':
                            value = msg['value']; chunks.append(value)
                            self.observe(value, receipt)
                        elif msg['kind'] == 'error':
                            raise RuntimeError(msg['error'])
                        elif msg['kind'] == 'done':
                            done = True
                        else:
                            raise RuntimeError('invalid SDK frame kind')
            p.wait(timeout=remaining_time(deadline))
            if p.returncode:
                raise RuntimeError('SDK child exit '+str(p.returncode))
            if receipt['returned_models'] != [self.model]:
                raise RuntimeError('returned model drift/missing version')
            usage = receipt['usage_lower_bound']
            receipt['response'] = self.complete(chunks, receipt, params)
            receipt['usage_complete'] = True
            receipt['cost_cny'] = sum(usage[k]*rate/1e6 for k, rate in zip(self.usage_keys, self.rates))
            receipt['outcome'] = 'ok'
        except BaseException as exc:
            if not isinstance(exc, Exception):
                exc.sdk_receipt = receipt
                raise
            receipt['error'] = str(exc)
            if isinstance(exc, BudgetStop):
                receipt['deadline_exceeded'] = True
        finally:
            if p.poll() is None:
                os.killpg(p.pid, signal.SIGKILL)
            p.wait()
            p.stdout.close()
            if not p.stdin.closed:
                p.stdin.close()
            receipt['reaped'] = True
            receipt['estimate_lower_bound_cny'] = sum(receipt['usage_lower_bound'].get(k, 0)*r/1e6 for k, r in zip(self.usage_keys, self.rates))
        return receipt


def normalize(chunks, model, streaming):
    text, calls = [], {}
    for chunk in chunks:
        for choice in chunk.get('choices', []):
            if choice.get('finish_reason') not in (None, 'stop', 'tool_calls'):
                raise RuntimeError('incomplete/failed completion')
            msg = choice.get('delta' if streaming else 'message') or {}
            text.append(msg.get('content') or '')
            for i, call in enumerate(msg.get('tool_calls') or []):
                slot = calls.setdefault(call.get('index', i), {'name': '', 'arguments': ''})
                fn = call.get('function') or {}
                slot['name'] += fn.get('name') or ''
                slot['arguments'] += fn.get('arguments') or ''
    if not any(c.get('finish_reason') in ('stop', 'tool_calls') for x in chunks for c in x.get('choices', [])):
        raise RuntimeError('missing completion finish')
    return dict(version=model, text=''.join(text), calls=[dict(name=c['name'], input=json.loads(c['arguments'])) for c in calls.values()])
