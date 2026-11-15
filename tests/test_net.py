import io
import os
import socket
import unittest
from unittest import mock
import urllib.error
import urllib.request

from feiyu import net

PUBLIC = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.215.14", 80))]
PRIVATE = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("169.254.169.254", 80))]


class PublicFetchTests(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.dict(os.environ, {"FEIYU_ALLOW_LOCAL_FETCH": "0"})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_mixed_dns_and_nonpublic_address_forms_never_open_a_socket(self):
        for ip in ("169.254.169.254", "127.0.0.1", "100.64.0.1", "::1",
                   "::ffff:127.0.0.1", "2001::1", "fe80::1"):
            private = [(socket.AF_INET6 if ":" in ip else socket.AF_INET,
                        socket.SOCK_STREAM, 6, "", (ip, 80))]
            with self.subTest(ip=ip), \
                    mock.patch.object(net.socket, "getaddrinfo", return_value=PUBLIC + private), \
                    mock.patch.object(net.socket, "socket") as create:
                self.assertTrue(net.blocked_host("mixed.example"))
                with self.assertRaises(urllib.error.URLError):
                    net.connect_public(("mixed.example", 80))
                create.assert_not_called()

    def test_dns_failure_and_empty_answers_fail_closed(self):
        for answer in ([], socket.gaierror("no DNS")):
            with mock.patch.object(net.socket, "getaddrinfo") as dns:
                if isinstance(answer, Exception):
                    dns.side_effect = answer
                else:
                    dns.return_value = answer
                self.assertTrue(net.blocked_host("missing.example"))

    def test_dns_change_after_preflight_is_checked_again_before_connect(self):
        with mock.patch.object(net.socket, "getaddrinfo", side_effect=[PUBLIC, PRIVATE]), \
                mock.patch.object(net.socket, "socket") as create:
            self.assertEqual(net.blocked_host("rebind.example"), "")
            with self.assertRaises(urllib.error.URLError):
                net._HTTPConnection("rebind.example").connect()
            create.assert_not_called()

    def test_connect_uses_validated_numeric_address_without_resolving_twice(self):
        sock = mock.MagicMock()
        with mock.patch.object(net.socket, "getaddrinfo", side_effect=[PUBLIC, PRIVATE]) as dns, \
                mock.patch.object(net.socket, "socket", return_value=sock):
            self.assertIs(net.connect_public(("public.example", 80), timeout=3), sock)
        dns.assert_called_once()
        sock.connect.assert_called_once_with(("93.184.215.14", 80))
        sock.settimeout.assert_called_once_with(3)

    def test_failed_connection_closes_socket_and_tries_only_validated_addresses(self):
        first, second = mock.MagicMock(), mock.MagicMock()
        first.connect.side_effect = OSError("failed")
        addresses = PUBLIC + [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("8.8.8.8", 80))]
        with mock.patch.object(net.socket, "getaddrinfo", return_value=addresses), \
                mock.patch.object(net.socket, "socket", side_effect=[first, second]):
            self.assertIs(net.connect_public(("public.example", 80)), second)
        first.close.assert_called_once()
        second.connect.assert_called_once_with(("8.8.8.8", 80))

    def test_https_preserves_hostname_for_sni_and_certificate_verification(self):
        context = mock.MagicMock()
        sock = mock.MagicMock()
        with mock.patch.object(net.socket, "getaddrinfo", return_value=PUBLIC), \
                mock.patch.object(net.socket, "socket", return_value=sock):
            connection = net._HTTPSConnection("public.example", context=context)
            connection.connect()
        context.wrap_socket.assert_called_once_with(sock, server_hostname="public.example")

    def test_http_handler_preserves_host_and_ignores_ambient_proxy(self):
        sock = mock.MagicMock()
        sock.makefile.return_value = io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nok")
        with mock.patch.dict(os.environ, {"http_proxy": "http://127.0.0.1:9", "no_proxy": ""}), \
                mock.patch.object(net.socket, "getaddrinfo", return_value=PUBLIC), \
                mock.patch.object(net.socket, "socket", return_value=sock):
            with net.opener().open("http://public.example/") as response:
                self.assertEqual(response.read(), b"ok")
        sock.connect.assert_called_once_with(("93.184.215.14", 80))
        self.assertIn(b"Host: public.example\r\n", sock.sendall.call_args_list[0].args[0])

    def test_redirect_cannot_reuse_explicit_initial_local_service_permission(self):
        sock = mock.MagicMock()
        sock.makefile.return_value = io.BytesIO(
            b"HTTP/1.1 302 Found\r\nLocation: http://169.254.169.254/latest\r\nContent-Length: 0\r\n\r\n")
        request = urllib.request.Request("http://127.0.0.1:8080/search")
        request._feiyu_allow_local = True
        with mock.patch.object(net.socket, "create_connection", return_value=sock) as connect, \
                mock.patch.object(net.socket, "getaddrinfo", return_value=PRIVATE):
            with self.assertRaises(urllib.error.URLError):
                net.opener().open(request)
        connect.assert_called_once()

    def test_https_handler_uses_checked_connection(self):
        handler = net.HTTPSHandler()
        request = urllib.request.Request("https://public.example/")
        with mock.patch.object(handler, "do_open") as open_request, \
                mock.patch.object(net, "_HTTPSConnection") as connection:
            handler.https_open(request)
            factory = open_request.call_args.args[0]
            factory("public.example", timeout=2)
        connection.assert_called_once_with("public.example", allow_local=False, timeout=2)

    def test_other_protocols_cannot_bypass_the_checked_connection(self):
        for url in ("file:///etc/passwd", "ftp://public.example/file", "data:text/plain,secret"):
            with self.subTest(url=url), mock.patch.object(net.socket, "socket") as create:
                with self.assertRaises(urllib.error.URLError):
                    net.opener().open(url)
                create.assert_not_called()
