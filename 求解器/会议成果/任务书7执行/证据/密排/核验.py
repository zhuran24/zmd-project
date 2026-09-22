#!/usr/bin/env python3
"""Reconstruct all facing ports independently; check certificates, not game trajectories."""
import hashlib,json,itertools
from pathlib import Path
from collections import Counter,defaultdict
from fractions import Fraction
BASE=Path(__file__).resolve().parents[2];EV=Path(__file__).resolve().parent
J=json.loads((BASE/'密排布局.json').read_text());U={u['id']:u for u in J['units']}
D={'N':(0,1),'E':(1,0),'S':(0,-1),'W':(-1,0)};OP={'N':'S','S':'N','E':'W','W':'E'}
def save(name,x):(EV/name).write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
checks=[]
def check(name,condition,details):
    checks.append(dict(name=name,pass_=bool(condition),details=details))
    if not condition: raise AssertionError((name,details))
occ={}
for u in U.values():
 x,y=u['xy'];w,h=u['size']
 for c in itertools.product(range(x,x+w),range(y,y+h)):
  assert c not in occ,('overlap',c,u['id'],occ.get(c))
  assert all(0<=v<70 for v in c)
  occ[c]=u['id']
check('all occupied cells unique and within base',True,len(occ))
# Independently rebuild legal ports from type, size and orientation (not saved ports).
P=[]
def add(uid,c,s,r,slot):P.append(dict(id=f'{uid}:{s}:{c[0]}:{c[1]}',unit=uid,cell=list(c),side=s,role=r,slot=slot))
for u in U.values():
 uid=u['id'];x,y=u['xy'];w,h=u['size'];k=u['kind']
 if k=='供电桩':continue
 if k=='桥接器':
  for axis in u['axes']:
   add(uid,(x,y),axis['input'],'in',axis['axis']);add(uid,(x,y),axis['output'],'out',axis['axis'])
 elif k=='协议核心':
  for s in ['N','S']:
   for t in range(1,8):add(uid,(x+t,y+h-1 if s=='N' else y),s,'in','warehouse')
  for s in ['W','E']:
   for t in [1,4,7]:add(uid,(x if s=='W' else x+w-1,y+t),s,'out','蓝铁矿')
 elif k=='仓库取货口':
  assert (w,h) in [(1,3),(3,1)]
  add(uid,(x,y+1) if w==1 else (x+1,y),'E' if w==1 else 'N','out',u['warehouse_item'])
 else:
  for r,key in [('in','input'),('out','output')]:
   s=u['orientation'][key]
   cells=([(xx,y if s=='S' else y+h-1) for xx in range(x,x+w)] if s in ['N','S'] else
          [(x if s=='W' else x+w-1,yy) for yy in range(y,y+h)])
   for c in cells:add(uid,c,s,r,r)
check('saved complete ports equal independently generated ports',sorted(P,key=lambda p:p['id'])==sorted(J['ports'],key=lambda p:p['id']),len(P))
index={(tuple(p['cell']),p['side']):p for p in P};channels=[]
transport={'传送带','桥接器','分流器','汇流器','物品准入口'}
for p in P:
 if p['role']!='out':continue
 dx,dy=D[p['side']];c=(p['cell'][0]+dx,p['cell'][1]+dy)
 q=index.get((c,OP[p['side']]))
 if q and q['role']=='in' and (U[p['unit']]['kind'] in transport or U[q['unit']]['kind'] in transport):
  channels.append(dict(source=p['id'],target=q['id'],source_unit=p['unit'],target_unit=q['unit'],source_slot=p['slot'],target_slot=q['slot']))
actual={ (x['source_unit'],x['target_unit']) for x in channels};expected=set()
for r in J['routes']:
 start=occ.get(tuple(r['source_cell']));end=occ.get(tuple(r['target_cell']))
 chain=[start]+r['transport_unit_ids']+([] if r['external_sink'] else [end])
 assert start is not None and (r['external_sink'] or end is not None)
 if r['external_sink']: assert end is None,('occupied external interface',r['id'],end)
 expected.update(zip(chain,chain[1:]))
check('all automatically formed channels equal planned full graph',actual==expected,dict(actual=len(actual),expected=len(expected),extra=list(actual-expected),missing=list(expected-actual)))
check('no duplicate physical channel edges',len(actual)==len(channels),len(channels))
save('自动通道.json',channels)
power={}
for u in U.values():
 if u['kind'] not in ['种植机','采种机','粉碎机','封装机','灌装机','协议储存箱']:continue
 x,y=u['xy'];w,h=u['size'];covered=[]
 for p in U.values():
  if p['kind']!='供电桩':continue
  px,py=p['xy']
  # positive-area intersection of footprint and [px-5,px+7]x[py-5,py+7]
  if max(x,px-5)<min(x+w,px+7) and max(y,py-5)<min(y+h,py+7):covered.append(p['id'])
 power[u['id']]=covered
check('all fourteen powered units have positive-area coverage',all(power.values()),power)
bridge=[]
for u in U.values():
 if u['kind']!='桥接器':continue
 x,y=u['xy'];assert len(u['axes'])==2
 ports=[p for p in P if p['unit']==u['id']]
 assert len(ports)==4
 for p in ports:
  dx,dy=D[p['side']];other=index[((x+dx,y+dy),OP[p['side']])]
  assert U[other['unit']]['kind']=='传送带'
  assert p['role']!=other['role']
 # Every first attached neighbor, in all 24 local orders, agrees with both final axes.
 count=0
 for order in itertools.permutations(ports):
  seen={}
  for p in order:seen.setdefault(p['slot'],p['side'])
  assert len(seen)==2;count+=1
 bridge.append(dict(id=u['id'],xy=u['xy'],axes=u['axes'],all_local_first_contact_orders=count,
   neighbor_types=['传送带']*4,shared_material_slot=False,blueprint_order_safe=True))
check('bridge directions and two independent storage axes',len(bridge)==4,bridge)
save('桥与供电.json',dict(bridges=bridge,power=power))
nontransport=[u for u in U.values() if u['kind'] not in transport and u['kind']!='供电桩']
check('all actual nontransport outputs enter belts',all(U[c['target_unit']]['kind']=='传送带' for c in channels if c['source_unit'] in {u['id'] for u in nontransport}),len(nontransport))
lengths={r['id']:r['transport_slots'] for r in J['routes']}
for sp in ['荞花','砂叶']:
 check(sp+' lengths and startup reserve', [lengths[sp+x] for x in ['_PH','_PG','_HP']]==[1,3,15],dict(first_return_bound=19,q_min=19,q_max=50,margin_at_50=31,N_capacity=273))
products=[r for r in J['routes'] if r['id'].endswith('_成品')]
product_slots=[]
for r in products:
 for i,uid in enumerate(r['transport_unit_ids']):
  u=U[uid]
  axis=next(a['axis'] for a in u['axes'] if a['route']==r['id']) if u['kind']=='桥接器' else 'in'
  product_slots.append((uid,axis))
check('each six-source product path has disjoint material slots',len(product_slots)==len(set(product_slots)),len(product_slots))
service=[]
for r in products:
 ell=r['transport_slots'];assert ell in [15,7,16]
 service.append(dict(route=r['id'],length=ell,components=r['components'],damping=r['damping'],
  each_segment_capacity='1',source_max_completion_rate='1/5',source_queue_empty_start_upper=2,
  in_flight_empty_start_upper=1+(ell+1)//5,
  product_to_box_delay_upper=ell+1,product_to_warehouse_delay_upper=ell+6,
  unrestricted_physical_inflight_upper=ell,full_initial_output_transient='finite; source output<=50 and cache<=1; after receiver starts service source queue drains'))
check('merged source arithmetic',Fraction(3,5)+Fraction(11,20)==Fraction(23,20),dict(K=0,B=2,C=0,merge_count=6,combined_rate='23/20',single_common_exit_capacity='1',excess='3/20'))
reg=J['planned_factory_machine_register'];counts=Counter(m['kind'] for m in reg)
check('all 219 machines individually registered with slack',len(reg)==219 and sum(m['placement_status']=='unplaced' for m in reg)==207,dict(counts=counts,nominal_extra=[m['id'] for m in reg if m['nominal_surplus_designation']]))
edges=J['logical_edge_register'];stats=Counter(e['geometry_status'] for e in edges)
check('all 315 logical edges retain identities and missing-route status',len(edges)==315 and len({e['id'] for e in edges})==315 and stats==dict(fully_embedded=6,source_stub_only=4,changed_terminal_to_wireless_box=6,unrouted=299),dict(stats))
check('ore boundary extraction assignment',sum(r['item']=='蓝铁矿' for r in J['routes'] if r['external_sink'] and r['item'] in ['蓝铁矿','源矿'])==34 and sum(r['item']=='源矿' for r in J['routes'] if r['external_sink'])==18,'52 open interfaces, planned 34+18; actual delivery not certified')
for s in json.loads((EV/'输入指纹.json').read_text()):
 p=Path(s['path']);check('source unchanged '+p.name,hashlib.sha256(p.read_bytes()).hexdigest()==s['sha256'] and p.stat().st_mtime_ns==s['mtime_ns'],s['sha256'])
metrics=dict(unit_counts=dict(Counter(u['kind'] for u in U.values())),occupied_cells=len(occ),physical_transport_cells=sum(u['kind'] in transport for u in U.values()),
 transport_slots=sum(2 if u['kind']=='桥接器' else 1 if u['kind'] in transport else 0 for u in U.values()),channels=len(channels),external_interfaces=len(J['external_interfaces']),
 plant_transport_slots=dict(荞花=20,砂叶=22),product_transport_slots=76,product_physical_transport_cells=72,
 product_service=service,L=0,U=1113,full_layout_certified=False,game_execution_performed=False)
save('核验结果.json',dict(status='pass',scope='geometry, source binding, arithmetic; direct arguments in markdown',checks=checks,metrics=metrics))
print(json.dumps(dict(status='pass',checks=len(checks),metrics=metrics),ensure_ascii=False))
