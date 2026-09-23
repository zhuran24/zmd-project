import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import sys,json,heapq,random,time,math
from collections import defaultdict,Counter
from pathlib import Path
from scipy.optimize import linear_sum_assignment
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'生成/代码'))
from 目录与流量 import *
BASE=Path(__file__).resolve().parent
B=load(ROOT/'求解器/数据/候选B/contract.json');rng=random.Random(int(sys.argv[1]) if len(sys.argv)>1 else 1)
d=load(Path(sys.argv[2]) if len(sys.argv)>2 else BASE/'实验/离散摆放.json');assert 'units' in d,d['status']
types={'crush':'粉碎机','refine':'精炼炉','parts':'配件机','mold':'塑形机','plant':'种植机','seed':'采种机','grind':'研磨机','pack':'封装机','fill':'灌装机'}
poses=[]
for typ,x,y,w,h,di in d['units']:poses.append(dict(model=types[typ],kind=KINDS[types[typ]],x0=x,y0=y,x1=x+w-1,y1=y+h-1,Din=di))
ori,cx,cy=d['core'];core=dict(id='CORE',x0=cx,y0=cy,x1=cx+8,y1=cy+8,Din=0 if ori==0 else 1,output_items=[])
poles=[dict(id=f'P{i:03}',x0=x,y0=y,x1=x+1,y1=y+1,orientation=0) for i,(x,y) in enumerate(d['poles'])]
occ={}
for i,u in enumerate(poses+[core]+poles):
 for x in range(u['x0'],u['x1']+1):
  for y in range(u['y0'],u['y1']+1):occ[x,y]=i
for j in range(70):occ[0,j]=-1;occ[j,0]=-1
# 6x6 reserved area only; actual empty rectangle recomputed after routing.
blocked=set(occ)|{(x,y) for x in range(64,70) for y in range(64,70)}
def ports(u,side,offs=None):
 ans=[]
 if offs is None:offs=range((u['y1']-u['y0']+1) if side%2==0 else (u['x1']-u['x0']+1))
 for z in offs:
  p=[(u['x1'],u['y0']+z),(u['x0']+z,u['y1']),(u['x0'],u['y0']+z),(u['x0']+z,u['y0'])][side];q=(p[0]+D[side][0],p[1]+D[side][1])
  if 0<=q[0]<70 and 0<=q[1]<70 and q not in blocked:ans.append((q,side,z))
 return ans
# Assignment of B's identities to same-model poses. Static batch rates and port multiplicities retained.
models=defaultdict(list)
for i,p in enumerate(poses):models[p['kind']].append(i)
raw={m['id']:m for m in B['machines']};feed=B['logical_feeds'];mids=list(raw);mi={m:i for i,m in enumerate(mids)}
inneed=Counter(f['target'] for f in feed);outneed=Counter(f['source'] for f in feed)
ps=[ports(p,p['Din']) for p in poses];po=[ports(p,(p['Din']+2)%4) for p in poses]
assign={}
for model,ix in models.items():
 ids=[m for m in mids if KINDS[raw[m]['kind']]==model]
 cost=[[10000*(max(0,inneed[m]-len(ps[p]))+max(0,outneed[m]-len(po[p])))+rng.random() for p in ix] for m in ids]
 rr,cc=linear_sum_assignment(cost)
 for i,j in zip(rr,cc):assign[ids[i]]=ix[j]
cent=[((p['x0']+p['x1'])/2,(p['y0']+p['y1'])/2) for p in poses]
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
mineral={f['target'] for f in feed if f['source'].startswith('ORE')};finals={f['source'] for f in feed if f['target']=='CORE'}
ore_points=[((1,2+3*j),0,1) for j in range(23)]+[((2+3*j,1),1,1) for j in range(23)]
for sd in [(core['Din']+1)%4,(core['Din']+3)%4]:ore_points.extend(ports(core,sd,[1,4,7]))
core_input=[]
for sd in [core['Din'],(core['Din']+2)%4]:core_input.extend(ports(core,sd,range(1,8)))
ore_cost=[pdist(ore_points,ps[p]) for p in range(len(poses))]
product_cost=[pdist(po[p],core_input) for p in range(len(poses))]
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import maximum_bipartite_matching
small=[i for i,p in enumerate(poses) if p['kind']=='小']
reach=[[int(pdist([src],ps[p])<2000) for p in small] for src in ore_points]
matching=maximum_bipartite_matching(csr_matrix(reach),perm_type='column')
proof=dict(physical_sources=len(ore_points),small_poses=len(small),maximum_matching=int(sum(i>=0 for i in matching)),matrix=reach,matching=matching.tolist(),scope='固定摆放；各空格无向连通且不限制运输格和交叉，原矿首个加工只能进入小机器；允许小机型任意重指派的必要条件放松')
(BASE/'实验/矿源可达放松.json').write_text(json.dumps(proof,ensure_ascii=False,indent=1))
print('ORE_RELAXATION_MATCHING',proof['maximum_matching'],flush=True)
def unary(m,p):
 x,y=cent[p];return 10000*(max(0,inneed[m]-len(ps[p]))+max(0,outneed[m]-len(po[p])))+(3*ore_cost[p] if m in mineral else 0)+(2*product_cost[p] if m in finals else 0)
def local(m):
 x,y=cent[assign[m]]
 return unary(m,assign[m])+sum(pdistmat[assign[m]][assign[n]] if forward else pdistmat[assign[n]][assign[m]] for n,forward in neighbors[m])
groups=[[m for m in mids if KINDS[raw[m]['kind']]==model] for model in models];groups=[g for g in groups if len(g)>1]
rawids=sorted(mineral)
source_to_pose=[[pdist([src],ps[j]) for j in small] for src in ore_points]
ri,ci=linear_sum_assignment(source_to_pose)
rawposes=[small[j] for j in ci]
for mid,p in zip(rawids,rawposes):assign[mid]=p
remaining=[p for p in small if p not in set(rawposes)]
otherids=[m for m in mids if KINDS[raw[m]['kind']]=='小' and m not in mineral]
cost=[[10000*(max(0,inneed[m]-len(ps[p]))+max(0,outneed[m]-len(po[p])))+rng.random() for p in remaining] for m in otherids]
rr,cc=linear_sum_assignment(cost)
for i,j in zip(rr,cc):assign[otherids[i]]=remaining[j]
groups=[rawids,otherids,[m for m in mids if KINDS[raw[m]['kind']]=='中'],[m for m in mids if KINDS[raw[m]['kind']]=='大']]
for step in range(240000):
 grp=rng.choice(groups);a,b=rng.sample(grp,2);before=local(a)+local(b);assign[a],assign[b]=assign[b],assign[a];after=local(a)+local(b)
 temp=max(.05,120*(1-step/240000)**2)
 if after>before and rng.random()>math.exp(min(0,(before-after)/temp)):assign[a],assign[b]=assign[b],assign[a]
machines=[]
for m in mids:
 u=dict(poses[assign[m]],id=m,recipe_ids=[raw[m]['recipes'][0]['recipe']],settings={'manufacture_on':True});u['model']=raw[m]['kind'];machines.append(u)
mu={u['id']:u for u in machines};unit={**mu,'CORE':core}
outs=[];physical_sources=[]
for side in [0,1]:
 for j in range(23):
  u=dict(id=f'OUT_{"L" if side==0 else "B"}{j:02}',x0=0 if side==0 else 1+3*j,y0=1+3*j if side==0 else 0,x1=0 if side==0 else 3+3*j,y1=3+3*j if side==0 else 0,Dout=side,item=None)
  outs.append(u);unit[u['id']]=u
  q=(1,2+3*j) if side==0 else (2+3*j,1);physical_sources.append((u['id'],side,1,q))
for side in [(core['Din']+1)%4,(core['Din']+3)%4]:
 for off in [1,4,7]:
  p=ports(core,side,[off]);assert p,('core port blocked',side,off);physical_sources.append(('CORE',side,off,p[0][0]))
orefeeds=[f for f in feed if f['source'].startswith('ORE')]
cost=[]
for f in orefeeds:
 u=mu[f['target']];qs=ports(u,u['Din']);cost.append([pdist([(p[3],p[1],p[2])],qs) for p in physical_sources])
rr,cc=linear_sum_assignment(cost);bind={}
for i,j in zip(rr,cc):
 f=orefeeds[i];p=physical_sources[j];bind[f['source']]=dict(unit=p[0],side=p[1],offset=p[2])
 if p[0]=='CORE':core['output_items'].append(dict(side=p[1],offset=p[2],item=f['item']))
 else:unit[p[0]]['item']=f['item']
# Reassign targets among logical edges of the same item and exact rate to shorten routing.
# This intentionally does NOT claim to preserve B's 315 endpoint assignments.
def endpoints(uid,inbound):
 if uid.startswith('ORE'):
  p=bind[uid];u=unit[p['unit']]
  if p['unit']=='CORE':return [(q,p['side'],p['offset']) for q,s,z in ports(u,p['side'],[p['offset']])]
  return [((1,u['y0']+1) if u['Dout']==0 else (u['x0']+1,1),u['Dout'],1)]
 u=unit[uid]
 if uid=='CORE':return [p for s in [u['Din'],(u['Din']+2)%4] for p in ports(u,s,range(1,8))]
 return ports(u,u['Din'] if inbound else (u['Din']+2)%4)
group=defaultdict(list)
for f in feed:group[f['item'],f['planned_rate']['value']].append(f)
nets=[]
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
 out=dict(round=roundno,machines=machines,warehouse_outlets=outs,core=core,power_poles=poles,bindings=[dict(logical_source_id=k,port=p) for k,p in sorted(bind.items())],nets=nets,paths={str(i):p for i,p in paths.items()},routed=len(paths),total=len(nets),missing=[nets[i]['id'] for i in range(len(nets)) if i not in paths],seed=int(sys.argv[1]) if len(sys.argv)>1 else 1)
 (BASE/f'实验/布线-{out["seed"]}.json').write_text(json.dumps(out,ensure_ascii=False,indent=1))
bestn=-1;start=time.time();order=list(range(len(nets)))
# Short paths first seed a valid geometrical candidate. Subsequent rounds rip 12% to escape order lock-in.
order.sort(key=lambda i:min((abs(a[0][0]-b[0][0])+abs(a[0][1]-b[0][1]) for a in nets[i]['starts'] for b in nets[i]['goals']),default=1e9))
for rnd in range(60):
 if rnd:
  missing=[i for i in range(len(nets)) if i not in paths];remove=rng.sample(list(paths),max(1,len(paths)//8))
  for i in remove:rip(i)
  rng.shuffle(missing);rng.shuffle(remove);order=missing+remove
 for i in order:
  if i in paths:continue
  p=route(nets[i])
  if p:add(i,p)
 if len(paths)>bestn:bestn=len(paths);save(rnd)
 print('ROUTE',rnd,len(paths),'best',bestn,'cells',sum(bool(v) for v in occup.values()),'seconds',round(time.time()-start,2),flush=True)
 if bestn==len(nets):break
