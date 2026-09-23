"""Bounded, recorded commands with protection checks and actual thread observations."""
import hashlib, json, os, subprocess, time
from pathlib import Path
import guarded
RUN=Path(__file__).resolve().parent

def write(path,data): Path(path).write_text(json.dumps(data,ensure_ascii=False,indent=2)+"\n")
def sha(p):
 with open(p,"rb") as f:return hashlib.file_digest(f,"sha256").hexdigest()
def processes(pid):
 rows={}
 for p in Path("/proc").iterdir():
  if not p.name.isdigit():continue
  try:
   s=(p/"stat").read_text(); tail=s[s.rindex(")")+2:].split()
   rows[int(p.name)]=(int(tail[1]),int(tail[17]),s[s.index("(")+1:s.rindex(")")])
  except (OSError,ValueError):pass
 result={pid};last=set()
 while last!=result:
  last=set(result);result|={p for p,(parent,_,_) in rows.items() if parent in result}
 observed=[]
 for p in result:
  if p not in rows:continue
  try:
   d=Path("/proc")/str(p)
   observed.append({"pid":p,"threads":rows[p][1],"name":rows[p][2],"argv":(d/"cmdline").read_bytes().replace(b"\0",b" ").decode(errors="replace"),"tasks":[t.joinpath("comm").read_text().strip() for t in (d/"task").iterdir()]})
  except (OSError,ProcessLookupError):pass
 return observed

def command(label,argv,cwd=None,expected=0):
 guarded.check(label+"-before");start=time.time();max_threads=0;peak=[]
 with (RUN/(label+".stdout.log")).open("wb") as out,(RUN/(label+".stderr.log")).open("wb") as err:
  p=subprocess.Popen(list(map(str,argv)),cwd=cwd,stdout=out,stderr=err)
  try:
   while p.poll() is None:
    rows=processes(p.pid);count=sum(x["threads"] for x in rows)
    if count>max_threads:
     max_threads=count;peak=rows;write(RUN/(label+".thread-peak.json"),dict(max_threads=count,peak=rows))
    time.sleep(.02)
  finally:
   code=p.wait()
   guarded.check(label+"-after")
 row=dict(label=label,argv=list(map(str,argv)),cwd=str(cwd or Path.cwd()),returncode=code,expected=expected,seconds=time.time()-start,max_threads=max_threads,peak=peak,affinity=sorted(os.sched_getaffinity(0)),stdout_sha256=sha(RUN/(label+".stdout.log")),stderr_sha256=sha(RUN/(label+".stderr.log")))
 write(RUN/(label+".command.json"),row);print(label,code,"threads",max_threads,flush=True)
 if code!=expected:raise RuntimeError(label+": unexpected exit "+str(code)+"; see raw logs")
 if max_threads>6:raise RuntimeError(label+": thread budget exceeded "+str(max_threads))
 return row
