from itertools import combinations, product
from fractions import Fraction as F
from math import ceil
from scipy.optimize import milp, LinearConstraint, Bounds
from scipy.sparse import lil_matrix
import numpy as np

def square(x,y):
    return frozenset(product(range(x,x+3),range(y,y+3)))

def geometry(g,h,t,w):
    def ports(d):
        return [a+1 for a in list(range(0,d,3))+list(range(d+1,70,3))]
    ore={(1,v) for v in ports(g)}|{(v,1) for v in ports(h)}
    assert len(ore)==46
    p=max(g,h)
    pin=(square(1,p-1) if g else square(p-1,1)) if t else set()
    bodies=[]
    for_left=[]
    for x,y in ore:
        # At (1,1), the gap on the opposite edge determines the source.
        left=x==1 and y in ports(g)
        for j in range(3):
            s=square(2,y-j) if left else square(x-j,2)
            if not (s & (ore|pin)) and all(1<=min(c) and max(c)<70 for c in s):
                bodies.append(s)
                for_left.append(left)
    # If weight is positive, choose one other free input on that very side.
    free_options=[set()]
    if w:
        free_options=[{(i,j) if g else (j,i)} for i in (2,3) for j in (p-2,p+2)
                      if 1<=j<=69 and (p!=3 or j!=1)]
    best=0
    for free in free_options:
        if free & ore:continue
        bs=[s for s in bodies if not s&free]
        cells=sorted(set.union(set(),*bs))
        A=lil_matrix((len(cells),len(bs)))
        idx={c:i for i,c in enumerate(cells)}
        for i,s in enumerate(bs):
            for c in s:A[idx[c],i]=1
        res=milp(-np.ones(len(bs)),integrality=np.ones(len(bs)),bounds=Bounds(0,1),
            constraints=LinearConstraint(A.tocsr(),-np.inf,1),options={'mip_rel_gap':0})
        assert res.success and abs(res.fun-res.mip_dual_bound)<1e-6
        # Exact check: only left-side squares starting in rows 1..4
        # can meet a bottom-side square. Once these are fixed, the
        # two interval families admit the earliest-finish optimum.
        lefts={b for b,left in zip(bodies,for_left) if left and not b&free}
        bottoms={b for b,left in zip(bodies,for_left) if not left and not b&free}
        near=[b for b in lefts if min(y for x,y in b)<=4]
        def pack(rectangles,axis):
            last=-1
            total=0
            for start in sorted(min(c[axis] for c in b) for b in rectangles):
                if start>last:
                    total+=1
                    last=start+2
            return total
        exact=0
        for k in range(len(near)+1):
            for picked in combinations(near,k):
                if any(a&b for a,b in combinations(picked,2)):continue
                used=set().union(*picked)
                left_rest=[b for b in lefts if b not in near and not used&b]
                bottom_rest=[b for b in bottoms if not used&b]
                exact=max(exact,k+pack(left_rest,1)+pack(bottom_rest,0))
        assert exact==round(-res.fun)
        # The pinned box may have three contacts at p=3, including
        # the normal contact of the OTHER edge. A weighted shaper has
        # neither lower contact in this case.
        bonus=(0 if not t else (1 if w else 3) if p==3 else 2)
        best=max(best,46+bonus+int(w)+round(-res.fun))
    return best

def widths(L):
    for k in range(1,L+1):
        for s in combinations(range(L),k):
            a=[0]*k
            for i in range(k-1):
                if s[i+1]-s[i]<=3:a[i]+=1;a[i+1]+=1
            yield sorted(a)
def unweighted(L,n,c,D):
    f=[0]+[min(sum(a) for a in widths(L) if len(a)==k) for k in range(1,L+1)]
    dp={0:0}
    for _ in range(n):
        nd={}
        for d,v in dp.items():
            for k,cost in enumerate(f):
                key=min(D,d+min(c,k))
                nd[key]=min(nd.get(key,10**5),v+cost)
        dp=nd
    return dp[D]
def weights():
    for L,c,slope,offset in [(6,3,2,-4),(3,2,2,-2),(6,5,0,8),(6,4,4,-10)]:
        for a in widths(L):
            for d in range(min(len(a),c)+1):
                if c==5 and d!=5: continue
                assert sum(a[:d])>=slope*d+offset
                if L==6 and len(a)>=3:assert sum(a[:d])>=d-1
def main():
    flows=[34,18,34,34,18,F(63,2),21,21,11,11,11,17,17,9,F(11,2),6,F(11,2),F(3,5),F(11,20)]
    print('flows',sum(flows),'source, sink',52+sum([95,51,32,6,6,32,32,3,3]),sum([68,51,95,11,6,32,16,15,11])+2)
    weights()
    print('incidences',[unweighted(*args) for args in [(3,68,3,95),(6,32,3,95),(3,6,2,11),(6,3,4,11),(6,3,5,15)]])
    all_cases={}
    for g,h in product(range(0,70,3),repeat=2):
        if min(g,h):continue
        modes=[(0,0)]+([(1,0),(1,1)] if 0<max(g,h)<69 else [])
        for t,w in modes:all_cases[g,h,t,w]=geometry(g,h,t,w)
    print('cases',len(all_cases),'max',max(all_cases.values()), 'g3',[(k,v) for k,v in all_cases.items() if k[:2]==(3,0)])
    print('over 92',[k for k,v in all_cases.items() if v>92])
    W=F(123,2)+10+24+14
    print('W',W,'four machine faces',619+184-max(all_cases.values())+8+W)
if __name__=='__main__':main()
