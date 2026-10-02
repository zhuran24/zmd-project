#!/usr/bin/env python3
"""B: no graph imports; equipment roles, integer inequalities, factor scan."""
import json
from pathlib import Path
from collections import Counter
from fractions import Fraction

HERE = Path(__file__).resolve().parent
devices = [('精炼炉',9,2)]*34+[('粉碎机',9,2)]*(34+18)
for n in (13,6):
    for _ in range(n): devices += [('采种机',25,3),('种植机',25,3),('种植机',25,3),('粉碎机',9,2)]
devices += [('研磨机',24,3)]*(17+9+6)+[('精炼炉',9,2)]*17
devices += [('配件机',9,2)]*6+[('塑形机',9,2)]*6
devices += [('封装机',24,3)]*3+[('灌装机',24,3)]*4
counts = Counter(d[0] for d in devices)
body = sum(x[1] for x in devices); power = sum(x[2] for x in devices)
# Count input routes by receiver, adding seven final warehouse routes.
routes = 34+34+18+17*3+9*3+5*3+2+19*4+17+6+11+3*5+2*4+2*2+7
best_num = best_specific = -10**9
best_pj = None; min_p = None
for p in range(1,279):
    jmax = min(p,(23*p-len(devices))//10,(54*p-power)//25)
    if jmax < 0: continue
    if min_p is None: min_p = p
    num = 9502-32*p+4*jmax-8*(body-3291)-203
    if num > best_num: best_num=num; best_pj=[p,jmax]
    best_specific=max(best_specific,num-2*(2*routes-619))
def fact(limit):
    for a in range(limit,-1,-1):
        divs=[(x,a//x) for x in range(6,69) if a%x==0 and x<=a//x<=68]
        if divs: return [a,*max(divs)]
def ceil4half(x): return (x+7)//8
ans = dict(machine_counts=dict(counts),machine_total=len(devices),body=body,E=body-3291,
           small=sum(a==9 for _,a,_ in devices),medium=sum(a==25 for _,a,_ in devices),large=sum(a==24 for _,a,_ in devices),
           power_weight=power,route_count=routes,nontransport_interfaces=2*routes,minimum_active_slots=routes+8,
           omega='203/2',minimum_P=min_p,best_PJ=best_pj,
           formal_bound=str(Fraction(best_num,8)),formal_integer=best_num//8,formal_rectangle=fact(best_num//8),
           formal_T_min=ceil4half(2*717+203),formal_TF_at_best=ceil4half(2*809+203-4*best_pj[1]),
           exact_route_bound=str(Fraction(best_specific,8)),exact_route_integer=best_specific//8,exact_route_rectangle=fact(best_specific//8),
           exact_route_T_min=ceil4half(4*routes+196+203),exact_route_TF_at_best=ceil4half(4*routes+380+203-4*best_pj[1]),
           pure_belt_bound=4900-body-219-4*min_p-routes-8,
           minimum_double_bridges_for_833=833-(4900-body-219-4*min_p-routes-8),
           transport_capacity_for_startup=2*(4900-body-219),
           plant_powder_flows=[str(Fraction(12*25+11*30,20)),str(Fraction(11*20,20))],
           ore_flows=[str(Fraction(12*30,20)),str(Fraction(12*20+11*40,20))],
           product_rates=[str(Fraction(12,20)),str(Fraction(11,20))],filler_rates=['1/5','1/5','1/10','1/20'])
other = json.loads((HERE/'arithmetic_a.json').read_text())
assert ans == other, {k:(v,other.get(k)) for k,v in ans.items() if v!=other.get(k)}
(HERE/'arithmetic_b.json').write_text(json.dumps(ans,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'independent_arithmetic_equal':True,'values':ans},ensure_ascii=False))
