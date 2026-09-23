import json,shutil,subprocess,re
from pathlib import Path
from continuation_guard import RUN,sha,write

def bind():
 paths=set();tools={}
 for name in ['rustc','cargo','cargo-clippy','clippy-driver','cc','ld']:
  p=Path(shutil.which(name)).resolve();paths.add(p);tools[name]=str(p)
  ldd=subprocess.run(['ldd',str(p)],capture_output=True,text=True)
  for s in re.findall(r'(/[^\s()]+)',ldd.stdout):
   f=Path(s).resolve()
   if f.is_file():paths.add(f)
 rows=[json.loads(s) for s in (RUN/'continue-production-a.stdout.log').read_text().splitlines() if s.startswith('{')]
 packages=[]
 for row in rows:
  if row.get('reason')!='compiler-artifact':continue
  p=Path(row['manifest_path']).parent
  if '/registry/src/' not in str(p):continue
  packages.append(str(p))
  for f in p.rglob('*'):
   if f.is_file():paths.add(f.resolve())
 root=Path(subprocess.check_output(['rustc','--print','sysroot'],text=True).strip())/'lib/rustlib'
 for f in root.rglob('*'):
  if f.is_file():paths.add(f.resolve())
 result=dict(tools=tools,registry_packages=sorted(set(packages)),files={str(p):sha(p) for p in sorted(paths)})
 write(RUN/'continuation-build-inputs.json',result);return result

def verify():
 data=json.loads((RUN/'continuation-build-inputs.json').read_text())
 for path,digest in data['files'].items():assert sha(path)==digest,('build input changed',path)
 return data
