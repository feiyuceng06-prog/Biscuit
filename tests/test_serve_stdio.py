"""Desktop UTF-8 contract, without configuration, history or model access."""
import io
import json
import sys
import unittest
from unittest.mock import patch

from feiyu.runtime import configure_serve_stdio
from feiyu.serve import Protocol

TEXT = '中文 简繁體 😀 𠮷 e\u0301'


class ServeStdioTests(unittest.TestCase):
    def test_legacy_wrappers_round_trip(self):
        for encoding in ('cp936', 'cp1252'):
            with self.subTest(encoding=encoding):
                wire = (json.dumps({'text': TEXT}, ensure_ascii=False) + '\n').encode()
                source = io.TextIOWrapper(io.BytesIO(wire), encoding=encoding, errors='strict')
                output, diagnostic = io.BytesIO(), io.BytesIO()
                sink = io.TextIOWrapper(output, encoding=encoding, errors='strict')
                err = io.TextIOWrapper(diagnostic, encoding=encoding, errors='strict')
                with patch.multiple(sys, stdin=source, stdout=sink, stderr=err):
                    configure_serve_stdio()
                    configure_serve_stdio()  # main then serve, before reads
                    row = json.loads(source.readline())
                    Protocol(sink).send('echo', **row)
                    err.write(TEXT + '\udcff')
                    err.flush()
                self.assertEqual(json.loads(output.getvalue().decode()), {'kind': 'echo', 'text': TEXT})
                self.assertEqual(diagnostic.getvalue().decode(), TEXT + '\\udcff')
                self.assertEqual(source.errors, 'strict')
                self.assertEqual(sink.errors, 'strict')

    def test_stringio_and_missing_streams(self):
        for stream in (None, io.StringIO()):
            with patch.multiple(sys, stdin=stream, stdout=stream, stderr=stream):
                configure_serve_stdio()
                self.assertIs(sys.stdout, stream)

    def test_request_cleans_waiter_on_write_or_flush_encoding_failure(self):
        for phase in ('write', 'flush'):
            error = UnicodeEncodeError('cp1252', TEXT, 0, 1, 'synthetic')
            class Sink:
                def write(self, value):
                    if phase == 'write':
                        raise error
                def flush(self):
                    if phase == 'flush':
                        raise error
            proto = Protocol(Sink())
            with self.subTest(phase=phase), self.assertRaises(UnicodeEncodeError) as caught:
                proto.request('ask', text=TEXT)
            self.assertIs(caught.exception, error)
            self.assertEqual(proto._waiting, {})
            proto.reply(1, 'late reply')
            self.assertEqual(proto._waiting, {})

    def test_protocol_does_not_hide_encoding_errors(self):
        out = io.TextIOWrapper(io.BytesIO(), encoding='cp1252', errors='strict')
        with self.assertRaises(UnicodeEncodeError):
            Protocol(out).send('echo', text=TEXT)
        out.close()

    def test_closed_stream_remains_tolerated(self):
        out = io.StringIO()
        out.close()
        Protocol(out).send('echo', text=TEXT)

    def test_main_configures_before_parse_only_for_serve(self):
        from feiyu import __main__ as cli
        import argparse
        class Parsed(Exception):
            pass
        for argv, expected in ((['feiyu', '--serve'], 1),
                               (['feiyu', '--', '--serve'], 0),
                               (['feiyu', '普通终端'], 0)):
            with self.subTest(argv=argv), patch.object(sys, 'argv', argv), \
                    patch('feiyu.runtime.configure_serve_stdio') as configure:
                def stop(_):
                    self.assertEqual(configure.call_count, expected)
                    raise Parsed()
                with patch.object(argparse.ArgumentParser, 'parse_args', stop):
                    with self.assertRaises(Parsed):
                        cli.main()


if __name__ == '__main__':
    unittest.main()
