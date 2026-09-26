"""Encoding B: independent interval enumeration; free-neighbor MILP (HiGHS)."""
import os
os.environ.update(OMP_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1', MKL_NUM_THREADS='1')
os.sched_setaffinity(0, set(sorted(os.sched_getaffinity(0))[:5]))
from pathlib import Path
import time, json, warnings
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_matrix

OUT=Path(__file__).resolve().parent

def generate(edge):
    opts=[]
    for w,h,axis in ((3,3,0),(3,3,1),(5,5,0),(5,5,1),(6,4,1),(4,6,0)):
        for x in range(1-w,12):
            for y in range(1-h,12):
                right,top=x+w,y+h
                if x<7 and right>5 and y<7 and top>5: continue
                if edge and right>7: continue
                if axis==0:
                    raw=[[(x-1,t) for t in range(y,top)],[(right,t) for t in range(y,top)]]
                else:
                    raw=[[(t,y-1) for t in range(x,right)],[(t,top) for t in range(x,right)]]
                sides=[[g for g in s if not (5<=g[0]<7 and 5<=g[1]<7) and (not edge or g[0]<7)] for s in raw]
                if not all(sides): continue
                opts.append(dict(key=[x,y,w,h,axis],body=[(a,b) for a in range(x,right) for b in range(y,top)],sides=sides,weight=2 if w==3 else 3))
    return opts

def solve(edge,threshold,unit=False):
    opts=generate(edge); n=len(opts); occ={}
    for i,o in enumerate(opts):
        for g in o['body']: occ.setdefault(g,[]).append(i)
    neighbor=sorted({g for o in opts for sd in o['sides'] for g in sd})
    free={g:n+i for i,g in enumerate(neighbor)}; nv=n+len(free)
    rr=[]; cc=[]; vv=[]; lo=[]; hi=[]
    def row(co,l,h):
        idx=len(lo);lo.append(l);hi.append(h)
        for k,v in co.items(): rr.append(idx);cc.append(k);vv.append(v)
    for g,ids in occ.items():
        co={i:1 for i in ids}
        if g in free: co[free[g]]=1
        row(co,-np.inf,1)
    for i,o in enumerate(opts):
        for sd in o['sides']:
            co={i:1};co.update({free[g]:-1 for g in sd});row(co,-np.inf,0)
    row({i:1 for i in range(n)},-np.inf,14 if edge else 23)
    row({i:1 if unit else o['weight'] for i,o in enumerate(opts)},threshold,np.inf)
    matrix=coo_matrix((vv,(rr,cc)),shape=(len(lo),nv)).tocsc()
    integral=np.r_[np.ones(n),np.zeros(nv-n)]
    start=time.monotonic()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        res=milp(np.zeros(nv),integrality=integral,bounds=Bounds(np.zeros(nv),np.ones(nv)),
            constraints=LinearConstraint(matrix,lo,hi),
            options={'time_limit':600,'disp':True,'mip_rel_gap':0,'threads':1})
    name=('edge' if edge else 'general')+('_count' if unit else '_weight')
    result=dict(encoding='B free-neighbor MILP',edge=edge,unit=unit,threshold=threshold,options=n,
        rows=len(lo),variables=nv,status=int(res.status),message=res.message,seconds=time.monotonic()-start,threads=1)
    if res.x is not None: result['chosen']=[o for i,o in enumerate(opts) if res.x[i]>.5]
    (OUT/(name+'_b.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    (OUT/(name+'_domain_b.json')).write_text(json.dumps(opts,separators=(',',':'))+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='chosen'},ensure_ascii=False),flush=True)

if __name__=='__main__':
    solve(False,55)
    solve(True,30)
    solve(True,14,True)
