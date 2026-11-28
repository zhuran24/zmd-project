from itertools import product
from fractions import Fraction as F
from math import ceil
from geometry import *

def machine_options(length,cap):
    """Enumerate supports, then solve the single-machine linear objective with fixed
    throughput by filling cheapest slots first. All flow is measured in half-items."""
    costs={}
    for active in product((False,True),repeat=length):
        ports=[i for i,v in enumerate(active) if v]
        c={i:0 for i in ports}
        for a,b in zip(ports,ports[1:]):
            if b-a<=3:
                c[a]+=1
                c[b]+=1
        marginal=sorted(v for v in c.values() for _ in range(2))
        for qty in range(min(2*cap,len(marginal))+1):
            cost=sum(marginal[:qty])
            costs[qty]=min(cost,costs.get(qty,cost))
    # Compare with direct enumeration at all nonzero actual supports.
    direct={}
    for rates in product((0,1,2),repeat=length):
        tot=sum(rates)
        if tot>2*cap: continue
        ps=[i for i,v in enumerate(rates) if v]
        v=sum(rates[i]+rates[j] for i,j in zip(ps,ps[1:]) if j-i<=3)
        direct[tot]=min(v,direct.get(tot,v))
    assert costs==direct
    return costs

def cost_table(nmin,nmax,l,batch,ticks,batches):
    cap=batch//ticks
    req=F(2)*batch*batches
    assert req.denominator==1 and cap*ticks==batch
    one=machine_options(l,cap)
    best={0:0}
    table=[]
    for n in range(1,nmax+1):
        cur={}
        for u,v in best.items():
            for q,c in one.items():
                if u+q<=req:
                    cur[u+q]=min(cur.get(u+q,10**6),v+c)
        best=cur
        if n>=nmin: table.append(F(cur[req],2))
    return table

def geometric_weights():
    # In a translated interior patch, test every possible origin and same-machine
    # endpoint. Translate to a boundary by deleting out-of-board placements. If the
    # whole segment were on an outer belt row/col, neither endpoint could be active.
    a=(33,33)
    pairs=0
    for d in D:
        for s,x,y,feed,k,r in candidates('weight',a,d,0):
            b=step(a,d,k)
            occupied=r|mask([a,b])
            assert not list(candidates('interface',a,d,occupied))
            assert all(tile&bit(b) for xx,yy,tile in q_windows(face(a,d)))
            pairs+=1
    # Same-side machines would cover the same neighbouring cell. For opposite-side
    # inlets test all orientations at a: ordinary units have one inventory, bridge
    # must import from the other machine's input-only side.
    for d in D:
        for name,ori,routes,bridge in TRANS:
            if not bridge: continue
            assert all(i in (d,opp(d)) for i,j in routes if j in (d,opp(d)))
    return pairs

if __name__=='__main__':
    info=[('研磨',32,48,6,3,1,F('31.5')),('塑形',6,11,3,2,1,F('5.5')),
          ('封装',3,8,6,25,5,F('0.6')),('灌装',3,6,6,20,5,F('0.55'))]
    first=[]
    for name,n,m,l,batch,ticks,rate in info:
        t=cost_table(n,m,l,batch,ticks,rate)
        expected={'研磨':[max(F(0),F(379-8*i,2)) for i in range(n,m+1)],
                  '塑形':[max(0,22-2*i) for i in range(n,m+1)],
                  '封装':[24,18,10,6,2,0],'灌装':[14,6,2,0]}[name]
        assert t==expected,(name,t,expected)
        print(name,'inputs=',batch*rate,'machines=',(n,m),'min weights=',*[str(v) for v in t])
        first.append(t[0])
    print('sum=',sum(first),'ceil=',ceil(sum(first)))
    print('geometric port-pair tests=',geometric_weights())
