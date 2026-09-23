"""与布线器分开重算固定摆放的矿口到首次小型制造单位可达二分图与Hall证书。"""
import json,sys
from collections import deque
from pathlib import Path
from 目录与流量 import BASE,sha
p=Path(sys.argv[1]);d=json.loads(p.read_text());occupied=set()
for typ,x,y,w,h,side in d['units']:
 occupied.update((a,b) for a in range(x,x+w) for b in range(y,y+h))
ori,x,y=d['core'];occupied.update((a,b) for a in range(x,x+9) for b in range(y,y+9))
for a,b in d['poles']:occupied.update((a+i,b+j) for i in range(2) for j in range(2))
occupied.update((0,j) for j in range(70));occupied.update((j,0) for j in range(70))
# Reserve NOT treated as blocked in this relaxation: even the claimed empty rectangle may be used for transport.
free={(a,b) for a in range(1,70) for b in range(1,70)}-occupied
components={};n=0
for c in sorted(free):
 if c in components:continue
 q=[c];components[c]=n
 while q:
  a,b=q.pop()
  for v in [(a+1,b),(a-1,b),(a,b+1),(a,b-1)]:
   if v in free and v not in components:components[v]=n;q.append(v)
 n+=1
sources=[dict(id=f'OUT_L{j:02}',side=0,offset=1,cell=[1,2+3*j]) for j in range(23)]+[dict(id=f'OUT_B{j:02}',side=1,offset=1,cell=[2+3*j,1]) for j in range(23)]
for side in ([1,3] if ori==0 else [0,2]):
 for off in [1,4,7]:
  cell=([x+9,y+off],[x+off,y+9],[x-1,y+off],[x+off,y-1])[side];sources.append(dict(id='CORE',side=side,offset=off,cell=cell))
small=[u for u in d['units'] if u[0] in ['crush','refine','parts','mold']]
fronts=[]
for typ,x,y,w,h,side in small:
 fronts.append(([(x+w,y+i) for i in range(h)],[(x+i,y+h) for i in range(w)],[(x-1,y+i) for i in range(h)],[(x+i,y-1) for i in range(w)])[side])
adj=[]
for s in sources:
 comp=components.get(tuple(s['cell']));adj.append([j for j,ps in enumerate(fronts) if comp is not None and any(components.get(q)==comp for q in ps)])
# Exact integer augmenting-path matching, no numerical solver.
rmatch={}
def augment(a,seen):
 for b in adj[a]:
  if b in seen:continue
  seen.add(b)
  if b not in rmatch or augment(rmatch[b],seen):rmatch[b]=a;return True
 return False
for a in range(len(sources)):augment(a,set())
lmatch={a:b for b,a in rmatch.items()};L=set(range(52))-set(lmatch);R=set();todo=list(L)
while todo:
 a=todo.pop()
 for b in adj[a]:
  if b not in R:
   R.add(b)
   if b in rmatch and rmatch[b] not in L:L.add(rmatch[b]);todo.append(rmatch[b])
N=set(b for a in L for b in adj[a]);assert N==R;assert len(L)-len(R)==52-len(lmatch)
result=dict(placement_file=str(p.resolve()),placement_sha256=sha(p),checker_sha256=sha(__file__),sources=sources,small_poses=small,adjacency=adj,maximum_matching=len(lmatch),matching=sorted(lmatch.items()),hall_sources=sorted(L),hall_neighbors=sorted(R),left_count=len(L),neighbor_count=len(R),deficit=len(L)-len(R),exact_checked=True,scope='固定全部非运输占格、朝向、矿口和供电桩；允许小机型任意重指派、全部空格含留白作无容量无向道路，不限制桥或路由。源满速1、首个消费原矿的小机每tick至多1，Hall缺额排除此固定摆放的p2p全厂达标；不排除其他摆放、不降低U。')
(BASE/'检查/矿源割证书.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print('Hall',len(L),len(R),'deficit',result['deficit'],'matching',result['maximum_matching'])
