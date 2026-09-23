#!/usr/bin/env python3
"""Global necessary relaxation with unoccupied powered 3x3 centers.
A: native M0, availability indicators and group indicators.
B: independent linear M0, at most one selected center per group, own occupancy.
One fixed partition suffices for a valid (weaker) necessary condition.
"""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.sched_setaffinity(0,set(range(12)))
from pathlib import Path
from collections import defaultdict
import json,hashlib,time,argparse,ast
from ortools.sat.python import cp_model
import cp72,mip72
OUT=Path(__file__).resolve().parent
cp72.ROUNDS=mip72.ROUNDS=OUT.parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--encoding',choices=['A','B'],required=True);p.add_argument('--cap',type=int,default=187)
    p.add_argument('--shift',type=int,nargs=2,default=[0,1]);p.add_argument('--seconds',type=float,default=600);p.add_argument('--workers',type=int,default=2);p.add_argument('--name',required=True);p.add_argument('--subsolver')
    a=p.parse_args();start=time.monotonic();ax,ay=a.shift
    if a.encoding=='A':
        m,bs,vs,score,gaps=cp72.build(cap=a.cap,groups=False);m.clear_objective()
        occ={ast.literal_eval(v.name[4:]):m.get_bool_var_from_proto_index(i) for i,v in enumerate(m.proto.variables) if v.name.startswith('cell')}
        centers=[];classes=defaultdict(list)
        for cx in range(2,69):
            for cy in range(2,69):
                square=cp72.cells(cx-1,cy-1,3,3)
                if square&cp72.HOLE:continue
                u=m.new_bool_var(f'available_{cx}_{cy}');centers.append(u)
                for cell in square:
                    if cell in occ:m.add(u+occ[cell]<=1)
                poles=[vs[i] for i,b in enumerate(bs) if b['kind']=='p' and cx-7<=b['x']<=cx+6 and cy-7<=b['y']<=cy+6]
                m.add(u<=sum(poles));classes[(cx+ax)//3,(cy+ay)//3].append(u)
        flags=[]
        for group,us in classes.items():
            g=m.new_bool_var(f'free_group{group}');flags.append(g);m.add(g<=sum(us))
        m.add(sum(flags)+sum(v for v,b in zip(vs,bs) if b['kind'] in ('s','m','l'))>=217)
    else:
        src,bs,obj,const,gaps=mip72.build(cap=a.cap,groups=False)
        m=cp_model.CpModel();vs=[m.new_int_var(int(lo),int(hi),'v'+str(i)) for i,(lo,hi) in enumerate(zip(src.lb,src.ub))]
        rows=[[] for _ in src.lo]
        for r,c,z in zip(src.rr,src.cc,src.vv):rows[r].append(z*vs[c])
        for terms,lo,hi in zip(rows,src.lo,src.hi):
            if lo!=float('-inf'):m.add(sum(terms)>=int(lo))
            if hi!=float('inf'):m.add(sum(terms)<=int(hi))
        incidence=defaultdict(list)
        for i,b in enumerate(bs):
            for cell in mip72.footprint(tuple(b[k] for k in ('x','y','w','h'))):incidence[cell].append(vs[i])
        occ={cell:m.new_bool_var('own_occupancy'+str(cell)) for cell in incidence}
        for cell,v in occ.items():m.add(v==sum(incidence[cell]))
        centers=[];classes=defaultdict(list)
        for cy in range(2,69):
            for cx in range(2,69):
                small=(cx-1,cy-1,3,3)
                if not mip72.valid(small):continue
                u=m.new_bool_var(f'chosen_center_{cy}_{cx}');centers.append(u);classes[(cx+ax)//3,(cy+ay)//3].append(u)
                for cell in mip72.footprint(small):
                    if cell in occ:m.add(u+occ[cell]<=1)
                allowed=[]
                for i,b in enumerate(bs):
                    if b['kind']!='p':continue
                    if cx-1<b['x']+7 and b['x']-5<cx+2 and cy-1<b['y']+7 and b['y']-5<cy+2:allowed.append(vs[i])
                m.add(u<=sum(allowed))
        for us in classes.values():m.add(sum(us)<=1)
        m.add(sum(centers)+sum(vs[i] for i,b in enumerate(bs) if b['kind'] in ('s','m','l'))>=217)
    out=dict(encoding=a.encoding,scope='M0 plus residual all-pole union; no forced warehouse cells, no residual single-pole capacities',cap=a.cap,shift=a.shift,workers=a.workers,time_limit=a.seconds,
             center_count=len(centers),group_count=len(classes),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),build_seconds=time.monotonic()-start,
             model_sha256=hashlib.sha256(str(m.proto).encode()).hexdigest(),variables=len(m.proto.variables),constraints=len(m.proto.constraints))
    print('BUILT',out,flush=True)
    solver=cp_model.CpSolver();solver.parameters.num_search_workers=a.workers;solver.parameters.max_time_in_seconds=a.seconds;solver.parameters.linearization_level=2;solver.parameters.log_search_progress=True
    if a.subsolver:solver.parameters.subsolvers.append(a.subsolver);out['subsolver']=a.subsolver
    st=solver.solve(m);out.update(status=solver.status_name(st),seconds=time.monotonic()-start,stats=solver.response_stats())
    if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        S=solver.value(score) if a.encoding=='A' else const+sum(int(c)*solver.value(vs[i]) for i,c in enumerate(obj))
        wg=[3*solver.value(g) for g in gaps] if a.encoding=='A' else [3*next(k for k,v in enumerate(gs) if solver.value(vs[v])) for gs in gaps]
        out.update(S=S,chosen=[b for b,v in zip(bs,vs) if solver.value(v)],warehouse_gaps=wg)
    (OUT/(a.name+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print({k:v for k,v in out.items() if k not in ('chosen','stats')},flush=True)
if __name__=='__main__':main()
