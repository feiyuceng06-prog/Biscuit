"""Offline consumed-plan batches and registry-authoritative synthetic export.

No credential or remote admission. Export is cooperative evidence, not attestation.
"""
import argparse
import copy
import json
import hashlib
import math
from pathlib import Path
import tempfile

from evals import architecture as a
from evals import architecture_authorization as auth
from evals import architecture_measurement as m
from evals.architecture_durable import Controller, atomic_json


def identity(item):
    return '/'.join((item['arm'], item['group'], item['split'], str(item['repeat'])))


def schedule(c):
    static = c.run['bundle']['static']
    expected = a.plan(static['config'])
    auth.need(static['schedule'] == expected, 'stored schedule drift')
    return expected


def batch(c, measured_out, limit):
    auth.need(type(limit) is int and limit > 0, 'positive batch limit required')
    from evals.architecture_execution import check_service_path
    items = schedule(c)
    for item in items:
        check_service_path(measured_out/identity(item).replace('/', '-'), item['group'])
    results = []
    for item in items:
        record = c.run.get('observations', {}).get(identity(item))
        if record is not None:
            auth.need(record['state'] == 'finished', 'unresolved observation; manual handling unavailable')
            continue
        c._check()  # Includes unresolved requests in any observation; never clear them.
        results.append(c.execute_loopback(measured_out, item['arm'], item['group'],
                                          split=item['split'], repeat=item['repeat']))
        if len(results) == limit:
            break
    return results


def validate_receipt(run, entry, parameters=None):
    """Check complete native evidence against the consumed source and settlement."""
    receipt = entry.get('sdk_receipt')
    auth.need(type(receipt) is dict, 'missing/invalid SDK receipt')
    plan, static = run['plan'], run['bundle']['static']
    provider = plan['provider']
    native = (('prompt_tokens', 'completion_tokens') if provider == 'openai' else
              ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens'))
    keys = ('input', 'output') if provider == 'openai' else ('input', 'output', 'cache_read', 'cache_creation')
    policy = plan['billing_policy']
    usage = receipt.get('usage_lower_bound')
    auth.need(type(usage) is dict and set(usage) == set(native), 'SDK usage shape drift')
    mapped = {k: usage[n] for k, n in zip(keys, native)}
    auth.need(all(type(v) is int and 0 <= v <= policy['token_ceiling_per_request'][k]
                  for k, v in mapped.items()) and mapped == entry['usage_lower_bound'], 'SDK usage drift')
    auth.need(receipt.get('synthetic') is True and receipt.get('usage_complete') is True and
              receipt.get('reaped') is True and receipt.get('outcome') == entry['outcome'] and
              receipt.get('requested_model') == plan['model']['version'] and
              receipt.get('returned_models') == [plan['model']['version']] and
              receipt.get('sdk_version') == static['sdk_version'], 'SDK completion/model drift')
    manifest = static['manifests']['snapshot']
    semantics = 'architecture_sdk.py' if provider == 'openai' else 'architecture_anthropic.py'
    child = 'architecture_sdk_child.py' if provider == 'openai' else 'architecture_anthropic_child.py'
    expected = dict(adapter_sha256=manifest['evals/architecture_sdk.py'],
                    semantics_sha256=manifest['evals/'+semantics],
                    child_sha256=manifest['evals/'+child],
                    interpreter_sha256=static['runtime']['executable_sha256'])
    auth.need(all(receipt.get(k) == v for k, v in expected.items()), 'SDK source/runtime drift')
    rates = [policy['rates_per_million'][k] for k in keys]
    recorded = receipt.get('rates_cny_per_million')
    auth.need(type(recorded) in (list, tuple) and len(recorded) == len(rates) and
              all(a.number(v) and v == r for v, r in zip(recorded, rates)), 'SDK rates drift')
    cost = receipt.get('cost_cny')
    auth.need(a.number(cost) and math.isclose(cost, entry['cost_cny'], rel_tol=1e-12, abs_tol=1e-18) and
              receipt.get('invoice') is None and receipt.get('supplier_invoice') is None and
              entry.get('supplier_invoice') is None and
              receipt.get('accounting_basis') == 'usage_fixed_price_estimate' and
              receipt.get('rate_source') == 'synthetic_fixture_not_supplier_quote', 'SDK settlement drift')
    from evals.architecture_sdk import SDKTransport
    SDKTransport(receipt.get('endpoint'), plan['model']['version'])
    if parameters is not None:
        expected_request = hashlib.sha256(json.dumps(parameters, sort_keys=True).encode()).hexdigest()
        auth.need(receipt.get('request_sha256') == expected_request, 'SDK request drift')


def export(c):
    auth.need(not c.poisoned and __debug__, 'closed/optimized export')
    r = c.run
    static = r['bundle']['static']
    items = schedule(c)
    planned = {identity(x): x for x in items}
    observations = r.get('observations', {})
    auth.need(set(observations) <= set(planned), 'unplanned observation')
    auth.need(all(e['observation'] in observations for e in r['entries']), 'unbound physical request')
    rows, states = [], []
    for name, item in planned.items():
        record = observations.get(name)
        if record is None:
            states.append(dict(observation=name, state='not_started'))
            continue
        auth.need(record['identity'] == item, 'observation identity drift')
        entries = [e for e in r['entries'] if e['observation'] == name]
        state = record['state']
        auth.need(state in ('started', 'interrupted', 'finished'), 'invalid observation state')
        states.append(dict(observation=name, record=copy.deepcopy(record)))
        seen = set()
        for e in entries:
            b = e['binding']; key = (b['request_id'], b['attempt'])
            auth.need(key not in seen, 'duplicate physical request')
            seen.add(key)
            auth.need(b['plan_sha256'] == auth.digest(r['plan']) and
                b['measurement_lock'] == r['plan']['measurement_lock'] and
                b['observation_identity'] == item and b['source_sha256'] == r['plan']['source_lock'][item['arm']]
                and b['budget_reserved'] is True, 'request binding drift')
            auth.need(e['cost_cny'] is None or a.number(e['cost_cny']), 'invalid cost')
            if e['state'] == 'complete':
                policy = r['plan']['billing_policy']; usage = e['usage_lower_bound']
                auth.fields(usage, ' '.join(policy['rates_per_million']))
                auth.need(all(type(v) is int and 0 <= v <= policy['token_ceiling_per_request'][k]
                              for k, v in usage.items()), 'usage drift')
                expected = sum(policy['rates_per_million'][k]*v/1e6 for k, v in usage.items())
                auth.need(e['outcome'] in ('ok', 'failed') and a.number(e['cost_cny']) and math.isclose(e['cost_cny'], expected, rel_tol=1e-12, abs_tol=1e-18), 'settlement drift')
                validate_receipt(r, e)
            else:
                auth.need(e['state'] in ('reserved', 'unknown', 'partial') and e['cost_cny'] is None,
                          'unknown result relabeled')
        if state != 'finished':
            continue
        result = record['result']
        auth.need(record['result_sha256'] == a.digest(result) and
                  record['requests_sha256'] == a.digest(entries), 'result/request evidence drift')
        ev = result['evidence']; case = a.cases.spec(item['group'], item['split'])
        auth.need(result['arm'] == item['arm'] and result['group'] == item['group'] and
                  result['synthetic'] is True and result['facts'] == ev['facts'] and
                  ev['case_sha256'] == a.digest(case), 'judge identity drift')
        # Re-run the independent judge on captured final artifacts, never worker tests.
        with tempfile.TemporaryDirectory(prefix='eval-judge-') as tmp:
            root = Path(tmp)
            for file, value in ev['files'].items():
                auth.need(Path(file).name == file and file not in ('.', '..'), 'invalid artifact path')
                (root/file).write_text(value, encoding='utf-8')
            passed = ev['inventory_regular'] is True and a.cases.judge(case, root, ev['facts'])
        auth.need(ev['judge_passed'] is passed, 'judge evidence drift')
        auth.need(result['status'] in a.STATUSES and
                  (result['status'] != 'success' or passed), 'unproved success')
        for e in entries:
            b = e['binding']
            auth.need(b['request_id'].isdigit() and 1 <= int(b['request_id']) <= len(ev['requests']), 'missing request evidence')
            req = ev['requests'][int(b['request_id'])-1]
            binding = m.bind_request(r['plan'], req['parameters'], req['system'], b['request_id'], b['attempt'], b['role'])
            auth.need(all(b[k] == v for k, v in binding.items() if k != 'budget_reserved'), 'dynamic request drift')
            if e['state'] == 'complete':
                validate_receipt(r, e, req['parameters'])
        if not entries:
            continue  # No invented attempt: state/evidence remain visible, no scored row.
        row = dict(schema_version=1, synthetic=True, **item, status=result['status'],
            plan_sha256=a.digest(r['plan']), source_sha256=r['plan']['source_lock'][item['arm']],
            judge_sha256=static['judge_sha256'], model_version=static['config']['model']['version'],
            seconds=ev['seconds'], human_interventions=0,
            accounting_complete=all(e['state'] == 'complete' and e['cost_cny'] is not None for e in entries),
            attempts=[dict(kind=e['binding']['role'] if e['outcome']=='ok' else 'failed', cost_cny=e['cost_cny']) for e in entries])
        a.validate_row(row); rows.append(row)
    return dict(schema_version=2, artifact_type='durable_sdk_loopback_results', mode='offline_synthetic',
        synthetic=True, remote_execution_allowed=False, run_id=r['plan']['run_id'],
        plan_sha256=a.digest(r['plan']), measurement_lock=r['plan']['measurement_lock'],
        source_lock=r['plan']['source_lock'], runtime_sha256=a.digest(static['runtime']),
        registry_run_sha256=a.digest(r), observations=states, requests=copy.deepcopy(r['entries']), rows=rows)


def aggregate(c, payload):
    auth.need(auth.canonical(payload) == auth.canonical(export(c)), 'export differs from authoritative registry')
    result = a.summarize(payload['rows'])
    result.update(planned_observations=len(schedule(c)), scored_observations=len(payload['rows']),
        missing_observations=len(schedule(c))-len(payload['rows']),
        observation_states=payload['observations'], comparison='confounded_full_snapshot',
        scope='synthetic SDK wiring only; no model benefit; local cooperative registry not host attestation')
    return result


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('command', choices=('create', 'batch', 'export', 'aggregate'))
    p.add_argument('--registry', type=Path, required=True)
    p.add_argument('--run-id')
    p.add_argument('--measured-out', type=Path)
    p.add_argument('--limit', type=int, default=1)
    for name in ('plan', 'authorization', 'policy', 'config', 'input', 'out'):
        p.add_argument('--'+name, type=Path)
    args = p.parse_args()
    try:
        auth.need(__debug__, 'optimized Python scheduling is disabled')
        with Controller(args.registry) as c:
            if args.command == 'create':
                c.create(auth.load(args.plan), auth.load(args.authorization), auth.load(args.policy),
                         args.config, args.measured_out, synthetic=True)
                result = dict(consumed=True, synthetic=True, run_id=c.run['plan']['run_id'])
            else:
                c.resume(args.run_id)
                if args.command == 'batch':
                    executed = batch(c, args.measured_out, args.limit)
                    result = dict(executed=len(executed), states=[x['status'] for x in executed], synthetic=True)
                elif args.command == 'export': result = export(c)
                else: result = aggregate(c, auth.load(args.input))
        if args.out:
            auth.need(not args.out.exists(), 'output already exists; no append/double count')
            atomic_json(args.out, result)
        print(json.dumps(result, allow_nan=False))
        return 0
    except Exception as exc:
        print(json.dumps(dict(status='rejected', error=str(exc), remote_execution_allowed=False)))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
