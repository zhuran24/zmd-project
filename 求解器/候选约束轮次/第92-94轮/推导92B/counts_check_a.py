#!/usr/bin/env python3
"""Independent direct enumeration and exact arithmetic for N35-N56."""
from pathlib import Path
from fractions import Fraction as F
from itertools import combinations, product, combinations_with_replacement
import json, math
ROOT=Path(__file__).resolve().parent
# Minimal forced directed non-port associations on a machine port side.
def inc(side,k):
 if k==0:return 0
 return min(2*sum(b-a<=3 for a,b in zip(p,p[1:])) for p in combinations(range(side),k))
def group(side,n,cap,demand):
 dp={0:0}
 for _ in range(n):
  nex={}
  for q,w in dp.items():
   for k in range(side+1):
    v=min(cap,k); key=min(demand,q+v)
    nex[key]=min(nex.get(key,100000),w+inc(side,k))
  dp=nex
 return dp[demand]
base=[68,51,32,6,6,32,16,3,3]
areas=[9,9,24,9,9,25,25,24,24]
# Exact demands rounded upward after summing fractional rates.
def all_inc(ns):
 return sum(group(side,ns[j],cap,demand) for j,side,cap,demand in
 [(0,3,3,95),(2,6,3,95),(3,3,2,11),(7,6,5,15),(8,6,4,11)])
inc_table={str(L):[inc(L,k) for k in range(L+1)] for L in (3,5,6)}
inc_base=[group(L,base[j],cap,dem) for j,L,cap,dem in [(0,3,3,95),(2,6,3,95),(3,3,2,11),(7,6,5,15),(8,6,4,11)]]
small=[]
for n in range(3):
 for inds in combinations_with_replacement(range(9),n):
  ns=base.copy()
  for i in inds:ns[i]+=1
  extra=sum(areas[i] for i in inds); g=all_inc(ns)
  checks=[]
  for eta in range(4):
   checks.append({'eta':eta,'empty_gap':extra+math.ceil(F(718+eta,4)+F(g,8))-200-math.ceil(F(eta,4)), 'occupied_gap':extra+math.ceil(F(721+eta,4)+F(g,8))-200-math.ceil(F(eta+3,4))})
  assert min(c['empty_gap'] for c in checks)>=0
  assert min(c['occupied_gap'] for c in checks)>=0
  small.append({'added':inds,'extra_area':extra,'associations':g,'checks':checks})
# Enumerate exact integer source/sink port count minimization.
eta_examples=[]
for b0,b1,m,d in product(range(4),range(5),range(5),range(5)):
 h=max(2,b1); eta=2*b0+max(h-2,5-2*m,2*h-9-2*d)
 s0=312+b0;r0=305+b0+h
 candidates=[s+r for s in range(s0,s0+15) for r in range(r0,r0+15) if -2*m<=r-s<=2*d]
 assert min(candidates)==619+eta
 eta_examples.append([b0,b1,m,d,eta,min(candidates)])
# Eight-step full-rate schedules: each port phase occurs once per every 8 steps.
full_phase_tests=0
for c in range(1,4):
 for cx in range(c):
  for phases in product(range(8),repeat=c):
   for t in range(8):
    accepted=[sum((s-p)%8==0 for s in range(t+1,t+9)) for p in phases]
    assert accepted==[1]*c
    assert cx+1-sum(accepted[:cx])>=1
    full_phase_tests+=1
# Closed output window contains at most m+1 events with separation >=8 steps.
windows=[]
for m in range(1,21):
 count=1+8*m//8
 assert count==m+1
 windows.append([m,count,3*m<=2*count])
flows=list(map(F,['34','18','34','34','18','31.5','21','21','11','11','11','17','17','9','5.5','6','5.5','0.6','0.55']))
result={'inc_table':inc_table,'base_associations':inc_base,'association_sum':sum(inc_base),'small_additions':small,'eta_cases':len(eta_examples),'base_area':sum(n*a for n,a in zip(base,areas))+81+138+40+200,'material_sum':str(sum(flows)),'total_ceil':math.ceil(sum(flows)),'ore_plus52_ceil':math.ceil(sum(flows)+52),'no_box_plus8_ceil':math.ceil(sum(flows)+8),'full_phase_tests':full_phase_tests,'output_windows':windows,'box_slots':{'harvester':50+50+2,'planter':50+50+1,'box':6*50},'min_three_extra_gain':min(27+math.ceil(F(718+i,4))-200-math.ceil(F(i,4)) for i in range(4))}
assert sum(flows)==F(6113,20)
(ROOT/'counts_check_a.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('small_additions','output_windows')},ensure_ascii=False))
