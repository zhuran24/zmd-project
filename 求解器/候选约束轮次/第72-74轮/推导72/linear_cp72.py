#!/usr/bin/env python3
"""Solve the separately written MIP encoding with CP-SAT as a second audit.
Occupancy is integral by its equality; repeats may be made integral WLOG
because the least feasible value for fixed bodies is max(0,k-1).
"""
import argparse,json,time,hashlib
from pathlib import Path
from ortools.sat.python import cp_model
import mip72
OUT=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--cap',type=int,required=True);p.add_argument('--seconds',type=float,default=180);p.add_argument('--name',required=True);p.add_argument('--groups',action='store_true');p.add_argument('--project',action='store_true');p.add_argument('--j',type=int);a=p.parse_args()
t=time.monotonic();src,bs,obj,constant,gaps=mip72.build(False,a.j,a.cap,a.project,a.groups)
m=cp_model.CpModel();v=[m.new_int_var(int(lo),int(hi),'v'+str(i)) for i,(lo,hi) in enumerate(zip(src.lb,src.ub))]
rows=[[] for _ in src.lo]
for r,c,z in zip(src.rr,src.cc,src.vv):rows[r].append(v[c]*z)
for row,lo,hi in zip(rows,src.lo,src.hi):
    expr=sum(row)
    if lo!=float('-inf'):m.add(expr>=int(lo))
    if hi!=float('inf'):m.add(expr<=int(hi))
# Feasibility search, no optimization or imported lower bound.
s=cp_model.CpSolver();s.parameters.max_time_in_seconds=a.seconds;s.parameters.num_search_workers=1;s.parameters.linearization_level=2;s.parameters.log_search_progress=True
st=s.solve(m);out=dict(encoding='independent linear MIP',engine='CP-SAT',status=s.status_name(st),cap=a.cap,project=a.project,groups=a.groups,branch_J=a.j,seconds=time.monotonic()-t,stats=s.response_stats(),mip_script_sha256=hashlib.sha256(Path(mip72.__file__).read_bytes()).hexdigest())
if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
    out.update(S=constant+sum(int(z)*s.value(v[i]) for i,z in enumerate(obj)),chosen=[b for i,b in enumerate(bs) if s.value(v[i])],warehouse_gaps=[3*next(k for k,i in enumerate(gs) if s.value(v[i])) for gs in gaps])
(OUT/(a.name+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ('stats','chosen')},ensure_ascii=False))
