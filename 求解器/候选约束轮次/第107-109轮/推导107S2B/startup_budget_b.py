#!/usr/bin/env python3
"""Independent explicit-equivalent and machine-role inventory for the kit."""
import json
from fractions import Fraction as F
from pathlib import Path
from collections import Counter

HERE=Path(__file__).resolve().parent
weights={
 '砂叶':[1,0,0,0], '砂叶种子':[1,0,0,0], '荞花':[0,1,0,0], '荞花种子':[0,1,0,0],
 '蓝铁矿':[0,0,1,0], '源矿':[0,0,0,1], '蓝铁块':[0,0,1,0], '蓝铁粉末':[0,0,1,0],
 '源石粉末':[0,0,0,1], '砂叶粉末':['1/3',0,0,0], '荞花粉末':[0,'1/2',0,0],
 '致密蓝铁粉末':['1/3',0,2,0], '致密源石粉末':['1/3',0,0,2],
 '细磨荞花粉末':['1/3',1,0,0], '钢块':['1/3',0,2,0],
 '钢制零件':['1/3',0,2,0], '钢质瓶':['2/3',0,4,0]}
weights={k:list(map(F,v)) for k,v in weights.items()}
roles=[(34,['蓝铁矿'],'蓝铁块',1),(34,['蓝铁块'],'蓝铁粉末',1),
       (18,['源矿'],'源石粉末',1),(17,['蓝铁粉末','砂叶粉末'],'致密蓝铁粉末',1),
       (9,['源石粉末','砂叶粉末'],'致密源石粉末',1),(6,['荞花粉末','砂叶粉末'],'细磨荞花粉末',1),
       (17,['致密蓝铁粉末'],'钢块',1),(6,['钢块'],'钢制零件',1),(6,['钢块'],'钢质瓶',1)]
for p,n,k in [('砂叶',13,3),('荞花',6,2)]:
    roles.extend([(n,[p],p+'种子',2),(2*n,[p+'种子'],p,1),(n,[p],p+'粉末',k)])
capacity=[F(0)]*4
for n,inputs,product,k in roles:
    for j in range(4): capacity[j] += n*(sum(50*weights[x][j] for x in inputs)+(50+k)*weights[product][j])
for n,inputs in [(3,['钢制零件','致密源石粉末']),(4,['钢质瓶','细磨荞花粉末'])]:
    for j in range(4): capacity[j] += n*sum(50*weights[x][j] for x in inputs)
maxcell=[max(w[j] for w in weights.values()) for j in range(4)]
totals=[capacity[j]+4900*maxcell[j] for j in range(4)]
quotas={k:min((totals[j]/w[j]).numerator//(totals[j]/w[j]).denominator for j in range(4) if w[j]) for k,w in weights.items()}
demand=Counter(quotas)
recipes=[('钢质瓶',1,{'钢块':2}),('钢制零件',1,{'钢块':1}),('钢块',1,{'致密蓝铁粉末':1}),
         ('细磨荞花粉末',1,{'荞花粉末':2,'砂叶粉末':1}),
         ('致密源石粉末',1,{'源石粉末':2,'砂叶粉末':1}),
         ('致密蓝铁粉末',1,{'蓝铁粉末':2,'砂叶粉末':1}),
         ('蓝铁粉末',1,{'蓝铁块':1}),('蓝铁块',1,{'蓝铁矿':1}),
         ('源石粉末',1,{'源矿':1}),('砂叶粉末',3,{'砂叶':1}),('荞花粉末',2,{'荞花':1})]
for p,k,ins in recipes:
    n=(demand.pop(p,0)+k-1)//k
    for x,q in ins.items(): demand[x]+=n*q
old=json.loads((HERE/'startup_budget.json').read_text())
assert [str(x) for x in capacity]==old['machine_capacity']
assert [str(x) for x in totals]==old['whole_factory_upper_weight']
assert quotas==old['feedstock_quota_by_item']
assert dict(demand)==old['independent_integer_recipe_expansion']
assert max(quotas.values())<80000
assert demand['砂叶']<80000-15031 and demand['荞花']<80000-15031
ans={'independent_equal':True,'machine_capacity':[str(x) for x in capacity],
     'whole_factory_upper_weight':[str(x) for x in totals], 'quota':quotas,'primitive_requirements':dict(demand),
     'physical_transport_slot_bound':2*(4900-3567-81-138),'conservative_slots_used':4900}
(HERE/'startup_budget_b.json').write_text(json.dumps(ans,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(ans,ensure_ascii=False))
