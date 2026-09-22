#!/usr/bin/env python3
"""Separate linear MIP encoding of the independently generated bodies."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[k]='1'
import argparse,json,time,hashlib,warnings
from collections import defaultdict
from dataclasses import asdict
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_array
from boundary62 import generate,measures,BASE

def mip_solve(R,seconds=300,edge0=False,fixed_p=None,cap=None,mode='joint',disp=False):
    start=time.monotonic()
    bodies,X,Y=generate(R,mode,edge0)
    weights=X+Y if mode=='joint' else X if mode=='X' else Y
    n=len(bodies); P=n; H=n+1
    incidence=defaultdict(list)
    for i,b in enumerate(bodies):
        for c in b.footprint(): incidence[c].append(i)
    occ={c:n+2+i for i,c in enumerate(sorted(incidence))}
    N=n+2+len(occ)
    rows=[];cols=[];vals=[];rl=[];ru=[]
    def row(pairs,lo=-np.inf,hi=np.inf):
        r=len(rl)
        for c,v in pairs:
            if v: rows.append(r);cols.append(c);vals.append(v)
        rl.append(lo);ru.append(hi)
    for c,i in occ.items(): row([(i,1)]+[(j,-1) for j in incidence[c]],0,0)
    for i,b in enumerate(bodies):
        for group,need in zip(b.ports,b.needs):
            row([(i,need)]+[(occ[c],1) for c in group if c in occ],hi=len(group))
    for kind,lim in [('s',131),('m',48),('l',38),('c',1)]:
        row([(i,1) for i,b in enumerate(bodies) if b.kind==kind],hi=lim)
    row([(i,1) for i,b in enumerate(bodies) if b.kind=='p']+[(H,1),(P,-1)],hi=0)
    row([(i,b.loss) for i,b in enumerate(bodies) if b.kind=='p']+[(H,9),(P,-23)],hi=-217)
    objective=np.zeros(N)
    for i,b in enumerate(bodies):
        objective[i]=-sum(weights[c] for c in b.footprint())-(2*b.j if mode=='joint' else 0)
    if mode=='joint': objective[P]=16;objective[H]=-2
    constant=sum(weights.values())
    if cap is not None: row([(i,v) for i,v in enumerate(objective) if v],hi=cap-constant)
    lb=np.zeros(N);ub=np.ones(N)
    lb[P]=fixed_p if fixed_p is not None else 10
    ub[P]=fixed_p if fixed_p is not None else 12
    ub[H]=12
    matrix=coo_array((np.array(vals,dtype=float),(np.array(rows,dtype=np.int32),np.array(cols,dtype=np.int32))),shape=(len(rl),N)).tocsc()
    fingerprint=hashlib.sha256(matrix.data.tobytes()+matrix.indices.tobytes()+matrix.indptr.tobytes()+objective.tobytes()+np.array(ru).tobytes()).hexdigest()
    build_seconds=time.monotonic()-start
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',message='Unrecognized options detected')
        res=milp(objective if cap is None else np.zeros(N),integrality=np.ones(N),bounds=Bounds(lb,ub),
                 constraints=LinearConstraint(matrix,np.array(rl),np.array(ru)),
                 options={'time_limit':seconds,'mip_rel_gap':0.0,'threads':1,'disp':disp})
    out={'R':R,'mode':mode,'allow_edge0_ports':edge0,'fixed_P':fixed_p,'cap':cap,'solver':'scipy_highs',
         'threads':1,'status':int(res.status),'message':res.message,'build_seconds':build_seconds,
         'solve_seconds':time.monotonic()-start-build_seconds,'bodies':n,'rows':len(rl),'variables':N,
         'matrix_sha256':fingerprint}
    if cap is None and getattr(res,'mip_dual_bound',None) is not None:
        out['lower_bound']=float(res.mip_dual_bound+constant)
        out['gap']=float(res.mip_gap)
    if res.x is not None:
        rounded=np.rint(res.x)
        assert np.max(np.abs(res.x-rounded))<1e-5
        activity=matrix@rounded
        assert np.all(activity>=np.array(rl)-1e-6) and np.all(activity<=np.array(ru)+1e-6)
        chosen=[b for i,b in enumerate(bodies) if rounded[i]==1]
        occupied=set(c for b in chosen for c in b.footprint())
        xval=sum(v for c,v in X.items() if c not in occupied)
        yval=sum(v for c,v in Y.items() if c not in occupied)
        p=int(rounded[P]);h=int(rounded[H]);j=h+sum(b.j for b in chosen)
        out.update({'objective':int(objective@rounded)+constant,'P':p,'J':j,'hidden_boundary_poles':h,
                    'X':xval,'Y':yval,'S':16*p-2*j+xval+yval,'chosen':[asdict(b) for b in chosen],
                    'rounded_matrix_check':True})
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('a',type=int);p.add_argument('b',type=int)
    p.add_argument('--W',type=int,default=21);p.add_argument('--H',type=int,default=53)
    p.add_argument('--seconds',type=float,default=300);p.add_argument('--allow-edge0',action='store_true')
    p.add_argument('--P',type=int);p.add_argument('--cap',type=int)
    p.add_argument('--mode',choices=['joint','X','Y'],default='joint');p.add_argument('--name',required=True)
    a=p.parse_args();assert '/' not in a.name
    res=mip_solve((a.a,a.b,a.W,a.H),a.seconds,a.allow_edge0,a.P,a.cap,a.mode,True)
    (BASE/(a.name+'.json')).write_text(json.dumps(res,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in res.items() if k!='chosen'},ensure_ascii=False),flush=True)
