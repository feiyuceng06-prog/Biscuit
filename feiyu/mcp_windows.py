"""Windows anonymous pipes: poll reads and cancel synchronous writer I/O.

No pipe helper is shared with LSP. CancelSynchronousIo is available since Vista;
3.10's os.set_blocking does not support Windows pipes.
"""
import ctypes
from ctypes import wintypes
import msvcrt
import os
import threading
import time


class WindowsPipe:
    def __init__(self, stdin, stdout):
        self.stdin, self.stdout = stdin, stdout
        self.stopped = threading.Event()
        self.writer = None
        self.lock = threading.Lock()
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.OpenThread.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        self.kernel.OpenThread.restype = wintypes.HANDLE
        self.kernel.CancelSynchronousIo.argtypes = [wintypes.HANDLE]
        self.kernel.CancelSynchronousIo.restype = wintypes.BOOL
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.kernel.PeekNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID,
            wintypes.DWORD, wintypes.LPVOID, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        self.kernel.PeekNamedPipe.restype = wintypes.BOOL

    def _cancel(self, thread):
        end = time.monotonic() + 2
        handle = self.kernel.OpenThread(1, False, thread.native_id)
        try:
            while thread.is_alive() and time.monotonic() < end:
                if handle:
                    self.kernel.CancelSynchronousIo(handle)
                thread.join(.01)
        finally:
            if handle:
                self.kernel.CloseHandle(handle)
        if thread.is_alive():
            raise RuntimeError('MCP Windows pipe writer not reaped within cleanup bound')

    def send(self, data, wait):
        errors = []
        done = threading.Event()
        def write():
            try:
                left = memoryview(data)
                while left and not done.is_set() and not self.stopped.is_set():
                    left = left[os.write(self.stdin.fileno(), left[:65536]):]
            except BaseException as exc:
                errors.append(exc)
        with self.lock:
            if self.stopped.is_set():
                raise RuntimeError('MCP pipe closed')
            thread = threading.Thread(target=write, name='mcp-pipe-write', daemon=True)
            self.writer = thread
            thread.start()
        try:
            while thread.is_alive():
                wait.check()
                thread.join(min(.05, wait.check()))
            if errors:
                raise RuntimeError('MCP pipe write failed: %s' % errors[0])
            if self.stopped.is_set():
                raise RuntimeError('MCP pipe closed')
        finally:
            done.set()
            # Repeated cancellation closes the race before the next WriteFile.
            from .mcp import _close_preserving
            import sys
            _close_preserving(lambda: self._cancel(thread), sys.exc_info()[1])

    def read(self, deadline):
        while not self.stopped.is_set():
            available = wintypes.DWORD()
            handle = msvcrt.get_osfhandle(self.stdout.fileno())
            if not self.kernel.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None):
                error = ctypes.get_last_error()
                if error in (109, 232, 6):
                    return b''
                raise ctypes.WinError(error)
            if available.value:
                return os.read(self.stdout.fileno(), min(65536, available.value))
            left = deadline - time.monotonic()
            if left <= 0:
                return b''
            self.stopped.wait(min(.05, left))
        return b''

    def close(self):
        with self.lock:
            self.stopped.set()
            if self.writer is not None:
                self._cancel(self.writer)
