"""Derived tables; exact fractions and a second direct enumeration of branch ceilings."""
from pathlib import Path
from fractions import Fraction as F
import math,json
OUT=Path(__file__).resolve().parent
a=json.loads((OUT/'accounts_a.json').read_text());b=json.loads((OUT/'accounts_b.json').read_text())
base=F(219,2)
spec=[('粉碎机',68,9,2,F(1,4)),('精炼炉',51,9,2,F(0)),('研磨机',32,24,3,F(1,2)),
    ('塑形机',6,9,2,F(1,4)),('配件机',6,9,2,F(0)),('种植机',32,25,3,F(0)),
    ('采种机',16,25,3,F(0)),('封装机',3,24,3,F(3,4)),('灌装机',3,24,3,F(1)),('协议储存箱',0,9,None,None)]
costs=[]
for name,n,area,charge,old_drop in spec:
    weight=base
    if name in a['cost_tables']:
        weight+=F(a['cost_tables'][name]['weight'][str(n+1)])-F(a['cost_tables'][name]['weight'][str(n)])
    cost=4*area+weight-base
    direct=next(A for A in range(1113,-1,-1) if F(4*A+160+4*area)+weight<=4751)
    algebra=math.floor((4751-160-4*area-weight)/4)
    assert direct==algebra
    grid=max(x*y for x in range(6,69) for y in range(6,69) if x*y<=direct)
    transport=208 if name not in ('研磨机','塑形机','封装机','灌装机','协议储存箱') else math.ceil((717+weight)/4)
    if name=='协议储存箱':transport=207
    costs.append(dict(name=name,extra_area=area,extra_active_weight=charge,old_200_drop=None if old_drop is None else str(old_drop),
        direction_weight=str(weight),net_direction_area_cost=str(cost),T_lower_after_one=transport,
        scalar_A_ceiling=algebra,integer_dimensions_ceiling=grid,all_A_ge_1110_excluded=True))
branches=[]
for P in range(10,19):
    for J in range(P+1):
        if 25*J>54*P-520 or 10*J>23*P-217:continue
        allowance=4639-4*1110-16*P+2*J
        if allowance<0:continue
        if P==12 and J==0:continue # X >= 8, but allowance is 7; see report.
        branches.append(dict(P=P,J=J,XY_upper=allowance))
assert max(x['P'] for x in branches)==13
assert [x['J'] for x in branches if x['P']==13]==[5,6,7]
power_min=2*(68+51+6+6)+3*(32+16+32+3+3)
assert power_min==520
assert power_min>9*54+29
result=dict(costs=costs,remaining_1110_scalar_branches=branches,power_required_weight=power_min,
    power_10_one_edge=9*54+29,scope='Remaining branches are necessary-condition survivors, not layouts.')
(OUT/'final_numbers.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
