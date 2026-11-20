"""Execution evidence and conservative, bounded workspace content checks.

No output parser grants a pass. Fingerprints are observations, not snapshots of
external services, ignored dependencies or transient external write/restore cycles.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import tempfile
import time
import uuid

from . import session

MAX_FILES = 20_000
MAX_BYTES = 256 * 1024 * 1024
MAX_SECONDS = 5.0


def storage():
    return Path(session.DIR).parent / 'verification'


def _identity(st):
    return tuple(getattr(st, k) for k in
                 ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_mtime_ns', 'st_ctime_ns'))


def _secure_open(path):
    if os.name == "nt":
        from .windows_storage import secure_open
        return secure_open(path)
    # Walk from / using directory descriptors: no ancestor may be a symlink.
    if (os.name != 'posix' or not all(hasattr(os, k) for k in
            ('O_NOFOLLOW', 'O_NONBLOCK', 'O_DIRECTORY')) or
            os.stat not in os.supports_dir_fd):
        raise ValueError('safe descriptor traversal unavailable on this platform')
    parts = Path(os.path.abspath(path)).parts
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in parts[1:-1]:
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = nxt
        return os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
    finally:
        os.close(fd)


def _read_safe(path, limit, check=lambda: None):
    if os.name == "nt":
        from .windows_storage import read_safe
        return read_safe(path, limit, check)
    fd = _secure_open(path)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError('special file not covered')
        raw = bytearray()
        while True:
            check()
            chunk = os.read(fd, min(65536, max(1, limit + 1 - len(raw))))
            if not chunk:
                break
            raw.extend(chunk)
            if len(raw) > limit:
                raise ValueError('byte budget exceeded')
        if _identity(before) != _identity(os.fstat(fd)):
            raise ValueError('file changed while reading')
        other = _secure_open(path)
        try:
            if _identity(before) != _identity(os.fstat(other)):
                raise ValueError('file or parent replaced while reading')
        finally:
            os.close(other)
        return bytes(raw), before
    finally:
        os.close(fd)


def _git(root, args, deadline):
    # Never execute a project command, hook, pager or external diff driver.
    with tempfile.TemporaryFile() as out:
        done = subprocess.run(['git', '--no-optional-locks', '-c', 'core.fsmonitor=false',
                               '-c', 'core.hooksPath=/dev/null', '-c', 'core.untrackedCache=false', '-C', str(root), *args],
                              stdout=out, stderr=subprocess.DEVNULL,
                              timeout=max(.001, deadline - time.monotonic()))
        if out.tell() > 8 * 1024 * 1024:
            raise ValueError('git inventory exceeds budget')
        out.seek(0)
        return done.returncode, out.read()


def fingerprint(root, cwd, config, *, max_files=MAX_FILES, max_bytes=MAX_BYTES,
                max_seconds=MAX_SECONDS):
    deadline = time.monotonic() + max_seconds
    root, cwd = Path(root).resolve(), Path(cwd).resolve()
    total = 0
    try:
        probe = _secure_open(root)
        os.close(probe)
        for owned in (storage().resolve(), Path(session.DIR).resolve()):
            if owned == root or root in owned.parents:
                raise ValueError('state/log storage overlaps workspace; move XDG_STATE_HOME outside workspace')
        def inventory():
            code, top = _git(root, ['rev-parse', '--show-toplevel'], deadline)
            meta = []
            if code == 0:
                if Path(os.fsdecode(top).strip()).resolve() != root:
                    raise ValueError('workspace is not git root')
                code, listing = _git(root, ['ls-files', '-z', '--cached', '--others', '--exclude-standard'], deadline)
                if code:
                    raise ValueError('git inventory failed')
                code, index = _git(root, ['ls-files', '--stage', '-z'], deadline)
                if code or any(x.startswith(b'160000 ') for x in index.split(b'\0')):
                    raise ValueError('submodule or unreadable index')
                _, head = _git(root, ['rev-parse', 'HEAD'], deadline)
                meta = [head.hex(), index.hex()]
                for flag in ('--absolute-git-dir', '--git-common-dir'):
                    code, location = _git(root, ['rev-parse', flag], deadline)
                    if code:
                        raise ValueError('git directory identity unknown')
                    directory = Path(os.fsdecode(location).strip())
                    if not directory.is_absolute():
                        directory = root / directory
                    meta.append(str(directory.resolve()))
                    for relative in ('config', 'config.worktree', 'info/exclude'):
                        try:
                            raw, _ = _read_safe(directory / relative, 1024 * 1024, check)
                        except FileNotFoundError:
                            raw = b''
                        meta.append(hashlib.sha256(raw).hexdigest())
                # Include ignored .gitignore sources too: their comments/config can
                # change without changing the visible source inventory.
                code, ignores = _git(root, ['ls-files', '-z', '--cached', '--others',
                                             '--ignored', '--exclude-standard', '--',
                                             '.gitignore', '**/.gitignore'], deadline)
                if code:
                    raise ValueError('ignore source inventory unavailable')
                ignore_paths = {'.gitignore'} | {os.fsdecode(x) for x in ignores.split(b'\0') if x}
                ignore_paths.update(str(Path(name).parent / '.gitignore') for name in
                                    (os.fsdecode(x) for x in listing.split(b'\0') if x))
                if len(ignore_paths) > max_files:
                    raise ValueError('ignore source budget exceeded')
                for name in sorted(ignore_paths):
                    if Path(name).is_absolute() or '..' in Path(name).parts:
                        raise ValueError('unsafe ignore path')
                    try:
                        raw, _ = _read_safe(root / name, 1024 * 1024, check)
                    except FileNotFoundError:
                        raw = b''
                    meta.append([name, hashlib.sha256(raw).hexdigest()])
                # Includes and custom excludes may reference arbitrary external paths.
                # Until safely enumerated, refuse a current conclusion even when the
                # visible file list happens to stay unchanged. Never expose values.
                code, effective = _git(root, ['config', '--no-includes', '--null', '--list'], deadline)
                if code:
                    raise ValueError('effective git configuration unavailable')
                keys = [row.split(b'\n', 1)[0].lower() for row in effective.split(b'\0')]
                if any(k == b'core.excludesfile' or k.startswith((b'include.', b'includeif.')) for k in keys):
                    raise ValueError('external excludes/include configuration not safely covered')
                meta.append(hashlib.sha256(effective).hexdigest())
                default_ignore = Path(os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config') / 'git/ignore'
                try:
                    raw, _ = _read_safe(default_ignore, 1024 * 1024, check)
                except FileNotFoundError:
                    raw = b''
                meta.append(hashlib.sha256(raw).hexdigest())
                paths = sorted(set(os.fsdecode(x) for x in listing.split(b'\0') if x))
            else:
                paths = []
                def walk(folder):
                    fd = _secure_open(folder)
                    try:
                        if not stat.S_ISDIR(os.fstat(fd).st_mode):
                            raise ValueError('directory changed')
                        for name in sorted(os.listdir(fd)):
                            check()
                            if name == '.git':
                                continue
                            p = folder / name
                            st = os.stat(name, dir_fd=fd, follow_symlinks=False)
                            if stat.S_ISDIR(st.st_mode):
                                walk(p)
                            else:
                                paths.append(str(p.relative_to(root)))
                                if len(paths) > max_files:
                                    raise ValueError('file budget exceeded')
                    finally:
                        os.close(fd)
                walk(root)
            if len(paths) > max_files:
                raise ValueError('file budget exceeded')
            return paths, meta

        def check():
            if time.monotonic() > deadline:
                raise ValueError('time budget exceeded')

        def scan(paths):
            nonlocal total
            h = hashlib.sha256()
            scan_bytes = 0
            for name in paths:
                check()
                p = root / name
                h.update(os.fsencode(name) + b'\0')
                if Path(name).is_absolute() or '..' in Path(name).parts:
                    raise ValueError('unsafe inventory path')
                try:
                    raw, before = _read_safe(p, max_bytes - scan_bytes, check)
                except FileNotFoundError:
                    h.update(b'deleted')
                    continue
                h.update(str(stat.S_IFMT(before.st_mode)).encode())
                h.update(str(before.st_mode & 0o111).encode())
                total += len(raw)
                scan_bytes += len(raw)
                h.update(raw)
            return h.hexdigest()

        # Two content reads catch changes to an earlier file during a scan.
        paths, meta = inventory()
        first = scan(paths)
        paths2, meta2 = inventory()
        second = scan(paths2)
        if (paths, meta, first) != (paths2, meta2, second):
            raise ValueError('workspace changed while scanning')
        check()
        digest = hashlib.sha256(json.dumps([str(root), str(cwd), config, meta, first],
                                           sort_keys=True).encode()).hexdigest()
        return {'digest': digest, 'reason': '', 'files': len(paths), 'bytes_read': total}
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        return {'digest': None, 'reason': str(exc)}


class Ledger:
    def __init__(self, emit=None):
        self.emit = emit
        self.records = []
        self.epoch = 0

    def invalidate(self):
        self.epoch += 1
        for r in self.records:
            r['validity'] = 'stale'
            r['reason'] = 'known potential write or configuration change'
        self._invalidated('known potential write or configuration change')

    def _invalidated(self, reason, records=None):
        if self.emit is not None:
            self.emit('verification_invalidated', epoch=self.epoch,
                      verification_refs=[r.get('verification_id') for r in (self.records if records is None else records)],
                      reason=reason)

    def begin(self, root, cwd, config, category, session_id, task_id):
        self.invalidate()  # verification commands themselves may write
        return dict(schema_version=1, verification_id=uuid.uuid4().hex,
                    session_id=session_id, task_id=task_id, run_id=uuid.uuid4().hex,
                    command=config['command'], cwd=str(cwd), workspace=str(root),
                    source=config['source'], category=category, config=config,
                    started_at=time.time(), started_monotonic=time.monotonic(),
                    epoch=self.epoch, before=fingerprint(root, cwd, config))

    def finish(self, r, outcome, root, cwd, config, busy=False):
        r.update(ended_at=time.time(), duration=time.monotonic()-r.pop('started_monotonic'),
                 exit_code=outcome.code if getattr(outcome, "execution_started", False) else None,
                 execution_started=getattr(outcome, "execution_started", False), stop_reason=getattr(outcome, "stop_reason", ""),
                 timed_out=outcome.timed_out,
                 cancelled=outcome.cancelled, log=outcome.log,
                 log_sha256=outcome.log_sha256, environment_error=outcome.environment_error, evidence_error=getattr(outcome, 'evidence_error', ''),
                 after=fingerprint(root, cwd, config))
        r['rejected'] = getattr(outcome, 'rejected', '')
        r['execution'] = ('not_run' if r['rejected'] else
                          'environment_blocked' if outcome.environment_error else
                          'unknown' if outcome.cancelled or outcome.timed_out else
                          'passed' if outcome.code == 0 else 'failed')
        r['validity'], r['reason'] = 'current', ''
        if outcome.cancelled or outcome.timed_out:
            r['validity'], r['reason'] = 'unknown', '命令已启动后停止；不能证明无副作用或验证通过'
        elif getattr(outcome, 'evidence_error', ''):
            r['validity'], r['reason'] = 'unknown', '命令已执行，持久日志缺失；验证证据不可用'
        elif not r['before']['digest'] or not r['after']['digest'] or not outcome.log:
            r['validity'], r['reason'] = 'unknown', 'incomplete fingerprint or persistent log'
        elif r['before']['digest'] != r['after']['digest'] or r['epoch'] != self.epoch:
            r['validity'], r['reason'] = 'stale', 'changed during verification'
        if busy:
            r['validity'], r['reason'] = 'unknown', 'background command may still write'
        self.records.append(r)
        return r

    def current(self, root, cwd, config, busy=False, owner=None):
        if not self.records:
            return None
        r = self.records[-1]
        if owner is not None and (r.get('session_id'), r.get('task_id')) != owner:
            return None
        return self._recheck(r, root, cwd, config, busy)

    def reference(self, verification_id, root, cwd, config, busy=False, owner=None):
        """Consume a historical reference without promoting it or changing ownership."""
        r = next((r for r in self.records if r.get('verification_id') == verification_id), None)
        if r is None:
            return dict(verification_id=verification_id, source_kind='execution_evidence',
                        validity='unknown', reason='missing Ledger record')
        owned = owner is None or (r.get('session_id'), r.get('task_id')) == owner
        if owned:
            self._recheck(r, root, cwd, config, busy)
        row = {k: r.get(k) for k in ('verification_id', 'session_id', 'task_id',
               'category', 'execution', 'exit_code', 'validity', 'reason',
               'source', 'workspace', 'run_id')}
        row['source_kind'] = 'execution_evidence'
        if not owned:
            row.update(validity='unknown', reason='different session/task owner')
        return row

    def _recheck(self, r, root, cwd, config, busy):
        previous = r['validity']
        now = fingerprint(root, cwd, config)
        if r['validity'] == 'current':
            if busy or not now['digest']:
                r['validity'], r['reason'] = 'unknown', 'background activity or scan unknown'
            elif now['digest'] != r['after']['digest'] or r['epoch'] != self.epoch:
                r['validity'], r['reason'] = 'stale', 'workspace/cwd/configuration changed'
            try:
                deadline = time.monotonic() + MAX_SECONDS
                def check_log():
                    if time.monotonic() > deadline:
                        raise ValueError('log check budget exceeded')
                raw, _ = _read_safe(r['log'], MAX_BYTES, check_log)
                if hashlib.sha256(raw).hexdigest() != r['log_sha256']:
                    raise ValueError('log changed')
            except (OSError, ValueError, TypeError):
                r['validity'], r['reason'] = 'unknown', 'persistent evidence missing or changed'
        if previous == 'current' and r['validity'] != previous:
            self._invalidated(r['reason'], [r])
        return r

    def export(self):
        return {'schema_version': 1, 'epoch': self.epoch, 'records': self.records}

    def restore(self, data):
        self.records = []
        self.epoch += 1
        if not isinstance(data, dict) or data.get('schema_version') != 1:
            return
        rows = data.get('records')
        if not isinstance(rows, list):
            return
        # Restored records remain historical evidence; never resurrect old passes.
        self.records = [dict(r, validity='stale', reason='restored; rerun required')
                        for r in rows if isinstance(r, dict) and
                        all(k in r for k in ('execution', 'category', 'after', 'epoch', 'command', 'log', 'log_sha256'))
                        and isinstance(r['execution'], str)
                        and r['execution'] in ('passed', 'failed', 'not_run', 'environment_blocked', 'unknown')
                        and isinstance(r['category'], str)
                        and isinstance(r['epoch'], int)]
        self.epoch = max((r['epoch'] for r in self.records if isinstance(r['epoch'], int)), default=0) + 1
