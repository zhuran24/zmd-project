"""独立区间几何 + HiGHS MILP；不导入复核甲或推导席。"""
import os
os.sched_setaffinity(0,{3,4})
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'): os.environ[k]='1'
from pathlib import Path
import json, time, warnings
from collections import defaultdict
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_array
OUT=Path(__file__).resolve().parent

def placements(edge):
    ans=[]
    # 轴 0 表示左右两侧；轴 1 表示上下两侧。
    for w,h,axis,wt in [(4,6,0,3),(6,4,1,3),(5,5,1,3),(5,5,0,3),(3,3,1,2),(3,3,0,2)]:
        for bottom in range(1-h,12):
            for left in range(1-w,12):
                right=left+w-1; top=bottom+h-1
                if edge and right>6: continue
                if left<=6 and right>=5 and bottom<=6 and top>=5: continue
                if axis:
                    candidates=[[(u,bottom-1) for u in range(left,right+1)],[(u,top+1) for u in range(left,right+1)]]
                else:
                    candidates=[[(left-1,v) for v in range(bottom,top+1)],[(right+1,v) for v in range(bottom,top+1)]]
                sides=[[g for g in s if not (5<=g[0]<=6 and 5<=g[1]<=6) and (not edge or g[0]<=6)] for s in candidates]
                if min(map(len,sides))==0: continue
                ans.append((left,bottom,w,h,axis,wt,sides))
    return ans

def check(edge,count,target):
    opts=placements(edge); n=len(opts)
    cover=defaultdict(list)
    for i,(x,y,w,h,_,_,_) in enumerate(opts):
        for u in range(x,x+w):
            for v in range(y,y+h): cover[u,v].append(i)
    freecells=sorted({g for o in opts for s in o[6] for g in s})
    f={g:n+i for i,g in enumerate(freecells)}
    rows=[]; cols=[]; data=[]; lo=[]; hi=[]
    def row(d,l=-np.inf,h=np.inf):
        j=len(lo); lo.append(l); hi.append(h)
        for i,v in d.items(): rows.append(j); cols.append(i); data.append(float(v))
    for ix in cover.values(): row({i:1 for i in ix},h=1)
    for g,k in f.items(): row({**{i:1 for i in cover.get(g,[])},k:1},h=1)
    for i,o in enumerate(opts):
        for side in o[6]: row({**{f[g]:1 for g in side},i:-1},l=0)
    row({i:1 for i in range(n)},h=14 if edge else 23)
    row({i:(1 if count else o[5]) for i,o in enumerate(opts)},l=target)
    mat=coo_array((data,(np.array(rows,dtype=np.int32),np.array(cols,dtype=np.int32))),shape=(len(lo),n+len(f))).tocsc()
    t=time.monotonic()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        result=milp(np.zeros(n+len(f)),integrality=np.r_[np.ones(n),np.zeros(len(f))],bounds=Bounds(0,1),constraints=LinearConstraint(mat,lo,hi),options={'threads':1,'time_limit':600,'mip_rel_gap':0})
    obj={'edge':edge,'count':count,'target':target,'options':n,'status':int(result.status),'message':result.message,'seconds':time.monotonic()-t}
    if result.x is not None: obj['placements']=[list(o[:6]) for i,o in enumerate(opts) if result.x[i]>.5]
    fname=f'power_b_{"edge" if edge else "general"}_{"count" if count else "weight"}.json'
    (OUT/fname).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(obj),flush=True)
    (OUT/f'domain_b_{int(edge)}.json').write_text(json.dumps([list(o[:6])+[o[6]] for o in opts])+'\n')

if __name__=='__main__':
    for e,c,t in [(True,True,14),(True,False,30),(False,False,55)]: check(e,c,t)
