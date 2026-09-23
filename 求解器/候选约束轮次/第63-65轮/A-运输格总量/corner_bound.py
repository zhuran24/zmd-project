#!/usr/bin/env python3
"""Necessary relaxation: free ore assignment to disjoint 3x3 first consumers.

No prescribed source/sink pairing, routes, orientation, or pure-material machines.
An integral matching is a relaxation of each actual fractional source/consumer
flow, since consumers take at most one raw ore per tick. All files stay here.
"""
from pathlib import Path
import json
from ortools.sat.python import cp_model

HERE = Path(__file__).resolve().parent

def ports(gap):
    return [s + 1 for s in range(0, gap, 3)] + [s + 1 for s in range(gap + 1, 70, 3)]

def dist(p, x, y):
    return max(x-p[0], 0, p[0]-x-2) + max(y-p[1], 0, p[1]-y-2)

def solve(gleft, gbottom, n=4, cutoff=7, budget=None):
    all_sources = [(1,y) for y in ports(gleft)] + [(x,1) for x in ports(gbottom)]
    sources = [(1,y) for y in ports(gleft)[:n]] + [(x,1) for x in ports(gbottom)[:n]]
    forced = set(all_sources)
    candidates=[]
    for x in range(1, min(68,max(p[0] for p in sources)+cutoff)):
        for y in range(1, min(68,max(p[1] for p in sources)+cutoff)):
            cells = [(a,b) for a in range(x,x+3) for b in range(y,y+3)]
            if any(p in forced for p in cells):
                continue
            costs=[dist(p,x,y) for p in sources]
            if min(costs)<cutoff:
                candidates.append((x,y,cells,costs))
    m=cp_model.CpModel()
    selected=[m.new_bool_var(f'm_{x}_{y}') for x,y,_,_ in candidates]
    assignments=[]
    bysource=[[] for _ in sources]
    bytarget=[[] for _ in candidates]
    weighted=[]
    for j,(_,_,_,costs) in enumerate(candidates):
        for i,c in enumerate(costs):
            if c<cutoff:
                v=m.new_bool_var(f'a_{i}_{j}')
                assignments.append((i,j,c,v))
                bysource[i].append(v)
                bytarget[j].append(v)
                weighted.append((c-1)*v)
    # Independent dummy consumers: distance >= cutoff receives the relaxed
    # cost cutoff; unlimited disjointness is granted outside the local model.
    dummy=[]
    for i in range(len(sources)):
        v=m.new_bool_var(f'dummy_{i}')
        dummy.append(v)
        m.add(sum(bysource[i])+v==1)
        weighted.append((cutoff-1)*v)
    for j,vs in enumerate(bytarget):
        m.add(sum(vs)==selected[j])
    covering={}
    for j,(_,_,cells,_) in enumerate(candidates):
        for cell in cells:
            covering.setdefault(cell,[]).append(selected[j])
    for vs in covering.values():
        m.add(sum(vs)<=1)
    if budget is None:
        m.minimize(sum(weighted))
    else:
        m.add(sum(weighted)<=budget)
    solver=cp_model.CpSolver()
    solver.parameters.num_search_workers=1
    solver.parameters.max_time_in_seconds=20
    status=solver.solve(m)
    result=dict(gap_left=gleft,gap_bottom=gbottom,n=n,cutoff=cutoff,budget=budget,
                sources=sources,candidate_count=len(candidates),status=solver.status_name(status),
                bound=solver.best_objective_bound,wall_time=solver.wall_time)
    if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        if budget is None:
            result['minimum_excess_or_incumbent']=solver.objective_value
        result['assignment_excess']=sum((c-1)*solver.value(v) for _,_,c,v in assignments)+(cutoff-1)*sum(solver.value(v) for v in dummy)
        result['assignment']=[dict(source=sources[i],machine=list(candidates[j][:2]),distance=c)
                              for i,j,c,v in assignments if solver.value(v)]
        result['dummy_sources']=[sources[i] for i,v in enumerate(dummy) if solver.value(v)]
    return result

def main():
    rows=[]
    # Only one orientation needed computationally; transposition is exact.
    for gap in range(0,70,3):
        row=solve(gap,0)
        rows.append(row)
        print(json.dumps(row,ensure_ascii=False),flush=True)
        (HERE/'corner_bound.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    main()
