"""Synthetic early-entry transport probe; never creates an agent or reads keys.

Intercept after argument parsing to exercise the real shared entry's pre-parse
stdio setup plus actual Protocol, without starting business services.
"""
import argparse
import json
from pathlib import Path
import runpy
import sys

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root))
mode = sys.argv.pop(1)
parse = argparse.ArgumentParser.parse_args


def echo(parser, *args, **kwargs):
    parse(parser, *args, **kwargs)
    from feiyu.serve import Protocol
    protocol = Protocol(sys.stdout)
    for line in sys.stdin:
        protocol.send('echo', text=json.loads(line)['text'])
    sys.stderr.write('合成诊断 😀 𠮷\n')
    raise SystemExit(0)


argparse.ArgumentParser.parse_args = echo
if mode == 'frozen-entry':
    runpy.run_path(str(root / 'desktop/scripts/backend_entry.py'), run_name='__main__')
else:
    runpy.run_module('feiyu', run_name='__main__')
