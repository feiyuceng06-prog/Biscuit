"""Native-only synthetic explicit-ACE migration diagnostic; no account/privilege changes.
Exit 20 = broad existing file ACE still present after directory migration/recover.
That is an observation requiring scope/security assessment, not cross-user exploit proof.
Exit 0 = broad ACE absent; 77 = not Windows; 1 = failed fixture/assertion/API.
"""
import os,sys,json,ctypes as C
from pathlib import Path
if os.name!='nt': print('SKIP native Windows required');sys.exit(77)
base=Path(sys.argv[1]).absolute()
base.mkdir(exist_ok=False) # require new scratch location, never use a real installation
for k in ('HOME','USERPROFILE','XDG_CONFIG_HOME','XDG_STATE_HOME','XDG_CACHE_HOME','XDG_DATA_HOME'):
 p=base/k;p.mkdir();os.environ[k]=str(p)
from ctypes import wintypes as W
from feiyu import session,windows_storage as w
from feiyu.taskstate import TaskStore,TaskState,workspace_id
root=base/'workspace';root.mkdir()
s=TaskStore(root,'synthetic');t=TaskState('synthetic','task',workspace_id(root));t.revise('synthetic only');s.save(t)
f=s.path(t.task_id);s.close()
def sddl(h):
 sd=W.LPVOID();txt=W.LPWSTR()
 r=w.bind(w.A,'GetSecurityInfo',[W.HANDLE,C.c_int,W.DWORD,W.LPVOID,W.LPVOID,W.LPVOID,W.LPVOID,C.POINTER(W.LPVOID)],W.DWORD)(h,1,5,None,None,None,None,C.byref(sd))
 if r:raise C.WinError(r)
 try:
  w.checked(w.bind(w.A,'ConvertSecurityDescriptorToStringSecurityDescriptorW',[W.LPVOID,W.DWORD,W.DWORD,C.POINTER(W.LPWSTR),W.LPVOID])(sd,1,5,C.byref(txt),None))
  return txt.value
 finally:w.free(txt);w.free(sd)
h=w.open_handle(f,0x60080,1)
try:
 owner=sddl(h).split('O:')[1].split('D:')[0]
 # Existing explicit broad file ACL; owner is retained, synthetic bytes only.
 sd=W.LPVOID();w.checked(w.bind(w.A,'ConvertStringSecurityDescriptorToSecurityDescriptorW',[W.LPCWSTR,W.DWORD,C.POINTER(W.LPVOID),W.LPVOID])('D:P(A;;FA;;;'+owner+')(A;;FR;;;WD)',1,C.byref(sd),None))
 try:
  acl=W.LPVOID();present=W.BOOL();default=W.BOOL()
  w.checked(w.bind(w.A,'GetSecurityDescriptorDacl',[W.LPVOID,C.POINTER(W.BOOL),C.POINTER(W.LPVOID),C.POINTER(W.BOOL)])(sd,C.byref(present),C.byref(acl),C.byref(default)))
  r=w.bind(w.A,'SetSecurityInfo',[W.HANDLE,C.c_int,W.DWORD,W.LPVOID,W.LPVOID,W.LPVOID,W.LPVOID],W.DWORD)(h,1,0x80000004,None,None,acl,None)
  if r:raise C.WinError(r)
 finally:w.free(sd)
 print('fixture',sddl(h))
finally:w.close(h)
s=TaskStore(root,'synthetic')
try:
 loaded=s.recover();assert loaded.requests[0]['text']=='synthetic only'
 h=w.open_handle(f,0x20080,1)
 try:after=sddl(h)
 finally:w.close(h)
 print('after directory migration and recover',after)
 retained=';;;WD)' in after or ';;;S-1-1-0)' in after
 # A subsequent atomic replacement should inherit private directory ACL.
 s.save(loaded)
 h=w.open_handle(f,0x20080,1)
 try:new=sddl(h)
 finally:w.close(h)
 print('after atomic save',new)
 assert ';;;WD)' not in new and ';;;S-1-1-0)' not in new,new
finally:s.close()
(base/'result.json').write_text(json.dumps(dict(existing_broad_ace_retained=retained,after_recover=after,after_save=new),indent=2))
sys.exit(20 if retained else 0)
