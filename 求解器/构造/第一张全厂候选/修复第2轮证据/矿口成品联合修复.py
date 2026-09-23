#!/usr/bin/env python3
"""有限局部摆放域内，同时兑现52个真实矿口到52台首加工机的P2P路径。
只用于候选构造，非全域不可行检查器；单商品路径的矿种在源端按终点绑定。
所有物理格限定为空/带/双轴桥，两桥不相邻。其余生产链仍须独立补齐。
"""
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']: os.environ[key]='1'
import json, time, sys, copy
from pathlib import Path
from collections import defaultdict
from ortools.sat.python import cp_model
BASE=Path(__file__).resolve().parent
D=[(1,0),(0,1),(-1,0),(0,-1)]
def nb(c,s):return (c[0]+D[s][0],c[1]+D[s][1])
def cells(u):return [(x,y) for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1)]
def side(u,s):
 if s%2==0:return [(u['x1'] if s==0 else u['x0'],y) for y in range(u['y0'],u['y1']+1)]
 return [(x,u['y1'] if s==1 else u['y0']) for x in range(u['x0'],u['x1']+1)]
data=json.loads((BASE/'候选-修复前.json').read_text());l=data['layout']
movable={u['id'] for u in l['machines']}|{'P000'}
units=l['machines']+l['warehouse_outlets']+l['power_poles']+[l['core']]
miner={u['id']:u for u in l['machines'] if u['recipe_ids'][0] in ['粉碎-源矿','精炼-蓝铁矿']}
assert len(miner)==52
blocked={(x,y) for x in range(70) for y in range(70) if x==0 or y==0 or (x>=64 and y>=64)}
for u in units:
 if u['id'] not in movable:blocked.update(cells(u))
grid={(x,y) for x in range(70) for y in range(70)}-blocked
m=cp_model.CpModel();cover=defaultdict(list);options={};sinks=defaultdict(list);endpoint={};obj=[]
for u in units:
 uid=u['id']
 if uid not in movable:
  if uid in miner:options[uid]=[(1,u)]
  continue
 opts=[]
 w=u['x1']-u['x0']+1;h=u['y1']-u['y0']+1
 radius=5 if uid in {'M005','M070','M081','M100','M199','P000'} else 2
 for x in range(max(1,u['x0']-radius),min(70-w,u['x0']+radius)+1):
  for y in range(max(1,u['y0']-radius),min(70-h,u['y0']+radius)+1):
   for dr in (range(4) if uid!='P000' else [0]):
    v=dict(u,x0=x,y0=y,x1=x+w-1,y1=y+h-1)
    if uid!='P000':
     v['Din']=dr
     if u['kind']=='大':v['x1']=x+(4 if dr%2==0 else 6)-1;v['y1']=y+(6 if dr%2==0 else 4)-1
    cc=cells(v)
    if any(c not in grid for c in cc):continue
    z=m.new_bool_var(f'p_{uid}_{x}_{y}_{dr}');opts.append((z,v))
    for c in cc:cover[c].append(z)
    obj.append(z*(abs(x-u['x0'])+abs(y-u['y0'])+int(dr!=u.get('Din',0))))
 opts and m.add_exactly_one(z for z,v in opts)
 assert opts,uid
 options[uid]=opts
for c,zs in cover.items():m.add(sum(zs)<=1)
free={c:m.new_bool_var(f'free_{c}') for c in grid}
for c in grid:m.add(free[c]+sum(cover[c])==1)
for uid in miner:
 terminals=[]
 for z,u in options[uid]:
  for off,c in enumerate(side(u,u['Din'])):
   q=nb(c,u['Din'])
   if q not in grid:continue
   a=m.new_bool_var(f'sink_{uid}_{q}_{off}');m.add(a<=z);m.add(a<=free[q])
   sinks[q,(u['Din']+2)%4].append(a);terminals.append(a)
   endpoint[a.index]=(uid,u['Din'],off)
 m.add(sum(terminals)==1)
emits=defaultdict(list);productstarts={};products={'高容谷地电池','精选荞愈胶囊'}
for uid,opts in options.items():
 if opts[0][1].get('model') not in ['封装机','灌装机']:continue
 terminals=[]
 for z,u in opts:
  dr=(u['Din']+2)%4
  for off,c in enumerate(side(u,dr)):
   q=nb(c,dr)
   if q not in grid:continue
   a=m.new_bool_var('product_source');m.add(a<=z);m.add(a<=free[q]);terminals.append(a)
   emits[q,(dr+2)%4].append(a);productstarts[a.index]=(uid,dr,off)
 m.add(sum(terminals)==1)
coreends=defaultdict(list);coreports={}
for dr in [l['core']['Din'],(l['core']['Din']+2)%4]:
 for off,c in enumerate(side(l['core'],dr)):
  if off not in range(1,8):continue
  q=nb(c,dr)
  if q not in grid:continue
  a=m.new_bool_var('core_sink');m.add(a<=free[q]);coreends[q,(dr+2)%4].append(a);coreports[a.index]=('CORE',dr,off)
m.add(sum(a for aa in coreends.values() for a in aa)==6)
sources={}
for u in l['warehouse_outlets']:
 c=nb(side(u,u['Dout'])[1],u['Dout']);sources[c,(u['Dout']+2)%4]=(u['id'],u['Dout'],1)
for p in l['core']['output_items']:
 c=nb(side(l['core'],p['side'])[p['offset']],p['side']);sources[c,(p['side']+2)%4]=('CORE',p['side'],p['offset'])
assert len(sources)==52
arcs={(c,s):m.new_int_var(0,2,f'a_{c}_{s}') for c in grid for s in range(4) if nb(c,s) in grid}
ins={};outs={};bridge={};used={};rows=[]
rows.append([0]*10)
for a in range(4):
 for b in range(4):
  if a!=b:
   for col in [1,2]:rows.append([col*int(s==a) for s in range(4)]+[col*int(s==b) for s in range(4)]+[0,1])
for h in [0,2]:
 for v in [1,3]:
  for hc in [1,2]:
   for vc in [1,2]:rows.append([hc*int(s==h)+vc*int(s==v) for s in range(4)]+[hc*int(s==(h+2)%4)+vc*int(s==(v+2)%4) for s in range(4)]+[1,1])
for c in sorted(grid):
 iv=[m.new_int_var(0,2,'') for s in range(4)];ov=[m.new_int_var(0,2,'') for s in range(4)]
 br=m.new_bool_var('');us=m.new_bool_var('');bridge[c]=br;used[c]=us;ins[c]=iv;outs[c]=ov
 m.add_allowed_assignments(iv+ov+[br,us],rows);m.add(us<=free[c])
 for s in range(4):
  q=nb(c,s);incoming=arcs.get((q,(s+2)%4),0)
  m.add(iv[s]==incoming+int((c,s) in sources)+2*sum(emits[c,s]))
  m.add(ov[s]==arcs.get((c,s),0)+sum(sinks[c,s])+2*sum(coreends[c,s]))
for c in grid:
 for s in [0,1]:
  if nb(c,s) in grid:m.add(bridge[c]+bridge[nb(c,s)]<=1)
# Unmoved mineral processors need output room; the moved seed also needs accessible
# input/output cells. This is a geometry prerequisite, not a fulfilled plant circuit.
for uid,opts in options.items():
 if uid=='P000':continue
 for z,u in opts:
  for s,need in [(u['Din'],1),((u['Din']+2)%4,2 if u.get('model')=='采种机' else 3 if s==u['Din'] and u.get('model')=='研磨机' else 5 if s==u['Din'] and u.get('model')=='封装机' else 4 if s==u['Din'] and u.get('model')=='灌装机' else 2 if s==u['Din'] and u.get('model')=='塑形机' else 3 if s!=u['Din'] and u.get('recipe_ids')==['粉碎-砂叶'] else 2 if s!=u['Din'] and u.get('recipe_ids')==['粉碎-荞花'] else 1)]:
   qs=[nb(c,s) for c in side(u,s) if nb(c,s) in free]
   m.add(sum(free[c] for c in qs)>=need*z)
m.minimize(sum(used.values())+100*sum(obj))
s=cp_model.CpSolver();s.parameters.num_workers=5;s.parameters.max_time_in_seconds=float(sys.argv[1]) if len(sys.argv)>1 else 180
s.parameters.random_seed=223;s.parameters.log_search_progress=True
start=time.monotonic();status=s.solve(m)
res={'status':s.status_name(status),'wall':time.monotonic()-start,'workers':5,'source_count':52,'sink_count':52,'movable':sorted(movable),'scope':'219台机器允许平移2格、任意合法朝向，角区5台与1桩允许平移5格；核心及其他桩固定。固定六台成品机的单独实体回库路径；兑现52矿口路径和6条成品入核心路径，其余路径和连续流须另验。'}
if status in [cp_model.OPTIMAL,cp_model.FEASIBLE]:
 chosen={uid:next(v for z,v in opts if isinstance(z,int) and z==1 or not isinstance(z,int) and s.value(z)) for uid,opts in options.items()}
 res['placements']={uid:chosen[uid] for uid in movable}
 end_by_pos={}
 for (c,dr),aa in sinks.items():
  for a in aa:
   if s.value(a):end_by_pos[c,dr]=endpoint[a.index]
 paths=[]
 for (c,dr),aa in coreends.items():
  for a in aa:
   if s.value(a):end_by_pos[c,dr]=coreports[a.index]
 sources=dict(sources)
 for (c,di),aa in emits.items():
  for a in aa:
   if s.value(a):sources[c,di]=productstarts[a.index]
 for (c,di),source in sorted(sources.items()):
  path=[];seen=set()
  while True:
   assert (c,di) not in seen;seen.add((c,di))
   do=(di+2)%4 if s.value(bridge[c]) else next(j for j in range(4) if s.value(outs[c][j]))
   path.append([list(c),(di+2)%4,do])
   if (c,do) in end_by_pos:
    target=end_by_pos[c,do];break
   assert s.value(arcs[c,do]);c=nb(c,do);di=(do+2)%4
  paths.append({'source':list(source),'target':list(target),'item':('高容谷地电池' if chosen[source[0]]['model']=='封装机' else '精选荞愈胶囊') if target[0]=='CORE' else '源矿' if miner[target[0]]['recipe_ids'][0]=='粉碎-源矿' else '蓝铁矿','path':path})
 res['paths']=paths;res['transport_cells']=sum(s.value(v) for v in used.values());res['bridges']=sum(s.value(v) for v in bridge.values())
(BASE/'矿口成品联合修复.json').write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in res.items() if k not in ['placements','paths']},ensure_ascii=False))
