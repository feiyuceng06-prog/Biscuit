"""Run from disposable local-fixed-NTFS Windows checkout; no install or network needed.
python windows_run.py <repo> <NEW-scratch-directory>
Preserve output, JSON exit codes and source drift check. Timeout 45s/case; no retries.
"""
import os,sys,pathlib,subprocess,json,hashlib
if os.name!='nt':sys.exit(77)
repo=pathlib.Path(sys.argv[1]).resolve();out=pathlib.Path(sys.argv[2]).absolute();out.mkdir(exist_ok=False)
probe=pathlib.Path(__file__).parent
manifest=json.loads((probe/'baseline-sha256.json').read_text())
def drift():return [f for f,h in manifest.items() if hashlib.sha256((repo/f).read_bytes()).hexdigest()!=h]
assert not drift(),'source differs from review baseline'
env={k:v for k,v in os.environ.items() if k.upper() in ('PATH','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC','PATHEXT')}
env.update(PYTHONPATH=str(repo),PYTHONDONTWRITEBYTECODE='1')
rows=[]
for mode in ['conversation','legacy','failure','crash','recover','effect-crash','effect-recover','acl']:
 case='crash' if mode=='recover' else 'effect-crash' if mode=='effect-recover' else mode
 command=[sys.executable,str(probe/'windows_acl_probe.py'),str(out/case)] if mode=='acl' else [sys.executable,str(probe/'product_probe.py'),str(out/case),mode]
 try:
  r=subprocess.run(command,env=env,cwd=repo,capture_output=True,timeout=45)
  (out/(mode+'.log')).write_bytes(r.stdout+r.stderr)
  rows.append(dict(mode=mode,exit=r.returncode,expected=83 if mode=='crash' else 84 if mode=='effect-crash' else '0 or 20 (diagnostic)' if mode=='acl' else 0))
 except subprocess.TimeoutExpired as e:
  (out/(mode+'.log')).write_bytes((e.stdout or b'')+(e.stderr or b''));rows.append(dict(mode=mode,exit='timeout45s'))
 print(rows[-1],flush=True)
result=dict(cases=rows,source_drift=drift());(out/'results.json').write_text(json.dumps(result,indent=2))
failed=int(bool(result['source_drift']) or any(r['exit']!=(83 if r['mode']=='crash' else 84 if r['mode']=='effect-crash' else 0) for r in rows if r['mode']!='acl'))
sys.exit(failed or next((r['exit'] for r in rows if r['mode']=='acl' and r['exit']!=0),0))
