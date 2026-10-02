#!/usr/bin/env python3
"""A: graph counts, Fraction inequalities, enumeration of rectangle dimensions."""
import json
from math import ceil
from fractions import Fraction as Q
from pathlib import Path
from factory_check import Layout

HERE = Path(__file__).resolve().parent
f = Layout(107,1,initial='prepared',separate=True)
areas = {'粉碎机':9,'精炼炉':9,'配件机':9,'塑形机':9,'种植机':25,'采种机':25,'研磨机':24,'封装机':24,'灌装机':24}
body = sum(areas[k]*v for k,v in f.types.items())
counts = {str(a):sum(v for k,v in f.types.items() if areas[k]==a) for a in (9,25,24)}
weight = 2*counts['9']+3*(counts['25']+counts['24'])
omega = Q(379-8*f.types['研磨机'],2)+22-2*f.types['塑形机']+24+6
E = body-3291
slots = len(f.rs)+8
interface = 2*len(f.rs)
rows = []
for P in range(1,(4900-body-81-138)//4+1):
    for J in range(P+1):
        if 23*P-10*J < len(f.ms) or 54*P-25*J < weight: continue
        general = (4751-16*P+2*J-4*E-omega)/4
        specific = (4751-(interface-619)-16*P+2*J-4*E-omega)/4
        rows.append((general,specific,P,J))
best = max(rows,key=lambda x:x[0])
best_specific = max(rows,key=lambda x:x[1])
def dims(limit):
    return list(max((w*h,min(w,h),max(w,h)) for w in range(6,69) for h in range(6,69) if w*h<=limit))
ans = dict(machine_counts=dict(f.types),machine_total=len(f.ms),body=body,E=E,
           small=counts['9'],medium=counts['25'],large=counts['24'],power_weight=weight,
           route_count=len(f.rs),nontransport_interfaces=interface,minimum_active_slots=slots,
           omega=str(omega),minimum_P=min(r[2] for r in rows),best_PJ=list(best[2:]),
           formal_bound=str(best[0]),formal_integer=best[0].numerator//best[0].denominator,
           formal_rectangle=dims(best[0]),formal_T_min=ceil((717+omega)/4),formal_TF_at_best=ceil((809+omega-2*best[3])/4),
           exact_route_bound=str(best_specific[1]),exact_route_integer=best_specific[1].numerator//best_specific[1].denominator,
           exact_route_rectangle=dims(best_specific[1]),exact_route_T_min=ceil((interface+98+omega)/4),exact_route_TF_at_best=ceil((interface+190+omega-2*best[3])/4),
           pure_belt_bound=4900-body-81-138-4*best[2]-slots,
           minimum_double_bridges_for_833=833-(4900-body-81-138-4*best[2]-slots),
           transport_capacity_for_startup=2*(4900-body-81-138),
           plant_powder_flows=['63/2','11'],ore_flows=['18','34'],
           product_rates=['3/5','11/20'],filler_rates=['1/5','1/5','1/10','1/20'])
(HERE/'arithmetic_a.json').write_text(json.dumps(ans,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(ans,ensure_ascii=False))
