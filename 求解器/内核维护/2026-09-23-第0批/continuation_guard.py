"""Continuation protection and CPU-budget observer; no Git mutations."""
import os,sys,json,time,hashlib,subprocess,signal,resource
from pathlib import Path
import bootstrap_guard as g
RUN=Path(__file__).resolve().parent
BASE=json.loads((RUN/'continuation-start.json').read_text())
REPO=Path(BASE['root'])/'求解器'
CPUS=set(sorted(os.sched_getaffinity(0))[:4])
os.sched_setaffinity(0,CPUS)
def sha(p): return g.digest(p)
def write(p,d): g.write(p,d)
def check(label):
 now=g.scan(BASE['root'],BASE['excludes']); diff=g.changes(BASE,now)
 markers=json.loads((RUN/'continuation-markers-approved.json').read_text()) if (RUN/'continuation-markers-approved.json').exists() else {}
 tools=json.loads((RUN/'continuation-tools-approved.json').read_text()) if (RUN/'continuation-tools-approved.json').exists() else {}
 markers.update(tools)
 concurrent=[x for x in diff if x['path'].startswith('求解器/候选约束轮次/') or (x['path']=='候选约束.txt' and (RUN/'continuation-external-drift.json').exists())]
 allowed=[x for x in diff if x['path'] in markers and x['before'] is None and x['after']==markers[x['path']]]
 edits=json.loads((RUN/'continuation-edits-approved.json').read_text()) if (RUN/'continuation-edits-approved.json').exists() else {}
 allowed += [x for x in diff if x['path'] in edits and x['before']==edits[x['path']]['before'] and x['after']==edits[x['path']]['after']]
 bad=[x for x in diff if x not in concurrent and x not in allowed]
 write(RUN/(label+'-protection.json'),dict(unexpected=bad,authorized_markers=allowed,concurrent=concurrent))
 if bad: raise RuntimeError('protected changes: '+str([x['path'] for x in bad]))
 return now

def observe(pgid):
 rows=[]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit(): continue
  try:
   raw=(p/'stat').read_text(); a=raw[raw.rindex(')')+2:].split()
   if int(a[2])!=pgid: continue
   tasks=[]
   for t in (p/'task').iterdir():
    try:
     raw=(t/'stat').read_text(); s=raw[raw.rindex(')')+2:].split(); aff=set(os.sched_getaffinity(int(t.name)))
     tasks.append(dict(tid=int(t.name),state=s[0],cpu_ticks=int(s[11])+int(s[12]),affinity=sorted(aff),name=(t/'comm').read_text().strip()))
    except (OSError,ValueError): pass
   rows.append(dict(pid=int(p.name),argv=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace'),tasks=tasks))
  except (OSError,ValueError): pass
 return rows

def command(label,argv,cwd=None,expected=0,env=None):
 check(label+'-before'); e=os.environ.copy();e.update(CARGO_TARGET_DIR=str(REPO/'target'),CARGO_BUILD_JOBS='2',CARGO_PROFILE_DEV_CODEGEN_UNITS='1',CARGO_PROFILE_TEST_CODEGEN_UNITS='1',CARGO_PROFILE_RELEASE_CODEGEN_UNITS='1',RUST_TEST_THREADS='1',RAYON_NUM_THREADS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',UV_THREADPOOL_SIZE='1',NODE_OPTIONS='--v8-pool-size=1')
 for k in ['RUSTC_BOOTSTRAP','RUSTC_WRAPPER','RUSTFLAGS']: e.pop(k,None)
 if env: e.update(env)
 start=time.monotonic(); ru=resource.getrusage(resource.RUSAGE_CHILDREN); total=running=0;peak=[]; violation=None
 with (RUN/(label+'.stdout.log')).open('wb') as out,(RUN/(label+'.stderr.log')).open('wb') as err:
  p=subprocess.Popen(list(map(str,argv)),cwd=cwd or REPO,env=e,stdout=out,stderr=err,start_new_session=True)
  try:
   while p.poll() is None:
    rows=observe(p.pid);tasks=[t for r in rows for t in r['tasks']];n=len(tasks);nr=sum(t['state']=='R' for t in tasks)
    if n>total: total=n;peak=rows
    running=max(running,nr)
    if any(not set(t['affinity'])<=CPUS for t in tasks):
     violation='CPU affinity escaped';os.killpg(p.pid,signal.SIGTERM);break
    time.sleep(.025)
  finally:
   code=p.wait(); elapsed=time.monotonic()-start; end=resource.getrusage(resource.RUSAGE_CHILDREN)
   protection_error=None
   try: check(label+'-after')
   except Exception as ex: protection_error=repr(ex)
 cpu=end.ru_utime+end.ru_stime-ru.ru_utime-ru.ru_stime
 row=dict(label=label,argv=list(map(str,argv)),cwd=str(cwd or REPO),returncode=code,expected=expected,seconds=elapsed,cpu_seconds=cpu,cpu_cores_average=cpu/elapsed,max_total_threads=total,max_runnable_threads=running,affinity=sorted(CPUS),peak=peak,violation=violation,protection_error=protection_error,environment={k:v for k,v in e.items() if k.startswith(('CARGO_','RUST','HEALTH_','KERNEL_')) or k in ['PATH','RAYON_NUM_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','NODE_OPTIONS']},stdout_sha256=sha(RUN/(label+'.stdout.log')),stderr_sha256=sha(RUN/(label+'.stderr.log')))
 write(RUN/(label+'.command.json'),row); print(label,code,round(elapsed,2),'sec; average cores',round(cpu/elapsed,3),'total threads',total,flush=True)
 if code!=expected or violation or protection_error or cpu/elapsed>6: raise RuntimeError(label+': rejected; see command and raw logs')
 return row
if __name__=='__main__': command(sys.argv[1],sys.argv[2:])
