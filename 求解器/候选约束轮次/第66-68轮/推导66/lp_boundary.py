import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import argparse,json,time
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import vstack
from boundary_power import build,OUT
p=argparse.ArgumentParser();p.add_argument('b',type=int);p.add_argument('P',type=int);a=p.parse_args()
t=time.monotonic();m,bs,sv,occ,cost,constant=build(a.b,a.P)
A=m.matrix().tocsr();c=np.zeros(len(m.names))
for i,v in cost.items():c[i]=v
ub=[];rhs=[];eq=[];er=[];uk=[];ek=[]
for j,(lo,hi) in enumerate(zip(m.lo,m.hi)):
 if lo==hi:eq.append(A[j:j+1]);er.append(lo);ek.append(j)
 else:
  if np.isfinite(hi):ub.append(A[j:j+1]);rhs.append(hi);uk.append((j,1))
  if np.isfinite(lo):ub.append(-A[j:j+1]);rhs.append(-lo);uk.append((j,-1))
r=linprog(c,A_ub=vstack(ub),b_ub=rhs,A_eq=vstack(eq),b_eq=er,bounds=list(zip(m.lb,m.ub)),method='highs')
out=dict(b=a.b,P=a.P,status=int(r.status),message=r.message,seconds=time.monotonic()-t,objective=None if r.fun is None else float(r.fun+constant))
if r.x is not None:out.update(y=r.ineqlin.marginals.tolist(),e=r.eqlin.marginals.tolist(),ub_keys=uk,eq_keys=ek)
(OUT/f'lp_boundary_b{a.b}_P{a.P}.json').write_text(json.dumps(out,ensure_ascii=False))
print({k:v for k,v in out.items() if k not in ('y','e','ub_keys','eq_keys')},flush=True)
