"""Synthetic HTTP fixture, not an external provider or benefit measurement."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import sys
import threading
from evals import architecture_cases as cases


@contextmanager
def service(group, model, responder=None, provider='openai', split='development'):
    stage = [0]
    case = cases.spec(group, split)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_POST(self):
            params = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            if responder:
                responder(self, params)
                return
            calls, text = [], 'done'
            def put(name, content):
                calls.append(dict(name='write_file', input=dict(path=name, content=content)))
            n = stage[0]
            if not params.get('stream'):
                text = 'Preserve protected.txt; '+str(case['after'])+'; continue unfinished b.txt.'
            else:
                if n == 0 and group != 'recovery':
                    calls.extend(dict(name='read_file', input={'path': name}) for name in case['before'])
                elif group == 'executor' and n == 1:
                    for name, content in case['after'].items(): put(name, content)
                elif group == 'verification' and n == 3:
                    calls.append(dict(name='read_file', input={'path': 'calc.py'}))
                elif group == 'verification' and n in (1, 4): put('calc.py', case['after']['calc.py'])
                elif group == 'compaction' and n in (1, 3): put('a.txt' if n == 1 else 'b.txt', case['after']['a.txt' if n == 1 else 'b.txt'])
                elif group == 'recovery' and n in (1, 2):
                    calls.append(dict(name='bash', input={'command': sys.executable+" -c \"import socket;s=socket.socket(socket.AF_UNIX);s.connect('/service');s.send(b'operation-5');s.recv(10)\""}))
                stage[0] += 1
            if provider == 'anthropic':
                content = [dict(type='text', text=text)] + [dict(type='tool_use', id='call-%s-%s' % (n, i),
                    name=c['name'], input=c['input']) for i, c in enumerate(calls)]
                usage = dict(input_tokens=10, output_tokens=5, cache_read_input_tokens=3, cache_creation_input_tokens=2)
                value = dict(id='synthetic', type='message', role='assistant', model=model, content=content,
                    stop_reason='tool_use' if calls else 'end_turn', stop_sequence=None, usage=usage)
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream' if params.get('stream') else 'application/json')
                self.end_headers()
                if not params.get('stream'):
                    self.wfile.write(json.dumps(value).encode())
                    return
                def emit(v):
                    self.wfile.write(('event: '+v['type']+'\ndata: '+json.dumps(v)+'\n\n').encode())
                emit(dict(type='message_start', message=dict(value, content=[], stop_reason=None,
                    usage=dict(usage, output_tokens=0))))
                for i, block in enumerate(content):
                    emit(dict(type='content_block_start', index=i, content_block=dict(block,
                        **({'input': {}} if block['type']=='tool_use' else {'text': ''}))))
                    delta = (dict(type='input_json_delta', partial_json=json.dumps(block['input'])) if block['type']=='tool_use'
                             else dict(type='text_delta', text=block['text']))
                    emit(dict(type='content_block_delta', index=i, delta=delta))
                    emit(dict(type='content_block_stop', index=i))
                emit(dict(type='message_delta', delta=dict(stop_reason=value['stop_reason'], stop_sequence=None), usage=dict(output_tokens=5)))
                emit(dict(type='message_stop'))
                return
            tools = [dict(index=i, id='call-%s-%s' % (n, i), type='function',
                          function=dict(name=c['name'], arguments=json.dumps(c['input']))) for i, c in enumerate(calls)]
            msg = dict(content=text, tool_calls=tools or None, role='assistant')
            choice = dict(index=0, finish_reason='tool_calls' if tools else 'stop',
                          **{('delta' if params.get('stream') else 'message'): msg})
            value = dict(id='synthetic', object='chat.completion.chunk' if params.get('stream') else 'chat.completion',
                         created=0, model=model, choices=[choice], usage=dict(prompt_tokens=10, completion_tokens=5, total_tokens=15))
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream' if params.get('stream') else 'application/json')
            self.end_headers()
            raw = json.dumps(value).encode()
            self.wfile.write(b'data: '+raw+b'\n\ndata: [DONE]\n\n' if params.get('stream') else raw)
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        yield 'http://127.0.0.1:%d/v1' % server.server_port
    finally:
        server.shutdown(); server.server_close(); thread.join()
