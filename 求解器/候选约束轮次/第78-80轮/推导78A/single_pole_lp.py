"""Cheap exploration of type-aware local power certificates. Exact dual repair."""
from geometry_a import *
from collections import defaultdict
from fractions import Fraction as F
import numpy as np
from scipy.optimize import linprog
from scipy.sparse import coo_matrix
import argparse,time

def matrix(wall=False):
    pole=cells((5,5,2,2));objs=[]
    def ok(c):return c not in pole and (not wall or c[0]<=6)
    for kind,w,h,a in SPECS:
        for x in range(1-w,12):
            for y in range(1-h,12):
                r=(x,y,w,h);b=cells(r)
                if not all(ok(c) for c in b):continue
                ports=[[c for c in ss if ok(c)] for ss in sides(r,a)]
                if all(ports):objs.append(dict(kind=kind,r=r,axis=a,body=b,ports=ports))
    inc=defaultdict(list)
    for i,z in enumerate(objs):
        for c in z['body']:inc[c].append(i)
    rows=[(Counter({i:1 for i in inc[c]}),1) for c in sorted(inc)]
    for i,z in enumerate(objs):
        for ps in z['ports']:
            r=Counter({i:1})
            for c in ps:r.update(inc[c])
            rows.append((r,len(ps)))
    rows.append((Counter({i:1 for i in range(len(objs))}),13 if wall else 23))
    rr=[];cc=[];vv=[]
    for j,(r,_) in enumerate(rows):
        for i,v in r.items():rr.append(j);cc.append(i);vv.append(v)
    A=coo_matrix((vv,(rr,cc)),shape=(len(rows),len(objs))).tocsr()
    return objs,rows,A,np.array([b for _,b in rows])

def main():
    start=time.monotonic(); results=[]
    for wall in (False,True):
        objs,rows,A,b=matrix(wall)
        for wm,wl in [(3,2),(6,4),(9,6),(12,8),(15,10),(6,3),(3,1),(1,0),(0,0)]:
            c=np.array([10+(wm if z['kind']=='m' else wl if z['kind']=='l' else 0) for z in objs])
            res=linprog(-c,A_ub=A,b_ub=b,bounds=(0,1),method='highs',options={'threads':1})
            assert res.success
            y=[F(float(max(0,-v))).limit_denominator(1000000) for v in res.ineqlin.marginals]
            coeff=[F(0) for _ in objs];rhs=F(0)
            for mult,(row,bb) in zip(y,rows):
                if mult:
                    rhs+=mult*bb
                    for i,v in row.items():coeff[i]+=mult*v
            repair=[max(F(0),int(c[i])-v) for i,v in enumerate(coeff)]
            rhs+=sum(repair)
            ans=dict(wall=wall,weights=[10,10+wm,10+wl],upper_float=-res.fun,upper_exact=str(rhs),
                     n=sum(res.x),m=sum(v for z,v in zip(objs,res.x) if z['kind']=='m'),
                     l=sum(v for z,v in zip(objs,res.x) if z['kind']=='l'),
                     dual=[[i,v.numerator,v.denominator] for i,v in enumerate(y) if v],
                     bounds=[[i,v.numerator,v.denominator] for i,v in enumerate(repair) if v])
            results.append(ans);print({k:v for k,v in ans.items() if k not in ('dual','bounds')},flush=True)
    dump('single_pole_mixed_lp.json',dict(results=results,seconds=time.monotonic()-start))
if __name__=='__main__':main()
