"""Independent read-only protection and four-CPU command observer."""
import os,sys,json,time,subprocess,signal,resource,importlib.util,stat
from pathlib import Path
from audit_files import OUT,IMPL,ROOT,scan,diff,save,sha
BASE=json.loads((OUT/'start-snapshot.json').read_text())
CPUS=set(sorted(os.sched_getaffinity(0))[:4]);os.sched_setaffinity(0,CPUS)
REPO=ROOT/'求解器'
def protect(label):
    now=scan(ROOT,BASE['excludes']);changes=diff(BASE['entries'],now['entries'])
    concurrent=[d for d in changes if d['path'].startswith('求解器/候选约束轮次/')]
    unexpected=[d for d in changes if d not in concurrent]
    save(label+'-protection.json',dict(errors=now['errors'],concurrent=concurrent,unexpected=unexpected))
    assert not now['errors'] and not unexpected,('protected change',label,unexpected)
def observe(pgid):
    rows=[]
    for p in Path('/proc').iterdir():
        if not p.name.isdigit():continue
        try:
            s=(p/'stat').read_text();v=s[s.rindex(')')+2:].split()
            if int(v[2])!=pgid:continue
            tasks=[]
            for t in (p/'task').iterdir():
                try:
                    s=(t/'stat').read_text();v=s[s.rindex(')')+2:].split()
                    tasks.append(dict(tid=int(t.name),state=v[0],affinity=sorted(os.sched_getaffinity(int(t.name))),cpu_ticks=int(v[11])+int(v[12])))
                except (OSError,ValueError):pass
            rows.append(dict(pid=int(p.name),argv=(p/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace'),tasks=tasks))
        except (OSError,ValueError):pass
    return rows
def command(label,argv,cwd,expected=0,env=None):
    protect(label+'-before');e=os.environ.copy()
    for k in ['RUSTC_BOOTSTRAP','RUSTC_WRAPPER','RUSTFLAGS','HEALTH_RUN','KERNEL_TEST_EVIDENCE_DIR','KERNEL_TEST_INSTANCE_DIR']:e.pop(k,None)
    e.update(CARGO_TARGET_DIR=str(REPO/'target'),CARGO_BUILD_JOBS='2',CARGO_PROFILE_DEV_CODEGEN_UNITS='1',CARGO_PROFILE_TEST_CODEGEN_UNITS='1',CARGO_PROFILE_RELEASE_CODEGEN_UNITS='1',RUST_TEST_THREADS='1',RAYON_NUM_THREADS='1',OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',PYTHONDONTWRITEBYTECODE='1',UV_THREADPOOL_SIZE='1',NODE_OPTIONS='--v8-pool-size=1')
    if env:e.update(env)
    start=time.monotonic();ru=resource.getrusage(resource.RUSAGE_CHILDREN);peak=[];total=running=0;violation=None
    with (OUT/(label+'.stdout.log')).open('wb') as out,(OUT/(label+'.stderr.log')).open('wb') as err:
        p=subprocess.Popen(list(map(str,argv)),cwd=cwd,env=e,stdout=out,stderr=err,start_new_session=True)
        try:
            while p.poll() is None:
                rows=observe(p.pid);tasks=[t for r in rows for t in r['tasks']]
                if len(tasks)>total:total=len(tasks);peak=rows
                running=max(running,sum(t['state']=='R' for t in tasks))
                if any(not set(t['affinity'])<=CPUS for t in tasks):
                    violation='affinity escaped';os.killpg(p.pid,signal.SIGTERM);break
                time.sleep(.03)
        finally:code=p.wait()
    seconds=time.monotonic()-start;end=resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu=end.ru_utime+end.ru_stime-ru.ru_utime-ru.ru_stime
    row=dict(label=label,argv=list(map(str,argv)),cwd=str(cwd),returncode=code,expected=expected,seconds=seconds,cpu_seconds=cpu,average_cores=cpu/seconds,max_total_threads=total,max_runnable_threads=running,affinity=sorted(CPUS),violation=violation,peak=peak,environment={k:v for k,v in e.items() if k.startswith(('CARGO_','HEALTH_','KERNEL_','RUST')) or k in ['RAYON_NUM_THREADS','OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','NODE_OPTIONS']},stdout_sha256=sha(OUT/(label+'.stdout.log')),stderr_sha256=sha(OUT/(label+'.stderr.log')))
    save(label+'.command.json',row);protect(label+'-after')
    print(label,code,round(seconds,2),'sec',round(cpu/seconds,3),'cores',flush=True)
    assert code==expected and not violation and cpu/seconds<=6,(label,code,expected,violation)
    return row
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
