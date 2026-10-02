#!/usr/bin/env python3
"""Arithmetic A: counts from the actual graph, rational area constraints."""
import json
from fractions import Fraction as Q
from pathlib import Path
from factory_check import Layout

HERE=Path(__file__).resolve().parent
SIZE={'粉碎机':9,'精炼炉':9,'配件机':9,'塑形机':9,'采种机':25,'种植机':25,'研磨机':24,'封装机':24,'灌装机':24}
BASE={'粉碎机':69,'精炼炉':51,'研磨机':32,'塑形机':6,'配件机':6,'种植机':34,'采种机':17,'封装机':3,'灌装机':3}

def rectangles(bound):
    possible=[(w*h,min(w,h),max(w,h)) for w in range(6,69) for h in range(6,69) if w*h<=bound]
    return max(possible) if possible else None

ans={}
for name,separate,layer in [('226',False,False),('230',True,False),('242',False,True)]:
    f=Layout(0,1,separate=separate,layer=layer)
    counts=dict(f.types)
    body=sum(SIZE[t]*n for t,n in counts.items())
    original=sum(SIZE[t]*n for t,n in BASE.items())
    E=body-3291
    omega=Q(379-8*counts['研磨机'],2)+max(0,22-2*counts['塑形机'])+24+6
    small=sum(n for t,n in counts.items() if SIZE[t]==9)
    middle=sum(n for t,n in counts.items() if SIZE[t]==25)
    large=sum(n for t,n in counts.items() if SIZE[t]==24)
    weight=2*small+3*(middle+large)
    branches=[]
    for P in range(1,301):
        for J in range(P+1):
            if 23*P-10*J<len(f.ms) or 54*P-25*J<weight: continue
            general=(Q(4751)-16*P+2*J-4*E-omega)/4
            pure=4900-body-81-138-4*P-(len(f.rs)+8)
            branches.append((general,pure,P,J))
    best=max(branches,key=lambda x:x[0]); best_pure=max(branches,key=lambda x:x[1])
    ans[name]={'counts':counts,'total':len(f.ms),'routes':len(f.rs),'body':body,'original_body':original,
               'extra_machines':len(f.ms)-221,'extra_body':body-original,'E':E,
               'small':small,'middle':middle,'large':large,'active_weight':weight,'omega':str(omega),
               'minimum_P':min(x[2] for x in branches),'general_area_bound':str(best[0]),
               'general_optimizing_PJ':[best[2],best[3]],'general_rectangle':rectangles(best[0]),
               'pure_belt_T_min':len(f.rs)+8,'pure_belt_area_bound':best_pure[1],
               'pure_belt_rectangle':rectangles(best_pure[1])}
# Eliminate intermediate ingredients in cycle balances.
battery=Q(18,30)
capsule=(Q(34,2)-10*battery)/20
sand=17+9+10*capsule
buck=20*capsule
ans['flows']={'battery':str(battery),'capsule':str(capsule),'sand':str(sand),'buck_powder':str(buck),
              'sand_plants_consumed':str(sand/3),'buck_plants_consumed':str(buck/2),
              'filler_rates':[str(Q(1,5)),str(Q(1,5)),str(Q(1,10)),str(Q(1,20))],
              'slow_filler_capacity_margins':[str(Q(1,5)-Q(1,10)),str(Q(1,5)-Q(1,20))],
              'filler_ingredient_margins':['1','3/2'],
              'minimum_sand_units_after_isolation':(31+2)//3+1}
ans['flows']['minimum_sand_units_per_product_group']=3*((5+2)//3)+2*((6+2)//3)+(3+2)//3+2
ans['source_bounds']={str(n):str(Q(8,8+n-1)) for n in (1,2,3,6)}
(HERE/'arithmetic_a.json').write_text(json.dumps(ans,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(ans,ensure_ascii=False))
