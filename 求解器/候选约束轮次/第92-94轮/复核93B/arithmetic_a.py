"""Independent review A: exact rational recipe elimination and support-based costs.
No derivation-seat modules are read or imported. All output stays beside this file.
"""
from fractions import Fraction as Q
from itertools import combinations
from pathlib import Path
import hashlib, json, math

OUT = Path(__file__).resolve().parent
SNAP = OUT.parent / '前提快照'

# Each tuple is (machine, duration, inputs, outputs), copied from the rule snapshot.
recipes = [
 ('粉碎机',1,{'源矿':1},{'源石粉末':1}),
 ('粉碎机',1,{'蓝铁块':1},{'蓝铁粉末':1}),
 ('粉碎机',1,{'荞花':1},{'荞花粉末':2}),
 ('粉碎机',1,{'砂叶':1},{'砂叶粉末':3}),
 ('精炼炉',1,{'蓝铁矿':1},{'蓝铁块':1}),
 ('精炼炉',1,{'致密蓝铁粉末':1},{'钢块':1}),
 ('精炼炉',1,{'蓝铁粉末':1},{'蓝铁块':1}),
 ('研磨机',1,{'蓝铁粉末':2,'砂叶粉末':1},{'致密蓝铁粉末':1}),
 ('研磨机',1,{'源石粉末':2,'砂叶粉末':1},{'致密源石粉末':1}),
 ('研磨机',1,{'荞花粉末':2,'砂叶粉末':1},{'细磨荞花粉末':1}),
 ('塑形机',1,{'钢块':2},{'钢质瓶':1}),
 ('配件机',1,{'钢块':1},{'钢制零件':1}),
 ('种植机',1,{'荞花种子':1},{'荞花':1}),
 ('种植机',1,{'砂叶种子':1},{'砂叶':1}),
 ('采种机',1,{'荞花':1},{'荞花种子':2}),
 ('采种机',1,{'砂叶':1},{'砂叶种子':2}),
 ('封装机',5,{'钢制零件':10,'致密源石粉末':15},{'高容谷地电池':1}),
 ('灌装机',5,{'钢质瓶':10,'细磨荞花粉末':10},{'精选荞愈胶囊':1}),
]

def eliminate(reflux):
    items=sorted(set().union(*(set(i)|set(o) for _,_,i,o in recipes)) - {'源矿','蓝铁矿'})
    matrix=[]
    demand={'高容谷地电池':Q(3,5),'精选荞愈胶囊':Q(11,20)}
    for item in items:
        matrix.append([Q(o.get(item,0)-i.get(item,0)) for _,_,i,o in recipes]+[demand.get(item,Q(0))])
    matrix.append([Q(j==6) for j in range(18)]+[Q(reflux)])
    row=0
    pivots=[]
    for col in range(18):
        p=next((k for k in range(row,len(matrix)) if matrix[k][col]),None)
        if p is None: continue
        matrix[row],matrix[p]=matrix[p],matrix[row]
        scale=matrix[row][col]
        matrix[row]=[v/scale for v in matrix[row]]
        for k in range(len(matrix)):
            if k!=row and matrix[k][col]:
                q=matrix[k][col]
                matrix[k]=[v-q*w for v,w in zip(matrix[k],matrix[row])]
        pivots.append(col);row+=1
    assert pivots==list(range(18))
    return [matrix[k][-1] for k in range(18)]

def support_costs(length, maxload):
    # Costs and capacities are doubled: integral min-cost allocation on each support.
    best=[10**9]*(2*maxload+1)
    for n in range(length+1):
        for supp in combinations(range(length),n):
            coefficients={s:0 for s in supp}
            for u,v in zip(supp,supp[1:]):
                if v-u<=3: coefficients[u]+=1;coefficients[v]+=1
            slots=sorted(c for c in coefficients.values() for _ in range(2))
            for load in range(min(len(slots),2*maxload)+1):
                best[load]=min(best[load],sum(slots[:load]))
    return best

def group_table(costs, total, maxn):
    d={0:0}; answer={}
    for n in range(1,maxn+1):
        nd={}
        for t,c in d.items():
            for u,v in enumerate(costs):
                if t+u<=total: nd[t+u]=min(nd.get(t+u,10**9),c+v)
        d=nd
        if total in d: answer[str(n)]=str(Q(d[total],2))
    return answer

rates=eliminate(0);rates1=eliminate(1)
machines={}
for (m,t,ins,outs),rate in zip(recipes,rates):
    entry=machines.setdefault(m,{'time':Q(0),'input':Q(0),'output':Q(0)})
    entry['time']+=rate*t;entry['input']+=rate*sum(ins.values());entry['output']+=rate*sum(outs.values())
footprints={'粉碎机':9,'精炼炉':9,'配件机':9,'塑形机':9,'种植机':25,'采种机':25,'研磨机':24,'封装机':24,'灌装机':24}
counts={m:math.ceil(v['time']) for m,v in machines.items()}
input_ports=sum(math.ceil(v['input']) for v in machines.values())
output_ports=sum(max(math.ceil(v['output']),counts[m] if m in ('封装机','灌装机') else 0) for m,v in machines.items())
raw_inputs={s:sum(r*i.get(s,0) for r,(_,_,i,_) in zip(rates,recipes)) for s in ('源矿','蓝铁矿')}
total=sum(r*sum(o.values()) for r,(_,_,_,o) in zip(rates,recipes))+sum(raw_inputs.values())
specs={'研磨机':(6,3,189,48),'塑形机':(3,2,22,12),'封装机':(6,5,30,8),'灌装机':(6,4,22,6)}
costs={m:support_costs(l,c) for m,(l,c,t,n) in specs.items()}
tables={m:group_table(costs[m],t,n) for m,(l,c,t,n) in specs.items()}
omega=sum(Q(tables[m][str(counts[m])]) for m in specs)
increments={m:min(4*footprints[m]+Q(tab[str(n+1)])-Q(tab[str(n)]) for n in range(counts[m],specs[m][3])) for m,tab in tables.items()}
legal=sorted({w*h for w in range(6,69) for h in range(w,69)})
pairs={str(a):[(w,a//w) for w in range(6,69) if a%w==0 and w<=a//w<=68] for a in (1090,1107,1110,1111,1112)}
pj=[]
for p in range(10,70):
    for j in range(p+1):
        if 23*p-10*j>=217 and 54*p-25*j>=520:
            budget=4751-4*1110-16*p+2*j
            if budget>=omega: pj.append([p,j,budget,4639-4440-16*p+2*j])
result={
 'method':'A: Fraction Gaussian elimination; support sets and cheapest capacity slots; dictionary convolution',
 'snapshot_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(SNAP.glob('*.txt'))},
 'recipe_rates_r0':list(map(str,rates)), 'recipe_rate_delta_r':list(map(str,(v-u for u,v in zip(rates,rates1)))),
 'machine_counts':counts,'manufacturing_area':sum(counts[m]*a for m,a in footprints.items()),
 'raw_inputs':{k:str(v) for k,v in raw_inputs.items()},'total_item_output':str(total),
 'machine_input_ports':input_ports,'machine_output_ports_active_products':output_ports,'interfaces':input_ports+output_ports+52+2,
 'single_costs_doubled':costs,'weight_tables':tables,'omega':str(omega),'increment_minima':{k:str(v) for k,v in increments.items()},
 'area_constants':{'remaining_after_machines_core_sources':4900-3291-81-138,'basic_budget':1390-208,'inner_direction_budget':4*1390-921,'general_direction_budget':4*1390-809},
 'factorizations':pairs,'next_below_1110':max(a for a in legal if a<1110),'pj_1110':pj,
}
(OUT/'arithmetic_a.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:result[k] for k in ('manufacturing_area','raw_inputs','interfaces','omega','increment_minima','factorizations')},ensure_ascii=False))
