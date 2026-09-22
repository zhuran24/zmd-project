#!/usr/bin/env python3
import hashlib, json, os, subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
TARGET=ROOT/'target'
env={**os.environ,'CARGO_TARGET_DIR':str(TARGET),'CARGO_BUILD_JOBS':'6','RAYON_NUM_THREADS':'6','OMP_NUM_THREADS':'6','GIT_OPTIONAL_LOCKS':'0'}
# Restrict this runner and children to at most six CPUs as well as Cargo jobs.
os.sched_setaffinity(0, sorted(os.sched_getaffinity(0))[:6])
commands=[]
def run(args, stdout, stderr):
 with (OUT/stdout).open('w') as out, (OUT/stderr).open('w') as err:
  p=subprocess.run(args,cwd=ROOT,env=env,stdout=out,stderr=err)
 commands.append({'argv':args,'cwd':str(ROOT),'exit_code':p.returncode,'stdout':stdout,'stderr':stderr})
 if p.returncode:
  print((OUT/stderr).read_text())
  raise SystemExit(p.returncode)
run(['cargo','build','--locked','--offline','--lib','-p','kernel','-j','6','--message-format=json'],'build.json','build.log')
artifacts={}
for line in (OUT/'build.json').read_text().splitlines():
 r=json.loads(line)
 if r.get('reason')=='compiler-artifact':
  for name in r['filenames']:
   if name.endswith('.rlib'): artifacts[r['target']['name']]=name
binary=TARGET/'debug'/'r1_state_boundary_probe'
run(['rustc','--edition=2021','--crate-name','r1_state_boundary_probe',str(OUT/'probe.rs'),'-C','codegen-units=1','-L',f'dependency={TARGET}/debug/deps','--extern',f'kernel={artifacts["kernel"]}','--extern',f'serde_json={artifacts["serde_json"]}','-o',str(binary)],'compile.log','compile-stderr.log')
run([str(binary),str(ROOT)],'probe.json','probe.log')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
meta={'commands':commands,'environment':{k:env[k] for k in ['CARGO_TARGET_DIR','CARGO_BUILD_JOBS','RAYON_NUM_THREADS','OMP_NUM_THREADS']},'cpu_affinity':sorted(os.sched_getaffinity(0)), 'rustc':subprocess.check_output(['rustc','-Vv'],env=env,text=True),'cargo':subprocess.check_output(['cargo','-V'],env=env,text=True),'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,env=env,text=True).strip(),'hashes':{str(p):sha(p) for p in [binary,OUT/'probe.rs',ROOT/'数据/样例/生产循环环带.json',ROOT/'规格/内核配置-v1.json']}}
(OUT/'run.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2)+'\n')
r=json.loads((OUT/'probe.json').read_text())
# Independent JSON diff: confirm the perturbation really is one leaf.
def diff(a,b,path='$'):
 if type(a)!=type(b):return [path]
 if isinstance(a,dict):return sum((diff(a.get(k),b.get(k),path+'.'+k) for k in a.keys()|b.keys()),[])
 if isinstance(a,list):
  if len(a)!=len(b):return [path]
  return sum((diff(x,y,f'{path}[{i}]') for i,(x,y) in enumerate(zip(a,b))),[])
 return [] if a==b else [path]
diffs=diff(r['before_state'],r['after_state'])
assert diffs==['$.'+r['mutation']['path'].removeprefix('state.')],diffs
summary={'verdict':r['verdict'],'time':[r['initial_time'],r['after_step_time']],'mutation':r['mutation'],'state_diffs':diffs,'before':{k:v['result'] for k,v in r['before'].items()},'after':{k:v.get('stop',v['result']) for k,v in r['after'].items()},'restored':{k:v['result'] for k,v in r['restored'].items()}}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
