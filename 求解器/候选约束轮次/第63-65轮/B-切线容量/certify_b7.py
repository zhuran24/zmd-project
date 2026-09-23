#!/usr/bin/env python3
"""穷尽整数机型数；每个连续放宽输出可用有理数直接核验的LP对偶证书。"""
from fractions import Fraction as F
from itertools import product
import json
from pathlib import Path
import numpy as np
from scipy.optimize import linprog

OUT=Path(__file__).resolve().parent
recipes=json.loads((OUT/"recipe_accounting.json").read_text())["recipes"]
items=sorted(set().union(*(set(r["inputs"])|set(r["outputs"]) for r in recipes)))
kinds=["粉碎机","精炼炉","配件机","塑形机","种植机","采种机"]
rates=[18,34,F(11,2),F(21,2),34,17,0,17,9,F(11,2),F(11,2),6,11,21,F(11,2),F(21,2),0,0]
assert len(recipes)==18 and len(items)==19
nr=len(recipes); z=nr; t0=z+1; nv=t0+len(items)
ub=list(map(F,rates))+[F(7)]+[None]*len(items)
c=[F(0)]*t0+[F(1)]*len(items)
A=[]; rhs=[]; labels=[]
def add(row,b,label):
    A.append(list(map(F,row)));rhs.append(F(b));labels.append(label)
row=[0]*nv;row[7:10]=[1,1,1]
add(row,1,"研磨机总批次上界")
add([-x for x in row],F(-1,2),"研磨机总批次下界")
row=[0]*nv;row[7:9]=[-1,-1]
add(row,F(-1,2),"矿物切线G下界")
row=[0]*nv;row[10]=1
add(row,0,"塑形机台数上界（按分支填写）")
add([-x for x in row],0,"塑形机全厂半批余量（按分支填写）")
for j,item in enumerate(items):
    row=[0]*nv
    for i,r in enumerate(recipes):
        row[i]=r["outputs"].get(item,0)-r["inputs"].get(item,0)
    const=0
    if item=="蓝铁矿":row[z]=1
    if item=="源矿":row[z]=-1;const=7
    a=row.copy();a[t0+j]=-1;add(a,-const,item+"正流量")
    a=[-x for x in row];a[t0+j]=-1;add(a,const,item+"负流量")
E=[];eq_kinds=[]
for kind in kinds:
    if kind=="塑形机":continue
    E.append([F(int(r["kind"]==kind)) for r in recipes]+[F(0)]*(nv-nr))
    eq_kinds.append(kind)
counts=list(product(range(6),range(6),range(6),range(6),range(4),range(4)))
counts=[n for n in counts if sum(w*k for w,k in zip([3,3,3,3,5,5],n))<=15]
certs=[];best=None
as_float=lambda mat: np.array([[float(x) for x in row] for row in mat])
for n in counts:
    nd=dict(zip(kinds,n))
    b=rhs.copy();b[3]=F(nd["塑形机"]);b[4]=F(1,2)-nd["塑形机"]
    d=[F(nd[k]) for k in eq_kinds]
    res=linprog(list(map(float,c)),A_ub=as_float(A),b_ub=list(map(float,b)),
                A_eq=as_float(E),b_eq=list(map(float,d)),
                bounds=[(0,None if u is None else float(u)) for u in ub],method="highs")
    assert res.status==0,(n,res.message)
    rf=lambda seq:[F(float(x)).limit_denominator(1000000) for x in seq]
    y,e,l,v=map(rf,[res.ineqlin.marginals,res.eqlin.marginals,res.lower.marginals,res.upper.marginals])
    assert all(x<=0 for x in y+v) and all(x>=0 for x in l)
    assert all(u is not None or vv==0 for u,vv in zip(ub,v))
    for j in range(nv):
        assert sum(A[i][j]*y[i] for i in range(len(A)))+sum(E[i][j]*e[i] for i in range(len(E)))+l[j]+v[j]==c[j],(n,j)
    bound=sum(a*bb for a,bb in zip(y,b))+sum(a*dd for a,dd in zip(e,d))+sum(u*vv for u,vv in zip(ub,v) if u is not None)
    x=rf(res.x)
    assert all(sum(a*xx for a,xx in zip(row,x))<=bb for row,bb in zip(A,b))
    assert all(sum(a*xx for a,xx in zip(row,x))==dd for row,dd in zip(E,d))
    assert all(xx>=0 and (u is None or xx<=u) for xx,u in zip(x,ub))
    primal=sum(cc*xx for cc,xx in zip(c,x))
    assert primal==bound
    rec=dict(counts=list(n),y=list(map(str,y)),e=list(map(str,e)),lower=list(map(str,l)),
             upper=list(map(str,v)),primal=list(map(str,x)),bound=str(bound))
    certs.append(rec)
    if best is None or bound<F(best["bound"]):best=rec
minimum=min(F(r["bound"]) for r in certs)
assert minimum==F(19,3)
model=dict(kinds=kinds,eq_kinds=eq_kinds,items=items,variable_count=nv,
           A=[[str(x) for x in r] for r in A],rhs=list(map(str,rhs)),
           E=[[str(x) for x in r] for r in E],upper=[None if x is None else str(x) for x in ub],
           objective=list(map(str,c)),labels=labels,
           recipe_variables=recipes,source_variable=z,absolute_flow_variable_start=t0,
           description="蓝铁矿口数放宽为0到7的连续数；只会降低下界。所有机型数穷尽整数。")
(OUT/"b7_lp_model.json").write_text(json.dumps(model,ensure_ascii=False,indent=2)+"\n")
(OUT/"b7_rational_certificates.json").write_text(json.dumps(certs,ensure_ascii=False,indent=2)+"\n")
summary=dict(branches=len(certs),minimum_total_crossing_rate=str(minimum),
             cut_capacity=6,deficit=str(minimum-6),all_primal_dual_exact=True,
             best_counts=dict(zip(kinds,best["counts"])),best_relaxed_primal=best["primal"],
             interpretation="有理数LP下界；最优点不是几何布局或循环态见证。")
(OUT/"b7_certificate_summary.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(summary,ensure_ascii=False,indent=2))
