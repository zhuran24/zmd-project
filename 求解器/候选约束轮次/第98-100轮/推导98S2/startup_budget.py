#!/usr/bin/env python3
"""Finite debugging feedstock budget, four nondecreasing material weights."""
import json
from collections import Counter
from fractions import Fraction as Q
from pathlib import Path
from factory_check import Layout

HERE=Path(__file__).resolve().parent
f=Layout(0,1,initial='prepared',separate=True)
items={r.kind for r in f.rs}|{k for u in f.ms for k in u.recipe[0]}
cat=('砂叶及种子','荞花及种子','蓝铁矿','源矿')
w={x:[Q(0)]*4 for x in items}
for x in ('砂叶','砂叶种子'): w[x][0]=Q(1)
for x in ('荞花','荞花种子'): w[x][1]=Q(1)
w['蓝铁矿'][2]=Q(1); w['源矿'][3]=Q(1)
# Topological recipe evaluation, skipping the primitive plant/seed recipes.
for _ in range(10):
    for u in f.ms:
        if u.typ in ('种植机','采种机'): continue
        ingredients,product,quantity,_=u.recipe
        value=[sum(q*w[k][i] for k,q in ingredients.items())/quantity for i in range(4)]
        if any(value): w[product]=value
growth=[]
for u in f.ms:
    ing,product,quantity,_=u.recipe
    delta=[quantity*w[product][i]-sum(q*w[k][i] for k,q in ing.items()) for i in range(4)]
    assert all(x>=0 for x in delta)
    if any(delta): growth.append({'machine':u.name,'increase':[str(x) for x in delta]})
machine=[Q(0)]*4
for u in f.ms:
    ing,product,quantity,_=u.recipe
    for i in range(4):
        machine[i]+=50*sum(w[k][i] for k in ing)
        if u.typ not in ('封装机','灌装机'):
            machine[i]+=(50+quantity)*w[product][i]
used={r.kind for r in f.rs if r.target is not f.sink}
max_cell=[max(w[k][i] for k in used) for i in range(4)]
maximum=[machine[i]+4900*max_cell[i] for i in range(4)]
quota={k:int(min(maximum[i]/w[k][i] for i in range(4) if w[k][i])) for k in sorted(used)}
assert max(quota.values())<80000
warehouse_cost=[sum(quota[k]*w[k][i] for k in quota) for i in range(4)]
demand=Counter(quota)
recipes={u.recipe[1]:u.recipe for u in f.ms if u.typ not in ('采种机','种植机','封装机','灌装机')}
production_order=['钢质瓶','钢制零件','钢块','细磨荞花粉末','致密蓝铁粉末','致密源石粉末','蓝铁粉末','蓝铁块','源石粉末','荞花粉末','砂叶粉末']
for product in production_order:
    ingredients,_,quantity,_=recipes[product]
    batches=(demand.pop(product,0)+quantity-1)//quantity
    for item,q in ingredients.items(): demand[item]+=batches*q
assert demand['砂叶']+demand['砂叶种子']==warehouse_cost[0]
assert demand['荞花']+demand['荞花种子']==warehouse_cost[1]
assert demand['蓝铁矿']==warehouse_cost[2] and demand['源矿']==warehouse_cost[3]
# Independent machine-weight accounting by role counts, not f.ms traversal.
# Basic plant cells: 7 ordinary 50-stacks plus powder 50 and completed caches.
leaf_plants=13*(350+Q(50,3)+2+1+1+1)
grain_plants=6*(350+Q(50,2)+2+1+1+1)
# The remaining terms are the named recipe roles, each recording input stacks,
# output stack and one completed batch; final machines have inputs only.
leaf_rest=(26*Q(101,3) + 6*Q(101,3) + 17*Q(101,3)
           +6*Q(101,3)+6*(Q(50,3)+Q(102,3))+3*Q(100,3)+4*50)
grain_rest=6*(25+51)+4*50
assert machine[0]==leaf_plants+leaf_rest,(machine[0],leaf_plants+leaf_rest)
assert machine[1]==grain_plants+grain_rest,(machine[1],grain_plants+grain_rest)
ans={'categories':cat,'machine_capacity':[str(x) for x in machine],
     'maximum_weight_per_transport_cell':[str(x) for x in max_cell],
     'whole_factory_upper_weight':[str(x) for x in maximum],
     'feedstock_quota_by_item':quota,'largest_per_item_quota':max(quota.values()),
     'weights':{k:[str(x) for x in v] for k,v in sorted(w.items())},
     'plant_weight_independent_sum_equal':True,
     'total_universal_kit_resource_cost':[str(x) for x in warehouse_cost],
     'independent_integer_recipe_expansion':dict(demand),
     'seed_maker_growth_terms':growth}
(HERE/'startup_budget.json').write_text(json.dumps(ans,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in ans.items() if k not in ('weights','seed_maker_growth_terms')},ensure_ascii=False))
