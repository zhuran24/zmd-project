"""Independent half-open interval + HiGHS local source-capacity audit.
Does not import the CP encoding. All 47 border patterns are rebuilt by tiling.
"""
from pathlib import Path
import os,json,time,hashlib
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_matrix
OUT=Path(__file__).resolve().parent

def overlap(a,b):return max(a[0],b[0])<min(a[0]+a[2],b[0]+b[2]) and max(a[1],b[1])<min(a[1]+a[3],b[1]+b[3])
def contains(a,p):return a[0]<=p[0]<a[0]+a[2] and a[1]<=p[1]<a[1]+a[3]
def lineports(gap):
    free=[i for i in range(70) if i!=gap]
    chunks=[free[j:j+3] for j in range(0,69,3)]
    assert all(b[2]-b[0]==2 for b in chunks)
    return [b[1] for b in chunks]

def audit(g,h,tangent,weighted):
    src=[(1,p,0) for p in lineports(g)]+[(p,1,1) for p in lineports(h)]
    blocked=(1,g-1,3,3) if g else (h-1,1,3,3)
    columns=[]
    for axis in range(2):
        for u in range(1,68):
            r=(2,u,3,3) if axis==0 else (u,2,3,3)
            if any(contains(r,p[:2]) for p in src):continue
            if tangent and overlap(r,blocked):continue
            for k,(x,y,a) in enumerate(src):
                if a!=axis:continue
                if (axis==0 and r[1]<=y<r[1]+3) or (axis==1 and r[0]<=x<r[0]+3):columns.append((k,r,axis))
    n=len(columns);rows=[]
    for i,(k,r,a) in enumerate(columns):
        for j,(l,s,b) in enumerate(columns[:i]):
            if k==l or overlap(r,s):rows.append(({i:1,j:1},1))
    if g==3:rows.append(({i:1 for i,(_,_,a) in enumerate(columns) if a==1},22))
    if h==3:rows.append(({i:1 for i,(_,_,a) in enumerate(columns) if a==0},22))
    # At gap=3 this includes the extra normal contact to the pinned body:
    # that contact and the corner tangent contact cannot both be active.
    bonus=2 if tangent else 0
    ub=[1]*n
    if weighted:
        ub += [1,1];rows.append(({n:1,n+1:1},1))
        pos=max(g,h)
        for end in range(2):
            along=pos-2 if end==0 else pos+2
            neighbours=[(cross,along) if g else (along,cross) for cross in (2,3)]
            neighbours=[p for p in neighbours if all(1<=v<=69 for v in p) and p not in [s[:2] for s in src]]
            if not neighbours:ub[n+end]=0;continue
            coeff={n+end:1}
            for i,(_,r,_) in enumerate(columns):
                a=sum(contains(r,p) for p in neighbours)
                if a:coeff[i]=a
            rows.append((coeff,len(neighbours)))
        if max(g,h)==3:ub[n]=0;bonus=1
    size=len(ub);ri=[];ci=[];av=[];upper=[]
    for k,(d,b) in enumerate(rows):
        upper.append(b)
        for i,v in d.items():ri.append(k);ci.append(i);av.append(v)
    mat=coo_matrix((av,(ri,ci)),shape=(len(rows),size)).tocsc()
    r=milp(-np.ones(size),integrality=np.ones(size),bounds=Bounds(np.zeros(size),ub),
      constraints=LinearConstraint(mat,-np.inf*np.ones(len(rows)),upper),
      options={'threads':1,'time_limit':30,'mip_rel_gap':0.0})
    assert r.status==0, (g,h,tangent,weighted,r.message)
    z=np.rint(r.x).astype(int);assert np.all(mat@z<=np.array(upper))
    return dict(gaps=[g,h],tangent=tangent,weighted=weighted,status='OPTIMAL',bound=46+bonus+sum(map(int,z)),
      options=n,chosen=[list(b) for i,(_,b,_) in enumerate(columns) if z[i]],
      model_sha256=hashlib.sha256(repr((columns,rows,ub)).encode()).hexdigest())

if __name__=='__main__':
    t=time.monotonic();rows=[]
    for g,h in [(g,h) for g in range(0,70,3) for h in range(0,70,3) if min(g,h)==0]:
        for tangent,weighted in [(False,False)]+([(True,False),(True,True)] if 0<max(g,h)<69 else []):
            rows.append(audit(g,h,tangent,weighted))
    other=json.loads((OUT/'corner_exploration.json').read_text())
    key=lambda d:(*d['gaps'],d['tangent'],d['weighted'])
    a={key(d):d['bound'] for d in other};b={key(d):d['bound'] for d in rows}
    assert a==b
    result=dict(cases=rows,max_bound=max(b.values()),case_count=len(rows),independent_exact_agreement=True,seconds=time.monotonic()-t)
    (OUT/'corner_independent.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print({k:v for k,v in result.items() if k!='cases'},flush=True)
