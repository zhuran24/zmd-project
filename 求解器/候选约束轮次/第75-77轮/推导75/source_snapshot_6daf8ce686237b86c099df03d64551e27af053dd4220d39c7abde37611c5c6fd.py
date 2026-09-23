#!/usr/bin/env python3
"""R75: unchanged M1, disjoint exact S,J branches; two existing independent encodings."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[k]='1'
os.sched_setaffinity(0,set(range(12)))
import sys, json, time, argparse, hashlib, importlib.util, warnings
from pathlib import Path
OUT=Path(__file__).resolve().parent
ROUNDS=OUT.parents[1]
def load(name):
    path=OUT/(name+'.py')
    spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    mod.ROUNDS=ROUNDS
    return mod
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--engine',choices=['native','linear','highs'],required=True)
    p.add_argument('--s',type=int,required=True);p.add_argument('--j',type=int,required=True)
    p.add_argument('--seconds',type=float,default=180);p.add_argument('--workers',type=int,default=1)
    p.add_argument('--seed',type=int,default=75);p.add_argument('--name',required=True)
    p.add_argument('--fixed');p.add_argument('--hint');p.add_argument('--nogroups',action='store_true')
    p.add_argument('--fixed-bodies');p.add_argument('--union-objective',action='store_true')
    a=p.parse_args();started=time.monotonic()
    from ortools.sat.python import cp_model
    enc=load('cp72' if a.engine=='native' else 'mip72')
    out=dict(engine=a.engine,S_branch=a.s,J_branch=a.j,groups=not a.nogroups,workers=a.workers,seed=a.seed,
             source_sha256=sha(enc.__file__),wrapper_sha256=sha(__file__),time_limit=a.seconds)
    if a.engine=='native':
        m,bs,vs,score,gaps=enc.build(fixed_j=a.j,cap=a.s,groups=not a.nogroups)
        m.add(score==a.s);m.clear_objective()
        # Same Boolean implication as the source, made explicit to the LP.
        for con in list(m.proto.constraints):
            if con.has_bool_or() and not con.enforcement_literal and len(con.bool_or.literals)>20:
                literals=con.bool_or.literals
                m.add(sum(m.get_bool_var_from_proto_index(i) if i>=0 else 1-m.get_bool_var_from_proto_index(-i-1) for i in literals)>=1)
    else:
        src,bs,obj,constant,gaps=enc.build(fixed_j=a.j,cap=a.s,groups=not a.nogroups)
        src.row([(i,int(v)) for i,v in enumerate(obj) if v],a.s-constant,a.s-constant,'exact S branch')
        if a.engine=='linear':
            m=cp_model.CpModel();vs=[m.new_int_var(int(lo),int(hi),'v'+str(i)) for i,(lo,hi) in enumerate(zip(src.lb,src.ub))]
            rows=[[] for _ in src.lo]
            for r,c,z in zip(src.rr,src.cc,src.vv):rows[r].append(vs[c]*z)
            for row,lo,hi in zip(rows,src.lo,src.hi):
                expr=sum(row)
                if lo!=float('-inf'):m.add(expr>=int(lo))
                if hi!=float('inf'):m.add(expr<=int(hi))
        else:vs=list(range(len(src.lb)))
    if a.fixed_bodies:
        w=json.loads(Path(a.fixed_bodies).read_text());keys={tuple(b[k] for k in ('kind','x','y','w','h','axis')) for b in w['chosen'] if b['kind']!='p'}
        for i,b in enumerate(bs):
            if b['kind']=='p':continue
            val=int(tuple(b[k] for k in ('kind','x','y','w','h','axis')) in keys)
            if a.engine=='highs':src.lb[i]=src.ub[i]=val
            else:m.add(vs[i]==val)
    if a.union_objective:
        assert a.engine=='native' and not a.nogroups
        m.maximize(sum(m.get_bool_var_from_proto_index(i) for i,v in enumerate(m.proto.variables) if v.name.startswith('global_center_group')))
    if a.fixed or a.hint:
        w=json.loads(Path(a.fixed or a.hint).read_text());keys={tuple(b[k] for k in ('kind','x','y','w','h','axis')) for b in w['chosen']}
        for i,b in enumerate(bs):
            val=int(tuple(b[k] for k in ('kind','x','y','w','h','axis')) in keys)
            if a.fixed:
                if a.engine=='highs':src.lb[i]=src.ub[i]=val
                else:m.add(vs[i]==val)
            elif a.engine!='highs':m.add_hint(vs[i],val)
    out['build_seconds']=time.monotonic()-started
    out['domain_count']=len(bs);out['domain_sha256']=hashlib.sha256(json.dumps(bs,sort_keys=True).encode()).hexdigest()
    if a.engine=='highs':
        import numpy as np
        from scipy.optimize import milp, Bounds, LinearConstraint
        A=src.matrix();out['matrix_shape']=A.shape;out['nonzeros']=A.nnz
        out['matrix_sha256']=hashlib.sha256(A.data.tobytes()+A.indices.tobytes()+A.indptr.tobytes()+np.array(src.lo).tobytes()+np.array(src.hi).tobytes()).hexdigest()
        print('BUILT',json.dumps(out),flush=True)
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            r=milp(np.zeros(len(src.lb)),integrality=src.integrality,bounds=Bounds(src.lb,src.ub),constraints=LinearConstraint(A,src.lo,src.hi),options={'time_limit':a.seconds,'threads':a.workers,'mip_rel_gap':0.0,'disp':True})
        out.update(status={0:'OPTIMAL',1:'UNKNOWN',2:'INFEASIBLE'}.get(int(r.status),str(r.status)),message=r.message)
        if r.x is not None:
            vals=r.x.copy();integer=np.array(src.integrality)==1;vals[integer]=np.rint(vals[integer]);act=A@vals
            assert max(np.max(np.array(src.lo)-act),np.max(act-np.array(src.hi)))<1e-5
            out.update(S=round(obj@vals+constant),chosen=[b for i,b in enumerate(bs) if vals[i]>.5],warehouse_gaps=[3*next(k for k,g in enumerate(gs) if vals[g]>.5) for gs in gaps])
    else:
        out.update(variables=len(m.proto.variables),constraints=len(m.proto.constraints),model_sha256=hashlib.sha256(str(m.proto).encode()).hexdigest())
        print('BUILT',json.dumps(out),flush=True)
        s=cp_model.CpSolver();s.parameters.num_search_workers=a.workers;s.parameters.max_time_in_seconds=a.seconds
        s.parameters.linearization_level=2;s.parameters.log_search_progress=True;s.parameters.random_seed=a.seed
        st=s.solve(m);out.update(status=s.status_name(st),stats=s.response_stats())
        if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
            out.update(S=a.s,chosen=[b for b,v in zip(bs,vs) if s.value(v)],warehouse_gaps=[3*s.value(g) for g in gaps] if a.engine=='native' else [3*next(k for k,i in enumerate(gs) if s.value(vs[i])) for gs in gaps])
    out['seconds']=time.monotonic()-started
    (OUT/(a.name+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in out.items() if k not in ('chosen','stats')},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
