#!/usr/bin/env python3
"""全325路的格点联合模型，机位在当前候选邻域内，允许相邻桥。"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,{6,7,8,9,10,11})
import json,sys,resource,importlib.util,traceback
from pathlib import Path
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
memory_gib=int(os.environ.get('FULL_MEMORY_GIB','10'));resource.setrlimit(resource.RLIMIT_AS,(memory_gib*1024**3,memory_gib*1024**3))
B=Path(__file__).resolve().parents[1]
sp=importlib.util.spec_from_file_location('full_grid',B/'代码/全厂格点联合.py');cp=importlib.util.module_from_spec(sp);sp.loader.exec_module(cp)
seed=int(os.environ.get('FULL_SEED','1109'));workers=int(os.environ.get('FULL_WORKERS','6'));os.sched_setaffinity(0,set(range(6,6+workers)))
raw=json.loads(Path(sys.argv[1]).read_text());c=json.loads((B/'逻辑接法.json').read_text());radius=int(sys.argv[2]);limit=float(sys.argv[3]);out=Path(sys.argv[4])
near={};fixed={};pole_map={};pn=0
original_flags={p.split()[0]:int(p.split()[-1]) for p in (B/'实验/改规划6初值.txt').read_text().splitlines()[1:304]}
for u in raw['units']:
    uid=u['id'];t=u['type'];name=uid
    if t==5:name=f'POWER{pn}';pole_map[name]=uid;pn+=1
    di=u['d']%2 if t==3 else u['d']
    p=dict(x0=u['x'],y0=u['y'],x1=u['x']+u['w']-1,y1=u['y']+u['h']-1,Din=di,kind='machine' if t<=2 else 'core' if t==3 else 'outlet' if t==4 else 'pole')
    near[name]=p
    # 保护既定机器、全部当前供电桩；22个蓝铁矿取货口仍可换身份。
    if t==5 or t<=2 and original_flags.get(uid) and (os.environ.get('FULL_RELEASE_TEMPLATES')!='1' or uid in ['H6','Q6','F4']):fixed[name]=p
tokens=list(map(int,(B/'实验/保护进路5.txt').read_text().split()));at=1;protected=[]
for _ in range(tokens[0]):
    k,n=tokens[at:at+2];at+=2+2*n;protected.append(k)
    e=c['logical_feeds'][k]
    if e['source'].startswith('W') and os.environ.get('FULL_RELEASE_TEMPLATES')!='1':fixed[e['source']]=near[e['source']]
paths=[]
for r in raw['paths']:
    if not r['cells']:continue
    e=c['logical_feeds'][r['r']];paths.append(dict(e,cells=[q[:2] for q in r['cells']],start=[*r['source'][:2],(r['source'][2]+2)%4],end=[*r['target'][:2],(r['target'][2]+2)%4]))
meta=dict(input=str(Path(sys.argv[1]).resolve()),radius=radius,limit=limit,seed=seed,workers=workers,memory_gib=memory_gib,cpu_affinity=sorted(os.sched_getaffinity(0)),feasibility_only=os.environ.get('FULL_FEASIBILITY_ONLY')=='1',released_templates=os.environ.get('FULL_RELEASE_TEMPLATES')=='1',power_name_map=pole_map,fixed_units=sorted(fixed),scope='全230台和325条路径；固定单位见fixed_units，其他机位在邻域内。运输逐格，桥可相邻，要求两条末端进路同长。')
out.with_name(out.stem+'-范围.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
try:
    result=cp.build(c,70,70,rect=(63,14,6,6),fixed=fixed,limit=limit,workers=workers,seed=seed,out=out,polenum=pn,near=near,radius=radius,no_lp=False,near_paths=paths)
except (MemoryError,RuntimeError) as e:
    out.with_name(out.stem+'-异常.json').write_text(json.dumps(dict(status='ERROR_OR_MEMORY_LIMIT',error=repr(e),traceback=traceback.format_exc()),ensure_ascii=False,indent=2));raise
