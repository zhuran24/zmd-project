#!/usr/bin/env python3
"""Independent linear M0 safe projection, CP-SAT quick-restart proof search."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.sched_setaffinity(0,set(range(12)))
from pathlib import Path
import json,time,argparse,hashlib
from ortools.sat.python import cp_model
import mip72
OUT=Path(__file__).resolve().parent;mip72.ROUNDS=OUT.parents[1]
p=argparse.ArgumentParser();p.add_argument('--cap',type=int,default=187);p.add_argument('--seconds',type=float,default=600);p.add_argument('--name',required=True);a=p.parse_args();start=time.monotonic()
src,bs,obj,const,gaps=mip72.build(fixed_j=0,cap=a.cap,project=True)
m=cp_model.CpModel();vs=[m.new_int_var(int(lo),int(hi),'v'+str(i)) for i,(lo,hi) in enumerate(zip(src.lb,src.ub))];rows=[[] for _ in src.lo]
for r,c,z in zip(src.rr,src.cc,src.vv):rows[r].append(z*vs[c])
for row,lo,hi in zip(rows,src.lo,src.hi):
    if lo!=float('-inf'):m.add(sum(row)>=int(lo))
    if hi!=float('inf'):m.add(sum(row)<=int(hi))
out=dict(scope='independent linear M0 safe projection, J=0, S<=cap',cap=a.cap,workers=1,subsolver='quick_restart',time_limit=a.seconds,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),model_sha256=hashlib.sha256(str(m.proto).encode()).hexdigest(),build_seconds=time.monotonic()-start)
print('BUILT',out,flush=True)
s=cp_model.CpSolver();s.parameters.num_search_workers=1;s.parameters.subsolvers.append('quick_restart');s.parameters.linearization_level=2;s.parameters.max_time_in_seconds=a.seconds;s.parameters.log_search_progress=True
st=s.solve(m);out.update(status=s.status_name(st),seconds=time.monotonic()-start,stats=s.response_stats())
if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):out.update(S=const+sum(int(c)*s.value(vs[i]) for i,c in enumerate(obj)),chosen=[b for b,v in zip(bs,vs) if s.value(v)],warehouse_gaps=[3*next(k for k,v in enumerate(gs) if s.value(vs[v])) for gs in gaps])
(OUT/(a.name+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print({k:v for k,v in out.items() if k not in ('stats','chosen')},flush=True)
