from collections import Counter
from itertools import product, combinations
from math import inf

def centers(k):
    return [1+3*i+(i>=k) for i in range(23)]

def coordinates(a,b,swapped):
    return (b,a) if swapped else (a,b)

def geometry():
    inner={(a,b) for a,b in product(range(1,70),repeat=2) if min(a,b)==1}
    groups=Counter()
    for l,r in product(range(24), repeat=2):
        if min(l,r): continue  # 两侧都覆盖角
        d=3*max(l,r)
        sources={(coordinates(1,s,side),side) for side,k in enumerate([l,r]) for s in centers(k)}
        mines={point for point,side in sources}
        assert len(mines)==46
        def fits(n):
            for a,b in product(range(1,71-n),repeat=2):
                if min(a,b)>1: continue
                block=set(product(range(a,a+n),range(b,b+n)))
                if block.isdisjoint(mines):
                    yield block & inner
        body=set().union(*fits(3))
        assert max(map(len,fits(2)))==2
        base=set()
        possible=set()
        g=0
        for start,side in sources:
            s=start[1-side]
            def p(a,b):return coordinates(a,b,side)
            base.update((start,p(1,s+e)) for e in [-1,1] if p(1,s+e) not in body)
            if all((p(1,s+e),side) in sources for e in [-3,3]):
                g+=1
                z=p(2,s)
                pairs={(start,z),(z,start)}
                for e in [-1,1]:
                    u=p(1,s+e)
                    v=p(1,s+2*e)
                    assert {u,v}.isdisjoint(body|mines)
                    pairs.update([(u,start),(u,v)])
                assert possible.isdisjoint(pairs)
                possible.update(pairs)
        t=92-len(base)
        base.update(((a,b),(a-1,b) if a==1 else (a,b-1)) for a,b in inner-body-mines)
        assert possible.isdisjoint(base)
        if d:
            def f(x,y):return coordinates(x,y,r>0)
            c,p,z,u,v=[f(*point) for point in [(1,1),(2,1),(2,2),(3,1),(4,1)]]
            corner={(c,p),(p,z),(z,p),(u,p),(u,v)}
        else:
            corner={((1,1),nbr) for nbr in [(2,1),(1,2),(1,0)]}
        assert corner.isdisjoint(base|possible)
        score=len(base)+2*g+3
        assert score==261+(9 if d in (0,69) else 2 if d in (3,66) else 0)
        groups[t,len(body),g,score]+=1
    print(groups)

def weights(length,cap,demand,last):
    # 枚举允许使用的端口集；系数取左右各三格内有没有另一允许口。
    # 给定总负载，先填最低系数的口即得该支持的线性松弛最小值。
    costs=[inf]*(2*cap+1)
    sites=range(length)
    for n in range(length+1):
        for allowed in combinations(sites,n):
            charges=sorted(int(any(0<i-j<=3 for j in allowed))+int(any(0<j-i<=3 for j in allowed)) for i in allowed)
            expanded=[c for c in charges for _ in (0,1)]
            for k in range(min(len(expanded),2*cap)+1):
                costs[k]=min(costs[k],sum(expanded[:k]))
    curve=[0]+[inf]*demand
    values=[]
    for n in range(1,last+1):
        curve=[min(curve[v-k]+costs[k] for k in range(min(v,2*cap)+1)) for v in range(demand+1)]
        if curve[demand]<inf:values.append(curve[demand]/2)
    return values

geometry()
for case in [(6,3,189,48),(3,2,22,11),(6,5,30,8),(6,4,22,6)]:
    print(case,weights(*case))
print(sum([68,51,95,11,6,32,16,15,11]),sum([95,51,32,6,6,32,32,3,3]))
