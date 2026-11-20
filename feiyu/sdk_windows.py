"""SDK private Windows pipe transport. Requires real Windows verification."""
import ctypes
from ctypes import wintypes
import msvcrt
import os
import threading
import time


class Pipe:
    def __init__(self, stdin, stdout):
        self.stdin, self.stdout = stdin, stdout
        self.thread = None
        self.errors = []
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.PeekNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID,
            wintypes.DWORD, wintypes.LPVOID, ctypes.POINTER(wintypes.DWORD), wintypes.LPVOID]
        self.kernel.PeekNamedPipe.restype = wintypes.BOOL

    def send(self, data, check):
        def write():
            try:
                left = memoryview(data)
                while left:
                    left = left[os.write(self.stdin.fileno(), left[:65536]):]
            except OSError as exc:
                self.errors.append(exc)
        self.thread = threading.Thread(target=write, name='sdk-private-pipe-write', daemon=True)
        self.thread.start()
        while self.thread.is_alive():
            check()
            self.thread.join(.05)
        if self.errors:
            raise RuntimeError('SDK private pipe write failed')

    def read(self, timeout):
        available = wintypes.DWORD()
        handle = msvcrt.get_osfhandle(self.stdout.fileno())
        if not self.kernel.PeekNamedPipe(handle, None, 0, None, ctypes.byref(available), None):
            if ctypes.get_last_error() in (109, 232, 6):
                return b''
            raise ctypes.WinError(ctypes.get_last_error())
        if available.value:
            return os.read(self.stdout.fileno(), min(65536, available.value))
        time.sleep(timeout)
        return None

    def join(self):
        # Called only after killing/waiting the sole read peer, releasing WriteFile.
        if self.thread:
            self.thread.join(3)
            if self.thread.is_alive():
                raise RuntimeError('SDK Windows writer cleanup unknown')
