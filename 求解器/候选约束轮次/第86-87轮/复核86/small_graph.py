"""Exhaustive reduced plant graph with nondeterministic successful-action order.
State: C stock/output/cache, A stock/output/cache, CA/AC/B ages.
All paths have one transport slot. External B receiver can accept or refuse.
This is an overapproximation of polling, so a passed check is corroborative.
"""
import heapq
import itertools
import json
import os
from collections import deque
from functools import lru_cache
from pathlib import Path

HERE=Path(__file__).resolve().parent
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))+2})


def run(m=3,q=1):
    def phi(s):
        cs,co,cc,as_,ao,ac,u,v,b=s
        return 2*(cs+(cc>=0)+as_+ao+(ac>=0)+(u>=0)+(v>=0))+co

    def moves(s,receive):
        cs,co,cc,as_,ao,ac,u,v,b=s
        out=[]
        def change(updates):
            row=list(s)
            for i,x in updates:
                row[i]=x
            out.append(tuple(row))
        if cc<0 and cs: change([(0,cs-1),(2,q)])
        if cc==0 and co+2<=m: change([(1,co+2),(2,-1)])
        if ac<0 and as_: change([(3,as_-1),(5,q)])
        if ac==0 and ao<m: change([(4,ao+1),(5,-1)])
        if co and u<0: change([(1,co-1),(6,q)])
        if co and b<0: change([(1,co-1),(8,q)])
        if ao and v<0: change([(4,ao-1),(7,q)])
        if u==0 and as_<m: change([(6,-1),(3,as_+1)])
        if v==0 and cs<m: change([(7,-1),(0,cs+1)])
        if b==0 and receive: change([(8,-1)])
        return out

    @lru_cache(None)
    def close(s,receive):
        todo=[s]; visited={s}; ends=set()
        while todo:
            u=todo.pop(); nxt=moves(u,receive)
            if not nxt: ends.add(u)
            for v in nxt:
                if v not in visited:
                    visited.add(v); todo.append(v)
        return tuple(ends)

    states=[]
    axes=[range(m+1),range(m+1),range(-1,q+1),range(m+1),range(m+1),range(-1,q+1),range(-1,q+1),range(-1,q+1),range(-1,q+1)]
    for s in itertools.product(*axes):
        if not moves(s,False): states.append(s)
    ids={s:i for i,s in enumerate(states)}
    adj=[set() for _ in states]; rev=[set() for _ in states]
    for i,s in enumerate(states):
        a=list(s)
        for j in (2,5,6,7,8):
            if a[j]>0:a[j]-=1
        for receive in (False,True):
            for z in close(tuple(a),receive):
                j=ids[z];adj[i].add(j);rev[j].add(i)
    mins=[phi(s) for s in states]
    heap=[(p,i) for i,p in enumerate(mins)];heapq.heapify(heap)
    while heap:
        p,i=heapq.heappop(heap)
        if p!=mins[i]:continue
        for j in rev[i]:
            if p<mins[j]:mins[j]=p;heapq.heappush(heap,(p,j))
    bad=[i for i,s in enumerate(states) if mins[i]<min(phi(s)-1,4+7*m+2)]
    assert not bad,(m,q,states[bad[0]],mins[bad[0]])
    # Independently test the key continuous-time vacancy implication on the grid:
    # C nonempty at t entails C nonempty at t+S, S=4 ticks for these paths.
    forward={i for i,s in enumerate(states) if s[2]>=0}
    for _ in range(4*q):
        forward={v for u in forward for v in adj[u]}
    shift_bad=sum(states[i][2]<0 for i in forward)
    assert not shift_bad,(m,q,shift_bad)
    # Iterative Kosaraju on the region Phi >= S=4.
    keep={i for i,s in enumerate(states) if phi(s)>=8}
    done=set();order=[]
    for i in keep:
        if i in done:continue
        stack=[(i,False)]
        while stack:
            u,back=stack.pop()
            if back:order.append(u);continue
            if u in done:continue
            done.add(u);stack.append((u,True))
            stack.extend((v,False) for v in adj[u] if v in keep and v not in done)
    used=set();cyclic=idle=components=0
    for i in reversed(order):
        if i in used:continue
        comp=[];todo=[i];used.add(i)
        while todo:
            u=todo.pop();comp.append(u)
            for v in rev[u]:
                if v in keep and v not in used:used.add(v);todo.append(v)
        if len(comp)>1 or i in adj[i]:
            components+=1;cyclic+=len(comp)
            idle+=sum(states[u][2]<0 for u in comp)
    assert not idle,(m,q,idle)
    return dict(capacity=m,q=q,states=len(states),edges=sum(map(len,adj)),
                population_bound_violations=len(bad),high_phi_cyclic_states=cyclic,
                high_phi_cyclic_components=components,high_phi_c_idle=idle,
                nonempty_forward_S_violations=shift_bad)


if __name__=='__main__':
    rows=[run(3,q) for q in (1,2,3)]
    (HERE/'small_graph.json').write_text(json.dumps(rows,indent=2)+'\n')
    print(json.dumps(rows))
