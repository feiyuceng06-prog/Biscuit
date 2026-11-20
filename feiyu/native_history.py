"""Small native-history seams; no cross-provider message conversion.

read() is a borrowed list for existing in-place tool-result thinning. Export is
an independent JSON-compatible snapshot; replacement retains all native fields.
Compression callers must validate their candidate before replace(), not infer
acceptance from this interface. Custom backends need only the existing messages.
"""
from copy import deepcopy


def read(backend):
    return backend.messages


def replace(backend, messages):
    if not isinstance(messages, list):
        raise TypeError('native history must be a list')
    backend.messages = messages


def plain(obj):
    if isinstance(obj, dict):
        return {k: plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [plain(v) for v in obj]
    dump = getattr(obj, 'model_dump', None)
    return plain(dump()) if callable(dump) else deepcopy(obj)


def export_session(backend):
    return plain(read(backend))


def restore_session(backend, messages):
    replace(backend, plain(messages))
