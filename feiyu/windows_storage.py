"""Fail-closed local NTFS storage. See docs/windows-taskstore.md for guarantees."""
import ctypes as C
from ctypes import wintypes as W
from contextlib import contextmanager
import os
from pathlib import Path
import msvcrt

K = C.WinDLL('kernel32', use_last_error=True)
A = C.WinDLL('advapi32', use_last_error=True)

def bind(dll, name, args, result=W.BOOL):
    fn = getattr(dll, name)
    fn.argtypes, fn.restype = args, result
    return fn

create = bind(K, 'CreateFileW', [W.LPCWSTR, W.DWORD, W.DWORD, W.LPVOID, W.DWORD, W.DWORD, W.HANDLE], W.HANDLE)
close = bind(K, 'CloseHandle', [W.HANDLE])
move = bind(K, 'MoveFileExW', [W.LPCWSTR, W.LPCWSTR, W.DWORD])
mkdir = bind(K, 'CreateDirectoryW', [W.LPCWSTR, W.LPVOID])
free = bind(K, 'LocalFree', [W.LPVOID], W.LPVOID)
class Info(C.Structure):
    _fields_ = [('attrs', W.DWORD), ('created', W.FILETIME), ('accessed', W.FILETIME),
                ('written', W.FILETIME), ('volume', W.DWORD), ('size_hi', W.DWORD),
                ('size_lo', W.DWORD), ('links', W.DWORD), ('index_hi', W.DWORD), ('index_lo', W.DWORD)]
info = bind(K, 'GetFileInformationByHandle', [W.HANDLE, C.POINTER(Info)])
class SA(C.Structure):
    _fields_ = [('length', W.DWORD), ('descriptor', W.LPVOID), ('inherit', W.BOOL)]

def checked(ok):
    if not ok:
        raise C.WinError(C.get_last_error())
    return ok

def details(h):
    row = Info()
    checked(info(h, C.byref(row)))
    if row.attrs & 0x400:
        raise ValueError('reparse point refused')
    if not row.attrs & 0x10 and row.links != 1:
        raise ValueError('multi-link file refused')
    return row

def open_handle(path, access=0x80000000, share=1, disposition=3):
    h = create(str(path), access, share, None, disposition, 0x02200000, None)
    if h == W.HANDLE(-1).value:
        raise C.WinError(C.get_last_error())
    try:
        details(h)
        return h
    except BaseException:
        close(h)
        raise

def canonical(path):
    value = os.path.abspath(path)
    p = Path(value)
    if not p.drive or len(p.drive) != 2 or p.drive[1] != ':' or ':' in value[2:]:
        raise ValueError('only local drive paths supported')
    if any(x.endswith((' ', '.')) for x in p.parts[1:]):
        raise ValueError('ambiguous Windows path')
    fs = C.create_unicode_buffer(32)
    volume = bind(K, 'GetVolumeInformationW', [W.LPCWSTR, W.LPWSTR, W.DWORD, W.LPVOID, W.LPVOID, W.LPVOID, W.LPWSTR, W.DWORD])
    checked(volume(p.anchor, None, 0, None, None, None, fs, len(fs)))
    drive_type = bind(K, 'GetDriveTypeW', [W.LPCWSTR], W.UINT)
    if fs.value != 'NTFS' or drive_type(p.anchor) != 3:
        raise ValueError('storage requires local fixed NTFS')
    return p

@contextmanager
def guard(path):
    p = canonical(path)
    handles = []
    try:
        current = Path(p.anchor)
        for part in (None, *p.parts[1:]):
            if part is not None:
                current /= part
            # Attribute-only handle, deny directory write/delete opens.
            h = open_handle(current, 0x80, 1)
            handles.append(h)
            if not details(h).attrs & 0x10:
                raise ValueError('not a directory')
        yield handles[-1]
    finally:
        for h in reversed(handles):
            close(h)

def secure_open(path):
    path = canonical(path)
    with guard(path.parent):
        h = open_handle(path)
        try:
            fd = msvcrt.open_osfhandle(h, os.O_RDONLY | os.O_BINARY)
        except BaseException:
            close(h)
            raise
        return fd

# Build a protected DACL for the actual token SID, never a username lookup.
def descriptor():
    token = W.HANDLE()
    checked(bind(A, 'OpenProcessToken', [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)])(
        bind(K, 'GetCurrentProcess', [], W.HANDLE)(), 8, C.byref(token)))
    try:
        size = W.DWORD()
        get = bind(A, 'GetTokenInformation', [W.HANDLE, C.c_int, W.LPVOID, W.DWORD, C.POINTER(W.DWORD)])
        get(token, 1, None, 0, C.byref(size))
        buf = C.create_string_buffer(size.value)
        checked(get(token, 1, buf, size, C.byref(size)))
        sid = C.cast(buf, C.POINTER(W.LPVOID))[0]
        text = W.LPWSTR()
        checked(bind(A, 'ConvertSidToStringSidW', [W.LPVOID, C.POINTER(W.LPWSTR)])(sid, C.byref(text)))
        try:
            sddl = 'O:' + text.value + 'D:P(A;OICI;FA;;;' + text.value + ')'
        finally:
            free(text)
        sd = W.LPVOID()
        checked(bind(A, 'ConvertStringSecurityDescriptorToSecurityDescriptorW', [W.LPCWSTR, W.DWORD, C.POINTER(W.LPVOID), W.LPVOID])(sddl, 1, C.byref(sd), None))
        return sd
    finally:
        close(token)

def default_owner_matches(owner):
    token = W.HANDLE()
    checked(bind(A, 'OpenProcessToken', [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)])(
        bind(K, 'GetCurrentProcess', [], W.HANDLE)(), 8, C.byref(token)))
    try:
        size = W.DWORD()
        get = bind(A, 'GetTokenInformation', [W.HANDLE, C.c_int, W.LPVOID, W.DWORD, C.POINTER(W.DWORD)])
        get(token, 4, None, 0, C.byref(size))  # TokenOwner, not a username/group lookup
        buf = C.create_string_buffer(size.value)
        checked(get(token, 4, buf, size, C.byref(size)))
        sid = C.cast(buf, C.POINTER(W.LPVOID))[0]
        return bool(bind(A, 'EqualSid', [W.LPVOID, W.LPVOID])(owner, sid))
    finally:
        close(token)

def restrict(h, sd):
    owner, dacl = W.LPVOID(), W.LPVOID()
    present, default = W.BOOL(), W.BOOL()
    checked(bind(A, 'GetSecurityDescriptorOwner', [W.LPVOID, C.POINTER(W.LPVOID), C.POINTER(W.BOOL)])(sd, C.byref(owner), C.byref(default)))
    actual, allocated = W.LPVOID(), W.LPVOID()
    result = bind(A, 'GetSecurityInfo', [W.HANDLE, C.c_int, W.DWORD, C.POINTER(W.LPVOID), W.LPVOID, W.LPVOID, W.LPVOID, C.POINTER(W.LPVOID)], W.DWORD)(h, 1, 1, C.byref(actual), None, None, None, C.byref(allocated))
    if result:
        raise C.WinError(result)
    try:
        if (not bind(A, 'EqualSid', [W.LPVOID, W.LPVOID])(owner, actual)
                and not default_owner_matches(actual)):
            raise ValueError('state directory owner differs from token user/default owner')
    finally:
        free(allocated)
    checked(bind(A, 'GetSecurityDescriptorDacl', [W.LPVOID, C.POINTER(W.BOOL), C.POINTER(W.LPVOID), C.POINTER(W.BOOL)])(sd, C.byref(present), C.byref(dacl), C.byref(default)))
    result = bind(A, 'SetSecurityInfo', [W.HANDLE, C.c_int, W.DWORD, W.LPVOID, W.LPVOID, W.LPVOID, W.LPVOID], W.DWORD)(h, 1, 0x80000005, owner, None, dacl, None)
    if result:
        raise C.WinError(result)

def private_dir(path):
    p = canonical(path)
    sd = descriptor()
    try:
        # Recursively create only missing components; do not privatize system ancestors.
        if not p.parent.exists():
            private_dir(p.parent)
        with guard(p.parent):
            sa = SA(C.sizeof(SA), sd, False)
            if not mkdir(str(p), C.byref(sa)) and C.get_last_error() != 183:
                raise C.WinError(C.get_last_error())
            h = open_handle(p, 0xe0080, 1)  # READ_CONTROL | WRITE_DAC | WRITE_OWNER | attributes
            try:
                if not details(h).attrs & 0x10:
                    raise ValueError('not directory')
                restrict(h, sd)
            finally:
                close(h)
    finally:
        free(sd)

class Writer:
    def __init__(self, directory):
        self.chain = guard(directory)
        self.chain.__enter__()
        self.handle = None
        try:
            self.handle = open_handle(Path(directory) / 'writer.lock', 0xc0000000, 0, 4)
        except BaseException:
            self.chain.__exit__(None, None, None)
            raise
    def close(self):
        if self.handle is not None:
            close(self.handle)
            self.handle = None
            self.chain.__exit__(None, None, None)

def flush(h):
    checked(bind(K, 'FlushFileBuffers', [W.HANDLE])(h))


def replace(source, target):
    # Caller pins the private directory; no cross-volume/copy fallback.
    checked(move(str(source), str(target), 1 | 8))
    h = open_handle(target, 0xc0000000)
    try:
        flush(h)
    finally:
        close(h)

def key(h):
    r = details(h)
    return (r.volume, r.index_hi, r.index_lo, r.attrs, r.size_hi, r.size_lo,
            r.written.dwHighDateTime, r.written.dwLowDateTime)

def directory_identity(path):
    with guard(path) as h:
        r = details(h)
        return dict(path=str(path), device=r.volume, inode=(r.index_hi << 32) | r.index_lo)

def read_safe(path, limit, check):
    path = canonical(path)
    with guard(path.parent):
        h = open_handle(path)
        fd = None
        try:
            if details(h).attrs & 0x10:
                raise ValueError('not regular file')
            before = key(h)
            fd = msvcrt.open_osfhandle(h, os.O_RDONLY | os.O_BINARY)
            raw = bytearray()
            while True:
                check()
                chunk = os.read(fd, min(65536, max(1, limit + 1 - len(raw))))
                if not chunk:
                    break
                raw.extend(chunk)
                if len(raw) > limit:
                    raise ValueError('byte budget exceeded')
            if key(h) != before:
                raise ValueError('file changed while reading')
            return bytes(raw), os.fstat(fd)
        finally:
            if fd is None:
                close(h)
            else:
                os.close(fd)

def atomic_json(path, data):
    import json
    import tempfile
    path = canonical(path)
    private_dir(path.parent)
    with guard(path.parent):
        # Validate existing entry before replacement, including hardlinks/reparse.
        try:
            h = open_handle(path, 0x80)
        except FileNotFoundError:
            pass
        else:
            try:
                if details(h).attrs & 0x10:
                    raise ValueError('snapshot is directory')
            finally:
                close(h)
        temporary = None
        try:
            fd, temporary = tempfile.mkstemp(prefix='.task-write-', dir=path.parent)
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                json.dump(data, stream, ensure_ascii=False, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
