"""Recompute counts, exact stock equivalents, backup recipes and area bounds."""
from fractions import Fraction as F
from collections import Counter
from pathlib import Path
import json
from model_spec import graph,AREA

ms,ss,es=graph()
unit={}
for item,axis in [("砂叶",0),("砂叶种子",0),("荞花",1),("荞花种子",1),("蓝铁矿",2),("源矿",3)]:
    v=[F(0)]*4; v[axis]=F(1); unit[item]=v
while any(m.product not in unit for m in ms.values()):
    progress=False
    for m in ms.values():
        if m.product not in unit and all(x in unit for x,_ in m.needs):
            unit[m.product]=[sum(unit[x][j]*a for x,a in m.needs)/m.amount for j in range(4)]
            progress=True
    assert progress
stock=[F(0)]*4
for m in ms.values():
    for x,a in m.needs:
        for j in range(4):stock[j]+=50*unit[x][j]
    if m.duration==8:
        for j in range(4):stock[j]+=(50+m.amount)*unit[m.product][j]
maxcell=[max(unit[x][j] for _,dst,x in es if dst!="核心") for j in range(4)]
bound=[stock[j]+4900*maxcell[j] for j in range(4)]
items=sorted({x for _,dst,x in es if dst!="核心"})
backup={x:min(int(bound[j]/unit[x][j]) for j in range(4) if unit[x][j]) for x in items}
# Expand all required intermediate reserves from virgin inputs, rounding batches up.
need=Counter(backup)
base={"砂叶","砂叶种子","荞花","荞花种子","蓝铁矿","源矿"}
recipes={m.product:m for m in ms.values() if m.product not in base}
unexpanded=set(recipes)
while unexpanded:
    eligible=[x for x in unexpanded if not any(x in dict(recipes[y].needs) for y in unexpanded)]
    assert eligible
    for x in eligible:
        m=recipes[x]; batches=(need[x]+m.amount-1)//m.amount
        need[x]=0
        for y,a in m.needs:need[y]+=a*batches
        unexpanded.remove(x)

counts=Counter(m.kind for m in ms.values())
body=sum(AREA[k]*v for k,v in counts.items())
omega=F(379-8*counts["研磨机"],2)+max(0,22-2*counts["塑形机"])+24+6
weight=sum((2 if AREA[m.kind]==9 else 3) for m in ms.values())
possible=[]
for p in range(1,(4900-body-81-138)//4+1):
    for j in range(p+1):
        if 23*p-10*j>=len(ms) and 54*p-25*j>=weight:
            a=(4751-16*p+2*j-4*(body-3291)-omega)/4
            possible.append((a,p,j))
best=max(possible)
rectangle=max((w*h,w,h) for w in range(6,69) for h in range(w,69) if w*h<=best[0])
pure=4900-body-81-46*3-4*min(p for _,p,_ in possible)-(len(es)+8)
result={"counts":dict(counts),"machine_count":len(ms),"body_area":body,"routes":len(es),
        "stock_equivalents":list(map(str,stock)),"transport_max_equivalents":list(map(str,maxcell)),
        "total_equivalent_bounds":list(map(str,bound)),"backup":backup,
        "virgin_inputs":{x:need[x] for x in sorted(base)},"power_weight":weight,"E":body-3291,
        "omega":str(omega),"direction_best":[str(best[0]),best[1],best[2]],
        "direction_rectangle":rectangle,"pure_area_bound":pure,
        "rates":{"battery":str(F(3,5)),"capsule":str(F(1,5)*2+F(1,10)+F(1,20)),
                 "source_ore":str(30*F(3,5)),"iron_ore":str(2*(10*F(3,5)+20*F(11,20)))}}
Path(__file__).with_suffix(".json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(result,ensure_ascii=False))
