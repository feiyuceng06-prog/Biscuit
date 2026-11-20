"""Foreground Shell/hooks wait. Keep the group leader pinned until cleanup.

Like jobrunner, this controls a process group, not descendants that escape via
setsid. File-backed streams avoid waiting for a descendant to close a pipe.
"""
from dataclasses import dataclass
import os
import signal
import subprocess
import tempfile
import time
import threading
from contextlib import contextmanager

from .runcontrol import RunStopped


@dataclass
class ProcessExit:
    code: int
    reason: str = ''
    error: str = ''


@contextmanager
def _defer_interrupt():
    # SIGINT must not raise between Popen creating a child and transferring
    # ownership to us, or interrupt killpg/wait. Workers receive cancellation
    # through RunControl; Python delivers signal handlers on the main thread.
    pending = [False]
    installed = threading.current_thread() is threading.main_thread()
    previous = signal.getsignal(signal.SIGINT) if installed else None
    def latch(signum, frame):
        pending[0] = True
    if installed:
        signal.signal(signal.SIGINT, latch)
    try:
        yield pending
    finally:
        if installed:
            signal.signal(signal.SIGINT, previous)


def run(argv, *, cwd, env, stdout, stderr, timeout, control=None, payload=b''):
    with _defer_interrupt() as pending:
        result = _run(argv, cwd=cwd, env=env, stdout=stdout, stderr=stderr,
                      timeout=timeout, control=control, payload=payload,
                      pending=pending)
        if pending[0]:
            result.reason = 'cancelled'
        return result


def _run(argv, *, cwd, env, stdout, stderr, timeout, control, payload, pending):
    if control:
        control.check()
    # waitid(WNOWAIT) prevents PID/group reuse before killpg on POSIX. Never
    # silently substitute poll(), which reaps and loses that guarantee.
    if os.name != 'nt' and not all(hasattr(os, n) for n in ('waitid', 'WNOWAIT', 'WEXITED', 'WNOHANG')):
        raise OSError('safe foreground process-group wait unavailable')
    with tempfile.TemporaryFile() as stdin:
        stdin.write(payload)
        stdin.seek(0)
        if control:
            control.check()
        if pending[0]:
            raise RunStopped('cancelled')
        proc = None
        reason, error = '', ''
        try:
            proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=stdin,
                                stdout=stdout, stderr=stderr,
                                start_new_session=os.name != 'nt')
            end = time.monotonic() + timeout
            while True:
                if pending[0]:
                    reason = 'cancelled'
                    break
                if control:
                    control.check()
                if os.name == 'nt':
                    try:
                        proc.wait(timeout=.02)
                        break
                    except subprocess.TimeoutExpired:
                        pass
                elif os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT) is not None:
                    break
                if time.monotonic() >= end:
                    reason = 'timeout'
                    break
                time.sleep(.02)
        except RunStopped as exc:
            reason = exc.reason
        except KeyboardInterrupt:
            if proc is None:
                raise
            reason = 'cancelled'
        except OSError as exc:
            if proc is None:
                raise
            error = str(exc)
        finally:
            # Also clean descendants when the leader exits normally. Do this
            # before wait(), while its unreaped PID still pins the group.
            if proc is not None:
                error = _cleanup(proc) or error
        return ProcessExit(proc.returncode, reason, error)


def _cleanup(proc):
    error = ''
    try:
        if os.name != 'nt':
            os.killpg(proc.pid, signal.SIGKILL)
        elif proc.returncode is None:
            proc.kill()
    except ProcessLookupError:
        pass
    except OSError as exc:
        error = str(exc)
    finally:
        proc.wait()
    return error
