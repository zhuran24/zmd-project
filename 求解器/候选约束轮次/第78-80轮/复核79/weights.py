"""Two fresh encodings of port weights: half-integral DP and support-class MILP."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
os.sched_setaffinity(0,set(range(10)))
import json,itertools,warnings
from pathlib import Path
from fractions import Fraction as F
from collections import Counter
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint

OUT=Path(__file__).resolve().parent
TYPES=[('研磨机',6,32,F(3,2),F(3),F(189,2)),('塑形机',3,6,F(1),F(2),F(11)),('封装机',6,3,F(5),F(5),F(15)),('灌装机',6,3,F(3),F(4),F(11))]

def supports(length):
    out=[]
    for mask in range(1,1<<length):
        p=[i+1 for i in range(length) if mask>>i&1];a=[0]*len(p)
        for i in range(len(p)-1):
            if p[i+1]-p[i]<=3:a[i]+=1;a[i+1]+=1
        out.append((p,a))
    return out

def single_min(length,d):
    best=None;wit=None
    for p,alpha in supports(length):
        if len(p)<d:continue
        left=d;value=F(0);flows=[F(0)]*len(p)
        for i in sorted(range(len(p)),key=lambda j:alpha[j]):
            v=min(left,F(1));flows[i]=v;left-=v;value+=alpha[i]*v
        if best is None or value<best:best=value;wit=(p,alpha,list(map(str,flows)))
    return best,wit

def dp(length,n,lo,hi,total):
    opt={k:single_min(length,F(k,2)) for k in range(int(2*lo),int(2*hi)+1)}
    tab={0:(F(0),[])}
    for _ in range(n):
        nxt={}
        for mass,(w,seq) in tab.items():
            for k,(val,_) in opt.items():
                if mass+k>2*total:continue
                if mass+k not in nxt or nxt[mass+k][0]>w+val:nxt[mass+k]=(w+val,seq+[k])
        tab=nxt
    val,seq=tab[int(2*total)]
    return dict(value=str(val),rates=[str(F(k,2)) for k in seq],single={str(F(k,2)):{'min':str(v),'witness':wit} for k,(v,wit) in opt.items()})

def aggregate_milp(length,n,lo,hi,total):
    # Independently determine per-position degrees by nearest occupied neighbours.
    classes=set()
    for r in range(1,length+1):
        for subset in itertools.combinations(range(length),r):
            deg=[]
            for p in subset:
                left=[q for q in subset if q<p];right=[q for q in subset if q>p]
                deg.append(int(bool(left) and p-max(left)<=3)+int(bool(right) and min(right)-p<=3))
            classes.add(tuple(deg.count(a) for a in range(3)))
    classes=sorted(classes);k=len(classes);nn=4*k
    A=[];lb=[];ub=[]
    def row(entries,l,u):
        r=np.zeros(nn)
        for i,v in entries:r[i]+=float(v)
        A.append(r);lb.append(float(l));ub.append(float(u))
    row([(4*i,1) for i in range(k)],n,n)
    row([(4*i+1+a,1) for i in range(k) for a in range(3)],total,total)
    for i,c in enumerate(classes):
        for a in range(3):row([(4*i+1+a,1),(4*i,-c[a])],-np.inf,0)
        row([(4*i+1+a,1) for a in range(3)]+[(4*i,-lo)],0,np.inf)
        row([(4*i+1+a,1) for a in range(3)]+[(4*i,-hi)],-np.inf,0)
    obj=np.tile(np.array([0,0,1,2]),k);integral=np.tile([1,0,0,0],k)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        res=milp(obj,integrality=integral,bounds=Bounds(np.zeros(nn),np.full(nn,np.inf)),constraints=LinearConstraint(np.array(A),lb,ub),options=dict(threads=1,mip_rel_gap=0,time_limit=60))
    assert res.status==0,res.message
    x=[F(float(t)).limit_denominator(100000) for t in res.x]
    # Exact verification of all integer coefficients, lower/upper rational rows.
    assert sum(x[4*i] for i in range(k))==n
    assert sum(x[4*i+1+a] for i in range(k) for a in range(3))==total
    for i,c in enumerate(classes):
        assert x[4*i].denominator==1
        assert all(0<=x[4*i+1+a]<=c[a]*x[4*i] for a in range(3))
        assert lo*x[4*i]<=sum(x[4*i+1+a] for a in range(3))<=hi*x[4*i]
    value=sum(a*x[4*i+1+a] for i in range(k) for a in range(3))
    return dict(status=res.message,value=str(value),classes=classes,solution=list(map(str,x)),solver_bound=float(res.mip_dual_bound))

def vertices(length,lo,hi):
    # Box cut by sum interval: at most one nonintegral coordinate at a vertex.
    for p,a in supports(length):
        n=len(p);seen=set()
        for bits in itertools.product((F(0),F(1)),repeat=n):
            if lo<=sum(bits)<=hi:seen.add(bits)
        for d in (lo,hi):
            for fractional in range(n):
                for bits in itertools.product((F(0),F(1)),repeat=n-1):
                    z=d-sum(bits)
                    if not 0<=z<=1:continue
                    v=list(bits);v.insert(fractional,z);seen.add(tuple(v))
        for f in seen:yield p,a,f

def main():
    out={'method_note':'Each fixed support is a box cut by total flow; all continuous extrema have half-integral flows for these totals. Zero flows enlarge a support relaxation; they are not asserted positive.'}
    for name,L,n,lo,hi,total in TYPES:
        one=dp(L,n,lo,hi,total);two=aggregate_milp(L,n,lo,hi,total)
        assert one['value']==two['value']
        margins=[];checks=0
        for p,a,f in vertices(L,lo,hi):
            d=sum(f);w=sum(i*j for i,j in zip(a,f))
            base=2*d-4 if name=='研磨机' else 2*d-2 if name=='塑形机' else F(8) if name=='封装机' else 4*d-10
            assert w>=base,(name,p,f,w,base)
            margins.append(w-base);checks+=1
        out[name]=dict(dp=one,milp=two,linear_slack_vertices=checks,minimum_linear_slack=str(min(margins)))
    out['total']=str(sum(F(out[n]['dp']['value']) for n,*_ in TYPES))
    # Supports of three channels split by a gap >3; these are the only low-slack ones.
    out['disconnected_three']=[p for p,a in supports(6) if len(p)==3 and 0 in a]
    assert out['disconnected_three']==[[1,2,6],[1,5,6]]
    (OUT/'weight_checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({n:out[n]['dp']['value'] for n,*_ in TYPES},ensure_ascii=False));print('total',out['total'])

if __name__=='__main__':main()
