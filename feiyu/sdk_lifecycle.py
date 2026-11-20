"""Linux-only direct SDK child ownership, independent of the application parent."""
import json
import os
import select
import signal
import stat
import time
import uuid
from pathlib import Path

SLOTS = 128
LIMIT = 4096


def record(fd, value):
    raw = json.dumps(value, sort_keys=True).encode()
    if len(raw) > LIMIT:
        raise ValueError('SDK lifecycle receipt too large')
    os.lseek(fd, 0, os.SEEK_SET)
    os.ftruncate(fd, 0)
    while raw:
        raw = raw[os.write(fd, raw):]
    os.fsync(fd)


def reserve():
    import fcntl
    # Descriptor traversal also rejects symlink ancestors before creating anything.
    path = Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'feiyu/sdk-lifecycle'
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in Path(os.path.abspath(path)).parts[1:]:
            try:
                os.mkdir(part, 0o700, dir_fd=directory)
            except FileExistsError:
                pass
            nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
            os.close(directory)
            directory = nxt
        st = os.fstat(directory)
        if st.st_uid != os.getuid() or stat.S_IMODE(st.st_mode) != 0o700:
            raise OSError('unsafe SDK lifecycle directory')
        token = uuid.uuid4().hex
        start = int(token[:8], 16) % SLOTS
        for offset in range(SLOTS):
            slot = (start + offset) % SLOTS
            fd = os.open(str(slot), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
                         0o600, dir_fd=directory)
            selected = False
            try:
                st = os.fstat(fd)
                if (not stat.S_ISREG(st.st_mode) or st.st_uid != os.getuid() or
                        stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1):
                    raise OSError('unsafe SDK lifecycle slot')
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                record(fd, dict(v=1, token=token, state='prepared', parent=os.getpid()))
                selected = True
                return fd, dict(token=token, slot=slot, directory=str(path))
            finally:
                if not selected:
                    os.close(fd)
        raise OSError('SDK lifecycle receipt slots busy')
    finally:
        os.close(directory)


def read_receipt(fd, token):
    raw = os.pread(fd, LIMIT + 1, 0)
    if len(raw) > LIMIT:
        raise ValueError('oversized SDK lifecycle receipt')
    value = json.loads(raw)
    if (value.get('v') != 1 or value.get('token') != token or
            value.get('state') != 'reaped' or value.get('source') != 'sdk-supervisor'):
        raise ValueError('SDK lifecycle cleanup unconfirmed')
    return value


def supervise(control_fd, receipt_fd, token, parent):
    # This fresh exec has no application threads. Fork before SDK imports.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    pid = os.fork()
    if pid == 0:
        os.close(control_fd)
        os.close(receipt_fd)
        from .sdk_worker import worker_main
        os._exit(worker_main())
    os.close(0)
    os.close(1)
    base = dict(v=1, token=token, source='sdk-supervisor', parent=parent,
                supervisor=os.getpid(), worker=pid)
    reason = 'exited'
    reaped = False
    try:
        record(receipt_fd, dict(base, state='running'))
        while True:
            child, status = os.waitpid(pid, os.WNOHANG)
            if child:
                reaped = True
                break
            ready, _, _ = select.select([control_fd], [], [], .02)
            if ready and os.read(control_fd, 1) == b'':
                reason = 'owner_pipe_closed'
                # pid remains our unreaped child throughout this signal/wait.
                os.kill(pid, signal.SIGKILL)
                end = time.monotonic() + 2
                while True:
                    child, status = os.waitpid(pid, os.WNOHANG)
                    if child:
                        reaped = True
                        break
                    if time.monotonic() >= end:
                        return 3
                    time.sleep(.02)
                break
        record(receipt_fd, dict(base, state='reaped', reason=reason,
                               wait_status=status, finished_at=time.time()))
        return 0
    except BaseException:
        # Receipt failure must still stop the owned child, without claiming success.
        if not reaped:
            try:
                os.kill(pid, signal.SIGKILL)
                end = time.monotonic() + 2
                while time.monotonic() < end:
                    if os.waitpid(pid, os.WNOHANG)[0]:
                        break
                    time.sleep(.02)
            except (ProcessLookupError, ChildProcessError):
                pass
        return 3
    finally:
        os.close(control_fd)
        os.close(receipt_fd)
