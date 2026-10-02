"""编码甲：逐台图、Fraction 当量、配方递归、整数枚举。"""
from fractions import Fraction as F
from collections import Counter
import json
from pathlib import Path
from model_data import build, RECIPES

nodes,routes,inc,out=build()
counts=Counter(r[0] for r in nodes.values())
small=sum(counts[x] for x in ['粉碎机','精炼炉','配件机','塑形机'])
medium=sum(counts[x] for x in ['种植机','采种机'])
large=sum(counts[x] for x in ['研磨机','封装机','灌装机'])
area=small*9+medium*25+large*24
base={'砂叶':(1,0,0,0),'砂叶种子':(1,0,0,0),'荞花':(0,1,0,0),'荞花种子':(0,1,0,0),'蓝铁矿':(0,0,1,0),'源矿':(0,0,0,1)}
equiv={k:tuple(map(F,v)) for k,v in base.items()}
todo=[r for r in RECIPES.values() if r[2] not in equiv and r[4]==8]
while todo:
    pending=[]
    for kind,inputs,product,q,d in todo:
        if all(x in equiv for x in inputs):
            equiv[product]=tuple(sum(equiv[x][k]*n for x,n in inputs.items())/q for k in range(4))
        else: pending.append((kind,inputs,product,q,d))
    assert len(pending)<len(todo)
    todo=pending
capacity=[F(0) for _ in range(4)]
for kind,inputs,product,q,d in nodes.values():
    for x in inputs:
        for k in range(4): capacity[k]+=50*equiv[x][k]
    if d==8:
        for k in range(4):
            cap_cache=max(q*equiv[product][k],sum(n*equiv[x][k] for x,n in inputs.items()))
            capacity[k]+=50*equiv[product][k]+cap_cache
route_max=[max(equiv[x][k] for _,_,x in routes if x in equiv) for k in range(4)]
total=[capacity[k]+4900*route_max[k] for k in range(4)]
stock={x:min(int(total[k]//v[k]) for k in range(4) if v[k]) for x,v in equiv.items()}
production={r[2]:(r[1],r[3]) for r in RECIPES.values() if r[2] not in base}
# 合并需求后逐产物展开，整批多出的粉末可用于下一种备用品。
need=Counter(stock)
pending=set(production)&set(need)
while pending:
    choices=[x for x in pending if not any(x in production[y][0] for y in pending)]
    assert choices
    for x in choices:
        ingredients,q=production[x]
        batches=(need[x]+q-1)//q
        for item,amount in ingredients.items():need[item]+=batches*amount
        pending.remove(x)
raw={item:need[item] for item in base}

# 最终速率作为证明结论输入，逐层守恒回算所有机器、进路。
rate={f'E{i}':F(1,5) for i in range(1,4)}
rate.update(F1=F(1,5),F2=F(1,5),F3=F(1,10),F4=F(1,20))
edge_rate={}
while True:
    old=len(rate)
    for name,rr in list(rate.items()):
        for j in inc[name]:
            item=routes[j][2]
            same=sum(routes[z][2]==item for z in inc[name])
            edge_rate[j]=rr*nodes[name][1][item]/same
    for name,rec in nodes.items():
        if name not in rate and all(j in edge_rate for j in out[name]):
            rate[name]=sum(edge_rate[j] for j in out[name])/rec[3]
    # 采种回路 2 c = a+b, a=c, b=k，故 c=a=b=k。
    for pref,n in [('S',13),('J',6)]:
        for i in range(1,n+1):
            if f'{pref}K{i}' in rate:
                for letter in 'CAB':rate[f'{pref}{letter}{i}']=rate[f'{pref}K{i}']
    if len(rate)==old:break
assert len(rate)==len(nodes)
for j,(a,b,x) in enumerate(routes):
    if b=='核心':edge_rate[j]=rate[a]
assert len(edge_rate)==len(routes) and min(edge_rate.values())>0
recipe_rates=Counter()
for n,rec in nodes.items():recipe_rates[rec[0]]+=rate[n]
shared=[j for j,(a,b,x) in enumerate(routes) if a=='核心' or (a.startswith(('SK','JK')) and len(out[a])>1)]
omega=F(379-8*counts['研磨机'],2)+max(0,22-2*counts['塑形机'])+24+6
weight=2*small+3*(medium+large)
pj=[(p,j) for p in range(0,1226) for j in range(p+1)
    if 23*p-10*j>=len(nodes) and 54*p-25*j>=weight]
best=min(16*p-2*j for p,j in pj)
best_pj=[(p,j) for p,j in pj if 16*p-2*j==best]
bound=(4751-best-4*(area-3291)-omega)/4
bound_specific=bound-F(2*len(routes)-619,4)
weights={'砂叶种子':2,'荞花种子':2,'砂叶':3,'荞花':3,'蓝铁矿':1,'源矿':1,
         '蓝铁块':2,'蓝铁粉末':3,'源石粉末':2,'砂叶粉末':4,'荞花粉末':4,
         '致密蓝铁粉末':11,'致密源石粉末':9,'细磨荞花粉末':13,'钢块':12,'钢制零件':13,'钢质瓶':25}
deltas={name:q*weights[prod]-sum(v*weights[x] for x,v in inputs.items())
        for name,(kind,inputs,prod,q,d) in RECIPES.items() if d==8}
assert min(deltas.values())>0
def dims(b):
    vals=[(w*h,w,h) for w in range(6,69) for h in range(w,69) if w*h<=b]
    top=max(x[0] for x in vals)
    return top,[(w,h) for a,w,h in vals if a==top]
result={
 'machines':dict(counts),'machine_count':len(nodes),'classes':[small,medium,large],
 'machine_area':area,'route_count':len(routes),'interfaces':2*len(routes),'shared_routes':len(shared),
 'power_weight':weight,'best_pj':best_pj,'power_cost':best,'extra_area':area-3291,
 'omega':str(omega),'generic_A':str(bound),'specific_A':str(bound_specific),
 'generic_integer_dimensions':dims(bound),'specific_integer_dimensions':dims(bound_specific),
 'generic_T_min':(717+omega).__ceil__()//4 + (int((717+omega).__ceil__())%4>0),
 'generic_T_plus_F_min':((809+omega-2)/4).__ceil__(),
 'specific_T_min':((2*len(routes)+98+omega)/4).__ceil__(),
 'T_plus_F_min':((2*len(routes)+190+omega-2)/4).__ceil__(),
 'transport_slots_upper':2*(4900-area-81-46*3),'route_slots_lower':len(routes)+8,
 'no_double_bridge_A_plus_F':4900-area-81-138-44-(len(routes)+8),
 'machine_equivalent_capacity':[str(x) for x in capacity],
 'transport_equivalent_max':[str(x) for x in route_max],
 'equivalent_capacity':[str(x) for x in total], 'stock':stock,'raw_stock':dict(raw),
 'cleanup_bound':52*50+18*(50+3)+9*(100+50+3)+3*100+2*70*70,
 'recipe_rates':{k:str(v) for k,v in recipe_rates.items()},
 'mine_rates':{x:str(sum(edge_rate[j] for j,(_,_,it) in enumerate(routes) if it==x)) for x in ['蓝铁矿','源矿']},
 'all_mine_routes_one':all(v==1 for j,v in edge_rate.items() if routes[j][2] in ('蓝铁矿','源矿')),
 'all_routes_positive':all(v>0 for v in edge_rate.values()),
 'plant_loop_constant':str(50+50+50+1+1+F(50,2)),
 'cycle_480_deliveries':[str(480*F(3,40)),str(480*F(11,160))],
 'cycle_480_mine_per_route':str(F(480,8)),
 'nonfinal_weight_increases':deltas,
 'plant_K_rates':{n:str(rate[n]) for n in rate if n.startswith(('SK','JK'))},
}
Path(__file__).with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False,indent=2))
