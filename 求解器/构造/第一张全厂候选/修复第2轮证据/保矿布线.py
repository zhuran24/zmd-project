#!/usr/bin/env python3
"""矿口硬路径先兑现；其他B速率类别重指派并按真实占格布线。未布通不等于无解。"""
import os,sys,json,heapq,random,time,math,copy
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='1'
from pathlib import Path
from collections import defaultdict,Counter
from scipy.optimize import linear_sum_assignment
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'生成/代码'))
from 目录与流量 import *
BASE=Path(__file__).resolve().parent
result=load(BASE/sys.argv[1]);tag=Path(sys.argv[1]).stem
seed=int(sys.argv[2]) if len(sys.argv)>2 else 22;rng=random.Random(seed)
B=load(ROOT/'求解器/数据/候选B/contract.json');initial=load(BASE/'候选-修复前.json');l=copy.deepcopy(initial['layout'])
assert 'placements' in result,result['status']
for cat in ['machines','power_poles']:
 l[cat]=[result['placements'].get(u['id'],u) for u in l[cat]]
existing_poles={u['id'] for u in l['power_poles']}
for uid,u in result['placements'].items():
 if uid.startswith('P') and uid not in existing_poles:l['power_poles'].append(u)
poses=l['machines'];core=l['core'];poles=l['power_poles'];outs=l['warehouse_outlets']
occ={}
for u in poses+[core]+poles+outs:
 for x in range(u['x0'],u['x1']+1):
  for y in range(u['y0'],u['y1']+1):assert (x,y) not in occ;(occ.__setitem__((x,y),u['id']))
blocked=set(occ)|{(x,y) for x in range(64,70) for y in range(64,70)}|{(0,0)}
def ports(u,side,offs=None):
 ans=[]
 if offs is None:offs=range((u['y1']-u['y0']+1) if side%2==0 else (u['x1']-u['x0']+1))
 for z in offs:
  p=[(u['x1'],u['y0']+z),(u['x0']+z,u['y1']),(u['x0'],u['y0']+z),(u['x0']+z,u['y0'])][side];q=(p[0]+D[side][0],p[1]+D[side][1])
  if 0<=q[0]<70 and 0<=q[1]<70 and q not in blocked:ans.append((q,side,z))
 return ans
raw={u['id']:u for u in B['machines']};feed=B['logical_feeds'];mids=list(raw)
inneed=Counter(f['target'] for f in feed);outneed=Counter(f['source'] for f in feed)
ps=[ports(p,p['Din']) for p in poses];po=[ports(p,(p['Din']+2)%4) for p in poses]
assign={u['id']:i for i,u in enumerate(poses)}
components={};number=0
for xx in range(70):
 for yy in range(70):
  c=(xx,yy)
  if c in blocked or c in components:continue
  components[c]=number;todo=[c]
  while todo:
   aa,bb=todo.pop()
   for dx,dy in D:
    v=(aa+dx,bb+dy)
    if 0<=v[0]<70 and 0<=v[1]<70 and v not in blocked and v not in components:components[v]=number;todo.append(v)
  number+=1
def pdist(pa,pb):
 return min((abs(a[0][0]-b[0][0])+abs(a[0][1]-b[0][1])+(2000 if components.get(tuple(a[0]))!=components.get(tuple(b[0])) else 0) for a in pa for b in pb),default=10000)
pdistmat=[[pdist(po[i],ps[j]) for j in range(len(poses))] for i in range(len(poses))]
print('FREE_COMPONENTS',number,'largest',Counter(components.values()).most_common(5),flush=True)

neighbors=defaultdict(list)
for f in feed:
 if f['source'] in raw and f['target'] in raw:neighbors[f['source']].append((f['target'],True));neighbors[f['target']].append((f['source'],False))
fixed_ids={p['target'][0] for p in result['paths'] if p['target'][0]!='CORE'}|{p['source'][0] for p in result['paths'] if p['target'][0]=='CORE'}
core_input=[q for dr in [core['Din'],(core['Din']+2)%4] for q in ports(core,dr,range(1,8))]
product_cost=[pdist(po[p],core_input) for p in range(len(poses))]
finals={f['source'] for f in feed if f['target']=='CORE'}
def unary(mid,p):
 return 10000*(max(0,inneed[mid]-len(ps[p]))+max(0,outneed[mid]-len(po[p])))+(10*product_cost[p] if mid in finals else 0)
def local(mid):return unary(mid,assign[mid])+sum(pdistmat[assign[mid]][assign[n]] if forward else pdistmat[assign[n]][assign[mid]] for n,forward in neighbors[mid])
groups=[[mid for mid in mids if mid not in fixed_ids and KINDS[raw[mid]['kind']]==kind] for kind in ['小','中','大']]
groups=[g for g in groups if len(g)>1]
for step in range(120000):
 a,b=rng.sample(rng.choice(groups),2);before=local(a)+local(b);assign[a],assign[b]=assign[b],assign[a];after=local(a)+local(b)
 temp=max(.05,100*(1-step/120000)**2)
 if after>before and rng.random()>math.exp(min(0,(before-after)/temp)):assign[a],assign[b]=assign[b],assign[a]
machines=[]
for mid in mids:
 u=dict(poses[assign[mid]],id=mid,model=raw[mid]['kind'],recipe_ids=[raw[mid]['recipes'][0]['recipe']],settings={'manufacture_on':True});machines.append(u)
unit={u['id']:u for u in machines+outs+[core]};bind={};forced=[]
bytarget={f['target']:f for f in feed if f['source'].startswith('ORE')};byfinal={f['source']:f for f in feed if f['target']=='CORE'}
for path in result['paths']:
 src,dr,off=path['source'];dst=path['target'][0]
 if dst=='CORE':f=byfinal[src]
 else:
  f=bytarget[dst];bind[f['source']]=dict(unit=src,side=dr,offset=off)
  if src=='CORE':
   for setting in core['output_items']:
    if setting['side']==dr and setting['offset']==off:setting['item']=path['item']
  else:unit[src]['item']=path['item']
 forced.append((f,path))
def endpoints(uid,inbound):
 if uid.startswith('ORE'):
  p=bind[uid];u=unit[p['unit']]
  if p['unit']=='CORE':return [(q,p['side'],p['offset']) for q,s,z in ports(u,p['side'],[p['offset']])]
  return [((1,u['y0']+1) if u['Dout']==0 else (u['x0']+1,1),u['Dout'],1)]
 u=unit[uid]
 if uid=='CORE':return [p for s in [u['Din'],(u['Din']+2)%4] for p in ports(u,s,range(1,8))]
 return ports(u,u['Din'] if inbound else (u['Din']+2)%4)
group=defaultdict(list)
fixed_feed_ids={f['id'] for f,p in forced}
for f in feed:
 if f['id'] not in fixed_feed_ids:group[f['item'],f['planned_rate']['value']].append(f)
nets=[]
for f,p in forced:
 nets.append(dict(id=f['id'],source=f['source'],target=f['target'],item=f['item'],rate=f['planned_rate']['value'],starts=endpoints(f['source'],False),goals=endpoints(f['target'],True)))
for (item,rate),fs in group.items():
 costs=[]
 for a in fs:
  pa=endpoints(a['source'],False);row=[]
  for b in fs:
   pb=endpoints(b['target'],True)
   row.append(pdist(pa,pb)+(10000 if a['source']==b['target'] else 0))
  costs.append(row)
 rr,cc=linear_sum_assignment(costs)
 for i,j in zip(rr,cc):
  a,b=fs[i],fs[j];nets.append(dict(id=a['id'],source=a['source'],target=b['target'],item=item,rate=rate,starts=endpoints(a['source'],False),goals=endpoints(b['target'],True)))
# Strict route occupancy: one belt or two perpendicular straight paths; no bridge adjacency.
occup=defaultdict(dict);paths={}
protected=set(range(len(forced)))
for i,(f,p) in enumerate(forced):
 route0=[(tuple(c),di,do) for c,di,do in p['path']];paths[i]=route0
 for c,di,do in route0:occup[c][i]=di%2 if di==do else 2
def use(di,do):return di%2 if di==do else 2
def can(c,di,do):
 o=occup.get(c)
 if not o:return True
 if len(o)!=1 or use(di,do)==2:return False
 other=next(iter(o.values()))
 if other!=1-use(di,do):return False
 return all(len(occup.get((c[0]+dx,c[1]+dy),{}))<2 for dx,dy in D)
def route(n):
 starts=n['starts'];goals=n['goals'];gd=defaultdict(list)
 for c,s,z in goals:gd[c].append((s+2)%4)
 if not starts or not goals:return None
 gcs=list(gd);pq=[];prev={};best={};seq=0
 def heur(c):return min(abs(c[0]-q[0])+abs(c[1]-q[1]) for q in gcs)
 for c,s,z in starts:
  st=(c,s);best[st]=0;heapq.heappush(pq,(heur(c),0,seq,st));seq+=1
 while pq:
  f,g,_,st=heapq.heappop(pq)
  if g!=best.get(st):continue
  c,di=st
  for do in gd.get(c,[]):
   if do!=(di+2)%4 and can(c,di,do):
    p=[(c,di,do)]
    walk=st
    while walk in prev:
     pre,pdo=prev[walk];p.append((pre[0],pre[1],pdo));walk=pre
    p.reverse()
    newbridges={tuple(t[0]) for t in p if occup.get(tuple(t[0]))}
    bridgeok=not any((a+dx,b+dy) in newbridges for a,b in newbridges for dx,dy in D)
    if len(set(t[0] for t in p))==len(p) and bridgeok:return p
  for do,(dx,dy) in enumerate(D):
   if do==(di+2)%4 or not can(c,di,do):continue
   q=(c[0]+dx,c[1]+dy)
   if not (0<=q[0]<70 and 0<=q[1]<70) or q in blocked:continue
   if occup.get(c) and occup.get(q):continue
   val=g+1+(0.2 if occup.get(c) else 0)+(0.03 if di!=do else 0);ns=(q,do)
   if val<best.get(ns,1e99):
    best[ns]=val;prev[ns]=(st,do);seq+=1;heapq.heappush(pq,(val+heur(q),val,seq,ns))
 return None
def add(i,p):
 assert all((a[0][0]+D[a[2]][0],a[0][1]+D[a[2]][1])==tuple(b[0]) and a[2]==b[1] for a,b in zip(p,p[1:])), 'nonadjacent path'
 paths[i]=p
 for c,di,do in p:occup[c][i]=use(di,do)
def rip(i):
 for c,di,do in paths.pop(i,[]):occup[c].pop(i,None)
def save(roundno):
 out=dict(round=roundno,machines=machines,warehouse_outlets=outs,core=core,power_poles=poles,bindings=[dict(logical_source_id=k,port=p) for k,p in sorted(bind.items())],nets=nets,paths={str(i):p for i,p in paths.items()},routed=len(paths),total=len(nets),missing=[nets[i]['id'] for i in range(len(nets)) if i not in paths],seed=seed,placement_source=tag,protected=len(protected))
 (BASE/f'实验/布线-{tag}-{seed}.json').write_text(json.dumps(out,ensure_ascii=False,indent=1))
bestn=-1;start=time.time();order=list(range(len(nets)))
# Short paths first seed a valid geometrical candidate. Subsequent rounds rip 12% to escape order lock-in.
order.sort(key=lambda i:(-10000 if nets[i]['target']=='CORE' else 0)+min((abs(a[0][0]-b[0][0])+abs(a[0][1]-b[0][1]) for a in nets[i]['starts'] for b in nets[i]['goals']),default=1e9))
for rnd in range(90):
 if rnd:
  missing=[i for i in range(len(nets)) if i not in paths];removable=list(set(paths)-protected);remove=rng.sample(removable,max(1,len(removable)//8)) if removable else []
  for i in remove:rip(i)
  rng.shuffle(missing);rng.shuffle(remove);order=missing+remove
 for i in order:
  if i in paths:continue
  p=route(nets[i])
  if p:add(i,p)
 if len(paths)>bestn:bestn=len(paths);save(rnd)
 print('ROUTE',rnd,len(paths),'best',bestn,'cells',sum(bool(v) for v in occup.values()),'seconds',round(time.time()-start,2),flush=True)
 if bestn==len(nets):break
