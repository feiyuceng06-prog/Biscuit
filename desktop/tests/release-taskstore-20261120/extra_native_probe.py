"""Suggested additional native evidence, NOT executed by this review.
Run on current-SHA disposable Windows fixed NTFS checkout:
python extra_native_probe.py NEW_SCRATCH
No network, accounts, real configuration, or installer. Non-Windows exit77.
"""
import os,sys,json,ctypes as C,hashlib
from pathlib import Path
if os.name!='nt':sys.exit(77)
from ctypes import wintypes as W
from unittest.mock import patch
from feiyu import windows_storage as w,session
from feiyu.taskstate import TaskStore,TaskState,workspace_id,PersistenceError
from feiyu.verification import _read_safe
base=Path(sys.argv[1]).absolute();base.mkdir(exist_ok=False)
root=base/'workspace';root.mkdir();session.DIR=str(base/'sessions')
def sddl(path):
 h=w.open_handle(path,0x20080);sd=W.LPVOID();txt=W.LPWSTR()
 try:
  r=w.bind(w.A,'GetSecurityInfo',[W.HANDLE,C.c_int,W.DWORD,W.LPVOID,W.LPVOID,W.LPVOID,W.LPVOID,C.POINTER(W.LPVOID)],W.DWORD)(h,1,5,None,None,None,None,C.byref(sd))
  if r:raise C.WinError(r)
  w.checked(w.bind(w.A,'ConvertSecurityDescriptorToStringSecurityDescriptorW',[W.LPVOID,W.DWORD,W.DWORD,C.POINTER(W.LPWSTR),W.LPVOID])(sd,1,5,C.byref(txt),None))
  return txt.value
 finally:w.free(txt);w.free(sd);w.close(h)
def broaden(path):
 owner=sddl(path).split('O:')[1].split('D:')[0];sd=W.LPVOID();acl=W.LPVOID();present=W.BOOL();default=W.BOOL();h=w.open_handle(path,0x60080)
 try:
  w.checked(w.bind(w.A,'ConvertStringSecurityDescriptorToSecurityDescriptorW',[W.LPCWSTR,W.DWORD,C.POINTER(W.LPVOID),W.LPVOID])('D:P(A;;FA;;;'+owner+')(A;;FR;;;WD)',1,C.byref(sd),None))
  w.checked(w.bind(w.A,'GetSecurityDescriptorDacl',[W.LPVOID,C.POINTER(W.BOOL),C.POINTER(W.LPVOID),C.POINTER(W.BOOL)])(sd,C.byref(present),C.byref(acl),C.byref(default)))
  r=w.bind(w.A,'SetSecurityInfo',[W.HANDLE,C.c_int,W.DWORD,W.LPVOID,W.LPVOID,W.LPVOID,W.LPVOID],W.DWORD)(h,1,0x80000004,None,None,acl,None)
  if r:raise C.WinError(r)
 finally:w.free(sd);w.close(h)
def facts(p):
 h=w.open_handle(p)
 try:identity=w.key(h)[:3]
 finally:w.close(h)
 return dict(identity=identity,sha256=hashlib.sha256(p.read_bytes()).hexdigest(),sddl=sddl(p))
s=TaskStore(root,'synthetic');t=TaskState('synthetic','task',workspace_id(root));t.revise('synthetic');s.activate(t)
paths=[s.path(t.task_id),s.directory/'active.json'];project=root/'project.json';project.write_text('{"synthetic":true}')
for p in [*paths,project]:broaden(p)
before={p.name:facts(p) for p in [*paths,project]}
assert _read_safe(project,1024)[0];assert facts(project)==before[project.name]
loaded=s.recover();assert loaded.requests[0]['text']=='synthetic'
after={p.name:facts(p) for p in [*paths,project]}
for p in paths:
 assert before[p.name]['identity']==after[p.name]['identity']
 assert before[p.name]['sha256']==after[p.name]['sha256']
 assert ';;;WD)' not in after[p.name]['sddl'] and ';;;S-1-1-0)' not in after[p.name]['sddl']
assert before[project.name]==after[project.name]
with patch.object(w,'restrict',side_effect=OSError('synthetic ACL rejection')):
 try:s.recover()
 except PersistenceError:pass
 else:raise AssertionError('active pointer ACL failure did not stop recovery')
assert s.blocked
assert {p.name:facts(p) for p in [*paths,project]}==after
s.close();(base/'extra-result.json').write_text(json.dumps(dict(before=before,after=after,blocked=True),indent=2));print('PASS extra native active/snapshot identity, bytes, project ACL isolation and active failure')
