"""Linux cooperative, eval-only durable budget API. Synthetic fake and native SDK loopback dispatch.

create() performs fresh v2 preflight. resume() uses the stored measured bundle,
checks current source/runtime, and never replays an unresolved physical attempt.
Registry ownership must remain local and exclusive; caller hashes are not identity.
"""
import copy
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from evals import architecture as a
from evals import architecture_authorization as auth
from evals import architecture_measurement as measurement
from evals.architecture_runtime import environment


class Blocked(RuntimeError):
    pass


class PersistenceFailure(Blocked):
    pass


def atomic_json(path, value):
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix='.eval-write-', dir=path.parent)
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def boot_id():
    return Path('/proc/sys/kernel/random/boot_id').read_text().strip()


class Controller:
    def __init__(self, root):
        auth.need(__debug__ and sys.platform == 'linux', 'Linux nonoptimized eval only')
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.lock = (self.root/'writer.lock').open('a')
        self.poisoned = False
        try:
            fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.path = self.root/'registry.json'
            self.data = auth.load(self.path) if self.path.exists() else dict(version=1, records={}, runs={})
            auth.fields(self.data, 'version records runs')
            auth.need(self.data['version'] == 1 and type(self.data['records']) is dict and
                      type(self.data['runs']) is dict, 'invalid registry')
        except BaseException:
            self.close()
            raise

    def close(self):
        self.poisoned = True
        self.lock.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _save(self):
        if self.poisoned:
            raise PersistenceFailure('handle blocked after persistence failure/close')
        try:
            atomic_json(self.path, self.data)
        except BaseException as exc:
            self.poisoned = True
            raise PersistenceFailure('durable write failed; execution may be unknown') from exc

    def create(self, plan, approval, policy, config_path, measurement_out, *, synthetic=False):
        auth.need(synthetic is True, 'explicit synthetic scope required')
        # Check reuse before expensive measurement; lock spans preflight and commit.
        key = auth.digest(approval['record_id'])
        auth.need(key not in self.data['records'] and plan['run_id'] not in self.data['runs'],
                  'approval consumed or run already exists; resume only')
        receipt = measurement.preflight(plan, approval, policy, config_path, measurement_out)
        bundle = auth.load(measurement_out/'measurement-manifest.json')
        return self._consume(plan, approval, receipt, bundle)

    def _consume(self, plan, approval, receipt, bundle):
        """Internal commit after preflight, not a public admission alternative."""
        auth.require_remote_contract(dict(plan=plan, fee_authorization=approval), plan)
        auth.need(plan['schema_version'] == 2 and auth.digest(bundle['static']) == plan['measurement_lock'],
                  'invalid measured bundle')
        auth.need(receipt['plan_sha256'] == auth.digest(plan) and
                  receipt['authorization_sha256'] == auth.digest(approval) and
                  receipt['measurement_lock'] == plan['measurement_lock'] and
                  receipt['trust'] == 'local_remeasurement_not_host_attestation' and
                  receipt['remote_execution_allowed'] is False, 'invalid preflight receipt')
        key = auth.digest(approval['record_id'])
        auth.need(key not in self.data['records'] and plan['run_id'] not in self.data['runs'], 'already consumed')
        started = time.monotonic()
        self.run = dict(plan=copy.deepcopy(plan), approval=copy.deepcopy(approval), preflight=receipt,
            bundle=bundle, limits=copy.deepcopy(plan['budget']), started=started,
            boot_id=boot_id(), deadline=started+plan['budget']['max_seconds'], entries=[],
            synthetic=True, remote_execution_allowed=False, session_fee_authorization=False)
        self.data['runs'][plan['run_id']] = self.run
        self.data['records'][key] = dict(run_id=plan['run_id'], plan_sha256=auth.digest(plan),
                                       authorization_sha256=auth.digest(approval), measurement_lock=plan['measurement_lock'])
        self._save()
        return copy.deepcopy(self.run)

    def resume(self, run_id):
        if self.poisoned:
            raise PersistenceFailure('handle blocked')
        try:
            return self._resume(run_id)
        except BaseException:
            self.poisoned = True
            raise

    def _resume(self, run_id):
        self.run = self.data['runs'][run_id]
        p = self.run['plan']
        auth.require_remote_contract(dict(plan=p, fee_authorization=self.run['approval']), p)
        auth.need(self.run['boot_id'] == boot_id(), 'cross-boot resume blocked')
        auth.need(auth.digest(self.run['bundle']['static']) == p['measurement_lock'], 'stored measurement drift')
        auth.need(auth.digest(a.source_lock()) == p['source_lock']['snapshot'] and
                  environment() == self.run['bundle']['static']['runtime'], 'source/runtime drift')
        key = auth.digest(self.run['approval']['record_id'])
        auth.need(self.data['records'][key] == dict(run_id=run_id, plan_sha256=auth.digest(p),
            authorization_sha256=auth.digest(self.run['approval']), measurement_lock=p['measurement_lock']), 'consumption binding drift')
        changed = False
        for entry in self.run['entries']:
            if entry['state'] == 'reserved':
                entry.update(state='unknown', cost_cny=None, error='writer ended before durable result')
                changed = True
        for record in self.run.get('observations', {}).values():
            if record['state'] == 'started':
                record.update(state='interrupted', error='writer ended before durable judge result')
                changed = True
        if changed:
            self._save()
        return copy.deepcopy(self.run)

    def tighten(self, limits):
        auth.fields(limits, 'max_cny max_seconds max_requests')
        for key, value in limits.items():
            auth.number(value)
            auth.need(value <= self.run['limits'][key], 'budget enlargement')
        auth.need(type(limits['max_requests']) is int, 'invalid request count')
        self.run['limits'] = copy.deepcopy(limits)
        self.run['deadline'] = min(self.run['deadline'], self.run['started']+limits['max_seconds'])
        self._save()

    def _check(self):
        if self.poisoned:
            raise PersistenceFailure('handle blocked')
        r = self.run
        auth.require_remote_contract(dict(plan=r['plan'], fee_authorization=r['approval']), r['plan'])
        if (any(o['state'] == 'interrupted' for o in r.get('observations', {}).values()) or
                r['boot_id'] != boot_id() or time.monotonic() >= r['deadline'] or
                len(r['entries']) >= r['limits']['max_requests'] or
                any(e['cost_cny'] is None or e['state'] != 'complete' for e in r['entries'])):
            raise Blocked('deadline, count or unresolved attempt')

    def invoke_fake(self, observation, request, attempt, role, parameters, system, *, outcome='ok', usage=None):
        """One physical child call, no retry. All observations share this run budget.

        parameters/system are hashed for dynamic-request evidence, not fixed future
        prompts. This independent fake API does not run/judge an observation.
        """
        auth.need(outcome in ('ok', 'failed', 'partial', 'unknown'), 'invalid fake outcome')
        policy = self.run['plan']['billing_policy']
        usage = {k: 1 for k in policy['rates_per_million']} if usage is None else copy.deepcopy(usage)
        auth.fields(usage, ' '.join(policy['rates_per_million']))
        for k, value in usage.items():
            auth.need(type(value) is int and 0 <= value <= policy['token_ceiling_per_request'][k], 'usage outside ceiling')
        return self._invoke(observation, request, attempt, role, parameters, system,
                            lambda deadline: self._physical(outcome, usage))

    def _invoke(self, observation, request, attempt, role, parameters, system, dispatch):
        self._check()
        auth.string(observation)
        binding = measurement.bind_request(self.run['plan'], parameters, system, request, attempt, role)
        if observation in self.run.get('observations', {}):
            binding['observation_identity'] = self.run['observations'][observation]['identity']
            binding['source_sha256'] = self.run['plan']['source_lock'][binding['observation_identity']['arm']]
        identity = (observation, request, attempt)
        auth.need(not any((e['observation'], e['binding']['request_id'], e['binding']['attempt']) == identity
                          for e in self.run['entries']), 'duplicate physical identity')
        policy = self.run['plan']['billing_policy']
        keys = policy['rates_per_million']
        worst = sum(keys[k]*policy['token_ceiling_per_request'][k]/1e6 for k in keys)
        known = sum(e['cost_cny'] for e in self.run['entries'])
        auth.need(known+worst <= self.run['limits']['max_cny'], 'estimated budget exhausted')
        entry = dict(observation=observation, binding=binding, state='reserved', cost_cny=None,
                     reserved_estimate_cny=worst, supplier_invoice=None, usage_lower_bound={},
                     outcome=None, accounting_basis='synthetic_usage_fixed_price_estimate')
        per = self.run['bundle']['static']['config']['budget']
        previous = [e for e in self.run['entries'] if e['observation'] == observation]
        auth.need(attempt <= per['attempts'], 'per-observation retry ceiling')
        auth.need(not previous or time.monotonic()-previous[0]['reserved_at'] < per['seconds'],
                  'per-observation deadline')
        rounds = {e['binding']['request_id'] for e in previous if e['binding']['role'] == 'primary'}
        auth.need(role != 'primary' or request in rounds or len(rounds) < per['rounds'],
                  'per-observation round ceiling')
        auth.need(sum(e['cost_cny'] for e in previous)+worst <= per['cny'], 'per-observation estimate ceiling')
        binding['budget_reserved'] = True
        entry['reserved_at'] = time.monotonic()
        self._observation_deadline = self.run.get('observations', {}).get(observation, {}).get('deadline',
            (previous[0]['reserved_at'] if previous else entry['reserved_at'])+per['seconds'])
        self.run['entries'].append(entry)
        self._save()  # No process or transport may precede this durable boundary.
        try:
            if time.monotonic() >= min(self.run['deadline'], self._observation_deadline):
                raise Blocked('deadline exhausted after reservation; no dispatch')
            result = dispatch(min(self.run['deadline'], self._observation_deadline))
            entry.update(result)
            values = result['usage_lower_bound']
            if (set(values) != set(keys) or any(type(values[k]) is not int or
                    not 0 <= values[k] <= policy['token_ceiling_per_request'][k] for k in keys)):
                entry['outcome'] = result['outcome'] = 'unknown'
            entry['state'] = 'complete' if result['outcome'] in ('ok', 'failed') else result['outcome']
            entry['cost_cny'] = (sum(keys[k]*result['usage_lower_bound'][k]/1e6 for k in keys)
                                 if result['outcome'] in ('ok', 'failed') else None)
            self._save()
        except BaseException as exc:
            # Preserve partial facts and the original exception even if saving fails.
            partial = getattr(exc, 'sdk_receipt', None)
            if partial is not None:
                entry['physical_error_receipt'] = copy.deepcopy(partial)
                entry['usage_lower_bound'] = copy.deepcopy(partial.get('usage_lower_bound', {}))
            entry.update(state='unknown', cost_cny=None, error=repr(exc))
            exc.durable_attempt = copy.deepcopy(entry)
            try:
                self._save()
            except BaseException as save_error:
                exc.persistence_error = save_error
            raise
        if time.monotonic() >= min(self.run['deadline'], self._observation_deadline):
            raise Blocked('deadline exceeded after physical call; result saved')
        return copy.deepcopy(entry)

    def execute_loopback(self, measured_out, arm, group, *, split='development', repeat=0):
        """One scheduled observation; no replay of started identities, even on resume."""
        from evals import architecture_execution as ex
        from evals.architecture_loopback import service
        from evals.architecture_sdk import SDKTransport
        from evals.architecture_anthropic import AnthropicTransport
        self._check()
        static = self.run['bundle']['static']
        config = static['config']
        auth.need(type(repeat) is int and repeat >= 0, 'invalid repeat identity')
        matches = [x for x in static['schedule'] if x['arm'] == arm and x['group'] == group
                   and x['split'] == split and x['repeat'] == repeat]
        auth.need(len(matches) == 1, 'unplanned observation')
        observation = '/'.join((arm, group, split, str(repeat)))
        auth.need(observation not in self.run.get('observations', {}), 'observation already started; no replay')
        auth.need(a.source_lock() == static['manifests']['snapshot'] and
                  environment() == static['runtime'], 'execution source/runtime drift')
        for name, manifest in static['manifests'].items():
            ex.verify_package(measured_out/name, manifest)
        adapter = measured_out/'adapter'
        ex.verify_adapter(adapter, static['manifests']['snapshot'])
        ex.check_service_path(measured_out/observation.replace('/', '-'), group)
        started = time.monotonic()
        record = dict(identity=matches[0], started=started,
                      deadline=min(self.run['deadline'], started+config['budget']['seconds']), state='started')
        self.run.setdefault('observations', {})[observation] = record
        self._save()
        adapter = measured_out/'adapter'
        ledger = DurableLedger(self, observation, record)
        policy = self.run['plan']['billing_policy']
        rates = tuple(policy['rates_per_million'][k] for k in
                      (('input', 'output') if config['model']['provider'] == 'openai' else
                       ('input', 'output', 'cache_read', 'cache_creation')))
        native = config['model']['provider'] == 'anthropic'
        try:
            with service(group, config['model']['version'], provider=config['model']['provider'], split=split) as endpoint:
                transport = (AnthropicTransport if native else SDKTransport)(endpoint, config['model']['version'], rates,
                    child_path=measured_out/('snapshot/evals/architecture_anthropic_child.py' if native else
                                            'snapshot/evals/architecture_sdk_child.py'))
                result = ex.execute(measured_out, static['manifests'], config, arm, group, adapter,
                    transport=transport, split=split, durable_ledger=ledger,
                    observation_name=observation.replace('/', '-'))
            selected = [e for e in self.run['entries'] if e['observation'] == observation]
            record.update(state='finished', result=result, result_sha256=a.digest(result),
                          requests_sha256=a.digest(selected))
            self._save()
            return result
        except BaseException as exc:
            record.update(state='interrupted', error=repr(exc))
            try:
                self._save()
            except BaseException as save_error:
                exc.persistence_error = save_error
            raise

    def invoke_sdk(self, observation, request, attempt, role, parameters, system, transport):
        # No arbitrary callback/remote subclass: only the reviewed local native adapters.
        from evals.architecture_sdk import SDKTransport
        from evals.architecture_anthropic import AnthropicTransport
        auth.need(type(transport) in (SDKTransport, AnthropicTransport), 'unsupported SDK transport')
        provider = 'anthropic' if type(transport) is AnthropicTransport else 'openai'
        auth.need(provider == self.run['plan']['provider'], 'SDK provider drift')
        keys = ('input', 'output') if provider == 'openai' else ('input', 'output', 'cache_read', 'cache_creation')
        def mapped(receipt):
            lower = receipt.get('usage_lower_bound', {})
            return {key: lower[native] for key, native in zip(keys, transport.usage_keys) if native in lower}
        def dispatch(deadline):
            try:
                receipt = transport.invoke(parameters, request, attempt, role, deadline)
            except BaseException as exc:
                if hasattr(exc, 'sdk_receipt'):
                    exc.sdk_receipt = dict(exc.sdk_receipt, usage_lower_bound=mapped(exc.sdk_receipt))
                raise
            return dict(outcome=receipt['outcome'] if receipt.get('usage_complete') else 'unknown',
                        usage_lower_bound=mapped(receipt), sdk_receipt=receipt, supplier_invoice=None)
        return self._invoke(observation, request, attempt, role, parameters, system, dispatch)

    def _physical(self, outcome, usage):
        # Fixed subprocess fake, no endpoint, credential, user code or SDK/network.
        code = "import json,sys; print(json.dumps(dict(outcome=sys.argv[1],usage_lower_bound=json.loads(sys.argv[2]),supplier_invoice=None)))"
        auth.require_remote_contract(dict(plan=self.run['plan'], fee_authorization=self.run['approval']), self.run['plan'])
        remaining = min(self.run['deadline'], self._observation_deadline)-time.monotonic()
        # Converting a rounded absolute deadline back to seconds can exceed the budget by one tick.
        timeout = min(remaining, self.run['limits']['max_seconds'],
                      self.run['bundle']['static']['config']['budget']['seconds'])
        if timeout <= 0:
            raise Blocked('deadline exhausted before physical dispatch')
        result = subprocess.run([sys.executable, '-I', '-c', code, outcome, auth.canonical(usage)],
            capture_output=True, text=True, timeout=timeout,
            env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8'})
        if result.returncode:
            raise RuntimeError('fake child failed: '+result.stderr)
        return json.loads(result.stdout)


class DurableLedger:
    """Observation receipt view; the Controller is the sole budget authority."""
    def __init__(self, controller, observation, record):
        self.controller, self.observation = controller, observation
        self.started, self.deadline = record['started'], record['deadline']
        self.budget = controller.run['bundle']['static']['config']['budget']
        self.rounds = 0

    @property
    def entries(self):
        return {(e['binding']['request_id'], e['binding']['attempt']): dict(
            e.get('sdk_receipt', {}), request_id=e['binding']['request_id'], attempt=e['binding']['attempt'],
            role=e['binding']['role'], outcome=e['outcome'], cost_cny=e['cost_cny'])
            for e in self.controller.run['entries'] if e['observation'] == self.observation}

    def check(self):
        from evals.architecture_execution import BudgetStop
        try:
            self.controller._check()
            if time.monotonic() >= self.deadline or self.rounds >= self.budget['rounds']:
                raise Blocked('observation exhausted')
        except Blocked as exc:
            raise BudgetStop(str(exc)) from exc

    def invoke_sdk(self, request, role, parameters, system, transport):
        from evals.architecture_execution import BudgetStop
        for attempt in range(1, self.budget['attempts']+1):
            self.check()
            try:
                entry = self.controller.invoke_sdk(self.observation, request, attempt, role, parameters, system, transport)
            except (Blocked, auth.RemoteBlocked) as exc:
                raise BudgetStop(str(exc)) from exc
            if entry['cost_cny'] is None:
                raise BudgetStop('unknown SDK usage; durable run blocked')
            if entry['outcome'] == 'ok':
                return entry['sdk_receipt']
        raise BudgetStop('durable retry attempts exhausted')
