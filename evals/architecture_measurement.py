"""Offline byte measurement. Never loads credentials or admits remote execution."""
import argparse
import copy
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess

from evals import architecture as a
from evals import architecture_authorization as auth
from evals import architecture_execution as execution
from evals.architecture_runtime import dependency_manifest, environment


def raw_sha(data):
    return hashlib.sha256(data).hexdigest()


def bind_request(plan, parameters, system, request_id, attempt=1, role='primary'):
    """Local request evidence only, neither dispatch admission nor budget reservation."""
    auth.validate_plan(plan)
    auth.need(plan['schema_version'] == 2, 'request binding requires measured plan')
    auth.string(request_id)
    auth.need(type(attempt) is int and attempt > 0 and role in ('primary', 'auxiliary'), 'invalid request identity')
    auth.need(type(parameters) is dict and parameters.get('model') == plan['model']['version'], 'request model drift')
    for key in ('temperature', 'top_p', 'seed'):
        auth.need(type(parameters.get(key)) is type(plan['sampling'][key]) and
                  parameters.get(key) == plan['sampling'][key], 'request sampling drift')
    auth.need(type(system) is str, 'invalid request system')
    return dict(plan_sha256=auth.digest(plan), measurement_lock=plan['measurement_lock'],
                request_id=request_id, attempt=attempt, role=role,
                parameters_sha256=auth.digest(parameters), system_bytes_sha256=raw_sha(system.encode('utf-8')),
                remote_execution_allowed=False, budget_reserved=False)


def policy_plan(policy):
    p = copy.deepcopy(policy)
    auth.need(p.get('schema_version') == 1, 'policy must be v1 candidate, not measured output')
    auth.validate_plan(p)
    return p


def measure(policy, config_path, out, expected=None):
    """Fresh output only; observed is built from bytes, not a supplied manifest."""
    auth.need(__debug__, 'optimized Python measurement is disabled')
    p = policy_plan(policy)
    config_bytes = config_path.read_bytes()
    config = a.validate(auth.load(config_path))
    auth.need(config['model']['provider'] == p['provider'] and
              config['model']['version'] == p['model']['version'], 'policy/config model mismatch')
    # Scope is the repository containing this module. Reject aliases into external data.
    names = a.source_lock()
    for name in names:
        path = a.ROOT / name
        auth.need(not any(parent.is_symlink() for parent in (path, *path.parents)), 'source symlink')
    baseline = subprocess.check_output(['git', 'rev-parse', config['baseline']+'^{commit}'], cwd=a.ROOT).decode().strip()
    auth.need(baseline == config['baseline'], 'baseline must be full commit ID')
    before = environment()
    deps = dependency_manifest()
    out.mkdir(parents=True, exist_ok=False)
    manifests = execution.freeze(out, config)
    auth.need(manifests['snapshot'] == names, 'source drift before freeze')
    runtime_lock = {arm: dict(interpreter_sha256=before['executable_sha256'],
                             dependencies_sha256=before['dependency_tree_sha256']) for arm in manifests}
    task_lock = auth.digest(dict(config=config, schedule=a.plan(config),
        cases=[a.cases.spec(g, s) for g in config['groups'] for s in config['splits']],
        judge=manifests['snapshot']['evals/architecture_cases.py']))
    if expected is not None:
        auth.validate_plan(expected)
        for key, value in dict(source_lock={arm: auth.digest(m) for arm, m in manifests.items()},
                               runtime_lock=runtime_lock, task_lock=task_lock,
                               sdk_version=importlib.metadata.version(p['provider'])).items():
            auth.need(expected[key] == value, 'measured input drift: '+key)
    adapter = out/'adapter'; adapter.mkdir()
    for name in ('architecture_worker.py', 'architecture_runtime.py'):
        (adapter/name).write_bytes((out/'snapshot/evals'/name).read_bytes())
    initial, actual = {}, []
    for arm in ('head', 'snapshot'):
        initial[arm] = []
        for group in config['groups']:
            for split in config['splits']:
                result = execution.execute(out, manifests, config, arm, group, adapter,
                                           measurement_only=True, split=split)
                record = auth.load(out/(arm+'-'+group+'-'+split)/'controller.json')
                auth.need(result['status'] == 'measured' and len(record['requests']) == 1,
                          'worker measurement failed: '+arm+'/'+group+'/'+split)
                hello = [e for e in record['events'] if e.get('kind') == 'hello']
                auth.need(len(hello) == 1 and hello[0]['environment'] == before, 'worker runtime mismatch')
                exits = [e for e in record['events'] if e.get('kind') == 'worker_exit']
                auth.need(len(exits) == 1 and exits[0]['code'] == 0, 'worker measurement exit')
                request = record['requests'][0]
                params = request['parameters']
                sampling = config['model']
                for key in ('temperature', 'top_p', 'seed'):
                    auth.need(params.get(key) == sampling[key], 'native sampling mismatch: '+key)
                prepared = [e for e in record['events'] if e.get('kind') == 'prepared']
                auth.need(len(prepared) == 1, 'missing initial constructor prompt')
                system = prepared[0]['system']
                auth.need(type(system) is str, 'system must be native UTF8 string')
                initial[arm].append(dict(group=group, split=split, system_utf8=system,
                    system_bytes_sha256=raw_sha(system.encode('utf-8')), tools=params.get('tools', []),
                    task_prompt_utf8=a.cases.spec(group, split)['prompt']))
                actual.append(dict(arm=arm, group=group, split=split, request_id='initial-1',
                    role='primary', system_utf8=request['system'],
                    system_bytes_sha256=raw_sha(request['system'].encode('utf-8')),
                    parameters=params, parameters_sha256=auth.digest(params),
                    encoding='canonical_json_utf8', scope='observed_initial_only_future_requests_dynamic'))
    auth.need(environment() == before and dependency_manifest() == deps, 'runtime changed during measurement')
    auth.need(config_path.read_bytes() == config_bytes and a.source_lock() == names and
              a.head_lock(baseline) == manifests['head'], 'inputs changed during measurement')
    for arm in manifests:
        execution.verify_package(out/arm, manifests[arm])
    execution.verify_adapter(adapter, manifests['snapshot'])
    constructor = {k: v for k, v in manifests['snapshot'].items() if k.startswith('evals/')}
    stable = dict(schema_version=2, baseline_commit=baseline, manifests=manifests,
        config=config, config_bytes_sha256=raw_sha(config_bytes), schedule=a.plan(config),
        cases=[a.cases.spec(g, s) for g in config['groups'] for s in config['splits']],
        judge_sha256=manifests['snapshot']['evals/architecture_cases.py'],
        runtime=before, dependencies=deps, initial=initial, constructor=constructor,
        sdk_version=importlib.metadata.version(p['provider']))
    p.update(schema_version=2, measurement_lock=auth.digest(stable),
        prompt_semantics='initial_constructor_and_system_not_full_requests',
        source_lock={arm: auth.digest(m) for arm, m in manifests.items()},
        runtime_lock={arm: dict(interpreter_sha256=before['executable_sha256'],
                               dependencies_sha256=before['dependency_tree_sha256']) for arm in manifests},
        prompt_lock={arm: auth.digest(dict(initial=initial[arm], constructor=constructor,
                           source=manifests[arm])) for arm in manifests},
        task_lock=auth.digest(dict(config=config, schedule=stable['schedule'], cases=stable['cases'],
                                  judge=stable['judge_sha256'])), sdk_version=stable['sdk_version'],
        sampling=dict(temperature=config['model']['temperature'], top_p=config['model']['top_p'],
                      seed=config['model']['seed'], auxiliary='same_exact_version_and_sampling'))
    auth.validate_plan(p)
    for record in actual:
        record['binding'] = bind_request(p, record['parameters'], record['system_utf8'],
            record['arm']+'/'+record['group']+'/'+record['split']+'/'+record['request_id'])
    execution.write(out/'measurement-manifest.json', dict(static=stable, actual_requests=actual,
        full_future_prompt_fixed=False, host_attestation=False, remote_execution_allowed=False))
    execution.write(out/'observed.json', p)
    return p


def preflight(plan, authorization, policy, config_path, out, now=None):
    auth.need(__debug__, 'optimized Python measurement is disabled')
    auth.need(type(plan) is dict and plan.get('schema_version') == 2, 'measured preflight requires v2 plan')
    observed = measure(policy, config_path, out, expected=plan)
    receipt = auth.require_remote_contract(dict(plan=plan, fee_authorization=authorization), observed, now)
    receipt.update(trust='local_remeasurement_not_host_attestation', measurement_lock=observed['measurement_lock'],
                   full_future_prompt_fixed=False)
    execution.write(out/'preflight-receipt.json', receipt)
    return receipt


def main():
    parser = argparse.ArgumentParser(__doc__)
    parser.add_argument('command', choices=('prepare', 'measure', 'preflight'))
    parser.add_argument('--policy', required=True, type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--authorization', type=Path)
    args = parser.parse_args()
    try:
        auth.need(__debug__, 'optimized Python measurement is disabled')
        policy = auth.load(args.policy)
        if args.command == 'preflight':
            auth.need(args.plan is not None and args.authorization is not None, 'missing plan/authorization')
            receipt = preflight(auth.load(args.plan), auth.load(args.authorization), policy, args.config, args.out)
        else:
            p = measure(policy, args.config, args.out)
            receipt = dict(status='measured_unapproved', observed_sha256=auth.digest(p), remote_execution_allowed=False)
            if args.command == 'prepare':
                execution.write(args.out/'unapproved-template.json', dict(plan=p, fee_authorization=auth.template(p)))
    except (Exception,) as exc:
        print(json.dumps(dict(status='rejected', error=str(exc), remote_execution_allowed=False)))
        return 2
    print(json.dumps(receipt, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
