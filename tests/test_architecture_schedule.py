"""Plan identity and scheduler fail-closed boundaries; native integration in evidence runner."""
import copy
from pathlib import Path
import tempfile
import subprocess
import sys
import json
from evals import architecture_authorization as auth
import unittest
from unittest.mock import patch
from evals import architecture as a
from evals import architecture_durable as d
from evals import architecture_schedule as s
from tests.test_architecture_durable import inputs, call


class ScheduleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.c = d.Controller(Path(self.tmp.name)); self.addCleanup(self.c.close)
        self.c._consume(*inputs())
        self.c.run['bundle']['static']['schedule'] = a.plan(a.CONTRACT)

    def test_long_paths_reject_batch_before_first_observation(self):
        from evals.architecture_execution import check_service_path
        before = self.c.path.read_bytes()
        long = Path(self.tmp.name)/('界'*40)
        with patch.object(self.c, 'execute_loopback') as worker:
            with self.assertRaisesRegex(ValueError, 'AF_UNIX'):
                s.batch(self.c, long, 1)
            worker.assert_not_called()
        self.assertEqual(self.c.path.read_bytes(), before)
        self.assertFalse(self.c.run.get('observations'))
        check_service_path(Path('/tmp/short'), 'recovery')
        with self.assertRaisesRegex(ValueError, 'AF_UNIX'):
            check_service_path(long, 'recovery')

    def test_complete_receipt_binding_and_mutations(self):
        import hashlib
        from evals.architecture_runtime import environment
        for provider in ('openai', 'anthropic'):
            keys = ('input', 'output') if provider == 'openai' else ('input', 'output', 'cache_read', 'cache_creation')
            native = ('prompt_tokens', 'completion_tokens') if provider == 'openai' else ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')
            from tests.test_architecture_authorization import fixture
            plan = fixture(provider)['plan']
            usage = dict.fromkeys(keys, 2)
            rates = plan['billing_policy']['rates_per_million']
            cost = sum(rates[k]*v/1e6 for k,v in usage.items())
            manifest = a.source_lock()
            runtime = environment()
            run = dict(plan=plan, bundle=dict(static=dict(sdk_version='test-sdk', runtime=runtime,
                                                         manifests=dict(snapshot=manifest))))
            params = dict(model=plan['model']['version'])
            receipt = dict(synthetic=True, usage_complete=True, reaped=True, outcome='ok',
                requested_model=params['model'], returned_models=[params['model']], sdk_version='test-sdk',
                usage_lower_bound=dict(zip(native,usage.values())), cost_cny=cost,
                rates_cny_per_million=[rates[k] for k in keys],
                accounting_basis='usage_fixed_price_estimate', rate_source='synthetic_fixture_not_supplier_quote',
                endpoint='http://127.0.0.1:1234/v1', invoice=None, supplier_invoice=None,
                adapter_sha256=manifest['evals/architecture_sdk.py'],
                semantics_sha256=manifest['evals/architecture_'+('sdk' if provider=='openai' else 'anthropic')+'.py'],
                child_sha256=manifest['evals/architecture_'+('sdk' if provider=='openai' else 'anthropic')+'_child.py'],
                interpreter_sha256=runtime['executable_sha256'],
                request_sha256=hashlib.sha256(json.dumps(params,sort_keys=True).encode()).hexdigest())
            entry = dict(sdk_receipt=receipt,usage_lower_bound=usage,outcome='ok',cost_cny=cost,supplier_invoice=None)
            s.validate_receipt(run,entry,params)
            for key,value in [('usage_complete',False),('synthetic',False),('request_sha256','bad'),
                              ('sdk_version','bad'),('child_sha256','bad'),('cost_cny',True),
                              ('usage_lower_bound',dict.fromkeys(native,False))]:
                bad=copy.deepcopy(entry);bad['sdk_receipt'][key]=value
                with self.subTest(provider=provider,key=key), self.assertRaises(Exception):
                    s.validate_receipt(run,bad,params)
            entry['sdk_receipt']=None
            with self.assertRaises(Exception): s.validate_receipt(run,entry,params)

    def test_socket_bind_failure_closes_descriptor(self):
        import hashlib
        from evals import architecture_execution as ex
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); adapter=root/'adapter';adapter.mkdir()
            source=root/'snapshot';(source/'feiyu').mkdir(parents=True);(source/'evals').mkdir()
            manifest={}
            for name in ('feiyu/__init__.py','evals/architecture_worker.py','evals/architecture_runtime.py'):
                (source/name).write_text('')
                manifest[name]=hashlib.sha256(b'').hexdigest()
                if name.startswith('evals/'): (adapter/Path(name).name).write_text('')
            with patch.object(ex.socket,'socket') as constructor:
                server=constructor.return_value
                server.bind.side_effect=OSError('synthetic bind failure')
                ex.execute(root,dict(snapshot=manifest),copy.deepcopy(a.CONTRACT),'snapshot','recovery',adapter)
                server.close.assert_called_once()

    def test_generated_counterbalance_holdout_repeat(self):
        cfg = copy.deepcopy(a.CONTRACT); cfg['repeat'] = 3
        plan = a.plan(cfg)
        self.assertEqual(len(plan), 2*len(cfg['groups'])*len(cfg['splits'])*cfg['repeat'])
        self.assertEqual([x['arm'] for x in plan[:4]], ['head','snapshot','snapshot','head'])
        self.assertTrue(any(x['split']=='holdout' and x['repeat']==2 for x in plan))

    def test_scheduler_order_and_duplicate_skip(self):
        invoked = []
        def execute(out, arm, group, **kw):
            item = next(x for x in s.schedule(self.c) if x['arm']==arm and x['group']==group
                        and x['split']==kw['split'] and x['repeat']==kw['repeat'])
            invoked.append(s.identity(item))
            self.c.run.setdefault('observations', {})[s.identity(item)] = dict(state='finished')
            return dict(status='agent_failure')
        with patch.object(self.c, 'execute_loopback', side_effect=execute):
            s.batch(self.c, Path('/unused'), 3); s.batch(self.c, Path('/unused'), 2)
        self.assertEqual(invoked, [s.identity(x) for x in s.schedule(self.c)[:5]])

    def test_unplanned_and_bad_repeat_rejected_before_worker(self):
        with patch('evals.architecture_execution.execute') as worker:
            for arm, group, split, repeat in [('head','executor','holdout',True),
                    ('head','executor','holdout',6), ('bad','executor','development',0),
                    ('head','executor','unknown',0), ('head','bad','development',0)]:
                with self.assertRaises(Exception):
                    self.c.execute_loopback(Path('/unused'),arm,group,split=split,repeat=repeat)
            worker.assert_not_called()
        self.assertEqual(self.c.run['entries'], [])

    def test_unknown_blocks_other_unstarted_observations(self):
        call(self.c, outcome='unknown')
        with patch.object(self.c, 'execute_loopback') as worker:
            with self.assertRaises(d.Blocked): s.batch(self.c, Path('/unused'), 2)
            worker.assert_not_called()

    def test_interrupted_blocks_and_no_automatic_replay(self):
        name = s.identity(s.schedule(self.c)[0])
        self.c.run['observations'] = {name: dict(state='interrupted')}
        with patch.object(self.c,'execute_loopback') as worker:
            with self.assertRaises(Exception): s.batch(self.c,Path('/unused'),1)
            worker.assert_not_called()

    def test_schedule_tampering_and_optimization(self):
        self.c.run['bundle']['static']['schedule'].reverse()
        with self.assertRaises(Exception): s.schedule(self.c)

    def test_export_empty_missing_and_strict_json_types(self):
        payload = s.export(self.c)
        self.assertEqual(payload['rows'], [])
        self.assertTrue(all(x['state']=='not_started' for x in payload['observations']))
        summary = s.aggregate(self.c, payload)
        self.assertEqual(summary['missing_observations'], len(s.schedule(self.c)))
        for key, value in [('synthetic', 1), ('schema_version', True), ('mode','live')]:
            bad = copy.deepcopy(payload); bad[key] = value
            with self.assertRaises(Exception): s.aggregate(self.c,bad)
        bad = copy.deepcopy(payload);bad['observations'].reverse()
        with self.assertRaises(Exception): s.aggregate(self.c,bad)

    def test_export_unknown_preserves_null_without_invented_score(self):
        item = s.schedule(self.c)[0]; name = s.identity(item)
        self.c.run['observations'] = {name: dict(identity=item,state='started')}
        call(self.c, outcome='unknown')
        payload = s.export(self.c)
        self.assertIsNone(payload['requests'][0]['cost_cny'])
        self.assertEqual(payload['rows'], [])
        self.assertEqual(payload['observations'][0]['record']['state'], 'started')
        with self.assertRaises(auth.RemoteBlocked): s.batch(self.c,Path('/unused'),1)

    def test_orphan_started_new_process_becomes_interrupted(self):
        root = Path(self.tmp.name)/'orphan'
        with d.Controller(root) as c:
            c._consume(*inputs())
            item = a.plan(a.CONTRACT)[0]
            c.run['observations'] = {s.identity(item): dict(identity=item,state='started')}
            c._save()
            limits, deadline = c.run['limits'], c.run['deadline']
        code = """from evals.architecture_durable import Controller, Blocked
import sys, json
with Controller(sys.argv[1]) as c:
 r=c.resume('synthetic-test-run')
 assert next(iter(r['observations'].values()))['state']=='interrupted'
 try: c._check()
 except Blocked: pass
 else: raise AssertionError('orphan replay admitted')
 print(json.dumps(dict(limits=r['limits'],deadline=r['deadline'],entries=r['entries'])))
"""
        result = subprocess.run([sys.executable,'-c',code,str(root)],capture_output=True,text=True,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr)
        facts = json.loads(result.stdout)
        self.assertEqual(facts,dict(limits=limits,deadline=deadline,entries=[]))
