#!/usr/bin/env python3
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
import argparse,json,random,subprocess
from pathlib import Path
from collections import Counter,defaultdict
from joint_cp import BASE,save
a=argparse.ArgumentParser();a.add_argument('--seed',type=int,default=1);a.add_argument('--seconds',type=float,default=90);a.add_argument('--resume');a.add_argument('--poles',type=int,choices=[16,25],default=25);a.add_argument('--movable-poles',action='store_true');a.add_argument('--connected',action='store_true');a.add_argument('--sources-clear',action='store_true');a.add_argument('--ports-in-base',action='store_true');p=a.parse_args();c=json.loads((BASE/'逻辑接法.json').read_text());spec={u['id']:u for u in c['machines']};rng=random.Random(p.seed);nin=Counter(e['target'] for e in c['logical_feeds']);nout=Counter(e['source'] for e in c['logical_feeds'])
groups={};adj=defaultdict(set)
for e in c['logical_feeds']:
 if e['source'] in spec and e['target'] in spec:adj[e['source']].add(e['target']);adj[e['target']].add(e['source'])
centers={'E1':(20,20),'E2':(13,31),'E3':(31,13),'F1':(17,54),'F2':(54,17),'F3':(43,54),'F4':(56,48)}
for f in centers:
 seen={f};todo=[f]
 while todo:
  for v in adj[todo.pop()]:
   if v not in seen:seen.add(v);todo.append(v)
 for v in seen:groups[v]=f
rows=[]
resume=json.loads(Path(p.resume).read_text())['placements'] if p.resume else {}
for uid,u in spec.items():
 k={'小':0,'中':1,'大':2}[u['kind']];cx,cy=centers[groups[uid]];x=max(1,min(62,round(rng.gauss(cx-2,9))));y=max(1,min(62,round(rng.gauss(cy-2,9))));d=rng.randrange(4)
 if uid in resume:x,y,d=resume[uid]['x0'],resume[uid]['y0'],resume[uid]['Din']
 if p.sources_clear:x=max(2,x);y=max(2,y)
 if p.ports_in_base:
  width,height=(3,3) if k==0 else (5,5) if k==1 else ((4,6) if d%2==0 else (6,4))
  if d%2==0:x=min(x,69-width)
  else:y=min(y,69-height)
 rows.append([uid,k,0,x,y,d,nin[uid],nout[uid]])
q=resume.get('CORE',dict(x0=16,y0=16,Din=0));rows.append(['CORE',3,0,q['x0'],q['y0'],q['Din'],7,6])
left=['WFE1','WFE2']+[f'WFE{j}' for j in range(5,9)]+[f'WO{j}' for j in range(7,13)]+[f'WFE{j}' for j in range(13,21)]+[f'WFE{j}' for j in range(29,32)]
bottom=['WFE3','WFE4']+[f'WFE{j}' for j in range(9,13)]+[f'WO{j}' for j in range(13,19)]+[f'WFE{j}' for j in range(21,29)]+['WFE32','WFE33','WFE34']
for i,uid in enumerate(left+bottom):j=i%23;side=0 if i<23 else 1;rows.append([uid,4 if side==0 else 5,1,0 if side==0 else 1+3*j,1+3*j if side==0 else 0,side,0,1])
poles=([(x,y) for x in (8,22,36,50,64) for y in (8,22,36,50,64) if (x,y)!=(64,64)]+[(60,60)]) if p.poles==25 else [(x,y) for x in (9,26,43,60) for y in (9,26,43,60)]
for i,(x,y) in enumerate(poles):rows.append(['POWER'+str(i),6,int(not p.movable_poles),x,y,0,0,0])
ix={u[0]:i for i,u in enumerate(rows)};inp=BASE/f'实验/anneal-{p.seed}.input.txt';out=BASE/f'实验/anneal-{p.seed}.coordinates.txt';inp.write_text(f'{len(rows)} {len(c["logical_feeds"])} 64 64 6 6\n'+'\n'.join(' '.join(map(str,r)) for r in rows)+'\n'+'\n'.join(f'{ix[e["source"]]} {ix[e["target"]]}' for e in c['logical_feeds'])+'\n')
with (BASE/f'实验/anneal-{p.seed}.log').open('w') as f:subprocess.run([str(BASE/'代码'/('anneal_sources2' if p.ports_in_base else 'anneal_sources' if p.sources_clear else 'anneal_connected' if p.connected else 'anneal')),str(inp),str(out),str(p.seconds),str(p.seed)],stdout=f,stderr=subprocess.STDOUT,check=True)
lines=out.read_text().splitlines();ov,po,pw,wi,it,tm=lines[0].split();placed={};anon=[]
for line in lines[1:]:
 uid,k,x,y,d=line.split();k,x,y,d=map(int,(k,x,y,d));w,h=(3,3) if k==0 else (5,5) if k==1 else ((4,6) if d%2==0 else (6,4)) if k==2 else (9,9) if k==3 else (1,3) if k==4 else (3,1) if k==5 else (2,2);u=dict(x0=x,y0=y,x1=x+w-1,y1=y+h-1,Din=d,kind='machine' if k<3 else 'core' if k==3 else 'outlet' if k<6 else 'pole');placed[uid]=u
 if k<3:anon.append(dict(u,id=uid,kind=spec[uid]['kind']))
poles=[(u['x0'],u['y0']) for uid,u in placed.items() if u['kind']=='pole']
result=dict(schema='s2-annealed-placement-v1',is_layout=False,status='PARTIAL_PLACEMENT',seed=p.seed,overlap_cells=int(ov),port_deficit=int(po),unpowered=int(pw),wire_cost=int(wi),iterations=int(it),seconds=float(tm),placements=placed,units=anon,core=placed['CORE'],poles=poles,rect=[64,64,6,6]);save(BASE/f'实验/anneal-{p.seed}.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ('placements','units','core','poles')},ensure_ascii=False))
