"""后台跑的 bash 命令 构建、dev server、跑一整套测试不该把整轮 turn 卡住 """

from __future__ import annotations

import hashlib
import stat
import os
import signal
import threading
import time

# Bound each output read; persistent logs are retained without automatic pruning.
MAX_CHARS = 200_000


class Jobs:
    def __init__(self) -> None:
        self._items: dict[int, DurableJob] = {}
        self._next = 1

    def get(self, jid) -> DurableJob | None:
        try:
            return self._items.get(int(jid))
        except (TypeError, ValueError):
            return None

    def all(self) -> list[DurableJob]:
        return [self._items[k] for k in sorted(self._items)]

    def running(self) -> list[DurableJob]:
        return [j for j in self.all() if j.running]

    def finished_since(self) -> list[DurableJob]:
        """上次问过之后新结束的 只报一次，每轮都提醒的话它会被这条消息带跑偏 """
        fresh = [j for j in self.all() if not j.running and not j.reported]
        for job in fresh:
            job.reported = True
        return fresh

    def kill_all(self) -> int:
        """退出前收尾 留着的话用户关掉 feiyu 之后那些进程还在跑 """
        count, error = 0, None
        for job in self.all():
            try:
                count += bool(job.kill())
            except Exception as exc:
                error = error or exc
        if error:
            raise error
        return count


def identity(pid):
    """A PID is never sufficient, including on unsupported platforms."""
    from pathlib import Path
    import sys
    if sys.platform != 'linux':
        return None
    try:
        boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        fields = Path('/proc/%d/stat' % pid).read_text().rsplit(')', 1)[1].split()
        if fields[0] == 'Z':
            return None
        return dict(pid=pid, boot=boot, start=fields[19])
    except (OSError, ValueError, IndexError):
        return None


# Some Python 3.10 builds omit the Linux wrappers despite a capable libc/kernel.
# Use libc's named APIs, never guessed architecture-specific syscall numbers.
_libc = None
try:
    import ctypes
    import sys
    if sys.platform == 'linux':
        candidate = ctypes.CDLL(None, use_errno=True)
        candidate.pidfd_open.argtypes = [ctypes.c_int, ctypes.c_uint]
        candidate.pidfd_open.restype = ctypes.c_int
        candidate.pidfd_send_signal.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p, ctypes.c_uint]
        candidate.pidfd_send_signal.restype = ctypes.c_int
        _libc = candidate
except (AttributeError, OSError):
    pass


def pidfd_supported():
    if not ((hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal')) or _libc is not None):
        return False
    try:
        fd = _pidfd_open(os.getpid())
        try:
            if hasattr(signal, 'pidfd_send_signal'):
                signal.pidfd_send_signal(fd, 0)
            elif _libc.pidfd_send_signal(fd, 0, None, 0) < 0:
                return False
            return True
        finally:
            os.close(fd)
    except OSError:
        return False


def _pidfd_open(pid):
    if hasattr(os, 'pidfd_open'):
        return os.pidfd_open(pid)
    if _libc is None:
        raise OSError('pidfd unavailable')
    fd = _libc.pidfd_open(pid, 0)
    if fd < 0:
        raise OSError(ctypes.get_errno(), 'pidfd_open')
    return fd


def _pidfd_send(fd):
    if hasattr(signal, 'pidfd_send_signal'):
        signal.pidfd_send_signal(fd, signal.SIGTERM)
    elif _libc is None or _libc.pidfd_send_signal(fd, signal.SIGTERM, None, 0) < 0:
        raise OSError(ctypes.get_errno(), 'pidfd_send_signal')


def signal_identity(expected):
    """Open first, then verify; pidfd pins the target across validation/signal."""
    if not expected or not pidfd_supported():
        return False
    try:
        fd = _pidfd_open(expected['pid'])
        try:
            if identity(expected['pid']) != expected:
                return False
            _pidfd_send(fd)
            return True
        finally:
            os.close(fd)
    except (OSError, KeyError, TypeError):
        return False


def validate_output(fd, receipt):
    from .verification import _identity, MAX_BYTES, MAX_SECONDS
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode):
        raise ValueError('invalid output')
    expected = receipt.get('output_size')
    digest = receipt.get('output_sha256')
    if (type(expected) is not int or expected < 0 or expected > MAX_BYTES or
            before.st_size != expected or not isinstance(digest, str) or len(digest) != 64):
        raise ValueError('output evidence missing or size changed')
    deadline = time.monotonic() + MAX_SECONDS
    h = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    size = 0
    while True:
        if time.monotonic() > deadline:
            raise ValueError('output evidence check timed out')
        chunk = os.read(fd, 65536)
        if not chunk:
            break
        size += len(chunk)
        if size > expected:
            raise ValueError('output grew')
        h.update(chunk)
    if size != expected or h.hexdigest() != digest or _identity(before) != _identity(os.fstat(fd)):
        raise ValueError('output evidence changed')
    return before


class DurableJob:
    def __init__(self, jid, store, state, op, command='[recovered job]', proc=None, control=None):
        self.id, self.store, self.state, self.op = jid, store, state, op
        self.command, self.proc, self.control = command, proc, control
        self.reported = False
        self.offset = 0
        self.error = None
        self.sent_deadline = None
        self.lock = threading.RLock()
        self.directory = store.directory / (op['id'] + '.job')

    def refresh(self):
        import json
        from .verification import _read_safe
        from .taskstate import PersistenceError
        with self.lock, self.store._mutex:
            if self.op['state'] == 'resolved' or self.error is not None:
                return
            previous = dict(self.op)
            receipt_found = False
            try:
                raw = _read_safe(self.directory / 'receipt.json', 65536)[0]
                receipt_found = True
                receipt = json.loads(raw)
                if (set(receipt) != {'operation', 'state', 'exit_code', 'reason', 'ended', 'output_size', 'output_sha256'} or
                        receipt['operation'] != self.op['id'] or
                        receipt['state'] not in ('completed', 'failed', 'cancelled') or
                        type(receipt['exit_code']) is not int):
                    raise ValueError('invalid job receipt')
                # Missing output never becomes successful execution evidence.
                from .verification import _secure_open
                fd = _secure_open(self.directory / 'output')
                try:
                    validate_output(fd, receipt)
                finally:
                    os.close(fd)
                self.op.update(receipt)
                self.op['output_ref'] = self.op['id'] + '.job/output'
            except (OSError, ValueError, KeyError, TypeError):
                self.op['state'] = ('running' if not receipt_found and not self.op.get('ended') and identity(self.op.get('process', {}).get('pid', -1))
                                    == self.op.get('process') and self.op.get('process') else 'unknown')
            if self.op != previous:
                try:
                    self.store.save(self.state)
                except PersistenceError as exc:
                    self.op['state'] = 'unknown'
                    self.error = exc
                    # Cleanup is independent of the failed journal writer.
                    if self.proc is not None:
                        signal_identity(self.op.get('process'))
            if self.proc is not None:
                self.proc.poll()

    @property
    def running(self):
        self.refresh()
        return self.op['state'] == 'running'

    @property
    def code(self):
        self.refresh()
        return self.op.get('exit_code') if self.op['state'] in ('completed', 'failed', 'cancelled') else None

    def status(self):
        self.refresh()
        if self.error:
            raise self.error
        if self.op['state'] == 'running':
            return '运行中'
        if self.op['state'] == 'unknown':
            return 'unknown（缺少可靠终态证据）'
        return '已结束，退出码 %s · %s' % (self.code, self.op['state'])

    def take(self):
        if self.error:
            raise self.error
        from .verification import _secure_open, _identity
        with self.lock:
            self.refresh()
            if self.error:
                raise self.error
            if self.op['state'] not in ('running', 'completed', 'failed', 'cancelled'):
                return '', False
            try:
                fd = _secure_open(self.directory / 'output')
                with os.fdopen(fd, 'rb') as stream:
                    before = os.fstat(fd)
                    if not stat.S_ISREG(before.st_mode):
                        raise ValueError('invalid output')
                    terminal = self.op['state'] != 'running'
                    if terminal:
                        before = validate_output(fd, self.op)
                    start = max(self.offset, before.st_size - MAX_CHARS)
                    stream.seek(start)
                    raw = stream.read(MAX_CHARS)
                    other = _secure_open(self.directory / 'output')
                    try:
                        if (os.fstat(other).st_ino, os.fstat(other).st_dev) != (before.st_ino, before.st_dev):
                            raise ValueError('output path replaced')
                    finally:
                        os.close(other)
                    if terminal and _identity(before) != _identity(os.fstat(fd)):
                        raise ValueError('output changed during read')
                    dropped = start > self.offset
                    self.offset = stream.tell()
                return raw.decode('utf-8', 'replace'), dropped
            except (OSError, ValueError):
                self.op['state'] = 'unknown'
                self.store.save(self.state)
                return '', False

    def kill(self):
        self.refresh()
        if self.op['state'] in ('completed', 'failed', 'cancelled'):
            return False
        if not signal_identity(self.op.get('process')):
            self.refresh()
            if self.error:
                raise self.error
            if self.op['state'] in ('completed', 'failed', 'cancelled'):
                return False
            from .taskstate import PersistenceError
            raise PersistenceError('job identity unknown; refused signal')
        end = time.monotonic() + 5
        while time.monotonic() < end:
            self.refresh()
            if self.op['state'] in ('completed', 'failed', 'cancelled'):
                break
            if identity(self.op.get('process', {}).get('pid', -1)) != self.op.get('process'):
                break
            time.sleep(.02)
        if self.error:
            raise self.error
        if self.op['state'] not in ('completed', 'failed', 'cancelled'):
            from .taskstate import PersistenceError
            raise PersistenceError('job stopped without durable terminal evidence; unknown')
        return True

    def wait(self, control=None):
        from .runcontrol import RunStopped
        try:
            while self.running:
                if self.error:
                    raise self.error
                if control:
                    control.wait(.05)
                else:
                    time.sleep(.05)
            if self.error:
                raise self.error
        except (KeyboardInterrupt, RunStopped):
            self.kill()
            raise

    def notify(self, deadline=None, reason=''):
        import json
        if self.proc is None or self.proc.stdin.closed:
            return
        if not reason and (not deadline or self.sent_deadline and deadline >= self.sent_deadline):
            return
        payload = (json.dumps(dict(deadline=deadline, reason=reason)) + '\n').encode()
        try:
            if os.write(self.proc.stdin.fileno(), payload) != len(payload):
                raise OSError('incomplete job control message')
        except BrokenPipeError:
            # A supervisor that has already finished owns its original receipt.
            if identity(self.op.get('process', {}).get('pid', -1)) == self.op.get('process'):
                raise
            return
        self.sent_deadline = deadline or self.sent_deadline

    def monitor(self):
        try:
            while self.running:
                if self.control:
                    deadline, reason = self.control.background_limits()
                    self.notify(deadline, reason)
                    if reason:
                        # Supervisor owns cleanup and the durable real-exit receipt.
                        break
                time.sleep(.05)
            while self.running:
                time.sleep(.05)
            if self.error:
                raise self.error
        except BaseException as exc:
            self.error = self.error or exc
            self.op['state'] = 'unknown'
            if self.control:
                self.control.background_error = self.error
            try:
                self.notify(reason='persistence_error')
            except BaseException:
                signal_identity(self.op.get('process'))
        finally:
            if self.proc is not None and not self.proc.stdin.closed:
                self.proc.stdin.close()


def restore_jobs(pool, store):
    """Only attach observations. No launch, replay, or recovery-time signals."""
    for state in store._states.values():
        for op in state.operations:
            if op.get('kind') != 'background-job':
                continue
            if any(isinstance(j, DurableJob) and j.op is op for j in pool.all()):
                continue
            job = DurableJob(pool._next, store, state, op)
            pool._next += 1
            pool._items[job.id] = job
            job.refresh()
