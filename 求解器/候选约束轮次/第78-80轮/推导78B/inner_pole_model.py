"""Frozen independent linear boundary encoding plus proved inner-pole condition.
The branch is P=10,J=1. No previous boundary tables or minima are used.
"""
from model77 import build,OUT,save,cells,WEIGHTS
from pathlib import Path
import argparse,time,json,hashlib,os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'

def main():
    a=argparse.ArgumentParser();a.add_argument('--engine',default='cp');a.add_argument('--seconds',type=int,default=120)
    a.add_argument('--workers',type=int,default=2);a.add_argument('--cap',type=int,default=186);a.add_argument('--name',default='inner_cp')
    args=a.parse_args();t=time.monotonic()
    m,units,reward,ware=build(1,args.cap)
    inner=[i for i,u in enumerate(units) if u['kind']=='p' and (u['r'][0]==1 or u['r'][1]==1)]
    m.row([(i,1) for i in inner],1,1)
    result=dict(engine=args.engine,cap=args.cap,inner_pole=True,units=len(units),rows=len(m.rows),variables=len(m.bounds),
      model_sha256=hashlib.sha256(json.dumps([m.bounds,m.rows]).encode()).hexdigest(),
      source_hashes={n:hashlib.sha256((OUT/n).read_bytes()).hexdigest() for n in ('inner_pole_model.py','model77.py','geometry77.py')})
    print('built',result,flush=True);values=None
    if args.engine=='cp':
        from ortools.sat.python import cp_model
        cm=cp_model.CpModel();v=[cm.new_int_var(l,h,str(i)) for i,(l,h) in enumerate(m.bounds)]
        for row,l,h in m.rows:
            ex=sum(v[i]*c for i,c in row)
            if l is not None:cm.add(ex>=l)
            if h is not None:cm.add(ex<=h)
        s=cp_model.CpSolver();s.parameters.num_search_workers=args.workers;s.parameters.max_time_in_seconds=args.seconds
        s.parameters.log_search_progress=True;s.parameters.linearization_level=2
        if args.workers==1:s.parameters.subsolvers.append('quick_restart')
        st=s.solve(cm);result.update(status=s.status_name(st),stats=s.response_stats())
        if st in (cp_model.FEASIBLE,cp_model.OPTIMAL):values=[s.value(x) for x in v]
    else:
        import numpy as np
        from scipy.optimize import milp,Bounds,LinearConstraint
        from scipy.sparse import coo_matrix
        ri=[];ci=[];co=[];lower=[];upper=[]
        for k,(row,l,h) in enumerate(m.rows):
            lower.append(-np.inf if l is None else l);upper.append(np.inf if h is None else h)
            for i,c in row:ri.append(k);ci.append(i);co.append(c)
        mat=coo_matrix((co,(ri,ci)),shape=(len(m.rows),len(m.bounds))).tocsc()
        r=milp(np.zeros(len(m.bounds)),integrality=np.ones(len(m.bounds)),bounds=Bounds(*zip(*m.bounds)),
          constraints=LinearConstraint(mat,lower,upper),options={'time_limit':args.seconds,'threads':args.workers,'disp':True,'mip_rel_gap':0.0})
        result.update(status={0:'OPTIMAL',1:'UNKNOWN',2:'INFEASIBLE'}.get(r.status,str(r.status)),message=r.message)
        if r.x is not None:values=[round(x) for x in r.x]
    if values is not None:
        for row,l,h in m.rows:
            ex=sum(values[i]*c for i,c in row);assert (l is None or ex>=l) and (h is None or ex<=h)
        result['chosen']=[u for i,u in enumerate(units) if values[i]]
        result['S']=298-sum(values[i]*v for i,v in reward)
    result['seconds']=time.monotonic()-t;save(args.name+'.json',result)
    print({k:v for k,v in result.items() if k not in ('stats','chosen','source_hashes')},flush=True)
if __name__=='__main__':main()
