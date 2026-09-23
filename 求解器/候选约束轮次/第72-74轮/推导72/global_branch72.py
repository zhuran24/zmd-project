#!/usr/bin/env python3
"""Two disjoint J branches of the global-group relaxation, using S>=185."""
import argparse,json,time
from pathlib import Path
from ortools.sat.python import cp_model
import cp72
OUT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('j',type=int,choices=[0,1]);p.add_argument('--seconds',type=float,default=300);a=p.parse_args()
assert json.loads((OUT/'cp_cap184.json').read_text())['status']=='INFEASIBLE'
t=time.monotonic();m,bs,vs,score,gaps=cp72.build(fixed_j=a.j,cap=187,groups=True);m.add(score>=185)
s=cp_model.CpSolver();s.parameters.num_search_workers=1;s.parameters.linearization_level=2;s.parameters.log_search_progress=True;s.parameters.max_time_in_seconds=a.seconds
st=s.solve(m);out=dict(status=s.status_name(st),branch_J=a.j,scope='global group relaxation; 185 <= S <= 187',seconds=time.monotonic()-t,lower=s.best_objective_bound,stats=s.response_stats())
if st in (cp_model.FEASIBLE,cp_model.OPTIMAL):out.update(S=round(s.objective_value),chosen=[b for b,v in zip(bs,vs) if s.value(v)],warehouse_gaps=[3*s.value(g) for g in gaps])
(OUT/('global_J'+str(a.j)+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ('chosen','stats')},ensure_ascii=False))
