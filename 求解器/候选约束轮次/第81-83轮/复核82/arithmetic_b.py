"""复核乙：逆向配方、有理供需、支持集 + 整数份数优化。"""
import os
os.sched_setaffinity(0,{2})
from pathlib import Path
from fractions import Fraction as Q
from itertools import combinations, product
from math import ceil, gcd
import json,hashlib
from ortools.sat.python import cp_model
OUT=Path(__file__).resolve().parent

# 以 20 tick 为期倒推，回炼率另设参数而非消元。
battery,capsule=12,11
parts,dense_source=10*battery,15*battery
bottles,fine_flower=10*capsule,10*capsule
steel=parts+2*bottles
dense_blue=steel
blue_powder=2*dense_blue; source_powder=2*dense_source
flower_powder=2*fine_flower
sand_powder=dense_blue+dense_source+fine_flower
flower_crush=Q(flower_powder,2); sand_crush=Q(sand_powder,3)
rates={'粉碎机':[str((source_powder+blue_powder+flower_crush+sand_crush)/20),'1'],
       '精炼炉':[str(Q(blue_powder+dense_blue,20)),'1'],
       '研磨机':[str(Q(sand_powder,20)),'0'],'塑形机':[str(Q(bottles,20)),'0'],
       '配件机':[str(Q(parts,20)),'0'],'种植机':[str((2*flower_crush+2*sand_crush)/20),'0'],
       '采种机':[str((flower_crush+sand_crush)/20),'0'],'封装机':['3/5','0'],'灌装机':['11/20','0']}
flows=[blue_powder,source_powder,blue_powder,blue_powder,source_powder,sand_powder,2*sand_crush,2*sand_crush,2*flower_crush,2*flower_crush,flower_powder,dense_blue,steel,dense_source,fine_flower,parts,bottles,battery,capsule]

tables={}
for name,w,cap,need,n0,n1 in [('研磨',6,3,189,32,48),('塑形',3,2,22,6,11),('封装',6,5,30,3,8),('灌装',6,4,22,3,6)]:
    costs=[10**6]*(2*cap+1)
    for mask in range(1<<w):
        indices=[j for j in range(w) if mask>>j&1]
        degree={j:0 for j in indices}
        for a,b in zip(indices,indices[1:]):
            if b-a<=3: degree[a]+=1; degree[b]+=1
        capacities=sorted(degree.values())
        for units in range(min(2*len(capacities),2*cap)+1):
            rem=units; cost=0
            for c in capacities:
                take=min(2,rem); cost+=c*take; rem-=take
            if rem==0: costs[units]=min(costs[units],cost)
    values={}
    for n in range(n0,n1+1):
        model=cp_model.CpModel(); numbers=[model.new_int_var(0,n,f'n{q}') for q in range(len(costs))]
        model.add(sum(numbers)==n); model.add(sum(q*z for q,z in enumerate(numbers))==need)
        model.minimize(sum(c*z for c,z in zip(costs,numbers)))
        solver=cp_model.CpSolver(); solver.parameters.num_search_workers=1; solver.parameters.max_time_in_seconds=30
        st=solver.solve(model); assert st==cp_model.OPTIMAL
        values[n]=str(Q(round(solver.objective_value),2))
    tables[name]={'single_cost_twice':costs,'global':values}

safety=[]
for a,b,m in [(2,1,6),(10,15,5),(10,10,6)]:
    # 穷尽约分料段的所有词；独立查每一前缀。
    na,nb=a//gcd(a,b),b//gcd(a,b)
    vals={0}
    for apos in combinations(range(na+nb),na):
        current=0
        for j in range(na+nb):
            current+=b if j in apos else -a; vals.add(current)
    excursion=max(vals)-min(vals)
    lo=max(b*x-a*50 for x in range(a))
    hi=min(b*50-a*y for y in range(b))
    center=b*50-a*50
    safety.append({'a':a,'b':b,'m':m,'L':lo,'U':hi,'Z0':center,'C':min(center-lo,hi-center),'arbitrary_segment_error':m*excursion,'pass':lo<center-m*excursion and center+m*excursion<hi})

# 条文两类的独立计数。另将一个误料种类加入首件集合。
dead={'研磨':{'only_recipe_inputs_as_heads':4+3*49*(2**2-1)+3*(2**3-1),'including_one_wrong_head_kind':4+3*49*(2**3-1)+3*(2**4-1)}}
for name,a,b in [('封装',10,15),('灌装',10,10)]:
    # 两格都有原料且不足一批：至少一格不足配方；误料首件此时总被拒。
    no_batch=50*50-(51-a)*(51-b)
    ordinary=(a-1)+(b-1)
    dead[name]={'only_recipe_inputs_as_heads':2+ordinary,'including_one_wrong_head_kind':2+no_batch+2*ordinary}

areas={a:[] for a in range(1107,1114)}
for a in areas:
    for w in range(6,int(a**.5)+1):
        if a%w==0 and a//w<=68: areas[a].append([w,a//w])
residues=[]
for a,b in [(10,10),(10,15),(2,1)]:
    for y in range(51):
        for x in range(51):
            left,right=x,y; batches=0
            while left>=a and right>=b:
                left-=a; right-=b; batches+=1
            residues.append([a,b,x,y,batches,left,right])
minima=[68,51,32,6,6,32,16,3,3]
size=[9,9,24,9,9,25,25,24,24]
cost_delta=[36,36,92,34,36,100,100,90,88,36]
result={'machine_rates':rates,'physical_source_rate':[str(sum(flows)/20),'2'],'direction_tables':tables,
        'mixed_safety':safety,'dead_combinations':dead,'areas':areas,'machine_count':sum(minima),'machine_area':sum(n*s for n,s in zip(minima,size)),
        'weighted_minimum':2*sum(minima[i] for i in [0,1,3,4])+3*sum(minima[i] for i in [2,5,6,7,8]),
        'residue_pairs':len(residues),'residue_sha256':hashlib.sha256(json.dumps(sorted(residues)).encode()).hexdigest(),
        'plant_capacity_coefficients':[2*50+max(1,2),2*50+max(1,1),1,2-1,6*50],
        'first_extra_costs':cost_delta,'boundary_X_lower_bounds':[ceil((71-14-8-10)/6),ceil((101-14-16-15)/6),ceil((138-14-16-10)/6)],
        'plant_mean':{'荞花种子':str(4*flower_crush/20),'荞花':str(4*flower_crush/20),'砂叶种子':str(4*sand_crush/20),'砂叶':str(4*sand_crush/20)}}
(OUT/'arithmetic_b.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
