#!/usr/bin/env python3
"""复现本轮求解与检查命令；写入本证据目录，历史快照保持不变。
原始CLI依赖当前正式文件/原始检查器；先核哈希，漂移时拒绝重跑。
"""
import os,sys,json,subprocess,time,hashlib
from pathlib import Path
E=Path(__file__).resolve().parent;B=E.parent;R=B.parents[2]
env={**os.environ,**{k:'1' for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS','PYTHONDONTWRITEBYTECODE']}}
manifest=json.loads((E/'输入哈希.json').read_text())
for p,v in manifest['files'].items():
    assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==v['sha256'], 'input changed: '+p
candidate=str(E/'候选只读快照.json')
commands=[
 ('A原始入口',[str(B/'检查器A/check_full.py'),candidate,'--out',str(E/'A原始入口.json'),'--time-limit','60'],[1]),
 ('B原始入口',[str(B/'检查器B/check.py'),candidate,'--output',str(E/'B原始入口.json'),'--time-limit','60'],[2]),
 ('A适配复核',[str(E/'版本适配复核.py'),'A'],[1]),
 ('B适配复核',[str(E/'版本适配复核.py'),'B'],[1]),
 ('独立LP',[str(E/'独立LP.py')],[0]),
 ('独立证书回放',[str(E/'独立证书回放.py')],[0]),
 ('A证书回放',[str(B/'检查器A/verify_certificate.py'),candidate,str(E/'A适配复核.json')],[0]),
 ('逐条复核',[str(E/'逐条复核.py')],[0]),
 ('补核与版本对照',[str(E/'补核与版本对照.py')],[0]),
]
status={}
for name,args,expected in commands:
    cmd=[sys.executable,'-B']+args;t=time.monotonic()
    with (E/(name+'.log')).open('w') as f:p=subprocess.run(cmd,cwd=R,env=env,stdout=f,stderr=subprocess.STDOUT)
    status[name]={'command':cmd,'exit_code':p.returncode,'seconds':time.monotonic()-t}
    (E/'执行状态.json').write_text(json.dumps(status,ensure_ascii=False,indent=2)+'\n')
    assert p.returncode in expected,(name,p.returncode)
    if name=='A证书回放':(E/'A证书回放.json').write_bytes((E/'A证书回放.log').read_bytes())
    print(name,p.returncode,flush=True)
