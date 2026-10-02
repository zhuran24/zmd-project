"""Fresh HiGHS coverage model, emptiness indicators + ports, one solver thread.
Generated with rectangle intervals and independent axis handling.
"""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import argparse,json,time,warnings
from pathlib import Path
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import lil_matrix
OUT=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=float,default=180);args=ap.parse_args()

def domain(edge):
    choices=[]
    for width,height,axis,weight in [(3,3,'x',2),(3,3,'y',2),(5,5,'x',3),(5,5,'y',3),(6,4,'y',3),(4,6,'x',3)]:
        for left in range(-width+1,12):
            right=left+width-1
            if edge and right>6:continue
            for bottom in range(-height+1,12):
                top=bottom+height-1
                if left<=6 and right>=5 and bottom<=6 and top>=5:continue
                if axis=='x':sides=[[(left-1,y) for y in range(bottom,top+1)],[(right+1,y) for y in range(bottom,top+1)]]
                else:sides=[[(x,bottom-1) for x in range(left,right+1)],[(x,top+1) for x in range(left,right+1)]]
                sides=[[p for p in s if not (5<=p[0]<=6 and 5<=p[1]<=6) and (not edge or p[0]<=6)] for s in sides]
                if min(map(len,sides))==0:continue
                choices.append((left,bottom,width,height,axis,weight,sides))
    return choices

results=[]
for edge in (False,True):
    opts=domain(edge);n=len(opts)
    empty={p:n+i for i,p in enumerate(sorted({p for o in opts for s in o[6] for p in s}))}
    occup={}
    for i,(x,y,w,h,axis,wt,sides) in enumerate(opts):
        for xx in range(x,x+w):
            for yy in range(y,y+h):occup.setdefault((xx,yy),[]).append(i)
    rows=[];lb=[];ub=[]
    for p,indices in occup.items():
        r={i:1 for i in indices}
        if p in empty:r[empty[p]]=1
        rows.append(r);lb.append(-np.inf);ub.append(1)
    for i,o in enumerate(opts):
        for side in o[6]:
            r={empty[p]:1 for p in side};r[i]=-1
            rows.append(r);lb.append(0);ub.append(np.inf)
    nvars=n+len(empty)
    for kind,target in [('count',14 if edge else 24),('weight',30 if edge else 55)]:
        extra=[{i:1 for i in range(n)},{i:(1 if kind=='count' else o[5]) for i,o in enumerate(opts)}]
        l=lb+[-np.inf,target];u=ub+[(14 if edge else 24) if kind=='count' else (13 if edge else 23),np.inf]
        mat=lil_matrix((len(rows)+2,nvars))
        for ri,row in enumerate(rows+extra):
            for c,v in row.items():mat[ri,c]=v
        start=time.monotonic()
        with warnings.catch_warnings():
            warnings.simplefilter('ignore',RuntimeWarning)
            res=milp(np.zeros(nvars),integrality=np.array([1]*n+[0]*len(empty)),bounds=Bounds(0,1),constraints=LinearConstraint(mat.tocsr(),np.array(l),np.array(u)),options={'threads':1,'time_limit':args.seconds,'mip_rel_gap':0})
        record={'edge':edge,'kind':kind,'target':target,'options':n,'status':{0:'FEASIBLE',1:'LIMIT',2:'INFEASIBLE'}.get(res.status,str(res.status)),'seconds':time.monotonic()-start,'message':res.message}
        results.append(record);print(json.dumps(record),flush=True)
        if kind=='count' and res.status!=2:break
    (OUT/f'power_b_domain_{edge}.json').write_text(json.dumps(sorted([list(o[:6]) for o in opts]))+'\n')
    (OUT/'power_b.json').write_text(json.dumps(results,indent=2)+'\n')
