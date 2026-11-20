"""Synthetic local records; no real approval, price, credentials or remote access."""
import copy
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from evals import architecture_authorization as a


def fixture(provider='openai'):
    h = 'a' * 64
    keys = ('input', 'output') if provider == 'openai' else ('input', 'output', 'cache_read', 'cache_creation')
    p = dict(schema_version=1, kind='remote_plan', run_id='synthetic-test-run', provider=provider,
             endpoint='https://provider.invalid/v1', model=dict(id='synthetic-model', version='synthetic-exact-version'),
             sdk_version='synthetic-sdk', source_lock=dict(head=h, snapshot=h),
             runtime_lock={k: dict(interpreter_sha256=h, dependencies_sha256=h) for k in ('head', 'snapshot')},
             prompt_lock=dict(head=h, snapshot=h), task_lock=h,
             sampling=dict(temperature=None, top_p=None, seed=None, auxiliary='same_exact_version_and_sampling'),
             budget=dict(max_cny=1.0, max_seconds=60, max_requests=2),
             billing_policy=dict(basis='fixed_price_estimate', currency='CNY', rate_source='synthetic test only',
                 rates_per_million={k: 1.0 for k in keys}, token_ceiling_per_request={k: 100 for k in keys},
                 unknown_cost='block', replenishment='forbidden', evidence='real_only_no_synthetic_merge'),
             dedicated_credential_file='/nonexistent/synthetic-credential', issued_at=1000, expires_at=2000)
    auth = dict(approved=True, approver='synthetic-test-asserted-approver', record_id='synthetic-record',
                plan_sha256=a.digest(p), granted_at=1100, expires_at=1900)
    return dict(plan=p, fee_authorization=auth)


class AuthorizationTests(unittest.TestCase):
    def check(self, c, observed=None, now=1200):
        # A credential dereference, process start or socket attempt must fail the test.
        with patch('builtins.open', side_effect=AssertionError('credential read')), \
             patch.object(Path, 'open', side_effect=AssertionError('credential read')), \
             patch.object(socket, 'socket', side_effect=AssertionError('network')), \
             patch.object(socket, 'getaddrinfo', side_effect=AssertionError('DNS')), \
             patch.object(subprocess, 'Popen', side_effect=AssertionError('spawn')):
            return a.require_remote_contract(c, copy.deepcopy(c.get('plan')) if observed is None else observed, now)

    def test_positive_both_providers_and_receipt(self):
        for provider in ('openai', 'anthropic'):
            c = fixture(provider)
            r = self.check(c)
            self.assertEqual(r['plan_sha256'], a.digest(c['plan']))
            self.assertEqual(r['observed_sha256'], r['plan_sha256'])
            self.assertEqual(r['status'], 'local_contract_valid')
            for key in ('remote_execution_allowed', 'session_fee_authorization', 'approval_consumed', 'host_attestation'):
                self.assertIs(r[key], False)
            self.assertIsNone(r['invoice']); self.assertIsNone(r['supplier_invoice'])

    def test_every_field_missing_extra_and_wrong_container(self):
        c = fixture()
        paths = [(), ('plan',), ('fee_authorization',), ('plan','model'), ('plan','source_lock'),
                 ('plan','runtime_lock'), ('plan','runtime_lock','head'), ('plan','runtime_lock','snapshot'),
                 ('plan','prompt_lock'), ('plan','sampling'), ('plan','budget'), ('plan','billing_policy'),
                 ('plan','billing_policy','rates_per_million'), ('plan','billing_policy','token_ceiling_per_request')]
        for path in paths:
            base = c
            for key in path: base = base[key]
            for field in list(base) + ['unexpected']:
                with self.subTest(path=path, field=field):
                    bad = copy.deepcopy(c); target = bad
                    for key in path: target = target[key]
                    if field in target: del target[field]
                    else: target[field] = 1
                    with self.assertRaises(a.RemoteBlocked): self.check(bad)
            if path:
                for value in (None, [], True, 'dict', 1):
                    bad = copy.deepcopy(c); target = bad
                    for key in path[:-1]: target = target[key]
                    target[path[-1]] = value
                    with self.assertRaises(a.RemoteBlocked): self.check(bad)

    def test_all_leaf_type_corruption(self):
        def leaves(obj, path=()):
            for k, v in obj.items():
                if type(v) is dict: yield from leaves(v, path+(k,))
                else: yield path+(k,)
        c = fixture()
        for path in leaves(c):
            for value in ([], {}, float('nan'), float('inf'), float('-inf')):
                with self.subTest(path=path, value=value):
                    bad = copy.deepcopy(c); t = bad
                    for key in path[:-1]: t = t[key]
                    t[path[-1]] = value
                    with self.assertRaises(a.RemoteBlocked): self.check(bad)

    def test_valid_drift_of_every_leaf_rejected(self):
        c = fixture()
        def change(v):
            if type(v) is str: return v + 'x'
            if type(v) in (int, float): return v + 1
            return 0
        def walk(d, path=()):
            for k, v in d.items():
                if type(v) is dict: yield from walk(v, path+(k,))
                else: yield path+(k,), v
        for path, value in walk(c['plan']):
            observed = copy.deepcopy(c['plan']); t = observed
            for key in path[:-1]: t = t[key]
            t[path[-1]] = change(value)
            with self.subTest(path=path), self.assertRaises(a.RemoteBlocked): self.check(c, observed)
        # An enlarged plan with a matching observed input still cannot reuse the old approval.
        for key in c['plan']['budget']:
            bad = copy.deepcopy(c); bad['plan']['budget'][key] *= 2
            with self.assertRaises(a.RemoteBlocked): self.check(bad)

    def test_time_numbers_endpoint_policy(self):
        c = fixture()
        for now in (100, 2000, 1900, True, None, float('nan'), float('inf'), -1):
            with self.subTest(now=now):
                with patch.object(a.time, 'time', return_value=2100):
                    with self.assertRaises(a.RemoteBlocked): self.check(c, now=now)
        for path, values in [
            (('plan','endpoint'), ['http://provider.invalid/v1','https://u:p@provider.invalid/v1',
              'https://provider.invalid/v1?q=1','https://provider.invalid/v1#x','https://127.0.0.1/v1',
              'https://provider.invalid:443/v1','https://PROVIDER.invalid/v1','https://provider.invalid/%2f']),
            (('plan','budget','max_cny'), [True, 0, -1, '1', 10**400]),
            (('plan','budget','max_seconds'), [True, 0, -1]),
            (('plan','budget','max_requests'), [True, 1.1, 0, -1]),
            (('fee_authorization','approved'), [False, 1, 'true', None]),
            (('fee_authorization','approver'), ['', ' ', None, True]),
            (('plan','dedicated_credential_file'), ['relative','/a/../b', '/a//b']),
            (('plan','billing_policy','unknown_cost'), ['allow', None]),
            (('plan','billing_policy','replenishment'), ['allow']),
            (('plan','billing_policy','evidence'), ['synthetic']),
            (('plan','billing_policy','rates_per_million','input'), [None, True, -1, 'unknown']),
            (('plan','billing_policy','token_ceiling_per_request','output'), [0, True, 1.5]),
            (('plan','issued_at'), [1900, 2000, 2100]),
            (('fee_authorization','expires_at'), [1000, 2100]),
            (('fee_authorization','granted_at'), [999, 1300])]:
            for v in values:
                bad = copy.deepcopy(c); t = bad
                for k in path[:-1]: t = t[k]
                t[path[-1]] = v
                with self.subTest(path=path,v=v), self.assertRaises(a.RemoteBlocked): self.check(bad)
        bad = fixture(); bad['plan']['billing_policy']['rates_per_million']['input'] = 1000000
        with self.assertRaises(a.RemoteBlocked): self.check(bad)

    def test_cli_blank_template_reject_and_live(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); c = fixture()
            for name, value in [('plan',c['plan']), ('auth',c['fee_authorization'])]:
                (root/name).write_text(json.dumps(value))
            def cli(*args):
                return subprocess.run([sys.executable,'-m','evals.architecture_authorization',*args], capture_output=True, text=True)
            r = cli('template','--plan',str(root/'plan'))
            self.assertEqual(r.returncode, 0, r.stderr)
            value = json.loads(r.stdout); auth = value['fee_authorization']
            self.assertIs(auth['approved'], False); self.assertIsNone(auth['approver'])
            self.assertIsNone(auth['record_id'])
            with self.assertRaises(a.RemoteBlocked): self.check(dict(plan=c['plan'], fee_authorization=auth))
            r = cli('preflight','--plan',str(root/'plan'),'--authorization',str(root/'auth'),'--observed',str(root/'plan'))
            self.assertEqual(r.returncode, 2); self.assertEqual(json.loads(r.stdout)['status'],'rejected')
            # Synthetic contemporary clock for a real CLI positive path, still fake approval and endpoint.
            c['plan'].update(issued_at=a.time.time()-10, expires_at=a.time.time()+600)
            c['fee_authorization'].update(plan_sha256=a.digest(c['plan']), granted_at=a.time.time()-5, expires_at=a.time.time()+500)
            for name, value in [('plan',c['plan']), ('auth',c['fee_authorization'])]:
                (root/name).write_text(json.dumps(value))
            r = cli('preflight','--plan',str(root/'plan'),'--authorization',str(root/'auth'),'--observed',str(root/'plan'))
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)['plan_sha256'], a.digest(c['plan']))
            for raw in ('{"x":1,"x":2}', '{"x":NaN}', '{"x":Infinity}'):
                (root/'bad').write_text(raw)
                with self.assertRaises(a.RemoteBlocked): a.load(root/'bad')
            r = subprocess.run([sys.executable,'-m','evals.architecture','live','--config',str(root/'nonexistent')],capture_output=True)
            self.assertEqual(r.returncode, 2); self.assertIn(b'BLOCKED',r.stderr)
