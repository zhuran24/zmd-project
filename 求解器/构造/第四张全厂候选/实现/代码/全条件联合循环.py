#!/usr/bin/env python3
"""局部机位和已有进路保留量联合优化，再用逐格布线评价。

所有中间候选留在实验/局部循环，不把必要子问题的成功当作全厂成功。
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,{6,7,8})
import json,sys,time,random,subprocess,hashlib,heapq
from collections import deque
from pathlib import Path
B=Path(__file__).resolve().parents[1];OUT=B/'实验/全条件连通循环';OUT.mkdir(exist_ok=True)
C=json.loads((B/'逻辑接法.json').read_text());rng=random.Random(907)
T0=time.monotonic();limit=float(sys.argv[1]) if len(sys.argv)>1 else 3600
incumbent=None;globalbest=None;summary=[]
def read(p):
    try:return json.loads(p.read_text())
    except (ValueError,OSError):return None
def stats(d):
    return (sum(bool(p['cells']) for p in d['paths']),-d.get('power_distance',1000),-d.get('deficit',1000),-sum(len(p['cells']) for p in d['paths']))
def analyze(d):
    if '_connection' in d:return d['_connection']
    us={u['id']:u for u in d['units']};occ={(x,y):u['id'] for u in d['units'] for x in range(u['x'],u['x']+u['w']) for y in range(u['y'],u['y']+u['h'])}
    for x in range(63,69):
        for y in range(14,20):occ[x,y]='EMPTY'
    comp={};ci=0
    for x in range(70):
        for y in range(70):
            if (x,y) in occ or (x,y) in comp:continue
            todo=[(x,y)];comp[x,y]=ci
            for a,b in todo:
                for dx,dy in [(1,0),(0,1),(-1,0),(0,-1)]:
                    q=a+dx,b+dy
                    if 0<=q[0]<70 and 0<=q[1]<70 and q not in occ and q not in comp:comp[q]=ci;todo.append(q)
            ci+=1
    def ports(u,inbound):
        x,y,w,h,d=u['x'],u['y'],u['w'],u['h'],u['d'];out=[]
        ss=([d,(d+2)%4] if inbound else [(d+1)%4,(d+3)%4]) if u['type']==3 else [d if inbound or u['type']==4 else (d+2)%4]
        for side in ss:
            off=(range(1,8) if inbound else [1,4,7]) if u['type']==3 else [1] if u['type']==4 else range(h if side%2==0 else w)
            out += [(x+w,y+k) if side==0 else (x+k,y+h) if side==1 else (x-1,y+k) if side==2 else (x+k,y-1) for k in off]
        return [q for q in out if 0<=q[0]<70 and 0<=q[1]<70]
    disconnected=[]
    for e in C['logical_feeds']:
        aa={comp[q] for q in ports(us[e['source']],False) if q in comp};bb={comp[q] for q in ports(us[e['target']],True) if q in comp}
        if not aa&bb:disconnected.append(e['id'])
    return dict(disconnected=disconnected,us=us,occ=occ,ports=ports)
def cost(d):
    n,p,df,l=stats(d);return 2500*(325-n)-400*p-3000*df-l+5000*len(analyze(d)['disconnected'])
def native_seed(d,pref):
    by={u['id']:u for u in d['units']};order=[a.split()[0] for a in (B/'实验/改规划5初值.txt').read_text().splitlines()[1:306]]
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
    pool=[(p,read(p)) for p in (B/'实验').glob('逐路联合9*-best.json')]
    pool=[(p,d) for p,d in pool if d and len(d['units'])==305 and d.get('overlap',0)==0 and d.get('power_distance',1)==0]
    if globalbest:pool.append((OUT/'全局最好.json',globalbest))
    bestpath,best=min(pool,key=lambda z:cost(z[1]))
    if incumbent is None or cost(best)<cost(incumbent):incumbent=best
    source=incumbent;by={u['id']:u for u in source['units']}
    present={p['r'] for p in source['paths'] if p['cells']};missing=[e for k,e in enumerate(C['logical_feeds']) if k not in present]
    if not missing:break
    aa=analyze(source);dis=set(aa['disconnected']);priority=[e for e in missing if e['id'] in dis];e=rng.choice(priority or missing)
    uid=rng.choice([e['source'],e['target']]);center=by[uid]
    # 单路放宽的最短软路径，选择挡路的可动机身作为局部中心。
    fixed_ids={a.split()[0] for a in (B/'实验/改规划5初值.txt').read_text().splitlines()[1:306] if a.split()[-1]=='1'}
    starts=aa['ports'](by[e['source']],False);goals=set(aa['ports'](by[e['target']],True));pq=[];dist={};prev={};end=None
    for q in starts:dist[q]=0;heapq.heappush(pq,(0,q))
    while pq:
        dd,q=heapq.heappop(pq)
        if dd!=dist[q]:continue
        if q in goals:end=q;break
        for dx,dy in [(1,0),(0,1),(-1,0),(0,-1)]:
            z=q[0]+dx,q[1]+dy
            if not(0<=z[0]<70 and 0<=z[1]<70):continue
            owner=aa['occ'].get(z);extra=10000 if owner in fixed_ids or owner=='EMPTY' else 6 if owner else 0
            val=dd+1+extra
            if val<dist.get(z,1e100):dist[z]=val;prev[z]=q;heapq.heappush(pq,(val,z))
    blockers=[]
    if end:
        q=end
        while q in prev:
            owner=aa['occ'].get(q)
            if owner and owner not in fixed_ids and owner!='EMPTY':blockers.append(owner)
            q=prev[q]
    if blockers:uid=rng.choice(blockers);center=by[uid]
    cx,cy=center['x']+center['w']/2,center['y']+center['h']/2
    movable=sorted((u for u in source['units'] if u['type']!=4),key=lambda u:abs(u['x']+u['w']/2-cx)+abs(u['y']+u['h']/2-cy))[:rng.choice([12,18,24,30])]
    chosen=[u['id'] for u in movable];tag=f'{iteration:04d}';pref=OUT/tag
    src=OUT/f'{tag}-source.json';src.write_text(json.dumps(source,ensure_ascii=False,indent=1))
    selection=OUT/f'{tag}-units.json';selection.write_text(json.dumps(chosen))
    with (OUT/f'{tag}-cp.log').open('w') as log:
        proc=subprocess.run([sys.executable,'-B',str(B/'代码/精确摆放修复5.py'),str(src),str(rng.choice([3,4,5,6])),str(20),str(pref),'--preserve-routes','--soft-ports','--require-power','--local-units',str(selection),'--focus-route',e['id']],stdout=log,stderr=subprocess.STDOUT)
    cpout=read(pref.with_suffix('.json'));status=read(pref.with_name(pref.name+'-status.json'))
    row=dict(iteration=iteration,elapsed=time.monotonic()-T0,source=str(bestpath),source_routes=stats(source)[0],center=uid,movable=chosen,cp=status)
    if cpout:
        pos,paths=native_seed(cpout,OUT/f'{tag}-refine-input')
        ref=OUT/f'{tag}-refine'
        with (OUT/f'{tag}-refine.log').open('w') as log:
            q=subprocess.run(['taskset','-c','6',str(B/'代码/全供电按连通'),str(B/'实验/改规划5初值.txt'),str(1907+iteration),str(ref),'8',str(pos),str(B/'实验/保护进路5.txt'),str(paths)],stdout=log,stderr=subprocess.STDOUT)
        d=read(ref.with_name(ref.name+'-best.json'))
        if d:
            row['result']=dict(routes=stats(d)[0],power_distance=d.get('power_distance'),deficit=d.get('deficit'),disconnected=len(analyze(d)['disconnected']),focus_connected=cpout.get('focus_connected_relaxation'))
            if cost(d)<cost(incumbent) or rng.random()<.08:incumbent=d
            if globalbest is None or stats(d)>stats(globalbest):
                globalbest=d;(OUT/'全局最好.json').write_text(json.dumps(d,ensure_ascii=False,indent=1));native_seed(d,OUT/'全局最好')
        else:row['refine_error']=q.returncode
    if incumbent:(OUT/'当前端口候选.json').write_text(json.dumps(incumbent,ensure_ascii=False,indent=1))
    summary.append(row);(OUT/'汇总.json').write_text(json.dumps(summary,ensure_ascii=False,indent=1))
    print(json.dumps({k:v for k,v in row.items() if k not in ['movable','cp']},ensure_ascii=False),flush=True)
    iteration+=1
print('结束',iteration,time.monotonic()-T0,flush=True)
