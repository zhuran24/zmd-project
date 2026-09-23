#!/usr/bin/env python3
"""Independent threshold checks on M0's safe pole projection, J=0."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.sched_setaffinity(0,set(range(12)))
from pathlib import Path
import json,time,hashlib,argparse,warnings
OUT=Path(__file__).resolve().parent
def main():
    p=argparse.ArgumentParser();p.add_argument('--engine',choices=['native','highs'],required=True);p.add_argument('--cap',type=int,required=True)
    p.add_argument('--seconds',type=float,default=600);p.add_argument('--workers',type=int,default=1);p.add_argument('--name',required=True)
    a=p.parse_args();t=time.monotonic();out=dict(engine=a.engine,cap=a.cap,J=0,scope='M0 safe projection, S <= cap',workers=a.workers,time_limit=a.seconds,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    if a.engine=='native':
        from ortools.sat.python import cp_model
        import cp72
        cp72.ROUNDS=OUT.parents[1]
        m,bs,vs,score,gaps=cp72.build(fixed_j=0,cap=a.cap,project=True);m.clear_objective()
        out.update(model_sha256=hashlib.sha256(str(m.proto).encode()).hexdigest(),domain_count=len(bs),build_seconds=time.monotonic()-t)
        print('BUILT',out,flush=True)
        s=cp_model.CpSolver();s.parameters.num_search_workers=a.workers;s.parameters.max_time_in_seconds=a.seconds;s.parameters.log_search_progress=True;s.parameters.linearization_level=2
        st=s.solve(m);out.update(status=s.status_name(st),stats=s.response_stats())
        if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):out.update(S=s.value(score),chosen=[b for b,v in zip(bs,vs) if s.value(v)],warehouse_gaps=[3*s.value(g) for g in gaps])
    else:
        import mip72, numpy as np
        from scipy.optimize import milp,Bounds,LinearConstraint
        mip72.ROUNDS=OUT.parents[1]
        m,bs,obj,const,gaps=mip72.build(fixed_j=0,cap=a.cap,project=True);A=m.matrix()
        out.update(matrix_sha256=hashlib.sha256(A.data.tobytes()+A.indices.tobytes()+A.indptr.tobytes()+np.array(m.lo).tobytes()+np.array(m.hi).tobytes()).hexdigest(),domain_count=len(bs),build_seconds=time.monotonic()-t)
        print('BUILT',out,flush=True)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore');r=milp(np.zeros(len(m.lb)),integrality=m.integrality,bounds=Bounds(m.lb,m.ub),constraints=LinearConstraint(A,m.lo,m.hi),options={'time_limit':a.seconds,'threads':a.workers,'mip_rel_gap':0.0,'disp':True})
        out.update(status={0:'OPTIMAL',1:'UNKNOWN',2:'INFEASIBLE'}.get(int(r.status),str(r.status)),message=r.message)
        if r.x is not None:
            vals=np.rint(r.x);act=A@vals;assert max(np.max(np.array(m.lo)-act),np.max(act-np.array(m.hi)))<1e-5
            out.update(S=round(obj@vals+const),chosen=[b for i,b in enumerate(bs) if vals[i]>.5],warehouse_gaps=[3*next(k for k,v in enumerate(gs) if vals[v]>.5) for gs in gaps])
    out['seconds']=time.monotonic()-t;(OUT/(a.name+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print({k:v for k,v in out.items() if k not in ('stats','chosen')},flush=True)
if __name__=='__main__':main()
