#!/usr/bin/env python3
"""局部机位和已有进路保留量联合优化，再用逐格布线评价。

所有中间候选留在实验/局部循环，不把必要子问题的成功当作全厂成功。
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,{6,7,8})
import json,sys,time,random,subprocess,hashlib
from pathlib import Path
B=Path(__file__).resolve().parents[1];OUT=B/'实验/局部循环';OUT.mkdir(exist_ok=True)
C=json.loads((B/'逻辑接法.json').read_text());rng=random.Random(907)
T0=time.monotonic();limit=float(sys.argv[1]) if len(sys.argv)>1 else 3600
incumbent=None;globalbest=None;summary=[]
def read(p):
    try:return json.loads(p.read_text())
    except (ValueError,OSError):return None
def stats(d):
    return (sum(bool(p['cells']) for p in d['paths']),-d.get('power_distance',1000),-d.get('deficit',1000),-sum(len(p['cells']) for p in d['paths']))
def cost(d):
    n,p,df,l=stats(d);return 2500*(325-n)-400*p-450*df-l
def native_seed(d,pref):
    by={u['id']:u for u in d['units']};order=[a.split()[0] for a in (B/'实验/改规划3初值.txt').read_text().splitlines()[1:304]]
    pref.with_suffix('.pos').write_text(''.join(f"{by[u]['x']} {by[u]['y']} {by[u]['d']}\n" for u in order))
    rr=[r for r in d['paths'] if r['cells']]
    with pref.with_suffix('.routes').open('w') as f:
        print(len(rr),file=f)
        for r in rr:
            print(r['r'],len(r['cells']),file=f)
            for x,y,*_ in r['cells']:print(x,y,file=f)
    return pref.with_suffix('.pos'),pref.with_suffix('.routes')
iteration=0
while time.monotonic()-T0<limit:
    pool=[(p,read(p)) for p in (B/'实验').glob('逐路联合*-best.json')]
    pool=[(p,d) for p,d in pool if d and d.get('overlap',0)==0]
    if globalbest:pool.append((OUT/'全局最好.json',globalbest))
    bestpath,best=max(pool,key=lambda z:stats(z[1]))
    if incumbent is None or rng.random()<.4:incumbent=best
    source=incumbent;by={u['id']:u for u in source['units']}
    present={p['r'] for p in source['paths'] if p['cells']};missing=[e for k,e in enumerate(C['logical_feeds']) if k not in present]
    if not missing:break
    e=rng.choice(missing);uid=rng.choice([e['source'],e['target']]);center=by[uid]
    cx,cy=center['x']+center['w']/2,center['y']+center['h']/2
    movable=sorted((u for u in source['units'] if u['type']!=4),key=lambda u:abs(u['x']+u['w']/2-cx)+abs(u['y']+u['h']/2-cy))[:rng.choice([12,18,24,30])]
    chosen=[u['id'] for u in movable];tag=f'{iteration:04d}';pref=OUT/tag
    src=OUT/f'{tag}-source.json';src.write_text(json.dumps(source,ensure_ascii=False,indent=1))
    selection=OUT/f'{tag}-units.json';selection.write_text(json.dumps(chosen))
    with (OUT/f'{tag}-cp.log').open('w') as log:
        proc=subprocess.run([sys.executable,'-B',str(B/'代码/精确摆放修复.py'),str(src),str(rng.choice([3,4,5,6])),str(20),str(pref),'--preserve-routes','--soft-ports','--local-units',str(selection)],stdout=log,stderr=subprocess.STDOUT)
    cpout=read(pref.with_suffix('.json'));status=read(pref.with_name(pref.name+'-status.json'))
    row=dict(iteration=iteration,elapsed=time.monotonic()-T0,source=str(bestpath),source_routes=stats(source)[0],center=uid,movable=chosen,cp=status)
    if cpout:
        pos,paths=native_seed(cpout,OUT/f'{tag}-refine-input')
        ref=OUT/f'{tag}-refine'
        with (OUT/f'{tag}-refine.log').open('w') as log:
            q=subprocess.run(['taskset','-c','6',str(B/'代码/按进路调整2'),str(B/'实验/改规划3初值.txt'),str(1907+iteration),str(ref),'8',str(pos),str(B/'实验/保护进路.txt'),str(paths)],stdout=log,stderr=subprocess.STDOUT)
        d=read(ref.with_name(ref.name+'-best.json'))
        if d:
            row['result']=dict(routes=stats(d)[0],power_distance=d.get('power_distance'),deficit=d.get('deficit'))
            if cost(d)<cost(incumbent) or rng.random()<.15:incumbent=d
            if globalbest is None or stats(d)>stats(globalbest):
                globalbest=d;(OUT/'全局最好.json').write_text(json.dumps(d,ensure_ascii=False,indent=1));native_seed(d,OUT/'全局最好')
        else:row['refine_error']=q.returncode
    summary.append(row);(OUT/'汇总.json').write_text(json.dumps(summary,ensure_ascii=False,indent=1))
    print(json.dumps({k:v for k,v in row.items() if k not in ['movable','cp']},ensure_ascii=False),flush=True)
    iteration+=1
print('结束',iteration,time.monotonic()-T0,flush=True)
