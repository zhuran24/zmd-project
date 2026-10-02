"""Two independent tests of the fixed-offset lemma.
A: timestamped individual belt cells and real shared 50-piece receiving stores.
B: first-cell readiness event recurrence; exhaustive work-conserving dispatch.
Neither uses original-seat programs. Tests supplement, not replace, the proof.
"""
import itertools,json,random
from collections import deque
from pathlib import Path

def event_round(previous, gap, offsets):
    ready=tuple(max(d+1,p+8-gap) for p,d in zip(previous,offsets))
    outcomes=set()
    def walk(t,done):
        if all(x is not None for x in done):outcomes.add(tuple(done));return
        available=[i for i in range(len(ready)) if done[i] is None and ready[i]<=t]
        if not available:walk(min(ready[i] for i in range(len(ready)) if done[i] is None),done);return
        for i in available:
            nxt=list(done);nxt[i]=t;walk(t+1,nxt)
    walk(1,[None]*len(offsets))
    return outcomes

def exhaustive(offsets):
    n=len(offsets);D=max(offsets)
    first=event_round(tuple([-99]*n),8,offsets)
    todo=deque(first);seen=set(first);edges=0
    while todo:
        state=todo.popleft()
        assert max(state)<=D+n
        # gaps >= 8+D+n are equivalent: all previous first-cell items mature.
        for gap in range(8,9+D+n):
            for nxt in event_round(state,gap,offsets):
                edges+=1;assert max(nxt)<=D+n
                if gap==8:assert all(nxt[i]>=state[i] for i in range(n))
                if nxt not in seen:seen.add(nxt);todo.append(nxt)
    return {"offsets":offsets,"states":len(seen),"transitions":edges,
            "largest_completion_offset":max(map(max,seen)),"deadline":D+n}

def cells_case(seed,offsets,lengths,shared=False,rounds=80):
    rng=random.Random(seed);n=len(offsets);D=max(offsets)
    x=[3]
    for _ in range(rounds-1):x.append(x[-1]+rng.choice([8,8,8,9,10,16,40,101]))
    cells=[[-100]*l for l in lengths]
    groups=[0]*n if shared else list(range(n))
    assert not shared or len(set(offsets))==1
    stock={g:50 for g in groups}; supply=[[] for _ in offsets]
    request={}
    for j,t in enumerate(x):
        for i,d in enumerate(offsets):request.setdefault(t+d,[]).append(i)
    # Second encoding runs ready event scheduling with the same per-step choice
    # priorities, but no belt cells or receiving-store state.
    active=[0]*n; previous=[-100]*n; event=[[] for _ in offsets]
    for t in range(x[-1]+D+n+2):
        order=list(range(n));rng.shuffle(order)
        # Independent target receiving rotations; underlying order may change each step.
        receiving=list(range(n));rng.shuffle(receiving)
        for i in receiving:
            row=cells[i];g=groups[i]
            if row[-1] is not None and row[-1]+8<=t and stock[g]<50:
                stock[g]+=1;row[-1]=None
            for k in range(len(row)-2,-1,-1):
                if row[k] is not None and row[k]+8<=t and row[k+1] is None:
                    row[k+1]=t;row[k]=None
        for i in order:
            if cells[i][0] is None:
                cells[i][0]=t;supply[i].append(t);break
        for i in order:
            j=active[i]
            if j<len(x) and t>=max(x[j]+offsets[i]+1,previous[i]+8):
                event[i].append(t);previous[i]=t;active[i]+=1;break
        for i in request.get(t,[]):stock[groups[i]]-=1
        for i in range(n):
            assert supply[i]==event[i],(seed,t,i,supply[i][-5:],event[i][-5:])
        assert all(v>=50-(n if shared else 1) for v in stock.values())
    assert all(len(v)==rounds for v in supply)
    for j,t in enumerate(x):assert max(supply[i][j] for i in range(n))<=t+D+n
    return t+1

if __name__=="__main__":
    shapes=[(0,),(0,0),(0,0,0),(0,2,2),(0,0,2),(0,)*6]
    exhausted=[exhaustive(s) for s in shapes]
    count=steps=0
    for n,off in enumerate(shapes):
        for j in range(16):
            r=random.Random(990000+100*n+j)
            ls=[r.randint(1,101) for _ in off]
            steps+=cells_case(990000+100*n+j,off,ls,shared=(n==1 and j%2==0))
            count+=1
    result={"exhaustive":exhausted,"two_encoding_cases":count,"two_encoding_steps":steps,
            "all_equal":True,"max_tested_route_length":101,
            "scope":"local arbitrary consumption/priority schedules, not geometric factory certificates"}
    Path(__file__).with_suffix(".json").write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(result,ensure_ascii=False))
