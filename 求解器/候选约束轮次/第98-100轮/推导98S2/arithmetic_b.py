#!/usr/bin/env python3
"""Arithmetic B: no model imports; explicit inventories and doubled integers."""
import json
from pathlib import Path
from fractions import Fraction

HERE=Path(__file__).resolve().parent
ans={}
for plants in (12,13,16):
    # Mineral equipment and plant units assembled as independent lists.
    devices=[]
    devices += [('精炼炉',9,2)]*34+[('粉碎机',9,2)]*34+[('粉碎机',9,2)]*18
    devices += [('研磨机',24,3)]*(17+9+6)
    for n in (plants,6):
        for _ in range(n):
            devices += [('采种机',25,3),('种植机',25,3),('种植机',25,3),('粉碎机',9,2)]
    devices += [('精炼炉',9,2)]*17+[('配件机',9,2)]*6+[('塑形机',9,2)]*6
    devices += [('封装机',24,3)]*3+[('灌装机',24,3)]*4
    counts={t:sum(d[0]==t for d in devices) for t,_,_ in devices}
    total=len(devices); area=sum(a for _,a,_ in devices); weight=sum(w for _,_,w in devices)
    # Input degree count, independent of the route list.
    routes=34+34+18+3*(17+9)+3*5+2+4*(plants+6)+17+6+11+5*3+4*2+2*2+7
    best_num=-10**10; best_pure=-10**10; best_pj=None; min_p=None
    # Enumerate all legal area A and P. Omega=203/2, E=area-3291.
    for poles in range(1,301):
        cap_j=min(poles,(23*poles-total)//10,(54*poles-weight)//25)
        if cap_j<0: continue
        if min_p is None: min_p=poles
        numerator=9502-32*poles+4*cap_j-8*(area-3291)-203
        if numerator>best_num:
            best_num=numerator; best_pj=[poles,cap_j]
        pure=4900-area-219-4*poles-routes-8
        best_pure=max(best_pure,pure)
    def factor_scan(limit):
        for A in range(limit,-1,-1):
            dims=[(min(w,A//w),max(w,A//w)) for w in range(6,69) if A%w==0 and 6<=A//w<=68]
            if dims:
                x,y=max(dims)
                return [A,x,y]
    ans[str(total)]={'counts':counts,'total':total,'routes':routes,'body':area,'original_body':132*9+51*25+38*24,
                      'extra_machines':total-221,'extra_body':area-(132*9+51*25+38*24),'E':area-3291,
                      'small':sum(a==9 for _,a,_ in devices),'middle':sum(a==25 for _,a,_ in devices),
                      'large':sum(a==24 for _,a,_ in devices),'active_weight':weight,'omega':'203/2',
                      'minimum_P':min_p,'general_area_bound':str(Fraction(best_num,8)),
                      'general_optimizing_PJ':best_pj,'general_rectangle':factor_scan(best_num//8),
                      'pure_belt_T_min':routes+8,'pure_belt_area_bound':best_pure,'pure_belt_rectangle':factor_scan(best_pure)}
# A 20-tick output accounting, using recipe counts directly.
# Batteries:12, capsules:11. Mineral costs:12*30=360, 12*20+11*40=680.
assert 12*30 == 18*20 and 12*20+11*40 == 34*20
ans['flows']={'battery':str(Fraction(12,20)),'capsule':str(Fraction(11,20)),
              'sand':str(Fraction(12*25+11*30,20)),'buck_powder':str(Fraction(11*20,20)),
              'sand_plants_consumed':str(Fraction(12*25+11*30,60)),
              'buck_plants_consumed':str(Fraction(11*20,40)),
              'filler_rates':['1/5','1/5','1/10','1/20'],
              'slow_filler_capacity_margins':['1/10','3/20'],
              'filler_ingredient_margins':['1','3/2'],
              'minimum_sand_units_after_isolation':next(n for n in range(1,100) if 3*(n-1)>=31)}
ans['source_bounds']={str(n):str(Fraction(8,7+n)) for n in [1,2,3,6]}
ans['flows']['minimum_sand_units_per_product_group']=sum(next(n for n in range(1,100) if 3*n>=q) for q in (5,5,5,6,6,3,1,1))
(HERE/'arithmetic_b.json').write_text(json.dumps(ans,ensure_ascii=False,indent=2)+'\n')
other=json.loads((HERE/'arithmetic_a.json').read_text())
assert ans==other, [(k,ans[k],other.get(k)) for k in ans if ans[k]!=other.get(k)]
print(json.dumps({'independent_arithmetic_equal':True,'values':ans},ensure_ascii=False))
