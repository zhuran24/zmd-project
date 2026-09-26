"""Fresh integer model for review 77. No imported edge table or S lower bound.

All rows are integer linear constraints, built locally. CP-SAT or HiGHS can
execute them. Thus the two engines here are cross-checks of ONE review encoding.
"""
from geometry77 import *
from collections import defaultdict
import os,time,hashlib,argparse
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'

class Model:
    def __init__(self):self.bounds=[];self.rows=[]
    def var(self,lo=0,hi=1):
        i=len(self.bounds);self.bounds.append((lo,hi));return i
    def row(self,terms,lo=None,hi=None):
        d=defaultdict(int)
        for k,v in terms:d[k]+=v
        self.rows.append(([(k,v) for k,v in sorted(d.items()) if v],lo,hi))

def build(j,limit,fixed=None,full=False):
    units=read(OUT/('domain.json' if full else 'projected_domain.json'))
    model=Model();selected=[model.var() for _ in units]
    incidence=defaultdict(list)
    for i,u in enumerate(units):
        for c in cells(u['r']):incidence[c].append(i)
    occupied={c:model.var() for c in sorted(incidence)}
    for c,v in occupied.items():model.row([(v,1)]+[(k,-1) for k in incidence[c]],0,0)
    def oc(ps):return [(occupied[tuple(c)],1) for c in ps if tuple(c) in occupied]
    for i,u in enumerate(units):
        for ps,need in u['ports']:model.row([(i,need)]+oc(ps),hi=len(ps))
    # The 47 paired warehouse patterns are generated from 23 disjoint triples
    # and their one leftover cell. One gap must occupy the shared corner.
    warehouse=[]
    for axis in (0,1):
        flags=[model.var() for _ in range(24)];warehouse.append(flags)
        model.row([(v,1) for v in flags],1,1)
        for gap,v in enumerate(flags):
            ports=[3*k+1+(k>=gap) for k in range(23)]
            for q in ports:
                c=(1,q) if axis==0 else (q,1)
                if c in occupied:model.row([(v,1),(occupied[c],1)],hi=1)
    model.row([(warehouse[0][0],1),(warehouse[1][0],1)],lo=1)
    exceptions=[]
    for i,u in enumerate(units):
        if u['kind']!='l':continue
        directions=[model.var(),model.var()];weak=model.var();exceptions.append(weak)
        model.row([(d,1) for d in directions]+[(i,-1)],0,0)
        model.row([(weak,1),(i,-1)],hi=0)
        for d,(ps,_) in zip(directions,u['ports']):
            model.row(oc(ps)+[(d,3),(weak,-1)],hi=len(ps))
    model.row([(v,1) for v in exceptions],hi=1)
    poles=[i for i,u in enumerate(units) if u['kind']=='p']
    model.row([(i,1) for i in poles],10 if full else 0,10)
    if j is not None:model.row([(i,units[i]['j']) for i in poles],j,j)
    for kind,n in [('s',131),('m',48),('l',38),('c',1)]:
        model.row([(i,1) for i,u in enumerate(units) if u['kind']==kind],hi=n)
    repeats=[]
    for i,u in enumerate(units):
        if u['kind'] not in ('s','m','l'):continue
        cover=[p for p in poles if hit(u['r'],power(units[p]['r'][:2]))]
        repeat=model.var(0,9);repeats.append(repeat)
        model.row([(p,1) for p in cover]+[(i,-1)],lo=0)
        # If selected, repeat is at least the number of selected covering
        # poles minus one. If unselected, zero suffices. This is a relaxation.
        model.row([(repeat,1)]+[(p,-1) for p in cover]+[(i,-10)],lo=-11)
    model.row([(r,1) for r in repeats]+[(p,units[p]['loss']) for p in poles],hi=13)
    reward=[(i,sum(WEIGHTS[c] for c in cells(u['r']))+2*u['j']) for i,u in enumerate(units)]
    model.row(reward,lo=298-limit)
    if fixed is not None:
        data=read(fixed)
        keys={(d['kind'],d['x'],d['y'],d['w'],d['h'],0 if d['axis']=='h' else 1 if d['axis']=='v' else -1) for d in data['chosen']}
        found=set()
        for i,u in enumerate(units):
            key=(u['kind'],*u['r'],u['axis']);value=int(key in keys)
            if value:found.add(key)
            model.row([(i,1)],value,value)
        assert found==keys
    return model,units,reward,warehouse

def main():
    p=argparse.ArgumentParser();p.add_argument('--j',type=int);p.add_argument('--cap',type=int,default=187)
    p.add_argument('--engine',choices=['cp','highs'],default='cp');p.add_argument('--seconds',type=int,default=600)
    p.add_argument('--workers',type=int,default=4);p.add_argument('--name',required=True);p.add_argument('--full',action='store_true');p.add_argument('--fixed')
    a=p.parse_args();t=time.monotonic();m,units,reward,warehouse=build(a.j,a.cap,a.fixed,a.full)
    out=dict(engine=a.engine,J=a.j,cap=a.cap,full=a.full,fixed=a.fixed,edge_tables=False,assumed_S_lower_bound=None,
      units=len(units),variables=len(m.bounds),rows=len(m.rows),model_sha256=hashlib.sha256(json.dumps([m.bounds,m.rows]).encode()).hexdigest(),
      source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),build_seconds=time.monotonic()-t)
    print('built',out,flush=True);values=None
    if a.engine=='cp':
        from ortools.sat.python import cp_model
        import ortools
        cm=cp_model.CpModel();vs=[cm.new_int_var(l,h,str(i)) for i,(l,h) in enumerate(m.bounds)]
        for row,lo,hi in m.rows:
            expr=sum(vs[i]*v for i,v in row)
            if lo is not None:cm.add(expr>=lo)
            if hi is not None:cm.add(expr<=hi)
        solver=cp_model.CpSolver();solver.parameters.num_search_workers=a.workers
        solver.parameters.max_time_in_seconds=a.seconds;solver.parameters.log_search_progress=True
        solver.parameters.linearization_level=2;solver.parameters.random_seed=7701
        st=solver.solve(cm);out.update(status=solver.status_name(st),solver_version=ortools.__version__,stats=solver.response_stats())
        if st in (cp_model.FEASIBLE,cp_model.OPTIMAL):values=[solver.value(v) for v in vs]
    else:
        import numpy as np, scipy
        from scipy.optimize import milp,Bounds,LinearConstraint
        from scipy.sparse import coo_matrix
        ri=[];ci=[];co=[];low=[];high=[]
        for k,(row,lo,hi) in enumerate(m.rows):
            low.append(-np.inf if lo is None else lo);high.append(np.inf if hi is None else hi)
            for i,v in row:ri.append(k);ci.append(i);co.append(v)
        mat=coo_matrix((co,(ri,ci)),shape=(len(m.rows),len(m.bounds))).tocsc()
        result=milp(np.zeros(len(m.bounds)),integrality=np.ones(len(m.bounds)),bounds=Bounds(*zip(*m.bounds)),
          constraints=LinearConstraint(mat,low,high),options={'disp':True,'time_limit':a.seconds,'threads':a.workers,'mip_rel_gap':0.0})
        out.update(status={0:'OPTIMAL',1:'UNKNOWN',2:'INFEASIBLE'}.get(result.status,str(result.status)),message=result.message,solver_version=scipy.__version__)
        if result.x is not None:values=[round(v) for v in result.x]
    if values is not None:
        assert all(l<=v<=h for (l,h),v in zip(m.bounds,values))
        for row,lo,hi in m.rows:
            v=sum(values[i]*coef for i,coef in row)
            assert (lo is None or v>=lo) and (hi is None or v<=hi)
        out.update(S=298-sum(values[i]*v for i,v in reward),chosen=[u for i,u in enumerate(units) if values[i]],
          warehouse_gaps=[3*next(k for k,v in enumerate(gs) if values[v]) for gs in warehouse])
    out['seconds']=time.monotonic()-t;save(a.name+'.json',out);print({k:v for k,v in out.items() if k not in ('stats','chosen')},flush=True)
if __name__=='__main__':main()
