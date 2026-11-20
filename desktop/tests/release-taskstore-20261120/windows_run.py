"""Release regression revision: old independent scripts/evidence remain untouched.
Conversation alone has no cost cap because its fake backend has unknown usage;
crash/recover retain budget=1 and unchanged no-refund assertions.
Each current tracked source is bound to exact Git HEAD before/after execution.
"""
"""Run from disposable local-fixed-NTFS Windows checkout; no install or network needed.
python windows_run.py <repo> <NEW-scratch-directory>
Preserve output, JSON exit codes and source drift check. Timeout 45s/case; no retries.
"""
import os,sys,pathlib,subprocess,json,hashlib
if os.name!='nt':sys.exit(77)
repo=pathlib.Path(sys.argv[1]).resolve();out=pathlib.Path(sys.argv[2]).absolute();out.mkdir(exist_ok=False)
probe=pathlib.Path(__file__).parent
commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()
tracked=subprocess.check_output(['git','ls-files','feiyu','tests','desktop/tests','docs/windows-taskstore.md'],cwd=repo,text=True).splitlines()
manifest={f:hashlib.sha256(subprocess.check_output(['git','show',commit+':'+f],cwd=repo)).hexdigest() for f in tracked}
(out/'source-binding.json').write_text(json.dumps(dict(commit=commit,sha256=manifest),indent=2))
def drift():return [f for f,h in manifest.items() if hashlib.sha256((repo/f).read_bytes()).hexdigest()!=h]
assert not drift(),'working tree differs from release commit'
env={k:v for k,v in os.environ.items() if k.upper() in ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC','PATHEXT')}
env.update(PYTHONPATH=str(repo),PYTHONDONTWRITEBYTECODE='1')
rows=[]
for mode in ['conversation','legacy','failure','crash','recover','effect-crash','effect-recover','acl','extra']:
 case='crash' if mode=='recover' else 'effect-crash' if mode=='effect-recover' else mode
 command=[sys.executable,str(probe.parent/'independent-taskstore-20261120/windows_acl_probe.py'),str(out/case)] if mode=='acl' else [sys.executable,str(probe/'product_probe.py'),str(out/case),mode]
 if mode=='extra':command=[sys.executable,str(probe/'extra_native_probe.py'),str(out/case)]
 try:
  r=subprocess.run(command,env=env,cwd=repo,capture_output=True,timeout=45)
  (out/(mode+'.log')).write_bytes(r.stdout+r.stderr)
  rows.append(dict(mode=mode,exit=r.returncode,expected=83 if mode=='crash' else 84 if mode=='effect-crash' else 0))
 except subprocess.TimeoutExpired as e:
  (out/(mode+'.log')).write_bytes((e.stdout or b'')+(e.stderr or b''));rows.append(dict(mode=mode,exit='timeout45s'))
 print(rows[-1],flush=True)
result=dict(cases=rows,source_drift=drift());(out/'results.json').write_text(json.dumps(result,indent=2))
failed=int(bool(result['source_drift']) or any(r['exit']!=(83 if r['mode']=='crash' else 84 if r['mode']=='effect-crash' else 0) for r in rows if r['mode']!='acl'))
sys.exit(failed or next((r['exit'] for r in rows if r['mode']=='acl' and r['exit']!=0),0))
