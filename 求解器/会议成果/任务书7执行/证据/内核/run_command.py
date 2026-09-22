"""逐条保存实际命令、cwd、退出码、stdout/stderr；不编译其它目标。"""
from pathlib import Path
import json,subprocess,time,shlex,sys
ROOT=Path('/home/zhuran24/zmd-research-fresh/求解器')
E=Path(__file__).resolve().parent

def run(name,argv,cwd=ROOT,expected=0,timeout=180):
    start=time.monotonic()
    p=subprocess.run([str(a) for a in argv],cwd=cwd,capture_output=True,text=True,timeout=timeout)
    entry={'name':name,'argv':[str(a) for a in argv],'command':shlex.join([str(a) for a in argv]),'cwd':str(cwd),'exit_code':p.returncode,'expected_exit_code':expected,'seconds':round(time.monotonic()-start,3),'stdout':p.stdout,'stderr':p.stderr}
    index=E/'commands.json';old=json.loads(index.read_text()) if index.exists() else []
    log=E/(name+'-'+str(len(old)+1)+'.log');log.write_text(json.dumps(entry,ensure_ascii=False,indent=2)+'\n')
    old.append({k:v for k,v in entry.items() if k not in ('stdout','stderr')}|{'log':str(log)});index.write_text(json.dumps(old,ensure_ascii=False,indent=2)+'\n')
    print(name,'exit',p.returncode,flush=True)
    if expected is not None and p.returncode!=expected:raise AssertionError((name,p.returncode,p.stdout[-3000:],p.stderr[-3000:]))
    return p
if __name__=='__main__':
    r=run(sys.argv[1],sys.argv[2:],expected=None);sys.stdout.write(r.stdout);sys.stderr.write(r.stderr);sys.exit(r.returncode)
