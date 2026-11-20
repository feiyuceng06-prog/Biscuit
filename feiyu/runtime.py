"""Keep the frozen Linux backend's libraries separate from host programs."""
import os
import ssl
import sys


def configure_frozen_environment():
    if not getattr(sys, 'frozen', False) or not sys.platform.startswith('linux'):
        return
    bundle = os.path.realpath(sys._MEIPASS)
    blocked = {bundle, os.path.join(bundle, '_internal')}
    appdir = os.environ.get('APPDIR')
    if appdir:
        appdir = os.path.realpath(appdir)
        if os.path.commonpath((appdir, bundle)) == appdir:
            blocked.add(os.path.join(appdir, 'usr', 'lib'))
    # The bootloader saves the pre-freeze path; AppRun may already have added its libs.
    original = os.environ.get('LD_LIBRARY_PATH_ORIG', os.environ.get('LD_LIBRARY_PATH', ''))
    clean = os.pathsep.join(p for p in original.split(os.pathsep)
                           if p and os.path.realpath(p) not in blocked)
    for name in ('LD_LIBRARY_PATH', 'LD_LIBRARY_PATH_ORIG'):
        if clean:
            os.environ[name] = clean
        else:
            os.environ.pop(name, None)

    # Respect explicit corporate/custom trust stores, including deliberate failures.
    if 'SSL_CERT_FILE' in os.environ or 'SSL_CERT_DIR' in os.environ:
        return
    if ssl.create_default_context().cert_store_stats()['x509_ca']:
        return
    for path in ('/etc/ssl/certs/ca-certificates.crt', '/etc/pki/tls/certs/ca-bundle.crt',
                 '/etc/ssl/cert.pem'):
        if not os.path.isfile(path):
            continue
        try:
            context = ssl.create_default_context(cafile=path)
        except (OSError, ssl.SSLError):
            continue
        if context.cert_store_stats()['x509_ca']:
            os.environ['SSL_CERT_FILE'] = path
            return


def configure_serve_stdio():
    """Use UTF-8 for desktop JSON lines, before any stdin read.

    Reconfigure the live wrappers rather than relying on interpreter startup
    environment variables (which may be overridden or absent in a frozen host).
    Leave terminal sessions and private binary worker IPC to their own entries.
    StringIO/embedder streams without reconfigure, including None, are retained.
    """
    for name in ('stdin', 'stdout', 'stderr'):
        stream = getattr(sys, name, None)
        reconfigure = getattr(stream, 'reconfigure', None)
        if callable(reconfigure):
            # Protocol data must round-trip without replacement. Diagnostics may
            # contain an unpaired surrogate from an OS path/exception; escape it.
            options = {'encoding': 'utf-8',
                       'errors': 'backslashreplace' if name == 'stderr' else 'strict'}
            if name != 'stdin':
                options['write_through'] = True
            reconfigure(**options)
