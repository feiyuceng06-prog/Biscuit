"""Resolve and connect public fetch targets without a second DNS lookup."""
import http.client
import ipaddress
import os
import socket
import urllib.error
import urllib.request


def local_allowed() -> bool:
    return os.environ.get("FEIYU_ALLOW_LOCAL_FETCH", "").strip().lower() not in ("", "0", "false", "no")


def internal_ip(ip) -> bool:
    mapped = getattr(ip, "ipv4_mapped", None)
    return not (mapped or ip).is_global


def public_addresses(host, port):
    if not host:
        raise urllib.error.URLError("地址里没有主机名")
    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise urllib.error.URLError("无法解析主机 %s：%s" % (host, exc)) from exc
    if not addresses:
        raise urllib.error.URLError("主机 %s 没有可用地址" % host)
    for family, _, _, _, address in addresses:
        try:
            ip = ipaddress.ip_address(address[0])
        except ValueError as exc:
            raise urllib.error.URLError("主机返回了无效地址") from exc
        if family not in (socket.AF_INET, socket.AF_INET6) or internal_ip(ip):
            raise urllib.error.URLError("%s 解析到非公网地址 %s" % (host, ip))
    return addresses


def blocked_host(host):
    if local_allowed():
        return ""
    try:
        public_addresses(host, None)
    except urllib.error.URLError as exc:
        return str(exc.reason)
    return ""


def connect_public(address, timeout=socket._GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    host, port = address
    addresses = public_addresses(host, port)
    error = None
    for family, kind, proto, _, sockaddr in addresses:
        sock = None
        try:
            sock = socket.socket(family, kind, proto)
            if timeout is not socket._GLOBAL_DEFAULT_TIMEOUT:
                sock.settimeout(timeout)
            if source_address:
                sock.bind(source_address)
            # sockaddr contains a validated numeric IP; never resolve host again here.
            sock.connect(sockaddr)
            return sock
        except OSError as exc:
            error = exc
            if sock is not None:
                sock.close()
    raise error or OSError("没有可用的公网连接")


class _CheckedConnection:
    def __init__(self, *args, allow_local=False, **kwargs):
        super().__init__(*args, **kwargs)
        if not allow_local and not local_allowed():
            self._create_connection = connect_public


class _HTTPConnection(_CheckedConnection, http.client.HTTPConnection):
    pass


class _HTTPSConnection(_CheckedConnection, http.client.HTTPSConnection):
    pass


class HTTPHandler(urllib.request.HTTPHandler):
    def http_open(self, req):
        return self.do_open(lambda *args, **kwargs: _HTTPConnection(
            *args, allow_local=getattr(req, "_feiyu_allow_local", False), **kwargs), req)


class HTTPSHandler(urllib.request.HTTPSHandler):
    def https_open(self, req):
        # Keep the original hostname on the connection for Host, TLS SNI and
        # certificate verification; only the socket destination uses a numeric IP.
        return self.do_open(lambda *args, **kwargs: _HTTPSConnection(
            *args, allow_local=getattr(req, "_feiyu_allow_local", False), **kwargs),
            req, context=self._context)


class _HTTPOnly(urllib.request.BaseHandler):
    def default_open(self, req):
        if req.type not in ("http", "https"):
            raise urllib.error.URLError("只允许 HTTP/HTTPS 抓取")


def opener(*handlers):
    # A proxy can resolve the hostname independently. Public fetches connect
    # directly so the socket destination remains the address checked above.
    return urllib.request.build_opener(urllib.request.ProxyHandler({}),
                                       _HTTPOnly(), HTTPHandler(), HTTPSHandler(), *handlers)
