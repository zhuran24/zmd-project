import sys,json
from pathlib import Path
from collections import defaultdict
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'生成/代码'))
from 目录与流量 import *
BASE=Path(__file__).resolve().parent
from 检查器甲 import maxrect
src=Path(sys.argv[1]);data=load(src);paths={int(k):v for k,v in data['paths'].items()};nets=data['nets'];occpaths=defaultdict(list)
for i,route in paths.items():
 for c,di,do in route:occpaths[tuple(c)].append((i,di,do))
transport=[]
for (x,y),uses in sorted(occpaths.items()):
 t=dict(id=f'T{x}_{y}',x=x,y=y)
 if len(uses)==1:t.update(type='belt',in_side=(uses[0][1]+2)%4,out_side=uses[0][2])
 else:
  assert len(uses)==2 and all(di==do for i,di,do in uses)
  t.update(type='bridge',H_in=next((di+2)%4 for i,di,do in uses if di%2==0),V_in=next((di+2)%4 for i,di,do in uses if di%2==1))
 transport.append(t)
def pr(uid,s,o=0):return dict(unit=uid,side=s,offset=o)
bind={b['logical_source_id']:b['port'] for b in data['bindings']};chs=[];completed=[]
for i,route in sorted(paths.items()):
 n=nets[i];first=route[0];last=route[-1];start=next(p for p in n['starts'] if p[0]==first[0] and p[1]==first[1]);goal=next(p for p in n['goals'] if p[0]==last[0] and (p[1]+2)%4==last[2]);a=bind[n['source']] if n['source'] in bind else pr(n['source'],start[1],start[2]);b=pr(n['target'],goal[1],goal[2]);chain=[]
 def emit(x,y):
  cid=f'PC{len(chs):06}';chs.append(dict(id=cid,**{'from':x,'to':y},allowed_items=[n['item']]));chain.append(cid)
 emit(a,pr(f'T{first[0][0]}_{first[0][1]}',(first[1]+2)%4))
 for p,q in zip(route,route[1:]):emit(pr(f'T{p[0][0]}_{p[0][1]}',p[2]),pr(f'T{q[0][0]}_{q[0][1]}',(q[1]+2)%4))
 emit(pr(f'T{last[0][0]}_{last[0][1]}',last[2]),b)
 completed.append(dict(id=n['id'],**{'from':a,'to':b},item=n['item'],rate=n['rate'],path=chain))
l=dict(W=70,H=70,machines=data['machines'],warehouse_outlets=data['warehouse_outlets'],core=data['core'],power_poles=data['power_poles'],storage_boxes=[],transport=transport,vin=[],vout=[])
occupied={}
for cat in ['machines','warehouse_outlets','core','power_poles']:
 for u in [l[cat]] if cat=='core' else l[cat]:
  for x in range(u['x0'],u['x1']+1):
   for y in range(u['y0'],u['y1']+1):assert (x,y) not in occupied;occupied[x,y]=u['id']
for t in transport:assert (t['x'],t['y']) not in occupied;occupied[t['x'],t['y']]=t['id']
def covered(m,p):return m['x0']<=p['x0']+6 and m['x1']>=p['x0']-5 and m['y0']<=p['y0']+6 and m['y1']>=p['y0']-5
extra=[]
while True:
 un=[m for m in l['machines'] if not any(covered(m,p) for p in l['power_poles'])]
 if not un:break
 best=None;score=0
 for x in range(1,69):
  for y in range(1,69):
   if any((x+i,y+j) in occupied or (x+i>=64 and y+j>=64) for i in range(2) for j in range(2)):continue
   p=dict(id=f'P{len(l["power_poles"]):03}',x0=x,y0=y,x1=x+1,y1=y+1,orientation=0);q=sum(covered(m,p) for m in un)
   if q>score:score=q;best=p
 if best is None:break
 l['power_poles'].append(best);extra.append(best)
 for x in range(best['x0'],best['x1']+1):
  for y in range(best['y0'],best['y1']+1):occupied[x,y]=best['id']
unpowered=[u['id'] for u in l['machines'] if not any(covered(u,p) for p in l['power_poles'])]
assert not unpowered,('unpowered',unpowered)
rect,score=maxrect(occupied);assert rect is not None
restr=load(BASE/'候选-修复前.json')['design']['restrictions']
prov=['求解器/数据/候选B/contract.json','求解器/会议成果/会议3/共识稿-v4-7aae9e20.md','求解器/构造/第一张全厂候选/格式.md']
c=dict(schema='full-factory-static-v1',candidate_id='factory-static-repair-0002',source_fingerprints={k:sha(ROOT/v) for k,v in FILES.items()},provenance=[dict(path=p,sha256=sha(ROOT/p)) for p in prov],targets={i:str(q) for i,q in PRODUCTS.items()},layout=l,empty_rectangle=rect,design={'class':'p2p','physical_channels':chs,'restrictions':restr,'source_bindings':data['bindings']},flow_witness=None)
c['design']['restrictions']=restr
for entry in restr:
 if entry['id']=='fixed-layout':entry['coverage_loss']='固定219台和B的逐机单配方；固定角格空的边带与当前实体；重新选择矿口身份和实际路径；不附logical_feeds，连续LP不预设315条B指派或其速率。此实例以52矿口真实路径为构造硬约束，其他路径按物品/速率类别启发式重指派，未布通的供需不豁免。排除其他台数、配方、边带、摆放和支持选择。'

(BASE/(sys.argv[2] if len(sys.argv)>2 else '候选-矿口修复.json')).write_text(json.dumps(c,ensure_ascii=False,indent=2))
(BASE/'实验/已完成路径.json').write_text(json.dumps(completed,ensure_ascii=False,indent=2))
(BASE/'实验/导出摘要.json').write_text(json.dumps(dict(source=str(src),source_sha256=sha(src),routed=len(paths),total=len(nets),missing=[n['id'] for i,n in enumerate(nets) if i not in paths],transport=len(transport),bridges=sum(t['type']=='bridge' for t in transport),channels=len(chs),occupied=len(occupied),rectangle=rect,area=score[0],short_side=score[1],extra_poles=extra),ensure_ascii=False,indent=2))
print(len(paths),len(transport),len(chs),rect,score)
