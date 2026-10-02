"""Independent group sums, integer sixths, backward recipe expansion.
Does not import graph/model_spec or arithmetic_graph.
"""
import json
from pathlib import Path
from collections import Counter

# Start with simple thirds, then normalize all coefficients to integer sixths.
c={"砂叶":(3,0,0,0),"砂叶种子":(3,0,0,0),"砂叶粉末":(1,0,0,0),
   "荞花":(0,3,0,0),"荞花种子":(0,3,0,0),"荞花粉末":(0,3,0,0),
   "蓝铁矿":(0,0,3,0),"蓝铁块":(0,0,3,0),"蓝铁粉末":(0,0,3,0),
   "源矿":(0,0,0,3),"源石粉末":(0,0,0,3),
   "致密蓝铁粉末":(1,0,6,0),"钢块":(1,0,6,0),"钢制零件":(1,0,6,0),
   "致密源石粉末":(1,0,0,6),"细磨荞花粉末":(1,6,0,0),"钢质瓶":(2,0,12,0)}
c={x:tuple(2*v for v in value) for x,value in c.items()}
c["荞花粉末"]=(0,3,0,0)
c["细磨荞花粉末"]=(2,6,0,0)
inventory=Counter()
groups=[(34,["蓝铁矿"],"蓝铁块",1),(34,["蓝铁块"],"蓝铁粉末",1),
        (18,["源矿"],"源石粉末",1),(17,["蓝铁粉末","砂叶粉末"],"致密蓝铁粉末",1),
        (9,["源石粉末","砂叶粉末"],"致密源石粉末",1),
        (6,["荞花粉末","砂叶粉末"],"细磨荞花粉末",1),
        (17,["致密蓝铁粉末"],"钢块",1),(6,["钢块"],"钢制零件",1),
        (6,["钢块"],"钢质瓶",1)]
for plant,n,k in [("砂叶",13,3),("荞花",6,2)]:
    groups.extend([(n,[plant],plant+"种子",2),(2*n,[plant+"种子"],plant,1),(n,[plant],plant+"粉末",k)])
for n,inputs,out,k in groups:
    for x in inputs:inventory[x]+=n*50
    inventory[out]+=n*(50+k)
for n,x,y in [(3,"钢制零件","致密源石粉末"),(4,"钢质瓶","细磨荞花粉末")]:
    inventory[x]+=n*50;inventory[y]+=n*50
stock=[sum(inventory[x]*c[x][j] for x in inventory) for j in range(4)]
bound=[stock[j]+4900*max(v[j] for v in c.values()) for j in range(4)]
backup={x:min(bound[j]//c[x][j] for j in range(4) if c[x][j]) for x in c}
n=dict(backup)
# Deliberate topological expansion instead of iterative graph recipe expansion.
for out,ins,k in [("钢质瓶",{"钢块":2},1),("钢制零件",{"钢块":1},1),
                  ("钢块",{"致密蓝铁粉末":1},1),
                  ("细磨荞花粉末",{"荞花粉末":2,"砂叶粉末":1},1),
                  ("致密蓝铁粉末",{"蓝铁粉末":2,"砂叶粉末":1},1),
                  ("致密源石粉末",{"源石粉末":2,"砂叶粉末":1},1),
                  ("蓝铁粉末",{"蓝铁块":1},1),("蓝铁块",{"蓝铁矿":1},1),
                  ("源石粉末",{"源矿":1},1),("砂叶粉末",{"砂叶":1},3),
                  ("荞花粉末",{"荞花":1},2)]:
    batches=(n.pop(out)+k-1)//k
    for x,a in ins.items():n[x]+=batches*a
small=71+51+6+6;medium=19+38;large=32+3+4
body=small*9+medium*25+large*24
routes=52+34+34+18+17+17+6+9+6+6+7+19*4+32+11
# Integer form: 8 A <= 9502 -32 P +4 J -8 E -203.
bound8=-1;best=None
for p in range(1,301):
    for j in range(p+1):
        if 23*p-10*j<230 or 54*p-25*j<556:continue
        v=9502-32*p+4*j-8*(body-3291)-203
        if v>bound8:bound8=v;best=(p,j)
areas=[]
for a in range(1,bound8//8+1):
    pairs=[(d,a//d) for d in range(6,69) if a%d==0 and d<=a//d<=68]
    if pairs:areas.append((a,pairs))
result={"machine_count":small+medium+large,"size_counts":[small,medium,large],
        "body_area":body,"routes":routes,"stock_equivalents_sixths":stock,
        "total_equivalent_bounds_sixths":bound,"backup":backup,"virgin_inputs":n,
        "power_weight":2*small+3*(medium+large),"E":body-3291,
        "direction_best_numerator_over_8":bound8,"direction_best_PJ":best,
        "direction_rectangle":areas[-1],"pure_area_bound":4900-body-81-138-44-routes-8,
        "variant_bodies":[3375,3375+108,3375+444],"variant_pure_bounds":[941,825,473]}
out=Path(__file__).with_suffix(".json")
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
# Comparison reads outputs only; neither independent calculation imports the other.
a=json.loads(out.with_name("arithmetic_graph.json").read_text())
for k in ["machine_count","body_area","routes","backup","virgin_inputs","power_weight","E","pure_area_bound"]:
    assert a[k]==result[k],(k,a[k],result[k])
from fractions import Fraction
assert [Fraction(x)*6 for x in a["stock_equivalents"]]==stock
assert [Fraction(x)*6 for x in a["total_equivalent_bounds"]]==bound
assert Fraction(a["direction_best"][0])*8==bound8
print(json.dumps(result,ensure_ascii=False))
