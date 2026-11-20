"""Trusted offline transport adapter, executed only in a bubblewrap namespace."""
import contextlib
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace as N

sys.path.insert(0, '/source')


class MeasurementStop(BaseException):
    pass


def rpc(kind, **data):
    sys.__stdout__.write(json.dumps(dict(kind=kind, **data), allow_nan=False,
        default=lambda value: value.model_dump(mode='json', exclude_unset=True)) + '\n')
    sys.__stdout__.flush()
    reply = json.loads(sys.stdin.readline())
    if reply.get('measurement_stop') is True:
        raise MeasurementStop()
    if 'error' in reply:
        raise RuntimeError(reply['error'])
    return reply


from architecture_runtime import environment


def main():
    import feiyu.agent as mod
    from feiyu import providers, keys, session
    from feiyu.agent import Feiyu
    origins = {name: dict(path=m.__file__, sha256=hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest())
               for name, m in list(sys.modules.items()) if name.startswith('feiyu') and getattr(m, '__file__', None)}
    boundary = {}
    for name in (sys.argv[1]+'/answer', sys.argv[1]+'/results', sys.argv[1]+'/receipt', sys.argv[1]+'/lock', '/source/evals/architecture_cases.py', '/source/feiyu/agent.py', '/adapter/architecture_worker.py'):
        for mode in ('r', 'w'):
            try:
                with open(name, mode):
                    pass
                boundary[name + ':' + mode] = 'ALLOWED'
            except OSError as exc:
                boundary[name + ':' + mode] = type(exc).__name__
    setup = rpc('hello', origins=origins, environment=environment(), boundary=boundary)
    version = setup['version']

    class Fake(providers.OpenAICompatBackend):
        def __init__(self, system, tools):
            self.model = version
            self.max_tokens = 8192
            self.system = system
            self.tools = providers._to_openai_tools(tools)
            self.messages = [dict(role='system', content=system)]
            self.request_number = 0
            self.cache = False
            self.thinking = False
            self._reset_usage()
            self.rates = (0.0, 0.0, 0.0)
            self.client = N(chat=N(completions=N(create=self.create)))

        def _sdk_call(self, operation, **kwargs):
            return self.create(**kwargs)

        def create(self, **kwargs):
            kwargs.update(temperature=0, top_p=1)
            self.request_number += 1
            reply = rpc('request', parameters=kwargs, system=self.system)
            if reply['version'] != version:
                raise RuntimeError('model version drift')
            observed = reply.get('usage', {'prompt_tokens': 1, 'completion_tokens': 1})
            usage = N(prompt_tokens=observed.get('prompt_tokens', 0), completion_tokens=observed.get('completion_tokens', 0), prompt_tokens_details=None)
            if not kwargs.get('stream'):
                return N(usage=usage, choices=[N(message=N(content=reply['text']))])
            calls = [N(index=i, id='call-%d-%d' % (self.request_number, i), function=N(name=c['name'], arguments=json.dumps(c['input'])))
                     for i, c in enumerate(reply.get('calls', []))]
            return iter([N(usage=usage, choices=[N(finish_reason='tool_calls' if calls else 'stop',
                          delta=N(content=reply.get('text', ''), tool_calls=calls))])])

    class Native(providers.AnthropicBackend):
        def __init__(self, system, tools):
            self.model, self.system, self.tools = version, system, tools
            self.max_tokens = 8192
            self.messages = []
            self.cache = True
            self.rates = (0., 0., 0., 0.)
            self._reset_usage()
            self.client = N(messages=N(create=self.create, stream=self.stream))

        def _sdk_call(self, operation, **kwargs):
            return self.stream(**kwargs) if operation == 'stream' else self.create(**kwargs)

        def create(self, **kwargs):
            from anthropic.types import Message
            reply = rpc('request', parameters=kwargs, system=self.system)
            if reply['version'] != version:
                raise RuntimeError('model version drift')
            content = [dict(type='text', text=reply['text'])]
            content += [dict(type='tool_use', id=c['id'], name=c['name'], input=c['input']) for c in reply.get('calls', [])]
            usage = {k: reply.get('usage', {}).get(k, 0) for k in
                     ('input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')}
            return Message.model_validate(dict(id='synthetic', type='message', role='assistant', model=version,
                content=content, stop_reason='tool_use' if len(content)>1 else 'end_turn', stop_sequence=None, usage=usage))

        def stream(self, **kwargs):
            kwargs['stream'] = True
            message = self.create(**kwargs)
            class Stream:
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def __iter__(self):
                    yield N(type='message_start', message=message)
                    yield N(type='content_block_delta', delta=N(type='text_delta', text=message.content[0].text))
                    yield N(type='message_stop')
                def get_final_message(self): return message
            return Stream()

    native = setup.get('provider') == 'anthropic'
    mod.build_backend = lambda entry, system, tools: (Native if native else Fake)(system, tools)
    keys.load = lambda: {'offline': dict(model=version, provider='anthropic' if native else 'openai', context=200000)}
    native_schemas = Feiyu.tool_schemas
    Feiyu.tool_schemas = lambda self: [s for s in native_schemas(self) if s['name'] in ('read_file', 'write_file', 'edit_file', 'bash')]
    agent = Feiyu(Path('/work'))
    agent.use_model('offline')
    agent.mode = 'auto'
    agent.max_rounds = 30
    agent.budget = 3.0
    agent.time_budget = 120
    group = setup['group']
    if setup.get('restore'):
        data = session.load(Path('/work'), setup['sid'])
        if not data or not agent.restore(data):
            raise RuntimeError('native session restore failed')
        rpc('restored', operations=getattr(getattr(agent, 'task_state', None), 'operations', []))
    if group == 'verification':
        import shlex
        agent.verify = "grep -qx " + shlex.quote(setup['verification_content'].strip()) + " calc.py"
        agent._baseline_done = True
    if setup.get('measurement_only'):
        rpc('prepared', system=agent.backend.system)
    with contextlib.redirect_stdout(sys.stderr):
        try:
            agent.send('continue' if setup.get('restore') else setup['prompt'])
        except Exception as exc:
            if setup.get('restore') and type(exc).__name__ == 'PersistenceError':
                rpc('replay_blocked', exception=type(exc).__name__, diagnostic=str(exc))
            else:
                raise
        if group == 'verification':
            rpc('verified', value=agent.verified_ok, records=getattr(getattr(agent, 'verifications', None), 'records', []))
            # Controller edits the actual workspace while the worker is paused.
            rpc('stale', value=agent.verified_ok)
            agent.send('continue')
        elif group == 'compaction':
            summary = agent.compact()
            rpc('compacted', summary=summary, messages=agent.backend.messages)
            agent.send('continue')
        elif group == 'recovery' and not setup.get('restore'):
            session.save(Path('/work'), agent)
            rpc('saved', sid=agent.session_id)
            agent.send('continue')
        session.save(Path('/work'), agent)
    rpc('done', sid=agent.session_id, verified=getattr(agent, 'verified_ok', None))
    store = getattr(agent, '_task_store', None)
    if store:
        store.close()


if __name__ == '__main__':
    try:
        main()
    except MeasurementStop:
        pass
