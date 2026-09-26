"""Independent accounting B: backward recipe substitution and integer profile counts."""
import os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
os.sched_setaffinity(0,set(sorted(os.sched_getaffinity(0))[:5]))
from pathlib import Path
from fractions import Fraction as F
from itertools import product
import json, math
from ortools.sat.python import cp_model
OUT=Path(__file__).resolve().parent

def support_cost(length, cap):
    result={}
    for flows in product(range(3),repeat=length):
        q=sum(flows)
        if q>2*cap:continue
        occupied=[i for i,f in enumerate(flows) if f]
        cost=0
        for i in occupied:
            previous=max((k for k in occupied if k<i),default=-100)
            following=min((k for k in occupied if k>i),default=100)
            cost+=flows[i]*(int(i-previous<=3)+int(following-i<=3))
        result[q]=min(result.get(q,10**9),cost)
    return result

def tables():
    settings=[('研磨机',6,3,189,32,48,24),('塑形机',3,2,22,6,11,9),
        ('封装机',6,5,30,3,8,24),('灌装机',6,4,22,3,6,24)]
    result={}
    for name,length,cap,target,low,high,area in settings:
        costs=support_cost(length,cap); values={}; witnesses={}
        for n in range(low,high+1):
            model=cp_model.CpModel(); x={q:model.NewIntVar(0,n,f'x{q}') for q in costs}
            model.Add(sum(x.values())==n);model.Add(sum(q*v for q,v in x.items())==target)
            model.Minimize(sum(costs[q]*v for q,v in x.items()))
            solver=cp_model.CpSolver();solver.parameters.num_workers=1
            solver.parameters.max_time_in_seconds=30
            status=solver.Solve(model);assert status==cp_model.OPTIMAL
            counts={q:solver.Value(v) for q,v in x.items() if solver.Value(v)}
            assert sum(counts.values())==n and sum(q*c for q,c in counts.items())==target
            value=F(sum(costs[q]*c for q,c in counts.items()),2)
            values[str(n)]=str(value);witnesses[str(n)]={str(q):c for q,c in counts.items()}
        base=F(values[str(low)])
        result[name]=dict(single=[str(F(costs[q],2)) for q in range(2*cap+1)],weight=values,
            net_cost={str(n):str(4*area*(n-low)+F(values[str(n)])-base) for n in range(low,high+1)},
            first_cost=str(4*area+F(values[str(low+1)])-base),profile_witnesses=witnesses)
    return result

def flow():
    # Backwards from the two products; pairs mean constant and coefficient of r.
    battery=F(3,5);capsule=F(11,20)
    part=10*battery;source_dense=15*battery;bottle=fine_buck=10*capsule
    steel=part+2*bottle;blue_dense=steel
    sandpow=blue_dense+source_dense+fine_buck
    sand_crush=sandpow/3;buck_crush=2*fine_buck/2
    rr=[(18,0),(34,1),(buck_crush,0),(sand_crush,0),
        (34,0),(steel,0),(0,1),(blue_dense,0),(source_dense,0),(fine_buck,0),
        (bottle,0),(part,0),(2*buck_crush,0),(2*sand_crush,0),
        (buck_crush,0),(sand_crush,0),(battery,0),(capsule,0)]
    rr=[tuple(map(F,p)) for p in rr]
    # Independently specified recipe stoichiometry, in rule order.
    rec=[({'源矿':1},{'源石粉末':1}),({'蓝铁块':1},{'蓝铁粉末':1}),
        ({'荞花':1},{'荞花粉末':2}),({'砂叶':1},{'砂叶粉末':3}),
        ({'蓝铁矿':1},{'蓝铁块':1}),({'致密蓝铁粉末':1},{'钢块':1}),
        ({'蓝铁粉末':1},{'蓝铁块':1}),
        ({'蓝铁粉末':2,'砂叶粉末':1},{'致密蓝铁粉末':1}),
        ({'源石粉末':2,'砂叶粉末':1},{'致密源石粉末':1}),
        ({'荞花粉末':2,'砂叶粉末':1},{'细磨荞花粉末':1}),
        ({'钢块':2},{'钢质瓶':1}),({'钢块':1},{'钢制零件':1}),
        ({'荞花种子':1},{'荞花':1}),({'砂叶种子':1},{'砂叶':1}),
        ({'荞花':1},{'荞花种子':2}),({'砂叶':1},{'砂叶种子':2}),
        ({'钢制零件':10,'致密源石粉末':15},{'高容谷地电池':1}),
        ({'钢质瓶':10,'细磨荞花粉末':10},{'精选荞愈胶囊':1})]
    balance={}
    for (ins,outs),v in zip(rec,rr):
        for sign,side in ((-1,ins),(1,outs)):
            for g,c in side.items():
                old=balance.get(g,(0,0));balance[g]=tuple(a+sign*c*b for a,b in zip(old,v))
    expected={'源矿':(-18,0),'蓝铁矿':(-34,0),'高容谷地电池':(battery,0),'精选荞愈胶囊':(capsule,0)}
    assert all(v==expected.get(g,(0,0)) for g,v in balance.items())
    out=tuple((52 if j==0 else 0)+sum(v[j]*sum(o.values()) for (i,o),v in zip(rec,rr)) for j in (0,1))
    assert out==(F(6113,20),2)
    return dict(affine_rates=[[str(v) for v in r] for r in rr],balances={k:[str(v) for v in a] for k,a in balance.items()},
        output=[str(v) for v in out],plant_mean={'荞花种子':22,'荞花':22,'砂叶种子':42,'砂叶':42})

def main():
    result=dict(cost_tables=tables(),flow=flow())
    a=json.loads((OUT/'accounts_a.json').read_text())
    assert result['flow']['affine_rates']==[r['affine'] for r in a['flow']['recipes']]
    for name,v in result['cost_tables'].items():
        for key in ('single','weight','net_cost','first_cost'): assert v[key]==a['cost_tables'][name][key]
    # Analytic global budget independently enumerates all possible P,J up to the official cap.
    supply=[(p,j,4751-4*1110-16*p+2*j) for p in range(10,19) for j in range(p+1)
        if 25*j<=54*p-520 and 10*j<=23*p-217]
    assert max(z[2] for z in supply)==151
    assert max(z[2] for z in supply if z[0]>=11)==139
    assert F(219,2)+2*34>151 and F(219,2)+34>139
    result['budget_maximum']=151;result['budget_maximum_P_ge_11']=139
    next_factor=next(n for n in range(1109,35,-1) if any(n%d==0 and 6<=n//d<=68 for d in range(6,69)))
    assert next_factor==a['budget']['next_below_1110']==1107
    result['next_below_1110']=next_factor
    result['all_independent_checks_equal']=True
    (OUT/'accounts_b.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'all_independent_checks_equal':True,'budget_maximum':151,'budget_maximum_P_ge_11':139,
        'weights':{k:v['weight'] for k,v in result['cost_tables'].items()}},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
