"""Private job supervisor. The gate is closed until the parent journals identity.

Linux WNOWAIT pins the child group leader until group cleanup, preventing PID/group
reuse between observation and killpg. Descendants escaping the group are excluded.
"""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def main(directory, operation):
    directory = Path(directory)
    stopped = []
    signal.signal(signal.SIGTERM, lambda *_: stopped.append('cancelled'))
    os.write(1, b'READY\n')
    # EOF before admission means no command ever starts. Never persist command/env.
    payload = sys.stdin.buffer.raw.readline()
    if not payload:
        return
    config = json.loads(payload)
    proc = None
    deadline = config.get('deadline')
    deadline_reason = 'deadline'
    channel_open, pending = True, b''
    os.set_blocking(0, False)
    monotonic_deadline = time.monotonic() + max(0, deadline - time.time()) if deadline else None
    try:
        with open(directory / 'output', 'x+b', buffering=0) as output:
            os.chmod(directory / 'output', 0o600)
            if stopped or (deadline and time.time() >= deadline):
                stopped.append('deadline' if not stopped else stopped[0])
                code = -signal.SIGTERM
                terminal_reason = stopped[0]
            else:
                proc = subprocess.Popen(config['argv'], cwd=config['cwd'], env=config['env'],
                                        stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                        start_new_session=True)
                while True:
                    status = os.waitid(os.P_PID, proc.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
                    if status is not None:
                        terminal_reason = ''  # Real exit already happened; do not rewrite it.
                        break
                    if channel_open:
                        try:
                            chunk = os.read(0, 4096)
                        except BlockingIOError:
                            chunk = None
                        if chunk == b'':
                            channel_open = False
                        elif chunk:
                            pending += chunk
                            while b'\n' in pending:
                                line, pending = pending.split(b'\n', 1)
                                update = json.loads(line)
                                value = update.get('deadline')
                                if value and (not deadline or value < deadline):
                                    deadline = value
                                    deadline_reason = 'deadline_stopped'
                                    candidate = time.monotonic() + max(0, value - time.time())
                                    monotonic_deadline = min(monotonic_deadline or candidate, candidate)
                                if update.get('reason') in ('deadline_stopped', 'budget_stopped', 'cancelled', 'persistence_error'):
                                    stopped.append(deadline_reason if update['reason'] == 'deadline_stopped' else update['reason'])
                    if deadline and (time.time() >= deadline or time.monotonic() >= monotonic_deadline):
                        stopped.append(deadline_reason)
                    if stopped:
                        terminal_reason = ('persistence_error' if 'persistence_error' in stopped else
                                           deadline_reason if deadline and (time.time() >= deadline or time.monotonic() >= monotonic_deadline) else stopped[0])
                        break
                    time.sleep(.02)
                # Child is not reaped, even if it exited before cancellation. Its PID
                # pins the original group; KILL also removes late-writing descendants.
                os.killpg(proc.pid, signal.SIGKILL)
                code = proc.wait()
            output.flush()
            os.fsync(output.fileno())
            output.seek(0)
            log_hash = hashlib.sha256()
            log_size = 0
            while chunk := output.read(65536):
                log_hash.update(chunk)
                log_size += len(chunk)
        receipt = dict(operation=operation, output_size=log_size, output_sha256=log_hash.hexdigest(), state='cancelled' if terminal_reason else
                       'completed' if code == 0 else 'failed', exit_code=code,
                       reason=terminal_reason or 'exit', ended=time.time())
        # Independent durable receipt survives a parent death before journal finish.
        tmp = directory / 'receipt.tmp'
        with open(tmp, 'x') as stream:
            os.chmod(tmp, 0o600)
            json.dump(receipt, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, directory / 'receipt.json')
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        if proc is not None and proc.returncode is None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            proc.wait()


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
