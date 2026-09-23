import json,shutil
from pathlib import Path
from continuation_guard import *
f=json.loads((RUN/'continuation-freeze.json').read_text());S=Path(f['source_root']);profile=f['continuation_profile']
for x in f['files']:assert sha(Path(f['root'])/x['path'])==x['sha256']
args=['cargo','build','--locked','--offline','--workspace','--bins','-j','2','--profile',profile,'--config',f'profile.{profile}.inherits="dev"','--config',f'profile.{profile}.codegen-units=1','--message-format=json']
command('continue-production-a',args,S)
rows=[json.loads(s) for s in (RUN/'continue-production-a.stdout.log').read_text().splitlines() if s.startswith('{')]
art=[x for x in rows if x.get('reason')=='compiler-artifact' and str(S) in x.get('manifest_path','')]
seal=REPO/'target'/'health-capture'/'continuation-20260923'/'production-a';seal.mkdir(parents=True,exist_ok=False)
for a in art:
 assert not a['fresh'];assert Path(a['manifest_path']).resolve().is_relative_to(S)
 if a.get('executable'):
  assert str(S).encode() in Path(a['executable']).read_bytes();a['sha256']=sha(a['executable']);shutil.copy2(a['executable'],seal/a['target']['name']);a['sealed']=str(seal/a['target']['name'])
write(RUN/'continuation-production-a-artifacts.json',art)
for x in f['files']:assert sha(Path(f['root'])/x['path'])==x['sha256']
check('continue-production-a-seal-after')
