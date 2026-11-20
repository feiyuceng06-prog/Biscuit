"""Actual offline worker measurements, synthetic approval and drift controls."""
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from evals import architecture as a
from evals import architecture_authorization as auth
from evals import architecture_measurement as m
from tests.test_architecture_authorization import fixture


class MeasurementTests(unittest.TestCase):
    def test_optimized_entrypoints_reject_before_inputs_or_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for option in ('-O', '-OO'):
                for command in ('prepare', 'measure', 'preflight'):
                    out = root/(option+command)
                    result = subprocess.run([sys.executable, option, '-m', 'evals.architecture_measurement',
                        command, '--policy', str(root/'missing-policy'), '--config', str(root/'missing-config'),
                        '--out', str(out)], capture_output=True, text=True, timeout=15)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertIn('optimized Python measurement is disabled', result.stdout)
                    self.assertFalse(out.exists())
                code = """
from evals import architecture_measurement as m
from evals.architecture_authorization import RemoteBlocked
for fn,args in ((m.measure,(None,None,None)),(m.preflight,(None,None,None,None,None))):
    try: fn(*args)
    except RemoteBlocked as exc:
        if str(exc) != 'optimized Python measurement is disabled': raise
    else: raise RuntimeError('optimized public entry accepted')
"""
                result = subprocess.run([sys.executable, option, '-c', code], capture_output=True, text=True, timeout=15)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_prepare_remeasure_both_providers_and_rejects(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for provider in ('openai', 'anthropic'):
                config = copy.deepcopy(a.CONTRACT) if provider == 'openai' else a.anthropic_config()
                cp = root/(provider+'.json'); cp.write_text(json.dumps(config))
                policy = fixture(provider)['plan']
                policy['model']['version'] = config['model']['version']
                policy.update(issued_at=time.time()-60, expires_at=time.time()+3600)
                plan = m.measure(policy, cp, root/(provider+'-prepare'))
                manifest = auth.load(root/(provider+'-prepare')/'measurement-manifest.json')
                self.assertEqual(len(manifest['actual_requests']), 16)
                for r in manifest['actual_requests']:
                    self.assertEqual(r['parameters_sha256'], auth.digest(r['parameters']))
                blank = auth.template(plan)
                with self.assertRaises(auth.RemoteBlocked):
                    auth.require_remote_contract(dict(plan=plan, fee_authorization=blank), plan)
                approved = dict(approved=True, approver='synthetic-only', record_id='synthetic-only',
                    plan_sha256=auth.digest(plan), granted_at=time.time()-10, expires_at=time.time()+1800)
                receipt = m.preflight(plan, approved, policy, cp, root/(provider+'-preflight'))
                self.assertFalse(receipt['remote_execution_allowed'])
                self.assertFalse(receipt['approval_consumed'])
                self.assertEqual(receipt['trust'], 'local_remeasurement_not_host_attestation')
                for key in ('source_lock', 'runtime_lock', 'prompt_lock', 'task_lock', 'measurement_lock'):
                    forged = copy.deepcopy(plan)
                    if type(forged[key]) is str: forged[key] = 'a'*64
                    elif key == 'runtime_lock': forged[key]['head']['dependencies_sha256'] = 'a'*64
                    else: forged[key]['head'] = 'a'*64
                    with self.subTest(provider=provider, key=key), self.assertRaises(auth.RemoteBlocked):
                        auth.require_remote_contract(dict(plan=forged,fee_authorization=approved), plan)
                with self.assertRaises(auth.RemoteBlocked):
                    m.preflight(policy, approved, policy, cp, root/'old-v1')
                for key in approved:
                    if key in ('approved', 'expires_at'):
                        bad = dict(approved); bad[key] = False if key == 'approved' else time.time()-1
                        with self.assertRaises(auth.RemoteBlocked):
                            auth.require_remote_contract(dict(plan=plan, fee_authorization=bad), plan)
                bad = copy.deepcopy(plan); bad['budget']['max_requests'] *= 2
                with self.assertRaises(auth.RemoteBlocked):
                    auth.require_remote_contract(dict(plan=bad,fee_authorization=approved), bad)
                # A bogus caller manifest cannot replace the regenerated source/runtime.
                forged = copy.deepcopy(plan); forged['source_lock']['head'] = 'b'*64
                with self.assertRaisesRegex(auth.RemoteBlocked, 'measured input drift'):
                    m.preflight(forged, approved, policy, cp, root/(provider+'-forged'))
                # Actual bytes in a separate source copy; no stash or mutation of product source.
                mirror = root/(provider+'-copy'); mirror.mkdir()
                (mirror/'.git').write_text('gitdir: '+str(a.ROOT/'.git')+'\n')
                for name in a.source_lock():
                    dest = mirror/name; dest.parent.mkdir(parents=True,exist_ok=True)
                    dest.write_bytes((a.ROOT/name).read_bytes())
                for name in ('feiyu/agent.py', 'evals/architecture_cases.py', 'evals/architecture_worker.py'):
                    target = mirror/name; original = target.read_bytes(); target.write_bytes(original+b'\n# negative actual byte change\n')
                    with patch.object(a, 'ROOT', mirror), self.subTest(changed=name), self.assertRaisesRegex(auth.RemoteBlocked,'measured input drift'):
                        m.preflight(plan, approved, policy, cp, root/(provider+'-drift-'+target.stem))
                    target.write_bytes(original)
                dep = root/(provider+'-dependencies'); dep.mkdir(); (dep/'package.py').write_text('VALUE=2\n')
                with patch('sysconfig.get_paths', return_value=dict(purelib=str(dep),platlib=str(dep))), self.assertRaisesRegex(auth.RemoteBlocked,'measured input drift'):
                    m.preflight(plan, approved, policy, cp, root/(provider+'-dep-drift'))
                changed = copy.deepcopy(config); changed['repeat'] += 1; cp.write_text(json.dumps(changed))
                with self.assertRaisesRegex(auth.RemoteBlocked,'measured input drift'):
                    m.preflight(plan, approved, policy, cp, root/(provider+'-schedule-drift'))
                changed['model']['temperature'] = .5; cp.write_text(json.dumps(changed))
                with self.assertRaises(AssertionError): m.measure(policy,cp,root/(provider+'-sampling-drift'))
                cp.write_text(json.dumps(config))
                with patch.object(m.execution, 'execute', return_value=dict(status='environment_failure')):
                    # Record absent: no observed/template/receipt can be emitted.
                    failed = root/(provider+'-failure')
                    with self.assertRaises(OSError): m.measure(policy,cp,failed)
                    self.assertFalse((failed/'observed.json').exists())
                    self.assertFalse((failed/'preflight-receipt.json').exists())
                with self.assertRaises(OSError): m.measure(policy, root/'missing',root/'missing-out')

    def test_request_binding_model_sampling_and_identity(self):
        for provider in ('openai', 'anthropic'):
            p = fixture(provider)['plan']
            p.update(schema_version=2, measurement_lock='a'*64,
                     prompt_semantics='initial_constructor_and_system_not_full_requests')
            params = dict(model=p['model']['version'], messages=[dict(role='user',content='dynamic')])
            r = m.bind_request(p,params,'actual dynamic system','request-1',role='auxiliary')
            self.assertEqual(r['parameters_sha256'],auth.digest(params))
            self.assertEqual(r['measurement_lock'],p['measurement_lock'])
            self.assertFalse(r['budget_reserved'])
            changed = copy.deepcopy(params); changed['messages'][0]['content'] = 'changed actual content'
            self.assertNotEqual(m.bind_request(p,changed,'system','request-2')['parameters_sha256'],r['parameters_sha256'])
            for key, value in (('model','wrong-model'),('temperature',True),('top_p',0),('seed',0)):
                with self.subTest(provider=provider,key=key), self.assertRaises(auth.RemoteBlocked):
                    m.bind_request(p,dict(params,**{key:value}),'system','request')
            with self.assertRaises(auth.RemoteBlocked): m.bind_request(p,params,'system','request',attempt=True)

    def test_cli_missing_and_live_remote_gates(self):
        r = subprocess.run([sys.executable,'-m','evals.architecture_measurement','prepare',
            '--policy','/nonexistent/synthetic-policy','--config','/nonexistent/synthetic-config',
            '--out','/nonexistent/synthetic-out'],capture_output=True,text=True,timeout=10)
        self.assertEqual(r.returncode,2); self.assertEqual(json.loads(r.stdout)['status'],'rejected')
        from evals.architecture_sdk import SDKTransport
        from evals.architecture_anthropic import AnthropicTransport
        for cls in (SDKTransport,AnthropicTransport):
            with self.assertRaises(auth.RemoteBlocked): cls('https://provider.invalid/v1','synthetic')
        r = subprocess.run([sys.executable,'-m','evals.architecture','live','--config','/missing'],capture_output=True,timeout=10)
        self.assertEqual(r.returncode,2); self.assertIn(b'BLOCKED',r.stderr)
