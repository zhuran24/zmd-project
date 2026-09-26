"""单桩几何：独立格集合 + CP-SAT 编码。两线程，限 5 核亲和。"""
import os
os.sched_setaffinity(0,{0,1,2,3,4})
os.environ['OMP_NUM_THREADS']='1'
from pathlib import Path
import json, time, hashlib
from ortools.sat.python import cp_model
OUT=Path(__file__).resolve().parent

def domain(edge):
    pole={(x,y) for x in (5,6) for y in (5,6)}
    opts=[]
    for w,h,axis,weight in [(3,3,0,2),(3,3,1,2),(5,5,0,3),(5,5,1,3),(6,4,1,3),(4,6,0,3)]:
        for x in range(-8,12):
            for y in range(-8,12):
                cells={(i,j) for i in range(x,x+w) for j in range(y,y+h)}
                if not any(0<=i<12 and 0<=j<12 for i,j in cells) or cells & pole: continue
                if edge and any(i>6 for i,j in cells): continue
                if axis==0: sides=[{(x-1,j) for j in range(y,y+h)},{(x+w,j) for j in range(y,y+h)}]
                else: sides=[{(i,y-1) for i in range(x,x+w)},{(i,y+h) for i in range(x,x+w)}]
                sides=[s-pole for s in sides]
                if edge: sides=[{g for g in s if g[0]<=6} for s in sides]
                if all(sides): opts.append((x,y,w,h,axis,weight,cells,sides))
    return opts

def solve(edge,count,target):
    opts=domain(edge); m=cp_model.CpModel(); z=[m.new_bool_var(f'x{i}') for i in range(len(opts))]
    bycell={}
    for i,o in enumerate(opts):
        for g in o[6]: bycell.setdefault(g,[]).append(i)
    occ={}
    for g,ix in bycell.items():
        a=m.new_bool_var('c'+str(g)); m.add(a==sum(z[i] for i in ix)); occ[g]=a
    for i,o in enumerate(opts):
        for side in o[7]:
            m.add(z[i]+sum(occ[g] for g in side if g in occ)<=len(side))
    m.add(sum(z)<=14 if edge else sum(z)<=23)
    weights=[1 if count else o[5] for o in opts]
    m.add(sum(w*x for w,x in zip(weights,z))>=target)
    solver=cp_model.CpSolver(); solver.parameters.num_search_workers=2
    solver.parameters.max_time_in_seconds=600
    solver.parameters.random_seed=82001
    t=time.monotonic(); status=solver.solve(m)
    res={'edge':edge,'count':count,'target':target,'options':len(opts),'status':solver.status_name(status),'seconds':time.monotonic()-t,'stats':solver.response_stats(),
         'domain_sha256':hashlib.sha256(json.dumps([list(o[:6])+[sorted(o[6]),list(map(sorted,o[7]))] for o in opts],sort_keys=True).encode()).hexdigest()}
    if status in (cp_model.OPTIMAL,cp_model.FEASIBLE): res['placements']=[list(o[:6]) for o,x in zip(opts,z) if solver.value(x)]
    fname=f'power_a_{"edge" if edge else "general"}_{"count" if count else "weight"}.json'
    (OUT/fname).write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(res),flush=True)
    return res

if __name__=='__main__':
    for edge,count,target in [(True,True,14),(True,False,30),(False,False,55)]: solve(edge,count,target)
