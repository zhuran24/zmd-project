#!/usr/bin/env python3
"""Second encoding: bitmasks, bounded capacity DP, integer twentieths."""
from pathlib import Path
from itertools import product
import json
P=Path(__file__).resolve().parent
# A directed association exists when one selected neighboring position is within
# three cells with no other selected position in between.
tables={}
for length in (3,5,6):
 best=[999]*(length+1)
 for mask in range(1<<length):
  selected=[j for j in range(length) if mask>>j&1]
  score=0
  for j in selected:
   for sign in (-1,1):
    for step in range(1,4):
     other=j+sign*step
     if other<0 or other>=length:break
     if mask>>other&1:
      score+=1;break
  best[len(selected)]=min(best[len(selected)],score)
 tables[str(length)]=best
# DP keeps the maximum rate obtainable for each forced association budget.
def maximum_rate_min_weight(side,count,per_machine,target):
 row={0:0}
 for machine in range(count):
  nxt={}
  for w,v in row.items():
   for k,cost in enumerate(tables[str(side)]):
    nw=w+cost; nv=v+min(k,per_machine)
    nxt[nw]=max(nxt.get(nw,-1),nv)
  row=nxt
 return min(w for w,v in row.items() if v>=target)
ns0=(68,51,32,6,6,32,16,3,3);asq=(9,9,24,9,9,25,25,24,24)
def get(ns):
 return [maximum_rate_min_weight(side,ns[j],cap,target) for j,side,cap,target in [(0,3,3,95),(2,6,3,95),(3,3,2,11),(7,6,5,15),(8,6,4,11)]]
cases=[]
for delta in product(range(3),repeat=9):
 if sum(delta)>2:continue
 ns=[a+b for a,b in zip(ns0,delta)]
 w=sum(get(ns)); added_area=sum(a*b for a,b in zip(asq,delta))
 gaps=[]
 for eta in range(4):
  # ceil((718+eta+w/2)/4) by eighths, with 3 extra associations for occupied gap.
  empty=added_area+(2*(718+eta)+w+7)//8-200-(eta+3)//4
  occupied=added_area+(2*(721+eta)+w+7)//8-200-(eta+6)//4
  assert empty>=0 and occupied>=0
  gaps.append([eta,empty,occupied])
 cases.append([list(delta),w,added_area,gaps])
# Independent parse of material list, numerators in twentieths.
flow20=[680,360,680,680,360,630,420,420,220,220,220,340,340,180,110,120,110,12,11]
eta_cases=0
for b0 in range(4):
 for b1 in range(5):
  for merger in range(5):
   for splitter in range(5):
    h=2 if b1<2 else b1
    minimal=None
    # parameterize d=R-S directly, minimize S subject to S>=s0,R>=r0.
    for dif in range(-2*merger,2*splitter+1):
     s=max(312+b0,305+b0+h-dif)
     val=2*s+dif
     minimal=val if minimal is None else min(minimal,val)
    eta=2*b0+max(h-2,5-2*merger,2*h-9-2*splitter)
    assert minimal==619+eta
    eta_cases+=1
result={'inc_table':tables,'base_associations':get(ns0),'association_sum':sum(get(ns0)),'addition_case_count':len(cases),'cases':cases,'eta_cases':eta_cases,'base_area':131*9+48*25+38*24+81+46*3+10*4+200,'material_sum_twentieths':sum(flow20),'total_ceil':(sum(flow20)+19)//20,'ore_plus52_ceil':(sum(flow20)+52*20+19)//20,'no_box_plus8_ceil':(sum(flow20)+8*20+19)//20,'box_slots':{'harvester':102,'planter':101,'box':300}}
a=json.loads((P/'counts_check_a.json').read_text())
for key in ('inc_table','base_associations','association_sum','eta_cases','base_area','total_ceil','ore_plus52_ceil','no_box_plus8_ceil','box_slots'):
 assert result[key]==a[key],(key,result[key],a[key])
assert result['material_sum_twentieths']==6113
# Compare all independently generated additions by multiplicity.
for delta,w,added,gaps in cases:
 inds=tuple(j for j,n in enumerate(delta) for _ in range(n))
 old=next(x for x in a['small_additions'] if tuple(x['added'])==inds)
 assert old['associations']==w and old['extra_area']==added
 assert [[x['eta'],x['empty_gap'],x['occupied_gap']] for x in old['checks']]==gaps
result['independent_comparison']='PASS'
(P/'counts_check_b.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='cases'},ensure_ascii=False))
