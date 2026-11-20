"""Durable budget routes actual native loopback requests, never a remote endpoint."""
import copy
import json
import os
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
from evals import architecture_durable as d
from evals import architecture_measurement as m
from evals.architecture_sdk import SDKTransport
from evals.architecture_loopback import service
from tests.test_architecture_authorization import fixture
from tests.test_architecture_durable import inputs


class NativeDurableTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='ds-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def opened(self):
        seed = inputs()
        c = d.Controller(self.root/'registry')
        c._consume(*seed)
        self.addCleanup(c.close)
        self.params = dict(model=seed[0]['model']['version'], temperature=None, top_p=None,
                           seed=None, messages=[dict(role='user', content='synthetic')], stream=False)
        return c

    def invoke(self, c, transport, request='one', role='primary', attempt=1):
        return c.invoke_sdk('head/executor/development/0', request, attempt, role,
                            self.params, 'actual native system', transport)

    def test_actual_usage_result_and_global_helper_count(self):
        c = self.opened()
        with service('executor', self.params['model']) as endpoint:
            t = SDKTransport(endpoint, self.params['model'])
            first = self.invoke(c,t)
            second = self.invoke(c,t,'helper','auxiliary')
            self.assertEqual(first['usage_lower_bound'], dict(input=10,output=5))
            self.assertAlmostEqual(first['cost_cny'], .000015)
            self.assertEqual(first['sdk_receipt']['endpoint'], endpoint)
            self.assertTrue(first['binding']['budget_reserved'])
            with self.assertRaises(d.Blocked): self.invoke(c,t,'retry',attempt=2)
        self.assertEqual(len(c.run['entries']),2)
        self.assertIsNone(second['supplier_invoice'])

    def test_cancel_save_failure_and_slow_reservation(self):
        c = self.opened()
        with service('executor', self.params['model']) as endpoint:
            t = SDKTransport(endpoint,self.params['model'])
            original = KeyboardInterrupt('synthetic cancellation')
            original.sdk_receipt = dict(usage_lower_bound=dict(prompt_tokens=8,completion_tokens=2))
            def cancel(*args): raise original
            with patch.object(t,'invoke',cancel), self.assertRaises(KeyboardInterrupt) as caught:
                self.invoke(c,t)
            self.assertIs(caught.exception,original)
            self.assertEqual(c.run['entries'][0]['usage_lower_bound'],dict(input=8,output=2))
            with self.assertRaises(d.Blocked): self.invoke(c,t,'two')
        c.close()
        with d.Controller(self.root/'registry2') as c:
            c._consume(*inputs())
            original_save = c._save
            clock = time.monotonic()
            def slow():
                nonlocal clock
                original_save(); clock += 121
            with service('executor',self.params['model']) as endpoint:
                t = SDKTransport(endpoint,self.params['model'])
                with patch.object(c,'_save',slow), patch.object(d.time,'monotonic',side_effect=lambda:clock), patch.object(t,'invoke') as physical:
                    with self.assertRaises(d.Blocked): self.invoke(c,t)
                    physical.assert_not_called()
            self.assertEqual(c.run['entries'][0]['state'],'unknown')
        with d.Controller(self.root/'registry3') as c:
            c._consume(*inputs())
            with service('executor',self.params['model']) as endpoint:
                t = SDKTransport(endpoint,self.params['model'])
                with patch.object(d,'atomic_json',side_effect=OSError('disk')), patch.object(t,'invoke') as physical:
                    with self.assertRaises(d.PersistenceFailure): self.invoke(c,t)
                    physical.assert_not_called()

    def test_result_saved_before_late_stop_and_cancel_save_failure(self):
        c = self.opened()
        with service('executor',self.params['model']) as endpoint:
            t = SDKTransport(endpoint,self.params['model'])
            real = t.invoke
            def late(*args):
                result = real(*args)
                c.run['deadline'] = time.monotonic()-1
                return result
            with patch.object(t,'invoke',late), self.assertRaises(d.Blocked): self.invoke(c,t)
            entry = auth.load(c.path)['runs'][c.run['plan']['run_id']]['entries'][0]
            self.assertEqual(entry['state'],'complete')
            self.assertEqual(entry['usage_lower_bound'],dict(input=10,output=5))
        c.close()
        with d.Controller(self.root/'cancel') as c:
            c._consume(*inputs())
            with service('executor',self.params['model']) as endpoint:
                t = SDKTransport(endpoint,self.params['model'])
                original = SystemExit(17)
                original.sdk_receipt = dict(usage_lower_bound=dict(prompt_tokens=8))
                def cancel(*args):
                    c._save = lambda: (_ for _ in ()).throw(d.PersistenceFailure('disk'))
                    raise original
                with patch.object(t,'invoke',cancel), self.assertRaises(SystemExit) as caught: self.invoke(c,t)
                self.assertIs(caught.exception,original)
                self.assertIsInstance(original.persistence_error,d.PersistenceFailure)
                self.assertEqual(original.durable_attempt['usage_lower_bound'],dict(input=8))

    def test_crash_windows_sdk_reservation_and_return_before_save(self):
        for sent in (False, True):
            root = self.root/str(sent)
            code = """from tests.test_architecture_durable_sdk import *
root=Path(ROOT)
c=d.Controller(root)
c._consume(*inputs())
params=dict(model=c.run['plan']['model']['version'], messages=[dict(role='user',content='synthetic')],stream=False)
with service('executor',params['model']) as endpoint:
 t=SDKTransport(endpoint,params['model'])
 original=t.invoke
 def crash(*args):
  if SENT:
   result=original(*args)
   (root/'sent.json').write_text(json.dumps(result))
  os._exit(74 if SENT else 73)
 t.invoke=crash
 c.invoke_sdk('head/executor/development/0','one',1,'primary',params,'actual system',t)
""".replace('ROOT',repr(str(root))).replace('SENT',repr(sent))
            result = subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=30)
            evidence = os.environ.get('DURABLE_SDK_EVIDENCE')
            if evidence:
                dest = Path(evidence)/('crash-'+str(sent)); dest.mkdir(parents=True,exist_ok=True)
                (dest/'command.json').write_text(json.dumps(dict(argv=[sys.executable,'-c',code],
                    exit_code=result.returncode,expected=74 if sent else 73,stdout=result.stdout,stderr=result.stderr)))
                shutil.copytree(root,dest/'before-resume')
            self.assertEqual(result.returncode,74 if sent else 73,result.stderr)
            with d.Controller(root) as c:
                run = c.resume('synthetic-test-run')
                self.assertEqual(run['entries'][0]['state'],'unknown')
                with self.assertRaises(d.Blocked): c._check()
            self.assertEqual((root/'sent.json').exists(),sent)
            if evidence: shutil.copytree(root,dest/'after-resume')

    def test_retry_and_unknown_cross_observation(self):
        c = self.opened()
        record = dict(started=time.monotonic(),deadline=c.run['deadline'])
        view = d.DurableLedger(c,'head/executor/development/0',record)
        with service('executor',self.params['model']) as endpoint:
            t = SDKTransport(endpoint,self.params['model'])
            real = t.invoke
            def failed_once(*args):
                receipt = real(*args)
                if args[2] == 1: receipt['outcome'] = 'failed'
                return receipt
            with patch.object(t,'invoke',failed_once):
                receipt = view.invoke_sdk('one','primary',self.params,'system',t)
            self.assertTrue(receipt['usage_complete'])
            self.assertEqual([e['binding']['attempt'] for e in c.run['entries']],[1,2])
            self.assertEqual(len(view.entries),2)
        c.close()
        with d.Controller(self.root/'unknown') as c:
            c._consume(*inputs())
            def invalid(h,p):
                h.send_response(200); h.end_headers()
                h.wfile.write(json.dumps(dict(model=self.params['model'],choices=[],
                    usage=dict(prompt_tokens=8,completion_tokens=False))).encode())
            with service('executor',self.params['model'],invalid) as endpoint:
                entry=self.invoke(c,SDKTransport(endpoint,self.params['model']))
            self.assertIsNone(entry['cost_cny'])
            with self.assertRaises(d.Blocked): c._check()

    def test_actual_observed_cancel_and_sdk_deadline(self):
        for broken_save in (False, True):
            with d.Controller(self.root/str(broken_save)) as c:
                c._consume(*inputs())
                model = c.run['plan']['model']['version']
                parameters = dict(model=model, messages=[dict(role='user',content='synthetic')],stream=False)
                with service('executor',model) as endpoint:
                    t = SDKTransport(endpoint,model)
                    real = t.observe
                    original = KeyboardInterrupt('after observed native usage')
                    def observed(value,receipt):
                        real(value,receipt)
                        if broken_save:
                            c._save = lambda: (_ for _ in ()).throw(d.PersistenceFailure('disk'))
                        raise original
                    with patch.object(t,'observe',observed), self.assertRaises(KeyboardInterrupt) as caught:
                        c.invoke_sdk('head/executor/development/0','one',1,'primary',parameters,'system',t)
                    self.assertIs(caught.exception,original)
                    self.assertEqual(original.durable_attempt['usage_lower_bound'],dict(input=10,output=5))
                    self.assertTrue(original.sdk_receipt['reaped'])
                    if broken_save: self.assertIsInstance(original.persistence_error,d.PersistenceFailure)
        with d.Controller(self.root/'deadline') as c:
            c._consume(*inputs())
            model = c.run['plan']['model']['version']
            parameters = dict(model=model,messages=[dict(role='user',content='synthetic')],stream=False)
            def silent(h,p):
                h.send_response(200); h.end_headers(); time.sleep(.6)
            with service('executor',model,silent) as endpoint:
                c.run['deadline'] = time.monotonic()+.2
                with self.assertRaises(d.Blocked):
                    c.invoke_sdk('head/executor/development/0','one',1,'primary',parameters,'system',SDKTransport(endpoint,model))
                entry = auth.load(c.path)['runs'][c.run['plan']['run_id']]['entries'][0]
                self.assertEqual(entry['state'],'unknown')
                self.assertIsNone(entry['cost_cny'])
            # SDK timeout is a partial/unknown receipt; the common boundary saves it
            # before raising the late-stop diagnostic.

    def test_public_create_rejects_adapter_drift_before_observation(self):
        config = copy.deepcopy(a.CONTRACT)
        cp = self.root/'config.json'
        cp.write_text(json.dumps(config))
        policy = fixture('openai')['plan']
        policy['model']['version'] = config['model']['version']
        policy.update(issued_at=time.time()-60, expires_at=time.time()+3600)
        policy['budget'].update(max_seconds=180, max_requests=60)
        plan = m.measure(policy, cp, self.root/'prepare')
        approval = dict(approved=True, approver='SYNTHETIC ONLY', record_id='adapter-test',
            plan_sha256=auth.digest(plan), granted_at=time.time()-1, expires_at=time.time()+1800)
        out = self.root/'preflight'
        with d.Controller(self.root/'registry') as c:
            c.create(plan, approval, policy, cp, out, synthetic=True)
            adapter = out/'adapter'
            before = c.path.read_bytes()
            long_out = self.root/('long-output-'*10)
            out.rename(long_out)
            try:
                with self.assertRaisesRegex(ValueError, 'AF_UNIX'):
                    c.execute_loopback(long_out, 'snapshot', 'recovery')
                self.assertEqual(c.path.read_bytes(), before)
                self.assertFalse(c.run.get('observations'))
                self.assertEqual(c.run['entries'], [])
            finally:
                long_out.rename(out)
            for name in ('architecture_worker.py', 'architecture_runtime.py'):
                path = adapter/name
                original = path.read_bytes()
                for mutation in ('changed', 'missing', 'symlink', 'extra'):
                    with self.subTest(name=name, mutation=mutation):
                        if mutation == 'changed':
                            path.write_bytes(original+b'\n# drift\n')
                        elif mutation == 'missing':
                            path.unlink()
                        elif mutation == 'symlink':
                            path.unlink()
                            path.symlink_to(out/'snapshot/evals'/name)
                        else:
                            (adapter/'extra.py').write_text('# extra')
                        try:
                            with patch('evals.architecture_execution.execute') as spawn:
                                with self.assertRaisesRegex(RuntimeError, 'adapter'):
                                    c.execute_loopback(out, 'snapshot', 'executor')
                                spawn.assert_not_called()
                            self.assertEqual(c.run['entries'], [])
                            self.assertFalse(c.run.get('observations'))
                            self.assertEqual(c.path.read_bytes(), before)
                        finally:
                            if path.exists() or path.is_symlink():
                                path.unlink()
                            path.write_bytes(original)
                            (adapter/'extra.py').unlink(missing_ok=True)
            adapter.rename(out/'original-adapter')
            adapter.symlink_to(out/'original-adapter', target_is_directory=True)
            with self.assertRaisesRegex(RuntimeError, 'adapter'):
                c.execute_loopback(out, 'snapshot', 'executor')
            adapter.unlink()
            (out/'original-adapter').rename(adapter)
            result = c.execute_loopback(out, 'snapshot', 'executor')
            self.assertEqual(result['status'], 'success')
            self.assertGreater(len(c.run['entries']), 0)
            (out/'pad').mkdir()
            padded = out
            for _ in range(20):
                padded = padded/'pad'/'..'
            before_count = len(c.run['entries'])
            result = c.execute_loopback(padded, 'snapshot', 'recovery')
            self.assertEqual(result['status'], 'agent_failure', result)
            self.assertEqual(len(c.run['entries'])-before_count, 3)
            self.assertEqual(c.run['observations']['snapshot/recovery/development/0']['state'], 'finished')

    def integration(self, provider):
        config = copy.deepcopy(a.CONTRACT) if provider == 'openai' else a.anthropic_config()
        cp = self.root/'config.json'; cp.write_text(json.dumps(config))
        policy = fixture(provider)['plan']
        policy['model']['version'] = config['model']['version']
        policy.update(issued_at=time.time()-60,expires_at=time.time()+3600)
        policy['budget'].update(max_seconds=180,max_requests=60)
        plan = m.measure(policy,cp,self.root/'prepare')
        approval = dict(approved=True,approver='SYNTHETIC ONLY',record_id='synthetic-'+provider,
            plan_sha256=auth.digest(plan),granted_at=time.time()-1,expires_at=time.time()+1800)
        with d.Controller(self.root/'registry') as c:
            c.create(plan,approval,policy,cp,self.root/'preflight',synthetic=True)
            for group in config['groups']:
                for arm in ('head','snapshot'):
                    result = c.execute_loopback(self.root/'preflight',arm,group)
                    self.assertEqual(result['status'],'agent_failure' if group=='recovery' else 'success',result)
            entries = copy.deepcopy(c.run['entries'])
            self.assertTrue(any(e['binding']['role']=='auxiliary' for e in entries))
            self.assertTrue(all(e['state']=='complete' and e['sdk_receipt']['reaped'] for e in entries))
            self.assertTrue(all(e['binding']['source_sha256']==plan['source_lock'][e['binding']['observation_identity']['arm']] for e in entries))
            for observation in c.run['observations']:
                receipt = auth.load(self.root/'preflight'/observation.replace('/','-')/'controller.json')
                selected = [e for e in entries if e['observation']==observation]
                self.assertEqual(len(receipt['ledger']),len(selected))
                self.assertEqual(sum(e['cost_cny'] for e in receipt['ledger']),sum(e['cost_cny'] for e in selected))
        code = ('from evals.architecture_durable import Controller, Blocked\n'
                'from pathlib import Path\n'
                'with Controller('+repr(str(self.root/'registry'))+') as c:\n'
                ' r=c.resume('+repr(plan['run_id'])+')\n'
                ' assert len(r["entries"])=='+str(len(entries))+'\n'
                ' try: c.execute_loopback(Path('+repr(str(self.root/'preflight'))+'),"head","executor")\n'
                ' except Exception as e: assert "already started" in str(e), str(e)\n'
                ' else: raise RuntimeError("replay")\n')
        result = subprocess.run([sys.executable,'-c',code],capture_output=True,text=True,timeout=30)
        (self.root/'resume.json').write_text(json.dumps(dict(argv=[sys.executable,'-c',code],exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr)))
        self.assertEqual(result.returncode,0,result.stderr)
        evidence = os.environ.get('DURABLE_SDK_EVIDENCE')
        if evidence:
            shutil.copytree(self.root,Path(evidence)/provider,
                            ignore=lambda directory,names: [n for n in names if (Path(directory)/n).is_socket()])

    def test_openai_product_create_resume(self): self.integration('openai')
    def test_anthropic_product_create_resume(self): self.integration('anthropic')
