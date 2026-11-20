"""Protected parent controller for synthetic product-path wiring checks only."""
import hashlib
import json
import os
from pathlib import Path
import selectors
import signal
import socket
import stat
import subprocess
import sys
import time

from evals import architecture as a
from evals import architecture_cases as cases
from evals.architecture_runtime import environment, dependency_manifest


def write(path, obj):
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def verify_package(root, manifest):
    actual = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in root.rglob('*') if p.is_file() and not p.is_symlink()}
    if actual != manifest or any(p.is_symlink() for p in root.rglob('*')):
        raise RuntimeError('source package inventory/bytes mismatch')


def verify_adapter(root, snapshot):
    """Bind the actual sandbox entry files to the measured snapshot."""
    names = ('architecture_worker.py', 'architecture_runtime.py')
    if (any(p.is_symlink() for p in (root, *root.parents)) or
            not root.is_dir() or {p.name for p in root.iterdir()} != set(names)):
        raise RuntimeError('adapter inventory/bytes mismatch')
    for name in names:
        path = root/name
        if (not stat.S_ISREG(path.lstat().st_mode) or
                hashlib.sha256(path.read_bytes()).hexdigest() != snapshot['evals/'+name]):
            raise RuntimeError('adapter inventory/bytes mismatch')


def freeze(out, config):
    manifests = dict(head=a.head_lock(config['baseline']), snapshot=a.source_lock())
    for arm, manifest in manifests.items():
        root = out / arm
        root.mkdir()
        for name, expected in manifest.items():
            data = (subprocess.check_output(['git', 'show', config['baseline']+':'+name], cwd=a.ROOT)
                    if arm == 'head' else (a.ROOT / name).read_bytes())
            if hashlib.sha256(data).hexdigest() != expected:
                raise RuntimeError('source changed while freezing')
            dest = root / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
        verify_package(root, manifest)
    write(out / 'manifests.json', manifests)
    return manifests


class BudgetStop(RuntimeError):
    pass


class Ledger:
    """Parent lifetime spans restores; roles and failed outcomes never double-charge."""
    def __init__(self, budget, now=time.monotonic):
        self.budget, self.now = budget, now
        self.started = now()
        self.rounds = 0
        self.entries = {}
        self.stopped = False

    def check(self):
        if (self.stopped or self.now()-self.started >= self.budget['seconds'] or
                self.rounds >= self.budget['rounds'] or
                any(not self.accounted(x) for x in self.entries.values()) or
                a.finite_sum(x['cost_cny'] for x in self.entries.values()) >= self.budget['cny']):
            self.stopped = True
            raise BudgetStop('parent budget_stop')

    def charge(self, request, attempt, role, cost, invoice, outcome='ok'):
        key = (request, attempt)
        if key in self.entries:
            raise RuntimeError('duplicate request/attempt invoice')
        if type(attempt) is not int or attempt > self.budget['attempts'] or attempt < 1:
            self.stopped = True
            raise BudgetStop('retry attempts exhausted')
        if cost is not None:
            if not a.number(cost):
                raise ValueError('invalid cost')
        self.entries[key] = dict(request_id=request, attempt=attempt, role=role,
                                 cost_cny=cost, invoice=invoice, outcome=outcome)


    @staticmethod
    def accounted(receipt):
        return receipt.get('cost_cny') is not None and bool(receipt.get('invoice') or (
            receipt.get('synthetic') is True and receipt.get('usage_complete') is True and
            receipt.get('accounting_basis') == 'usage_fixed_price_estimate'))

    def invoke(self, request, role, transport):
        for attempt in range(1, self.budget['attempts'] + 1):
            self.check()
            # Reserve before physical dispatch, including callback exceptions/cancellation.
            self.entries[(request, attempt)] = dict(request_id=request, attempt=attempt, role=role,
                cost_cny=None, invoice=None, outcome='pending')
            try:
                receipt = transport(request, attempt, role)
            except BaseException as exc:
                self.entries[(request, attempt)].update(getattr(exc, 'sdk_receipt', {}))
                self.entries[(request, attempt)].update(outcome='failed', error=type(exc).__name__)
                self.stopped = True
                raise
            pending = self.entries.pop((request, attempt))
            try:
                self.charge(request, attempt, role, receipt.get('cost_cny'),
                            receipt.get('invoice'), receipt.get('outcome', 'ok'))
            except BaseException as exc:
                self.entries[(request, attempt)] = dict(pending, outcome='failed', error=type(exc).__name__)
                self.stopped = True
                raise
            self.entries[(request, attempt)].update(receipt)
            if receipt.get('deadline_exceeded'):
                self.stopped = True
                raise BudgetStop('parent SDK deadline')
            if any(not self.accounted(e) for e in self.entries.values()):
                self.stopped = True
                raise BudgetStop('unknown or missing invoice')
            if a.finite_sum(e['cost_cny'] for e in self.entries.values()) > self.budget['cny']:
                self.stopped = True
                raise BudgetStop('cost ceiling exceeded')
            if receipt.get('outcome', 'ok') == 'ok':
                return receipt
        self.stopped = True
        raise BudgetStop('retry attempts exhausted')



MAX_FRAME = 8 * 1024 * 1024


def remaining_time(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise BudgetStop('parent wall deadline')
    return remaining


def send_frame(pipe, reply, deadline):
    data = (json.dumps(reply, allow_nan=False) + '\n').encode()
    if len(data) > MAX_FRAME:
        raise RuntimeError('worker reply frame too large')
    view = memoryview(data)
    with selectors.DefaultSelector() as writable:
        writable.register(pipe, selectors.EVENT_WRITE)
        while view:
            timeout = remaining_time(deadline)
            if not writable.select(timeout):
                remaining_time(deadline)
                continue
            remaining_time(deadline)
            try:
                count = os.write(pipe.fileno(), view)
            except BlockingIOError:
                continue
            if not count:
                raise RuntimeError('worker reply pipe closed')
            view = view[count:]

def sandbox(source, adapter, work, state, service=None):
    cmd = ['/usr/bin/bwrap', '--die-with-parent', '--unshare-all', '--new-session',
           '--ro-bind', '/usr', '/usr', '--ro-bind', '/lib', '/lib', '--ro-bind', '/lib64', '/lib64',
           '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp']
    # Only the selected environment, never its ancestor HOME or real configuration.
    prefixes = {str(Path(sys.prefix)), str(Path(sys.base_prefix))}
    for prefix in sorted(prefixes):
        if prefix != '/usr':
            cmd += ['--ro-bind', prefix, prefix]
    cmd += ['--ro-bind', str(source/'feiyu'), '/source/feiyu', '--ro-bind', str(adapter), '/adapter',
            '--bind', str(work), '/work', '--bind', str(state), '/state']
    if service:
        cmd += ['--bind', str(service), '/service']
    return cmd + ['--chdir', '/work', '--clearenv', '--setenv', 'HOME', '/state',
                  '--setenv', 'XDG_CONFIG_HOME', '/state/config', '--setenv', 'XDG_STATE_HOME', '/state/state',
                  '--setenv', 'XDG_CACHE_HOME', '/state/cache', '--setenv', 'XDG_DATA_HOME', '/state/data',
                  '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'LANG', 'C.UTF-8',
                  '--setenv', 'PYTHONDONTWRITEBYTECODE', '1', sys.executable, '/adapter/architecture_worker.py']


def check_service_path(dest, group, measurement_only=False):
    if group == 'recovery' and not measurement_only:
        physical = (dest/'service.sock').resolve()
        size = len(os.fsencode(physical))
        if size >= 108:
            raise ValueError(f'AF_UNIX service path is {size} bytes; maximum 107: {physical}')
        return physical


def execute(out, manifests, config, arm, group, adapter, transport=None, fault=None, measurement_only=False, split='development', durable_ledger=None, observation_name=None):
    verify_adapter(adapter, manifests['snapshot'])
    dest = out / (observation_name or (arm+'-'+group+('-'+split if measurement_only else '')))
    service = check_service_path(dest, group, measurement_only)
    dest.mkdir()
    work, state = dest/'work', dest/'state'
    work.mkdir(); state.mkdir()
    case = cases.spec(group, split)
    cases.setup(case, work)
    for name in ('answer', 'results', 'receipt', 'lock'):
        write(dest/name, case['after'] if name == 'answer' else {})
    ledger = durable_ledger if durable_ledger is not None else Ledger(config['budget'])
    events, requests = [], []
    facts = {}
    if fault == 'rounds':
        ledger.rounds = config['budget']['rounds']
    stage = 0
    sid = None
    accepted = 0
    status = 'agent_failure'
    server = None
    source = out/arm
    expected_env = None
    expected_env = environment()
    try:
        if group == 'recovery' and not measurement_only:
            server = socket.socket(socket.AF_UNIX)
            server.bind(str(service)); server.listen(1)
        for restart in range(2 if group == 'recovery' and not measurement_only else 1):
            verify_package(source, manifests[arm])
            log = (dest/('worker-%d.log' % restart)).open('w')
            cmd = sandbox(source, adapter, work, state, service if server else None) + [str(dest)]
            try:
                p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                                     bufsize=0, start_new_session=True)
            except BaseException:
                log.close()
                raise
            os.set_blocking(p.stdout.fileno(), False)
            os.set_blocking(p.stdin.fileno(), False)
            buffer = bytearray()
            eof = False
            deadline = ledger.deadline if durable_ledger is not None else ledger.started + config['budget']['seconds']
            sel = selectors.DefaultSelector()
            sel.register(p.stdout, selectors.EVENT_READ, 'worker')
            if server:
                sel.register(server, selectors.EVENT_READ, 'service')
            killed = False
            try:
                while True:
                    ready = sel.select(min(remaining_time(deadline), 1))
                    remaining_time(deadline)
                    if not ready and p.poll() is not None:
                        if buffer:
                            raise RuntimeError('worker EOF with incomplete frame')
                        break
                    for key, _ in ready:
                        if key.data == 'service':
                            conn, _ = server.accept()
                            conn.settimeout(1)
                            conn.recv(1024)
                            accepted += 1
                            events.append(dict(kind='service_accept_disconnect', count=accepted))
                            conn.close()
                            os.killpg(p.pid, signal.SIGKILL)
                            killed = True
                            break
                        try:
                            chunk = os.read(p.stdout.fileno(), 65536)
                        except BlockingIOError:
                            continue
                        if not chunk:
                            if buffer:
                                raise RuntimeError('worker EOF with incomplete frame')
                            eof = True
                            break
                        buffer.extend(chunk)
                        if len(buffer) > MAX_FRAME:
                            raise RuntimeError('worker frame too large')
                        while b'\n' in buffer:
                            remaining_time(deadline)
                            line, _, tail = buffer.partition(b'\n')
                            buffer = bytearray(tail)
                            msg = json.loads(line)
                            events.append(msg)
                            kind = msg['kind']
                            reply = {}
                            if kind == 'hello':
                                if fault == 'environment' or msg['environment'] != expected_env:
                                    raise RuntimeError('environment drift')
                                for name, record in msg['origins'].items():
                                    path = record['path']
                                    if not path.startswith('/source/') or manifests[arm].get(path[8:]) != record['sha256']:
                                        raise RuntimeError('module source drift: '+name)
                                boundary = msg['boundary']
                                if any(v == 'ALLOWED' for k, v in boundary.items() if k.endswith(':w') or k.startswith(str(dest)) or k.startswith('/source/evals')):
                                    raise RuntimeError('controller isolation failed')
                                reply = dict(provider=config['model']['provider'], version=config['model']['version'], group=group, prompt=case['prompt'], restore=bool(restart), sid=sid, measurement_only=measurement_only, verification_content=case['after'].get('calc.py'))
                            elif kind == 'request':
                                ledger.check()
                                params = msg['parameters']
                                if params['model'] != config['model']['version']:
                                    raise RuntimeError('request model drift')
                                role = 'primary' if params.get('stream') else 'auxiliary'
                                req = str(len(requests)+1)
                                requests.append(dict(msg, request_sha256=a.digest(msg), system_sha256=a.digest(msg['system']), tools_sha256=a.digest(params.get('tools', []))))
                                if measurement_only:
                                    send_frame(p.stdin, dict(measurement_stop=True), deadline)
                                    status = 'measured'
                                    continue
                                receipt = (ledger.invoke_sdk(req, role, params, msg['system'], transport) if durable_ledger is not None else ledger.invoke(req, role,
                                    (lambda request, attempt, role: transport.invoke(params, request, attempt, role, deadline) if hasattr(transport, 'invoke') else transport(params, request, attempt, role)) if transport else
                                    (lambda request, attempt, role: dict(
                                        cost_cny=None if fault == 'unknown' else 3.1 if fault == 'cost' else 0.0,
                                        invoice=None if fault == 'missing' else 'synthetic:'+request,
                                        outcome='failed' if fault == 'retry' else 'ok'))))
                                calls = []
                                text = 'done'
                                def put(name, content):
                                    calls.append(dict(name='write_file', input=dict(path=name, content=content)))
                                if role == 'auxiliary':
                                    text = 'Preserve protected.txt; a.txt=5, b.txt=6; continue unfinished b.txt.'
                                else:
                                    ledger.rounds += 1
                                    if stage == 0 and group != 'recovery':
                                        calls.extend(dict(name='read_file', input={'path': name}) for name in case['before'])
                                    elif group == 'executor' and stage == 1:
                                        for name, content in case['after'].items():
                                            put(name, content)
                                    elif group == 'verification' and stage == 3:
                                        calls.append(dict(name='read_file', input={'path': 'calc.py'}))
                                    elif group == 'verification' and stage in (1, 4):
                                        put('calc.py', 'VALUE = 5\n')
                                    elif group == 'compaction' and stage in (1, 3):
                                        put('a.txt' if stage == 1 else 'b.txt', '5\n' if stage == 1 else '6\n')
                                    elif group == 'recovery' and stage in (1, 2):
                                        calls.append(dict(name='bash', input={'command': sys.executable+" -c \"import socket;s=socket.socket(socket.AF_UNIX);s.connect('/service');s.send(b'operation-5');s.recv(10)\""}))
                                    stage += 1
                                reply = (receipt['response'] if transport else dict(version=config['model']['version'], calls=calls, text=text))
                                if transport:
                                    reply['usage'] = receipt.get('usage_lower_bound', {})
                                if fault == 'model':
                                    reply['version'] = 'unexpected-version'
                            elif kind == 'verified':
                                if msg['value'] is not True or (work/'calc.py').read_text() != case['after']['calc.py']:
                                    raise RuntimeError('initial actual verification did not pass')
                                (work/'calc.py').write_text('VALUE = 0\n')
                                facts['controller_mutation'] = True
                            elif kind == 'stale':
                                facts['stale_rejected'] = msg['value'] is not True
                            elif kind == 'compacted':
                                facts['compacted'] = bool(msg['summary'])
                                facts['constraints_preserved'] = 'protected.txt' in json.dumps(msg['messages'])
                            elif kind == 'replay_blocked':
                                facts['replay_blocked'] = True
                            elif kind == 'saved':
                                sid = msg['sid']
                            elif kind == 'restored':
                                facts['resumed'] = True
                                facts['unknown_observed'] = any(op['state'] == 'unknown' for op in msg['operations'])
                            elif kind == 'done':
                                facts['fresh_verification'] = msg['verified'] is True
                                status = 'success' if cases.judge(case, work, facts) else 'agent_failure'
                            send_frame(p.stdin, reply, deadline)
                    if killed or eof:
                        break
                code = p.wait(timeout=3)
                events.append(dict(kind='worker_exit', code=code, intentional_disconnect=killed))
                if code and not killed:
                    status = 'environment_failure'
                    break
            finally:
                sel.close()
                if p.poll() is None:
                    os.killpg(p.pid, signal.SIGKILL)
                p.wait()
                p.stdin.close(); p.stdout.close(); log.close()
        facts['service_accepts'] = accepted
        facts['unknown_not_retried'] = accepted == 1 and facts.get('unknown_observed', False)
    except BudgetStop as exc:
        status = 'budget_stop'
        events.append(dict(kind='error', error=str(exc)))
    except BaseException as exc:
        status = 'environment_failure'
        events.append(dict(kind='error', error=repr(exc)))
        if not isinstance(exc, Exception):
            try:
                write(dest/'controller.json', dict(status=status, facts=facts, events=events,
                      requests=requests, ledger=list(ledger.entries.values()),
                      budget=config['budget'], synthetic=True, environment=expected_env,
                      seconds=time.monotonic()-ledger.started))
            except BaseException as save_error:
                exc.controller_persistence_error = save_error
                print('controller persistence failed during cancellation: '+repr(save_error), file=sys.stderr)
            raise
    finally:
        if server:
            server.close()
    verify_package(source, manifests[arm])
    if environment() != expected_env:
        status = 'environment_failure'
        events.append(dict(kind='error', error='environment drift after execution'))
    write(dest/'controller.json', dict(status=status, facts=facts, events=events, requests=requests,
          ledger=list(ledger.entries.values()), budget=config['budget'], synthetic=True,
          environment=expected_env, seconds=time.monotonic()-ledger.started))
    result = dict(arm=arm, group=group, status=status, synthetic=True, facts=facts)
    if durable_ledger is not None:
        # Capture from the actual parent/workspace, never reload diagnostic controller.json.
        result['evidence'] = dict(case_sha256=a.digest(case), facts=facts, events=events,
            requests=requests, files={p.name: p.read_text(encoding='utf-8') for p in work.iterdir()
                if p.is_file() and not p.is_symlink()},
            inventory_regular=all(p.is_file() and not p.is_symlink() for p in work.iterdir()),
            judge_passed=bool(cases.judge(case, work, facts)), seconds=time.monotonic()-ledger.started)
    return result


def run(config, out, loopback=False):
    out.mkdir(parents=True, exist_ok=False)
    manifests = freeze(out, config)
    adapter = out/'adapter'; adapter.mkdir()
    for name in ('architecture_worker.py', 'architecture_runtime.py'):
        (adapter/name).write_bytes((a.ROOT/'evals'/name).read_bytes())
    write(out/'dependency-manifest.json', dependency_manifest())
    results = []
    for group in config['groups']:
        for arm in ('head', 'snapshot'):
            if loopback:
                from evals.architecture_loopback import service
                from evals.architecture_sdk import SDKTransport
                native = config['model']['provider'] == 'anthropic'
                if native:
                    from evals.architecture_anthropic import AnthropicTransport
                for name in ('architecture_sdk.py', 'architecture_sdk_child.py', 'architecture_anthropic.py',
                             'architecture_anthropic_child.py', 'architecture_loopback.py', 'architecture_worker.py', 'architecture_runtime.py'):
                    if hashlib.sha256((a.ROOT/'evals'/name).read_bytes()).hexdigest() != manifests['snapshot']['evals/'+name]:
                        raise RuntimeError('SDK adapter source drift')
                with service(group, config['model']['version'], provider=config['model']['provider']) as endpoint:
                    result = execute(out, manifests, config, arm, group, adapter,
                                     transport=(AnthropicTransport if native else SDKTransport)(endpoint, config['model']['version'],
                                         child_path=out/('snapshot/evals/architecture_anthropic_child.py' if native else 'snapshot/evals/architecture_sdk_child.py')))
            else:
                result = execute(out, manifests, config, arm, group, adapter)
            results.append(result)
    # Existing row schema remains in force; this receipt lock is deliberately
    # separate from fixture locks and cannot be relabeled as live evidence.
    lock = dict(mode='offline_synthetic', artifact_type='synthetic_product_execution',
                transport=config['model']['provider']+'_sdk_loopback' if loopback else 'scripted_fake',
                config=config, manifests=manifests, environment=json.loads((out/'head-executor/controller.json').read_text())['environment'],
                receipts={r['arm']+'-'+r['group']: hashlib.sha256((out/(r['arm']+'-'+r['group'])/'controller.json').read_bytes()).hexdigest() for r in results})
    write(out/'execution-lock.json', lock)
    rows = []
    for result in results:
        item = next(x for x in a.plan(config) if x['arm'] == result['arm'] and x['group'] == result['group'] and x['split'] == 'development' and x['repeat'] == 0)
        receipt = json.loads((out/(result['arm']+'-'+result['group'])/'controller.json').read_text())
        attempts = [dict(kind=e['role'] if e['outcome'] == 'ok' else 'failed', cost_cny=e['cost_cny']) for e in receipt['ledger']]
        row = dict(schema_version=1, synthetic=True, **item, status=result['status'],
                   plan_sha256=a.digest(lock), source_sha256=a.digest(manifests[result['arm']]),
                   judge_sha256=manifests['snapshot']['evals/architecture_cases.py'],
                   model_version=config['model']['version'], seconds=receipt['seconds'], human_interventions=0,
                   accounting_complete=bool(attempts) and all(Ledger.accounted(e) for e in receipt['ledger']),
                   attempts=attempts or [dict(kind='primary', cost_cny=None)])
        a.validate_row(row)
        rows.append(row)
    (out/'synthetic.jsonl').write_text(''.join(json.dumps(row, allow_nan=False)+'\n' for row in rows))
    write(out/'execution-summary.json', dict(results=results, synthetic=True,
          comparison=config['comparison'], scope='development wiring only; not model benefit'))
    return results
