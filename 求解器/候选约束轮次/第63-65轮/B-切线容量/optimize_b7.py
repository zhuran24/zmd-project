#!/usr/bin/env python3
"""b=7完整条带的整数台数、配方平均流量、全物料割；不假设独占端口。"""
import hashlib
import json
from pathlib import Path
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

OUT = Path(__file__).resolve().parent
data = json.loads((OUT / "recipe_accounting.json").read_text())
recipes = data["recipes"]
items = sorted(set().union(*(set(r["inputs"]) | set(r["outputs"]) for r in recipes)))
kinds = ["粉碎机", "精炼炉", "配件机", "塑形机", "种植机", "采种机"]
global_rates = [18,34,5.5,10.5,34,17,0,17,9,5.5,5.5,6,11,21,5.5,10.5,.6,.55]
assert [(r["kind"],list(r["outputs"])[0]) for r in recipes] == [
 ("粉碎机","源石粉末"),("粉碎机","蓝铁粉末"),("粉碎机","荞花粉末"),("粉碎机","砂叶粉末"),
 ("精炼炉","蓝铁块"),("精炼炉","钢块"),("精炼炉","蓝铁块"),
 ("研磨机","致密蓝铁粉末"),("研磨机","致密源石粉末"),("研磨机","细磨荞花粉末"),
 ("塑形机","钢质瓶"),("配件机","钢制零件"),
 ("种植机","荞花"),("种植机","砂叶"),("采种机","荞花种子"),("采种机","砂叶种子"),
 ("封装机","高容谷地电池"),("灌装机","精选荞愈胶囊")]
nr, nk, ni = len(recipes), len(kinds), len(items)
z = nr+nk
t0 = z+1
nv = t0+ni
lb = np.zeros(nv)
ub = np.full(nv, np.inf)
ub[:nr] = global_rates
ub[16:18] = 0  # 唯一大制造单位为研磨机。
ub[nr:nr+nk] = [5,5,5,5,3,3]
ub[z] = 7
integ = np.zeros(nv)
integ[nr:t0] = 1  # 台数及七个原矿端口中的蓝铁矿口数。
c = np.zeros(nv)
c[t0:] = 1
rows, lo, hi, labels = [], [], [], []
def add(row, low, high, label):
    rows.append(row); lo.append(low); hi.append(high); labels.append(label)
for j,k in enumerate(kinds):
    row = np.zeros(nv)
    for i,r in enumerate(recipes):
        if r["kind"] == k:
            row[i] = 1
    row[nr+j] = -1
    add(row, -.5 if k == "塑形机" else 0, 0, k+"台数与批次")
row=np.zeros(nv); row[7:10]=1
add(row,.5,1,"一台研磨机平均批次")
row=np.zeros(nv); row[7:9]=1
add(row,.5,1,"矿物切线要求G至少二分之一")
row=np.zeros(nv); row[nr:nr+nk]=[3,3,3,3,5,5]
add(row,0,15,"全部机身同过第4行，研磨机以外至多15格宽")
for j,item in enumerate(items):
    net=np.zeros(nv)
    for i,r in enumerate(recipes):
        net[i]=r["outputs"].get(item,0)-r["inputs"].get(item,0)
    constant=0
    if item=="蓝铁矿": net[z]=1
    if item=="源矿": net[z]=-1; constant=7
    a=net.copy(); a[t0+j]=-1
    add(a,-np.inf,-constant,item+"正净流量")
    a=-net; a[t0+j]=-1
    add(a,-np.inf,constant,item+"负净流量")
res=milp(c,integrality=integ,bounds=Bounds(lb,ub),
         constraints=LinearConstraint(np.array(rows),np.array(lo),np.array(hi)),
         options={"time_limit":60,"mip_rel_gap":0})
out=dict(status=int(res.status),message=res.message,variables=nv,constraints=len(rows),
         objective=float(res.fun) if res.fun is not None else None,
         dual_bound=float(res.mip_dual_bound) if getattr(res,"mip_dual_bound",None) is not None else None,
         model="仅条带台数、平均配方率、19种物料守恒和第4行机身宽度；放宽所有端口、供电、时序和外部工厂")
if res.x is not None:
    out["recipe_rates"]=[dict(recipe=r,rate=float(res.x[i])) for i,r in enumerate(recipes) if abs(res.x[i])>1e-8]
    out["machine_counts"]={k:int(round(res.x[nr+j])) for j,k in enumerate(kinds)}
    out["blue_ore_sources"]=int(round(res.x[z]))
    out["absolute_net_item_flows"]={item:float(res.x[t0+j]) for j,item in enumerate(items) if abs(res.x[t0+j])>1e-8}
    out["minimum_slack"]=float(min(np.min(np.array(rows)@res.x-np.array(lo)),np.min(np.array(hi)-np.array(rows)@res.x),np.min(res.x-lb),np.min(ub-res.x)))
(OUT / "b7_optimization.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(out,ensure_ascii=False,indent=2))
