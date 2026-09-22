from pathlib import Path
import os, json, hashlib, subprocess, shlex
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器')
OUT=ROOT/'内核维护/2026-09-22d/R2-来源与计时'
TARGET=ROOT/'target'
ENV=dict(os.environ, CARGO_TARGET_DIR=str(TARGET), CARGO_BUILD_JOBS='1', RAYON_NUM_THREADS='1', OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', UV_THREADPOOL_SIZE='1', NODE_OPTIONS='--v8-pool-size=1', PYTHONDONTWRITEBYTECODE='1', GIT_OPTIONAL_LOCKS='0')
CPUS=sorted(os.sched_getaffinity(0))[:6]
os.sched_setaffinity(0,CPUS)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def dump(p,v):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def run(name,args,cwd=ROOT,timeout=180):
 args=list(map(str,args)); dest=OUT/name;dest.parent.mkdir(parents=True,exist_ok=True)
 result=subprocess.run(args,cwd=cwd,env=ENV,capture_output=True,timeout=timeout)
 Path(str(dest)+'.stdout.log').write_bytes(result.stdout);Path(str(dest)+'.stderr.log').write_bytes(result.stderr)
 meta=dict(argv=args,shell_command=shlex.join(args),cwd=str(cwd),returncode=result.returncode,stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),stderr_sha256=hashlib.sha256(result.stderr).hexdigest(),cpu_affinity=CPUS)
 dump(str(dest)+'.command.json',meta)
 return result
def changes(a,b,p='$'):
 if type(a)!=type(b):return [dict(path=p,a=a,b=b)]
 if isinstance(a,dict):
  out=[]
  for k in sorted(a.keys()|b.keys()):
   q=p+'['+json.dumps(k,ensure_ascii=False)+']'
   if k not in a or k not in b:out.append(dict(path=q,a=a.get(k),b=b.get(k),missing='a' if k not in a else 'b'))
   else:out+=changes(a[k],b[k],q)
  return out
 if isinstance(a,list):
  out=[] if len(a)==len(b) else [dict(path=p+'.length',a=len(a),b=len(b))]
  for i,(x,y) in enumerate(zip(a,b)):out+=changes(x,y,f'{p}[{i}]')
  return out
 return [] if a==b else [dict(path=p,a=a,b=b)]
def byte_diff(a,b):
 try:return dict(byte_equal=a==b,json_differences=changes(json.loads(a),json.loads(b)))
 except (ValueError,UnicodeDecodeError):return dict(byte_equal=a==b,text_a=a.decode(errors='replace') if a!=b else None,text_b=b.decode(errors='replace') if a!=b else None)
