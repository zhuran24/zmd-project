#!/usr/bin/env python3
"""Rational-time local transport witness. R13 same species exclusion; R23 residence.
Three independent 5-tick producer streams, empty output/routes, always-receiving box.
At every bridge entry in the reported prefix only one input is physically eligible;
zero-time failed polling attempts can be inserted to realize the same fixed-order moves.
This is a local conditional trace, not a whole-factory certificate.
"""
from pathlib import Path
from fractions import Fraction as F
from collections import deque
import json
B=Path('/home/zhuran24/zmd-research-fresh/求解器');E=Path(__file__).resolve().parent
j=json.loads((B/'会议成果/任务书7执行/密排布局.json').read_text());U={tuple(u['xy']):u for u in j['units'] if u['kind'] in ['传送带','桥接器']}
routes={r['source_unit']:r for r in j['routes'] if r['id'] in ['M213_成品','M214_成品','M215_成品']}
first={'M213':F(14,5),'M214':F(19,10),'M215':F(5)};queues={r:deque() for r in routes};positions={r:[None]*len(v['cells']) for r,v in routes.items()}
births={r:t for r,t in first.items()};produced={r:0 for r in routes};next_transfer=F(27,10);box=[];moves=[];deliveries=[];t=F(0);bridge_eligibility=[]
def record(kind,**args):moves.append({'time':str(t),'kind':kind,**args})
def can_accept(route,i):
 if positions[route][i] is not None:return False
 cell=tuple(routes[route]['cells'][i])
 if U[cell]['kind']=='桥接器':
  for other in routes:
   if other==route:continue
   for k,c in enumerate(routes[other]['cells']):
    if tuple(c)==cell and positions[other][k] is not None:return False
 return True
while t<=30:
 for r in routes:
  if births.get(r)==t:
   queues[r].append((r,str(t)));produced[r]+=1;record('completion',route=r,token=[r,str(t)])
   if produced[r]<3:births[r]+=5
   else:del births[r]
 if t==next_transfer:
  for token in box:deliveries.append({'token':list(token),'wireless_time':str(t)})
  box=[];next_transfer+=5
 moved=True
 while moved:
  moved=False
  for r in sorted(routes):
   cells=routes[r]['cells']
   for edge in range(len(cells)+1):
    src=queues[r][0] if edge==0 and queues[r] else (positions[r][edge-1][0] if edge>0 and positions[r][edge-1] is not None and positions[r][edge-1][1]+1<=t else None)
    if src is None:continue
    if edge<len(cells) and not can_accept(r,edge):continue
    if edge<len(cells) and U[tuple(cells[edge])]['kind']=='桥接器':
     contenders=[]
     for rr in routes:
      for ii,cc in enumerate(routes[rr]['cells']):
       if cc==cells[edge] and ii>0 and positions[rr][ii-1] and positions[rr][ii-1][1]+1<=t and can_accept(rr,ii):contenders.append(rr)
     bridge_eligibility.append({'time':str(t),'bridge':U[tuple(cells[edge])]['id'],'eligible_inputs':contenders})
    if edge==0:queues[r].popleft()
    else:positions[r][edge-1]=None
    if edge<len(cells):positions[r][edge]=(src,t)
    else:box.append(src)
    record('move',route=r,token=list(src),source='output' if edge==0 else cells[edge-1],target='BOX_B' if edge==len(cells) else cells[edge]);moved=True
 # Advance to the next time an actual guard or completion can change.
 future=list(births.values())+[next_transfer]
 future += [v[1]+1 for values in positions.values() for v in values if v is not None and v[1]+1>t]
 t=min(x for x in future if x>t)
token=['M215','5'];path=[m for m in moves if m.get('token')==token];receipt=next(m for m in path if m.get('target')=='BOX_B');delivery=next(d for d in deliveries if d['token']==token)
assert F(receipt['time'])-5==F(89,5)>17
assert F(delivery['wireless_time'])-5==F(227,10)>22
assert all(len(x['eligible_inputs'])==1 for x in bridge_eligibility)
result={'scope':__doc__,'first_completions':{k:str(v) for k,v in first.items()},'recurrence':'3 completions per source, separated by 5 ticks; then source stops','wireless_phase':'27/10 + 5k','fixed_move_order':'route id then path edge; repeat while enabled; unique eligible bridge input at every admitted event','all_bridge_entries_unique_eligible':True,'counterexample':{'token':token,'box_time':receipt['time'],'warehouse_time':delivery['wireless_time'],'completion_to_box':str(F(receipt['time'])-5),'completion_to_warehouse':str(F(delivery['wireless_time'])-5),'claimed_upper_bounds':{'box':17,'warehouse':22}},'target_token_moves':path,'bridge_eligibility':bridge_eligibility,'all_moves':moves,'deliveries':deliveries}
(E/'bridge-delay-witness.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result['counterexample'],ensure_ascii=False))
