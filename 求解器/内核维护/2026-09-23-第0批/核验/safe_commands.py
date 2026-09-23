#!/usr/bin/env python3
import datetime,json,os,signal,subprocess,time,shutil
from pathlib import Path
from audit_files import ROOT,OUT,save,sha
SRC=ROOT/'求解器'
PROFILE='healthaudit'+str(time.time_ns())
env=os.environ.copy()
for k in list(env):
 if k.startswith(('HEALTH_','CARGO_','RUST','KERNEL_')):env.pop(k)
env.update(CARGO_TARGET_DIR=str(SRC/'target'),CARGO_BUILD_JOBS='1',CARGO_PROFILE_DEV_CODEGEN_UNITS='1',CARGO_PROFILE_TEST_CODEGEN_UNITS='1',CARGO_PROFILE_RELEASE_CODEGEN_UNITS='1',RUST_TEST_THREADS='1',RAYON_NUM_THREADS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',GIT_OPTIONAL_LOCKS='0',CARGO_INCREMENTAL='0',RUSTC_BOOTSTRAP='1',RUSTC_WRAPPER=str(OUT/'rustc_serial.py'),RUSTFLAGS='-Z threads=1 -Z no-parallel-backend -C linker=clang -C link-arg=-fuse-ld=lld -C link-arg=-Wl,--threads=1',UV_THREADPOOL_SIZE='1',NODE_OPTIONS='--v8-pool-size=1')
def processes(rootpid):
 # Follow children of every thread, then read actual thread counts/names. No process name filtering.
 queue=[rootpid];seen=set();rows=[]
 while queue:
  pid=queue.pop()
  if pid in seen:continue
  seen.add(pid);p=Path('/proc')/str(pid)
  try:
   status=dict(l.split(':',1) for l in (p/'status').read_text().splitlines() if ':' in l)
   tids=list((p/'task').iterdir());names=[]
   for t in tids:
    try:
     names.append((t/'comm').read_text().strip());queue.extend(map(int,(t/'children').read_text().split()))
    except (OSError,ValueError):pass
   rows.append({'pid':pid,'threads':int(status['Threads']),'name':status['Name'].strip(),'state':status['State'].strip(),'thread_names':names,'argv':(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')})
  except (OSError,ValueError):pass
 return rows

def run(label,argv):
 start=time.monotonic();peak=0;peakrows=[];reason=None;observed=set()
 with (OUT/(label+'.stdout.log')).open('wb') as o,(OUT/(label+'.stderr.log')).open('wb') as e:
  p=subprocess.Popen(argv,cwd=SRC,env=env,stdout=o,stderr=e,start_new_session=True)
  try:
   while p.poll() is None:
    rows=processes(p.pid);observed.update(r['pid'] for r in rows);n=sum(r['threads'] for r in rows)
    if n>peak:peak=n;peakrows=rows
    if n+1>6:
     reason='thread_budget_exceeded';os.killpg(p.pid,signal.SIGTERM);break
    if time.monotonic()-start>55:
     reason='timeout';os.killpg(p.pid,signal.SIGTERM);break
    time.sleep(.005)
   try:code=p.wait(timeout=3)
   except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);code=p.wait()
  finally:
   if p.poll() is None:os.killpg(p.pid,signal.SIGKILL);p.wait()
 row={'label':label,'argv':argv,'cwd':str(SRC),'profile':PROFILE,'exit_code':code,'guard_reason':reason,'passed':code==0 and reason is None,'command_tree_peak_threads':peak,'observer_threads':1,'total_observed_lower_bound':peak+1,'peak_processes':peakrows,'seconds':time.monotonic()-start,'cpu_affinity':sorted(os.sched_getaffinity(0)),'environment':{k:v for k,v in env.items() if k.startswith(('CARGO_','RUST','HEALTH_','KERNEL_')) or k in ['RAYON_NUM_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','PYTHONDONTWRITEBYTECODE','GIT_OPTIONAL_LOCKS','UV_THREADPOOL_SIZE','NODE_OPTIONS']},'stdout_sha256':sha(OUT/(label+'.stdout.log')),'stderr_sha256':sha(OUT/(label+'.stderr.log'))}
 save(label+'.json',row);print(json.dumps({k:row[k] for k in ['label','exit_code','guard_reason','command_tree_peak_threads','total_observed_lower_bound','seconds']}),flush=True)
 return row
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
versions=[]
for program,args in [('rustc',['-Vv']),('cargo',['-V']),('python',['--version']),('clang',['--version'])]:
 p=Path(shutil.which(program));result=run('version-fixed-'+program,[str(p),*args]);versions.append({'name':program,'invoked':str(p),'resolved':str(p.resolve()),'sha256':sha(p.resolve()),'accepted':result['passed']})
save('toolchain.json',versions)
metadata=run('metadata-fixed',[shutil.which('cargo'),'metadata','--locked','--offline','--no-deps','--format-version','1'])
if not metadata['passed']:raise SystemExit(2)
args=['--profile',PROFILE,'--config',f'profile.{PROFILE}.inherits="dev"','--config',f'profile.{PROFILE}.codegen-units=1']
build=run('safe-build-fixed',[shutil.which('cargo'),'build','--locked','--offline','--workspace','-j','1',*args])
save('execution-gates.json',{'safe_build':build['passed'],'safe_regression_rounds_completed':0,'cli_suite_executed':False,'cli_reason':'isolation-accepted.json and kernel_regression.py check-isolation absent','stop_after':build['label'],'no_tests_claimed':True})
raise SystemExit(0 if build['passed'] else 2)
