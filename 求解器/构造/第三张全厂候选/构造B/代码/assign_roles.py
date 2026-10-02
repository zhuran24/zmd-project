#!/usr/bin/env python3
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,sys,random,math,time,copy
from collections import defaultdict,Counter,deque
from pathlib import Path
from scipy.optimize import linear_sum_assignment
from pack_factory import machine,cells,C,MC,BASE,edge,D
from route_factory import ports
raw=json.loads(Path(sys.argv[1]).read_text());l=raw['fixed'];slots=raw['moving'];todo=raw['todo'];rect=raw['reserved_rectangle'];seed=int(sys.argv[2]) if len(sys.argv)>2 else 1;rng=random.Random(seed)
ni=Counter(f['target'] for f in C['feeds']);no=Counter(f['source'] for f in C['feeds']);fixed={u['id']:u for u in l['machines']}
# Every occupied machine footprint is known before identities are assigned.
body=set(q for u in l['machines']+slots+l['warehouse_outlets']+l['power_poles']+[l['core'],rect] for q in cells(u))
component={};cc=0
for x in range(70):
 for y in range(70):
  if (x,y) in body or (x,y) in component:continue
  cc+=1;component[x,y]=cc;q=deque([(x,y)])
  while q:
   a,b=q.popleft()
   for dx,dy in D:
    v=(a+dx,b+dy)
    if 0<=v[0]<70 and 0<=v[1]<70 and v not in body and v not in component:component[v]=cc;q.append(v)
Sout,Sin=ports(l)
# Configuration tables list actual free external port cells, plus physical footprints.
conf={};gout={};gin={};centers={}
for j,u in enumerate(slots):
 dirs=range(4) if u['kind']=='小' else [0,2] if u['x1']-u['x0']==3 else [1,3]
 for di in dirs:
  key=(j,di);conf[key]=u
  gin[key]=[p for p in edge(u,di,True) if p in component]
  gout[key]=[p for p in edge(u,(di+2)%4,True) if p in component]
  centers[key]=((u['x0']+u['x1'])/2,(u['y0']+u['y1'])/2)
for uid,u in {**fixed,**{u['id']:u for u in l['warehouse_outlets']},'CORE':l['core']}.items():
 key=(uid,0);gin[key]=[c for c,d,p in Sin[uid] if c in component];gout[key]=[c for c,d,p in Sout[uid] if c in component];centers[key]=((u['x0']+u['x1'])/2,(u['y0']+u['y1'])/2)
fixedconf={u:(u,0) for u in list(fixed)+[z['id'] for z in l['warehouse_outlets']]+['CORE']}
edges=[(f['source'],f['target'],4 if f['item'] in ['源矿','蓝铁矿'] else 1) for f in C['feeds']];adj=defaultdict(list)
for ei,(a,b,w) in enumerate(edges):adj[a].append(ei);adj[b].append(ei)
valid={u:[k for k in conf if slots[k[0]]['kind']==machine(u,0,0,0)['kind'] and len(gin[k])>=ni[u] and len(gout[k])>=no[u]] for u in todo}
# Start from harmonic targets; exact endpoint distances are used in the improvement pass.
targets={u:centers[k] for u,k in fixedconf.items()}
for u in todo:targets[u]=(28.,32.)
for _ in range(200):
 for u in todo:
  neigh=[b if a==u else a for ei in adj[u] for a,b,w in [edges[ei]]];targets[u]=tuple(sum(targets[v][q] for v in neigh)/len(neigh) for q in [0,1])
assignment={**fixedconf}
for kind in ['小','大']:
 us=[u for u in todo if machine(u,0,0,0)['kind']==kind];js=[j for j,v in enumerate(slots) if v['kind']==kind];cost=[];choose={}
 for u in us:
  row=[]
  for j in js:
   opts=[k for k in conf if k[0]==j];vals=[]
   for k in opts:
    penalty=10000*(max(0,ni[u]-len(gin[k]))+max(0,no[u]-len(gout[k])))
    x,y=centers[k];vals.append((penalty+abs(x-targets[u][0])+abs(y-targets[u][1])+rng.random()*.1,k))
   val,k=min(vals);choose[u,j]=k;row.append(val)
  cost.append(row)
 ri,ci=linear_sum_assignment(cost)
 for i,jj in zip(ri,ci):u=us[i];j=js[jj];assignment[u]=choose[u,j]
cache={}
def dist(ka,kb):
 key=(ka,kb)
 if key in cache:return cache[key]
 a=gout[ka];b=gin[kb]
 if not a or not b:value=10000
 else:
  pairs=[abs(x-v)+abs(y-w) for x,y in a for v,w in b if component[x,y]==component[v,w]]
  value=min(pairs)+1 if pairs else 2000+min(abs(x-v)+abs(y-w) for x,y in a for v,w in b)
 cache[key]=value;return value

def evalue(i):
 a,b,w=edges[i];return w*dist(assignment[a],assignment[b])
def penalty(u,k):return 10000*(max(0,ni[u]-len(gin[k]))+max(0,no[u]-len(gout[k])))
score=sum(evalue(i) for i in range(len(edges)))+sum(penalty(u,assignment[u]) for u in todo);best=score;ba=assignment.copy();start=time.time();trace=[]
kindids={k:[u for u in todo if machine(u,0,0,0)['kind']==k] for k in ['小','大']}
iterations=int(sys.argv[3]) if len(sys.argv)>3 else 45000
for it in range(iterations):
 u=rng.choice(todo);old=assignment[u]
 if rng.random()<.38:
  opts=[k for k in conf if k[0]==old[0] and k!=old]
  if not opts:continue
  changed={u:rng.choice(opts)}
 else:
  kind=slots[old[0]]['kind'];v=rng.choice(kindids[kind])
  if u==v:continue
  changed={u:assignment[v],v:old}
 ei=set(e for z in changed for e in adj[z]);before=sum(evalue(e) for e in ei)+sum(penalty(z,assignment[z]) for z in changed)
 orig={z:assignment[z] for z in changed};assignment.update(changed)
 after=sum(evalue(e) for e in ei)+sum(penalty(z,assignment[z]) for z in changed);delta=after-before
 temp=12*(1-(it%15000)/15000)+.3
 if delta<=0 or rng.random()<math.exp(-min(700,delta/temp)):
  score+=delta
  if score<best:best=score;ba=assignment.copy()
 else:assignment.update(orig)
 if it%5000==0:trace.append([it,score,best]);print('assign',it,score,best,flush=True)
assignment=ba
new=[]
for uid in todo:
 j,di=assignment[uid];u=slots[j];new.append(machine(uid,u['x0'],u['y0'],di))
ll={**l,'machines':l['machines']+new};blocked=[u for u in todo if penalty(u,assignment[u])]
out=dict(layout=ll,reserved_rectangle=rect,assignment_score=best,blocked_port_machines=blocked,free_components=cc,seconds=time.time()-start,seed=seed,trace=trace)
path=BASE/f'证据/assigned-{seed}.json';path.write_text(json.dumps(out,ensure_ascii=False,indent=2));print('DONE',best,'blocked',len(blocked),'components',cc,'seconds',time.time()-start,flush=True)
