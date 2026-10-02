#!/usr/bin/env python3
import os,sys
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))});sys.dont_write_bytecode=True
from pathlib import Path
import numpy as np,json,time,warnings
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_matrix
from geo_power_check import domain
opts=domain('general','B');n=len(opts);occ={}
for i,o in enumerate(opts):
 for g in o['body']:occ.setdefault(g,[]).append(i)
free={g:n+i for i,g in enumerate(sorted({g for o in opts for side in o['sides'] for g in side}))}
nv=n+len(free);rr=[];cc=[];vv=[];lo=[];hi=[]
def row(co,l,h):
 k=len(lo);lo.append(l);hi.append(h)
 for i,v in co.items():rr.append(k);cc.append(i);vv.append(v)
for g,ids in occ.items():
 co={i:1 for i in ids}
 if g in free:co[free[g]]=1
 row(co,-np.inf,1)
for i,o in enumerate(opts):
 for sd in o['sides']:
  row({i:1,**{free[g]:-1 for g in sd}},-np.inf,0)
row({i:1 for i in range(n)},-np.inf,23)
row({i:o['weight'] for i,o in enumerate(opts)},55,np.inf)
mat=coo_matrix((vv,(rr,cc)),shape=(len(lo),nv)).tocsc();t=time.monotonic()
with warnings.catch_warnings():
 warnings.simplefilter('ignore')
 res=milp(np.zeros(nv),integrality=np.r_[np.ones(n),np.zeros(nv-n)],bounds=Bounds(np.zeros(nv),np.ones(nv)),constraints=LinearConstraint(mat,lo,hi),options={'threads':1,'time_limit':120,'mip_rel_gap':0})
r=dict(case='general',objective='weight',threshold=55,encoding='B free-neighbor MILP',prior_count_cap=23,domain=n,status=int(res.status),message=res.message,seconds=time.monotonic()-t)
(Path(__file__).parent/'geo_power_general_weight_55_B_highs.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r))
