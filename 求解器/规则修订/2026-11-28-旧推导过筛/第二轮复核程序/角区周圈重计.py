# 改写自 求解器/候选约束轮次/第78-80轮/推导78B/corner_independent78.py 的局部 MILP：
# 加入一个 a=2 (或转置 b=2) 的空矩形 R，禁止与 R 相交的 3x3 原矿加工机身与缺口切向单位，
# 检查 N+w+d<=91，d 为左带落在 R 行跨度内（即与 R 左侧周圈重合）的矿源格数。
import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/'求解器/候选约束轮次/第78-80轮/推导78B'))
os.environ['OPENBLAS_NUM_THREADS']='1'
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_matrix
def overlap(a,b):return max(a[0],b[0])<min(a[0]+a[2],b[0]+b[2]) and max(a[1],b[1])<min(a[1]+a[3],b[1]+b[3])
def contains(a,p):return a[0]<=p[0]<a[0]+a[2] and a[1]<=p[1]<a[1]+a[3]
def lineports(gap):
    free=[i for i in range(70) if i!=gap]
    return [free[j+1] for j in range(0,69,3)]
def audit(g,h,tangent,weighted,R):
    src=[(1,p,0) for p in lineports(g)]+[(p,1,1) for p in lineports(h)]
    blocked=(1,g-1,3,3) if g else (h-1,1,3,3)
    if tangent and overlap(blocked,R): return None
    columns=[]
    for axis in range(2):
        for u in range(1,68):
            r=(2,u,3,3) if axis==0 else (u,2,3,3)
            if any(contains(r,p[:2]) for p in src):continue
            if overlap(r,R):continue
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
    bonus=2 if tangent else 0
    ub=[1]*n
    if weighted:
        ub += [1,1];rows.append(({n:1,n+1:1},1))
        pos=max(g,h)
        for end in range(2):
            along=pos-2 if end==0 else pos+2
            nb=[(cross,along) if g else (along,cross) for cross in (2,3)]
            nb=[p for p in nb if all(1<=v<=69 for v in p) and p not in [s[:2] for s in src] and not contains(R,p)]
            if not nb:ub[n+end]=0;continue
            coeff={n+end:1}
            for i,(_,r,_) in enumerate(columns):
                a=sum(contains(r,p) for p in nb)
                if a:coeff[i]=a
            rows.append((coeff,len(nb)))
        if max(g,h)==3:ub[n]=0;bonus=1
    size=len(ub);ri=[];ci=[];av=[];upper=[]
    for k,(d,b) in enumerate(rows):
        upper.append(b)
        for i,v in d.items():ri.append(k);ci.append(i);av.append(v)
    if not rows:
        return 46+bonus+sum(ub)
    mat=coo_matrix((av,(ri,ci)),shape=(len(rows),size)).tocsc()
    r=milp(-np.ones(size),integrality=np.ones(size),bounds=Bounds(np.zeros(size),ub),
      constraints=LinearConstraint(mat,-np.inf*np.ones(len(rows)),upper),options={'mip_rel_gap':0.0,'time_limit':60})
    assert r.status==0
    return 46+bonus+int(round(-r.fun))
# 无 R 时复现原最大值
NOR=(100,100,1,1)
base=max(audit(g,h,t,w,NOR) for g in range(0,70,3) for h in range(0,70,3) if min(g,h)==0
         for t,w in [(False,False)]+([(True,False),(True,True)] if 0<max(g,h)<69 else []))
print('无R复现最大',base)
worst=-99;arg=None;cnt=0
for g in range(0,70,3):
  for h in range(0,70,3):
    if min(g,h)!=0: continue
    L=lineports(g)
    for b in range(3,64):
      for H in range(6,70-b):
        m=sum(b<=p<=b+H-1 for p in L)
        if m>2: break
        R=(2,b,6,H)
        best=None
        for t,w in [(False,False)]+([(True,False),(True,True)] if 0<max(g,h)<69 else []):
          v=audit(g,h,t,w,R)
          if v is not None: best=v if best is None else max(best,v)
        cnt+=1
        if best+m>worst: worst=best+m;arg=(g,h,b,H,m,best)
print('a=2 情形数',cnt,'max N+w+d =',worst,arg)
