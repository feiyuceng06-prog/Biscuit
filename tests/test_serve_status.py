"""Status snapshots must reach the renderer in their capture order."""
import io
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from feiyu.serve import Protocol, Server


class TestStatusOrdering(unittest.TestCase):
    def test_reader_snapshot_cannot_overwrite_completion_with_stale_busy(self):
        captured = threading.Event()
        release = threading.Event()
        competing = threading.Event()
        errors = []

        class Output(io.StringIO):
            def write(self, text):
                result = super().write(text)
                # Without serialization, idle can be sent while the reader's
                # busy snapshot is paused. Release that reader only afterward.
                if json.loads(text).get('busy') is False:
                    competing.set()
                return result

        class ObservedLock:
            def __init__(self, lock):
                self.lock = lock

            def __enter__(self):
                if threading.current_thread().name == 'completion':
                    competing.set()
                self.lock.acquire()

            def __exit__(self, *args):
                self.lock.release()

        with tempfile.TemporaryDirectory() as directory:
            out = Output()
            agent = SimpleNamespace(ready=False, mode='default', style='', profile='', bot='')
            with patch('feiyu.serve.skills_mod.load_commands', return_value=[]):
                server = Server(agent, Path(directory), None, Protocol(out))
            server._status_lock = ObservedLock(getattr(server, '_status_lock', threading.Lock()))
            original = server.status

            def status():
                result = original()
                if threading.current_thread().name == 'reader':
                    captured.set()
                    if not release.wait(5):
                        raise TimeoutError('reader was not released')
                return result

            server.status = status

            def publish():
                try:
                    server.push_status()
                except Exception as error:
                    errors.append(error)

            reader = threading.Thread(target=publish, name='reader')
            completion = threading.Thread(target=publish, name='completion')
            server.busy = True
            reader.start()
            try:
                self.assertTrue(captured.wait(5))
                server.busy = False
                completion.start()
                self.assertTrue(competing.wait(5))
            finally:
                release.set()
                reader.join(5)
                if completion.ident is not None:
                    completion.join(5)
            self.assertFalse(reader.is_alive())
            self.assertFalse(completion.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual([json.loads(line)['busy'] for line in out.getvalue().splitlines()], [True, False])
