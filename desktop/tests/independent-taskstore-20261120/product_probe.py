"""Synthetic only. Run each mode in a clean process with isolated home/state/config."""
import contextlib, io, json, os, sys
from pathlib import Path
base=Path(sys.argv[1]); mode=sys.argv[2]
base.mkdir(exist_ok=True)
for key in ('HOME','USERPROFILE','XDG_STATE_HOME','XDG_CONFIG_HOME','XDG_CACHE_HOME','XDG_DATA_HOME'):
    value=base/key; value.mkdir(exist_ok=True); os.environ[key]=str(value)
from feiyu import session
from feiyu.agent import Feiyu
from feiyu.taskstate import TaskStore,TaskState,PersistenceError,workspace_id
from tests.fakes import FakeBackend,call,unpaired
root=base/'workspace';root.mkdir(exist_ok=True)
if mode=='legacy':
    p=Path(session._legacy_path(root));p.parent.mkdir(parents=True,exist_ok=True)
    original=json.dumps(dict(model='synthetic',messages=[dict(role='user',content='old synthetic')])).encode()
    p.write_bytes(original)
    data=session.load(root,session.LEGACY)
    assert data['messages'][0]['content']=='old synthetic'
    a=Feiyu(root)
    def model(name): a.backend=FakeBackend([('new synthetic',[])]);a.name=name;return True
    a.use_model=model
    assert a.restore(data)
    with contextlib.redirect_stdout(io.StringIO()):a.send('continue synthetic')
    assert p.read_bytes()==original
    assert a.task_state.requests[0]['source']=='unknown/legacy'
    a._task_store.close()
    print('legacy-read-restore-send preserves original PASS');sys.exit(0)
if mode in ('effect-crash','effect-recover'):
    from feiyu.tools import Toolbox
    store=TaskStore(root,'effect');marker=root/'effect-marker'
    try:
        if mode=='effect-crash':
            state=TaskState('effect','effecttask',workspace_id(root))
            box=Toolbox(root);box.execution.durable=(store,state)
            store.finish=lambda *args:os._exit(84)
            box.execution.invoke('write_file',dict(path='effect-marker'),lambda:marker.write_text('once'))
            raise AssertionError('crash missing')
        state=store.recover()
        assert state.operations[0]['state']=='unknown'
        box=Toolbox(root);box.execution.durable=(store,state)
        try:box.execution.invoke('write_file',dict(path='effect-marker'),lambda:marker.write_text('replayed'))
        except PersistenceError:pass
        else:raise AssertionError('unknown replay permitted')
        assert marker.read_text()=='once'
        print('effect happened, process crashed before finish; unknown blocks replay PASS')
    finally:store.close()
    sys.exit(0)
a=Feiyu(root);a.backend=FakeBackend([('synthetic answer',[])]);a.name='synthetic';a.mode='auto';a.budget=1
try:
    if mode=='crash':
        a.session_id='reviewcrash'
        def die(*args,**kwargs):os._exit(83)
        a.backend.run_turn=die
        with contextlib.redirect_stdout(io.StringIO()):a.send('synthetic crash request')
        raise AssertionError('crash not reached')
    if mode=='recover':
        assert a.restore(dict(session_id='reviewcrash',journal_only=True))
        a._control()  # Pending cost becomes unknown when durable budget controller is initialized.
        b=a.task_state.budget
        assert b['attempts']==1 and b['pending_attempts']==1 and b['cost'] is None,b
        before=b['attempts'];calls=[]
        a.backend.run_turn=lambda *args,**kwargs:calls.append('UNEXPECTED')
        with contextlib.redirect_stdout(io.StringIO()):a.send('synthetic continuation')
        assert not calls and b['attempts']==before,b
        print('Agent.send crash admission/recover no new request PASS',json.dumps(b));sys.exit(0)
    if mode=='conversation':
        with contextlib.redirect_stdout(io.StringIO()):a.send('synthetic request')
        assert a.task_state.requests[-1]['text']=='synthetic request'
        if os.name=='nt':
            from feiyu.providers import ToolCall
            a.backend.script=[('',[call('bg','bash',command='echo synthetic',background=True),ToolCall('sym','symbol',dict(action='definition',path='x.py',name='x'))]),('continued',[])]
            with contextlib.redirect_stdout(io.StringIO()):a.send('synthetic refusal')
            results=[m for m in a.backend.messages if m['role']=='tool']
            assert len(results)==2 and all('Windows' in m['content'] for m in results),results
            assert not unpaired(a.backend.messages)
        print('Agent.send actual persistence PASS; Windows refusal executed:',os.name=='nt')
    elif mode=='failure':
        # Real execution coordinator, deterministic failure at the critical publication boundary.
        from unittest.mock import patch
        s=TaskStore(root,'failure');t=TaskState('failure','task',workspace_id(root))
        a.toolbox.execution.durable=(s,t)
        marker=root/'effect'
        try:
            with patch('feiyu.taskstate.atomic_json',side_effect=PersistenceError('synthetic storage full')):
                try:a.toolbox.execution.invoke('write_file',{},lambda:marker.write_text('BAD'))
                except PersistenceError:pass
                else:raise AssertionError('not blocked')
            try:a.toolbox.execution.invoke('write_file',{},lambda:marker.write_text('BAD'))
            except PersistenceError:pass
            else:raise AssertionError('second effect permitted')
            assert not marker.exists() and s.blocked
        finally:s.close()
        print('critical prepare failure then second invocation: no effects PASS')
finally:
    if a._task_store:a._task_store.close()
