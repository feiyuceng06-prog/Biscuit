"""Critical task storage. No model output or diagnostic sink owns these facts."""
from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from functools import wraps
import os
import stat
from pathlib import Path
import tempfile
import threading
import time
import uuid

from . import files

SCHEMA_VERSION = 1


class PersistenceError(RuntimeError):
    pass


def local_relative_path(value):
    if (not isinstance(value, str) or not value or '\x00' in value or
            '\\' in value or ':' in value):
        raise ValueError('invalid local path')
    path = Path(value)
    if path.is_absolute() or any(part in ('', '.', '..') for part in value.split('/')):
        raise ValueError('local path must be canonical and relative')
    return path


def critical_write(method):
    @wraps(method)
    def guarded(self, *args, **kwargs):
        try:
            return method(self, *args, **kwargs)
        except PersistenceError:
            self.blocked = True
            raise
        except (OSError, ValueError, TypeError) as exc:
            self.blocked = True
            raise PersistenceError('关键持久化受阻；禁止新增副作用') from exc
    return guarded


def atomic_json(path, data):
    path = Path(path)
    files.private_dir(str(path.parent))
    temporary = None
    try:
        fd, temporary = tempfile.mkstemp(prefix='.task-write-', dir=path.parent)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, ensure_ascii=False, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | getattr(os, 'O_DIRECTORY', 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except (OSError, TypeError, ValueError) as exc:
        raise PersistenceError('关键持久化失败: %s' % path) from exc
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)


def workspace_identity(root):
    """Read Git linkage without invoking Git, config, hooks or fsmonitor."""
    from .verification import _read_safe, _secure_open
    root = Path(root).resolve()
    def directory(path):
        fd = _secure_open(path)
        try:
            st = os.fstat(fd)
            if not stat.S_ISDIR(st.st_mode):
                raise ValueError('not directory')
            return dict(path=str(path), device=st.st_dev, inode=st.st_ino)
        finally:
            os.close(fd)
    answer = dict(root=directory(root), git=None, common=None)
    for parent in (root, *root.parents):
        marker = parent / '.git'
        try:
            st = marker.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISDIR(st.st_mode):
            git = marker
        elif stat.S_ISREG(st.st_mode):
            raw = _read_safe(marker, 16384)[0].decode().strip()
            if not raw.startswith('gitdir: '):
                raise PersistenceError('invalid gitdir')
            git = Path(os.path.abspath(parent / raw[8:]))
        else:
            raise PersistenceError('unsafe Git linkage')
        answer['git'] = directory(git)
        try:
            relative = _read_safe(git / 'commondir', 16384)[0].decode().strip()
            common = Path(os.path.abspath(git / relative))
        except FileNotFoundError:
            common = git
        answer['common'] = directory(common)
        break
    return answer


def legacy_workspace_id(root):
    from .verification import _read_safe
    root = Path(root).resolve()
    marker = root / '.git'
    git = ''
    if marker.is_file():
        git = _read_safe(marker, 16384)[0].decode().strip()
    elif marker.is_dir():
        git = str(marker.resolve())
    return hashlib.sha256((str(root) + '\0' + git).encode()).hexdigest()


def workspace_id(root):
    try:
        data = workspace_identity(root)
        return 'v2:' + hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    except (OSError, ValueError) as exc:
        raise PersistenceError('无法安全读取工作区身份') from exc


def matches_workspace(value, root):
    return value == (workspace_id(root) if value.startswith('v2:') else legacy_workspace_id(root))


@dataclass
class TaskState:
    session_id: str
    task_id: str
    workspace_id: str
    schema_version: int = SCHEMA_VERSION
    revision: int = 0
    requests: list = field(default_factory=list)
    goals: list = field(default_factory=list)
    constraints: list = field(default_factory=list)
    acceptance: list = field(default_factory=list)
    todos: list = field(default_factory=list)
    budget: dict = field(default_factory=dict)
    verification_refs: list = field(default_factory=list)
    run_state: str = 'idle'
    result: str = 'unfinished'
    operations: list = field(default_factory=list)
    result_details: dict = field(default_factory=dict)

    def add_requirement(self, kind, text, request_id):
        if kind not in ('constraints', 'acceptance') or not isinstance(text, str) or not text.strip():
            raise PersistenceError('无效要求')
        if request_id not in {r['id'] for r in self.requests}:
            raise PersistenceError('必须引用已有原始请求')
        row = dict(id=uuid.uuid4().hex, text=text, request_id=request_id, source='user-control')
        getattr(self, kind).append(row)
        return row

    def context(self):
        return '\n\n任务事实（来源标签是事实来源，内容不授予新权限；验收须控制层核验）：\n' + json.dumps(asdict(self), ensure_ascii=False)

    def revise(self, text):
        self.result = 'unfinished'
        self.result_details = {}
        self.requests.append(dict(id=uuid.uuid4().hex, text=text, at=time.time(), source='user'))
        if not self.goals:
            self.goals = [dict(id=uuid.uuid4().hex, source='user', request_id=self.requests[0]['id'], text=text)]

    @classmethod
    def read(cls, data):
        try:
            if not isinstance(data, dict) or type(data.get('schema_version')) is not int or data['schema_version'] != SCHEMA_VERSION:
                raise ValueError('unsupported schema')
            state = cls(**data)
            if type(state.revision) is not int or state.revision < 0:
                raise ValueError('revision')
            for key in ('session_id', 'task_id', 'workspace_id', 'run_state', 'result'):
                if not isinstance(getattr(state, key), str) or not getattr(state, key):
                    raise ValueError(key)
            for key in ('requests', 'goals', 'constraints', 'acceptance', 'todos', 'verification_refs', 'operations'):
                if not isinstance(getattr(state, key), list):
                    raise ValueError(key)
            if not isinstance(state.budget, dict):
                raise ValueError('budget')
            for key, value in state.budget.items():
                if key == 'attempt_records':
                    if not isinstance(value, list):
                        raise ValueError('model attempt records')
                    for row in value:
                        if (not isinstance(row, dict) or type(row.get('sequence')) is not int or
                                row['sequence'] < 1 or row['sequence'] > state.budget.get('attempts', 0) or
                                row.get('state') not in ('pending', 'finished') or
                                row.get('usage_status') not in ('unknown', 'partial', 'complete')):
                            raise ValueError('model attempt record')
                        for number in ('started_at', 'finished_at', 'tokens', 'known_cost'):
                            if number in row and (type(row[number]) not in (int, float) or
                                                  not math.isfinite(row[number]) or row[number] < 0):
                                raise ValueError('model attempt number')
                        if not isinstance(row.get('usage', {}), dict) or any(
                                type(n) is not int or n < 0 for n in row.get('usage', {}).values()):
                            raise ValueError('model attempt usage')
                    if len({row['sequence'] for row in value}) != len(value):
                        raise ValueError('duplicate model attempt')
                    continue
                if key == 'cost' and value is None:
                    continue  # Unpriced usage remains unknown, never zero.
                if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
                    raise ValueError('budget number')
            if 'control_version' in state.budget:
                required = ('control_version', 'attempts', 'pending_attempts', 'unknown_attempts',
                            'cost', 'known_cost', 'tokens', 'cost_limit', 'time_limit')
                if any(k not in state.budget for k in required) or state.budget['control_version'] != 1:
                    raise ValueError('unsupported run control')
                for key in ('control_version', 'attempts', 'pending_attempts', 'unknown_attempts'):
                    if type(state.budget[key]) is not int:
                        raise ValueError('run control counter')
                if state.budget['pending_attempts'] > state.budget['attempts'] or state.budget['unknown_attempts'] > state.budget['attempts'] + 1:
                    raise ValueError('run control attempt count')
            for todo in state.todos:
                if not isinstance(todo, dict) or not isinstance(todo.get('text'), str) or todo.get('status') not in ('pending', 'doing', 'done'):
                    raise ValueError('todo')
            for request in state.requests:
                if not isinstance(request, dict) or not isinstance(request.get('id'), str) or not isinstance(request.get('text'), str):
                    raise ValueError('request')
                if not request['id'] or not isinstance(request.get('source'), str) or type(request.get('at')) not in (int, float) or not math.isfinite(request['at']):
                    raise ValueError('request provenance')
            ids = [r['id'] for r in state.requests]
            if len(ids) != len(set(ids)):
                raise ValueError('duplicate request')
            for kind in ('goals', 'constraints', 'acceptance'):
                for row in getattr(state, kind):
                    if not isinstance(row, dict) or not isinstance(row.get('text'), str):
                        raise ValueError(kind)
                    # Legacy rows remain explicitly unbound until entered through control.
                    if 'id' in row and (not isinstance(row['id'], str) or row.get('request_id') not in ids):
                        raise ValueError('requirement reference')
            if any(not isinstance(r, str) for r in state.verification_refs):
                raise ValueError('verification reference')
            if state.result not in ('unfinished', 'completed', 'partial', 'unverifiable') or state.run_state not in (
                    'idle', 'running', 'interrupted', 'waiting_user', 'blocked', 'budget_stopped', 'deadline_stopped'):
                raise ValueError('state enum')
            details = state.result_details
            if not isinstance(details, dict):
                raise ValueError('result details')
            if details:
                if (set(details) != {'source', 'reason', 'at', 'request_id', 'acceptance', 'verification_refs'}
                        or details['source'] != 'user-control'
                        or not isinstance(details['reason'], str)
                        or type(details['at']) not in (int, float) or not math.isfinite(details['at'])
                        or details['request_id'] not in ids
                        or not isinstance(details['acceptance'], list)
                        or not isinstance(details['verification_refs'], list)
                        or any(not isinstance(r, str) for r in details['verification_refs'])):
                    raise ValueError('result provenance')
                for row in details['acceptance']:
                    if (not isinstance(row, dict) or set(row) != {'id', 'verification_id', 'status'}
                            or row['status'] not in ('verified', 'unverified')
                            or any(row[k] is not None and not isinstance(row[k], str)
                                   for k in ('id', 'verification_id'))):
                        raise ValueError('result acceptance snapshot')
            if state.result in ('partial', 'unverifiable') and (not details or not details['reason'].strip()):
                raise ValueError('result requires user explanation')
            operation_ids = [op.get('id') for op in state.operations if isinstance(op, dict)]
            if len(operation_ids) != len(set(operation_ids)):
                raise ValueError('duplicate operation')
            for sequence, operation in enumerate(state.operations, 1):
                if not isinstance(operation, dict) or operation.get('state') not in ('prepared', 'running', 'completed', 'failed', 'cancelled', 'unknown', 'resolved', 'serving', 'not_run'):
                    raise ValueError('operation')
                if type(operation.get('sequence')) is not int or operation['sequence'] != sequence:
                    raise ValueError('sequence')
                for key in ('id', 'name', 'source', 'cwd', 'parameter_digest'):
                    if not isinstance(operation.get(key), str) or not operation[key]:
                        raise ValueError('operation ' + key)
                if type(operation.get('started')) not in (float, int) or not math.isfinite(operation['started']):
                    raise ValueError('started')
                if 'local_path' in operation:
                    local_relative_path(operation['local_path'])
                if operation['state'] == 'serving' and operation.get('kind') != 'lsp-service':
                    raise ValueError('serving requires LSP service')
                if operation.get('kind') == 'lsp-service':
                    if operation.get('service_status') not in ('prepared', 'initializing', 'ready', 'stopped', 'unknown') or operation.get('lifecycle_only') is not True:
                        raise ValueError('LSP lifecycle state')
                if operation.get('kind') in ('background-job', 'lsp-service'):
                    import re
                    if not re.fullmatch('[0-9a-f]{32}', operation['id']):
                        raise ValueError('job operation identity')
                    if operation.get('kind') == 'background-job' and operation.get('output_ref') != operation['id'] + '.job/output':
                        raise ValueError('job output reference')
                    process = operation.get('process')
                    if process is not None:
                        if (not isinstance(process, dict) or set(process) != {'pid', 'boot', 'start'}
                                or type(process['pid']) is not int or process['pid'] <= 0
                                or not isinstance(process['boot'], str) or not process['boot']
                                or not isinstance(process['start'], str) or not process['start'].isdigit()):
                            raise ValueError('job process identity')
                    if operation['state'] in ('running', 'serving') and process is None:
                        raise ValueError('running without process identity')
                if operation['state'] == 'resolved':
                    resolution = operation.get('resolution')
                    if not isinstance(resolution, dict) or resolution.get('source') != 'user-control' or not isinstance(resolution.get('acknowledgement'), str) or not resolution['acknowledgement'].strip() or not isinstance(resolution.get('observation'), dict):
                        raise ValueError('resolution')
            return state
        except (TypeError, ValueError, KeyError) as exc:
            raise PersistenceError('任务格式损坏或版本不支持；保留原件') from exc


class TaskStore:
    """A lifetime session writer lock, plus a thread lock for parallel readers/tools.

    The journal is an atomic, checksummed snapshot of monotonically ordered operations.
    A session checkpoint can lag it; the sidecar always wins on restore.
    """
    def __init__(self, root, sid):
        from . import session
        if not isinstance(sid, str) or not session._ID_OK.fullmatch(sid) or sid == session.LEGACY:
            raise PersistenceError('无效 session id')
        self.root = Path(root)
        self.sid = sid
        self.directory = Path(session.folder(root)) / sid
        # Validate the parent and session directory before chmod/open follows links.
        from .verification import _secure_open
        parent = self.directory.parent
        files.private_dir(str(parent))
        parent_fd = _secure_open(parent)
        try:
            try:
                os.mkdir(sid, mode=0o700, dir_fd=parent_fd)
            except FileExistsError:
                pass
            fd = os.open(sid, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
            os.close(fd)
        except OSError as exc:
            raise PersistenceError('不安全的 session journal 目录') from exc
        finally:
            os.close(parent_fd)
        files.private_dir(str(self.directory))
        self._mutex = threading.RLock()
        self._lock = os.fdopen(os.open(self.directory / 'writer.lock',
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600), 'a+b')
        os.chmod(self.directory / 'writer.lock', 0o600)
        try:
            import fcntl
            fcntl.flock(self._lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (ImportError, OSError) as exc:
            self.close()
            raise PersistenceError('会话已有 writer 或平台不支持安全 writer 锁') from exc
        self.blocked = False
        self._seen = {}
        self._states = {}

    def close(self):
        if getattr(self, '_lock', None):
            self._lock.close()
            self._lock = None

    def __del__(self):
        self.close()

    def path(self, tid):
        from . import session
        if not isinstance(tid, str) or not session._ID_OK.fullmatch(tid):
            raise PersistenceError('无效 task id')
        return self.directory / (tid + '.task.json')

    @critical_write
    def save(self, state):
        with self._mutex:
            if self._lock is None:
                raise PersistenceError('writer 已关闭')
            if self.blocked:
                raise PersistenceError('任务持久化受阻；需要重新打开并核对')
            path = self.path(state.task_id)
            if path.exists():
                before = path.read_bytes()
                expected = self._seen.get(state.task_id)
                if json.loads(before)['payload'].get('revision', 0) != state.revision:
                    raise PersistenceError('陈旧任务修订；禁止覆盖')
                if expected is None or hashlib.sha256(before).hexdigest() != expected:
                    self.blocked = True
                    raise PersistenceError('陈旧 writer 或未加载任务；禁止覆盖')
            payload = asdict(state)
            payload['revision'] = state.revision + 1
            TaskState.read(payload)
            if state.session_id != self.sid or not matches_workspace(state.workspace_id, self.root):
                raise PersistenceError('任务身份不匹配')
            packed = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
            try:
                atomic_json(self.path(state.task_id), dict(schema_version=1, payload=payload,
                            sha256=hashlib.sha256(packed).hexdigest()))
                self._states[state.task_id] = state
                state.revision = payload['revision']
                self._seen[state.task_id] = hashlib.sha256(self.path(state.task_id).read_bytes()).hexdigest()
            except PersistenceError:
                self.blocked = True
                raise

    def load(self, tid):
        path = self.path(tid)
        try:
            from .verification import _read_safe
            raw = _read_safe(path, 64 * 1024 * 1024)[0]
            data = json.loads(raw)
            if type(data.get('schema_version')) is not int or data['schema_version'] != 1:
                raise ValueError('version')
            payload = data['payload']
            packed = json.dumps(payload, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()
            if hashlib.sha256(packed).hexdigest() != data['sha256']:
                raise ValueError('checksum')
            state = TaskState.read(payload)
            if (state.session_id, state.task_id) != (self.sid, tid) or not matches_workspace(state.workspace_id, self.root):
                raise ValueError('identity')
            for operation in state.operations:
                if operation['state'] in ('prepared', 'serving'):
                    operation['state'] = 'unknown'
            if state.run_state == 'running':
                state.run_state = 'interrupted'
            self._seen[tid] = hashlib.sha256(raw).hexdigest()
            return state
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            raise PersistenceError('任务恢复受阻，保留原件: %s' % path) from exc

    def pending(self):
        return [s.task_id for s in self._states.values()
                if any(o['state'] in ('prepared', 'running', 'unknown') for o in s.operations)]

    @critical_write
    def recover(self, fallback=None):
        """Validate every same-session journal before changing any original."""
        from .verification import _read_safe
        active = None
        path = self.directory / 'active.json'
        try:
            raw = _read_safe(path, 65536)[0]
        except FileNotFoundError:
            raw = None  # Pre-pointer versions and crashes before activation.
        try:
            if raw is not None:
                data = json.loads(raw)
                payload = data['payload']
                packed = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
                if (type(data.get('schema_version')) is not int or data['schema_version'] != 1
                        or hashlib.sha256(packed).hexdigest() != data['sha256']
                        or payload['session_id'] != self.sid
                        or not matches_workspace(payload['workspace_id'], self.root)):
                    raise ValueError('active pointer identity/version/checksum')
                active = payload['task_id']
                self.path(active)  # Validate before using as a filename.
            states = {}
            for item in sorted(self.directory.glob('*.task.json')):
                tid = item.name[:-len('.task.json')]
                states[tid] = self.load(tid)
            if active is not None and active not in states:
                raise ValueError('active task missing')
            if fallback and fallback not in states:
                raise ValueError('session task missing')
            self._states = states
            selected = active or fallback or next(iter(states), None)
            return states.get(selected)
        except (OSError, ValueError, KeyError, TypeError, AttributeError, PersistenceError) as exc:
            self.blocked = True
            raise PersistenceError('活动任务恢复受阻；保留全部原件') from exc

    def activate(self, state, recovery_selection=False):
        """Sidecar first, durable pointer second, prepared/effect strictly later."""
        with self._mutex:
            if self.blocked or self._lock is None:
                raise PersistenceError('活动任务持久化受阻')
            if not recovery_selection and any(tid != state.task_id for tid in self.pending()):
                raise PersistenceError('同 session 有未决任务；先选择核对: ' + ', '.join(self.pending()))
            if state.task_id not in self._seen:
                self.save(state)
            payload = dict(session_id=self.sid, task_id=state.task_id,
                           workspace_id=state.workspace_id)
            packed = json.dumps(payload, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()
            try:
                atomic_json(self.directory / 'active.json', dict(schema_version=1,
                    payload=payload, sha256=hashlib.sha256(packed).hexdigest()))
            except PersistenceError:
                self.blocked = True
                raise

    def prepare(self, state, record):
        with self._mutex:
            self.activate(state)
            if self.blocked or self.pending() or any(op['state'] in ('prepared', 'running', 'unknown') for op in state.operations):
                raise PersistenceError('存在未知副作用；先核对结果，禁止新增副作用')
            # Parameters and environment are deliberately omitted: commands can embed secrets.
            op = dict(id=record['id'], call_id=record['call_id'], name=record['name'],
                      source=record['source'], cwd=record['cwd'], state='prepared',
                      sequence=len(state.operations) + 1, started=record['started'],
                      parameter_digest=hashlib.sha256(json.dumps(record.get('args', {}),
                          sort_keys=True, ensure_ascii=False).encode()).hexdigest())
            op['authorization'] = dict(source=record['source'], fact=record.get('authorization', 'caller-boundary; not a reusable grant'), call_id=record.get('call_id'),
                scope='exact-call', parameter_digest=op['parameter_digest'], reusable=False)
            path = record.get('args', {}).get('path')
            if isinstance(path, str):
                candidate = Path(os.path.abspath(Path(record['cwd']) / path))
                if self.root.resolve() in candidate.parents:
                    op['local_path'] = str(candidate.relative_to(self.root.resolve()))
            op['before'] = self.observe(op)
            state.operations.append(op)
            self.save(state)
            return op

    def prepare_service(self, state, active, argv):
        import uuid
        with self._mutex:
            self.activate(state)
            if self.blocked or any(o['state'] in ('prepared', 'running', 'unknown')
                    and o is not active for o in state.operations):
                raise PersistenceError('LSP service has unresolved operations')
            op = dict(id=uuid.uuid4().hex, call_id=active.get('call_id') if active else None,
                name='lsp-service', kind='lsp-service', source='symbol-lifecycle',
                cwd=str(self.root), state='prepared', sequence=len(state.operations)+1,
                started=time.time(), parameter_digest=hashlib.sha256(json.dumps(argv).encode()).hexdigest(),
                service_status='prepared', lifecycle_only=True,
                parent_operation_id=active['id'] if active else None,
                authorization=active.get('authorization') if active else 'caller-boundary; not a reusable grant')
            state.operations.append(op)
            self.save(state)
            return op

    def finish(self, state, op, record):
        with self._mutex:
            op.update(state='unknown' if record['state'] == 'cancelled' else record['state'],
                      ended=record['ended'], exit_code=record.get('exit_code'),
                      execution_started=record.get('execution_started'),
                      stop_reason=record.get('stop_reason', ''),
                      evidence_error=record.get('evidence_error', ''))
            try:
                self.save(state)
            except PersistenceError:
                op['state'] = 'unknown'
                raise

    def observe(self, op):
        from .verification import fingerprint
        try:
            observation = fingerprint(self.root, self.root, {})
        except Exception:
            observation = dict(digest=None, reason='observation unavailable')
        local = dict(status='not-applicable')
        if 'local_path' in op:
            relative = local_relative_path(op['local_path'])
            target = self.root / relative
            if self.root.resolve() not in target.resolve().parents:
                raise ValueError('local path escapes workspace')
            from .verification import _read_safe
            try:
                raw, _ = _read_safe(target, 16 * 1024 * 1024)
                local = dict(status='present', sha256=hashlib.sha256(raw).hexdigest())
            except FileNotFoundError:
                local = dict(status='absent; not external absence proof')
            except (OSError, ValueError):
                local = dict(status='unknown')
        from .jobs import identity
        process = op.get('process')
        process_observation = ('same-identity-alive' if process and identity(process['pid']) == process else
                               'absent-or-different; not success') if op.get('kind') == 'lsp-service' else 'unknown; PID alone is not process identity'
        return dict(at=time.time(), workspace=workspace_id(self.root), files_git=observation, local=local,
                    external='unknown; local observations never prove external absence',
                    process=process_observation)

    def reconcile(self, state):
        for op in state.operations:
            if op['state'] in ('unknown', 'prepared', 'running') and op.get('kind') != 'background-job':
                op['state'] = 'unknown'
                op['observation'] = self.observe(op)
        self.save(state)

    def resolve(self, state, operation_id, acknowledgement):
        if not isinstance(acknowledgement, str) or not acknowledgement.strip():
            raise PersistenceError('必须提供用户核对依据；不得包含秘密')
        op = next((o for o in state.operations if o['id'] == operation_id), None)
        if op is None or op['state'] != 'unknown':
            raise PersistenceError('不是未知操作')
        if op.get('kind') in ('background-job', 'lsp-service'):
            from .jobs import identity
            process = op.get('process')
            if process and identity(process['pid']) == process:
                raise PersistenceError('仍在运行的服务/job 不能人工 resolve；先关闭或等待终态')
        observation = self.observe(op)
        op.update(state='resolved', resolution=dict(source='user-control',
            acknowledgement=acknowledgement, at=time.time(), observation=observation,
            conclusion='acknowledged-unknown; no success or absence proof; no replay authorization'))
        try:
            self.save(state)
        except PersistenceError:
            op['state'] = 'unknown'
            raise
