#!/usr/bin/env python3
"""Independent reconstruction from R8,12,16,41,44,50,54,60,63,72,73,76; no author checker import."""
from pathlib import Path
from collections import Counter,defaultdict
from itertools import permutations
from fractions import Fraction
import json,hashlib
B=Path('/home/zhuran24/zmd-research-fresh/求解器');E=Path(__file__).resolve().parent
P=B/'会议成果/任务书7执行/密排布局.json';j=json.loads(P.read_text());U={u['id']:u for u in j['units']}
dirs={'N':(0,1),'S':(0,-1),'E':(1,0),'W':(-1,0)};opp={'N':'S','S':'N','E':'W','W':'E'}
transport={'传送带','桥接器','物品准入口','分流器','汇流器'}
checks=[]
def check(name,c,details=None):
 checks.append({'name':name,'passed':bool(c),'details':details});assert c,(name,details)
def write(name,x): (E/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
occup={};ports={}
def add(u,side,role,offsets=None):
 x,y=u['xy'];w,h=u['size'];cells={'N':[(x+i,y+h-1) for i in range(w)],'S':[(x+i,y) for i in range(w)],'W':[(x,y+i) for i in range(h)],'E':[(x+w-1,y+i) for i in range(h)]}[side]
 for i,c in enumerate(cells):
  if offsets is not None and i not in offsets:continue
  key=(c,side);assert key not in ports
  ports[key]={'id':f"{u['id']}:{side}:{c[0]}:{c[1]}",'unit':u['id'],'cell':list(c),'side':side,'role':role}
for u in U.values():
 x,y=u['xy'];w,h=u['size'];k=u['kind']
 expected={'种植机':(5,5),'采种机':(5,5),'粉碎机':(3,3),'封装机':(6,4),'灌装机':(6,4),'协议储存箱':(3,3),'协议核心':(9,9),'供电桩':(2,2),'传送带':(1,1),'桥接器':(1,1),'仓库取货口':(3,1)}[k]
 check('size:'+u['id'],sorted((w,h))==sorted(expected))
 for cx in range(x,x+w):
  for cy in range(y,y+h):
   assert 0<=cx<70 and 0<=cy<70
   assert (cx,cy) not in occup,((cx,cy),u['id'],occup.get((cx,cy)))
   occup[cx,cy]=u['id']
 if k=='供电桩':continue
 if k=='协议核心':
  for s in 'NS':add(u,s,'in',range(1,8))
  for s in 'EW':add(u,s,'out',[1,4,7])
 elif k=='仓库取货口':
  assert (x==0 and (w,h)==(1,3)) or (y==0 and (w,h)==(3,1));add(u,'E' if x==0 else 'N','out',[1])
 elif k=='桥接器':
  assert {a['axis'] for a in u['axes']}=={'horizontal','vertical'}
  for a in u['axes']:
   assert opp[a['input']]==a['output'];add(u,a['input'],'in');add(u,a['output'],'out')
 else:
  a=u['orientation'];assert a['input']!=a['output']
  if k!='传送带':assert opp[a['input']]==a['output']
  if k in ['封装机','灌装机']:assert a['input'] in ('N','S') if w==6 else a['input'] in ('E','W')
  add(u,a['input'],'in');add(u,a['output'],'out')
canonical=lambda p:(p['id'],p['unit'],tuple(p['cell']),p['side'],p['role'])
check('all_declared_ports_equal_rule_reconstruction',set(map(canonical,j['ports']))==set(map(canonical,ports.values())))
edges=[]
for (cell,side),p in ports.items():
 if p['role']!='out':continue
 dx,dy=dirs[side];q=ports.get(((cell[0]+dx,cell[1]+dy),opp[side]))
 if q and q['role']=='in' and p['unit']!=q['unit'] and (U[p['unit']]['kind'] in transport or U[q['unit']]['kind'] in transport):edges.append((p['id'],q['id']))
reported=json.loads((B/'会议成果/任务书7执行/证据/密排/自动通道.json').read_text())
check('all_automatic_channels_equal',set(edges)=={(c['source'],c['target']) for c in reported},{'independent':len(edges),'reported':len(reported)})
expected_edges=set();routestats=[]
def side_between(a,b):return next(s for s,d in dirs.items() if (b[0]-a[0],b[1]-a[1])==d)
def pid(c,s):return ports[(tuple(c),s)]['id']
for r in j['routes']:
 cells=r['cells'];assert len(set(map(tuple,cells)))==len(cells)
 chain=[r['source_cell']]+cells+([r['target_cell']] if not r['external_sink'] else [])
 for a,b in zip(chain,chain[1:]):
  s=side_between(a,b);pair=(pid(a,s),pid(b,opp[s]));assert pair in edges,(r['id'],pair);expected_edges.add(pair)
 kinds=[U[occup[tuple(c)]]['kind'] for c in cells];comp=sum(k!='传送带' or i==0 or kinds[i-1]!='传送带' for i,k in enumerate(kinds))
 for i,c in enumerate(cells):
  u=U[occup[tuple(c)]];assert u['kind'] in transport
  if u['kind']=='桥接器':
   prev=chain[i];nxt=chain[i+2];assert side_between(prev,c)==side_between(c,nxt)
 assert r['transport_slots']==len(cells)==r['minimum_delay_ticks'] and r['components']==comp
 assert r['damping']==(None if r['external_sink'] else comp)
 routestats.append({'id':r['id'],'slots':len(cells),'components':comp,'item':r['item']})
check('routes_cover_all_automatic_channels',expected_edges==set(edges))
power={}
for u in U.values():
 if u['kind'] not in ['种植机','采种机','粉碎机','封装机','灌装机','协议储存箱']:continue
 x,y=u['xy'];w,h=u['size'];power[u['id']]=[]
 for p in U.values():
  if p['kind']!='供电桩':continue
  px,py=p['xy'];x0,y0=px-5,py-5
  if max(x,x0)<min(x+w,x0+12) and max(y,y0)<min(y+h,y0+12):power[u['id']].append(p['id'])
check('all_14_powered',len(power)==14 and all(power.values()),power)
bridges=[]
for u in U.values():
 if u['kind']!='桥接器':continue
 x,y=u['xy'];counts=0
 for order in permutations('NSEW'):
  for a in u['axes']:
   s=next(s for s in order if s in (a['input'],a['output']));dx,dy=dirs[s];p=ports[((x+dx,y+dy),opp[s])]
   assert U[p['unit']]['kind']=='传送带'
   assert p['role']==('out' if s==a['input'] else 'in')
  counts+=1
 bridges.append({'unit':u['id'],'all_local_first_contact_orders':counts,'axes':u['axes'],'same_species_exclusion':u['axes'][0]['item']==u['axes'][1]['item'],'rule_13_aggregate_capacity_for_planned_species':1})
check('bridge_directions_all_orders',all(b['all_local_first_contact_orders']==24 for b in bridges))
nontransport_outputs=defaultdict(list)
for a,b in edges:
 up=next(p for p in ports.values() if p['id']==a);vp=next(p for p in ports.values() if p['id']==b)
 if U[up['unit']]['kind'] not in transport:nontransport_outputs[up['unit']].append(U[vp['unit']]['kind'])
check('all_nontransport_outputs_only_one_priority_group',all('汇流器' not in v for v in nontransport_outputs.values()))
check('actual_guaranteed_factory_rates_remain_null',all(r['actual_rate'] is None for r in j['routes']))
summary={'units':len(U),'occupied_cells':len(occup),'ports':len(ports),'channels':len(edges),'routes':len(j['routes']),'kinds':dict(Counter(u['kind'] for u in U.values())),'transport_cells':sum(u['kind'] in transport for u in U.values()),'structural_transport_slots':sum((2 if u['kind']=='桥接器' else 1) for u in U.values() if u['kind'] in transport),'planned_species_simultaneous_capacity':sum(u['kind'] in transport for u in U.values()),'product_structural_slots':sum(r['slots'] for r in routestats if r['id'].endswith('成品')),'product_planned_species_capacity':len({tuple(c) for r in j['routes'] if r['id'].endswith('成品') for c in r['cells']})}
write('geometry-independent.json',{'input_sha256':hashlib.sha256(P.read_bytes()).hexdigest(),'checks':checks,'summary':summary,'routes':routestats,'power':power,'bridges':bridges,'channels':edges})
print(json.dumps(summary,ensure_ascii=False,indent=2))
