#!/usr/bin/env python3
"""Independent layer enumeration, chain recurrences, and checker controls."""
import itertools
import json
import random
from pathlib import Path
from bridge_factory import BridgeFactory
from engine_b import EngineB

HERE=Path(__file__).resolve().parent


def layer_enumeration():
    patterns=0; starts=0; maximum=0
    for length in range(1,11):
        for word in itertools.product('LB',repeat=length):
            runs=[]; j=0
            while j<length:
                k=j+1
                if word[j]=='L':
                    while k<length and word[k]=='L': k+=1
                runs.append((j,k)); j=k
            successors={e:[e+1] for e in range(len(runs))}
            terminal=len(runs)
            for e,(a,b) in enumerate(runs):
                if word[a]=='B' and a and word[a-1]=='B': successors[e].append(e-1)
            for start in range(terminal):
                # Encoding A: enumerate simple path lengths using an explicit
                # stack, accepting ONLY the actual nontransport terminal.
                stack=[(start,(start,))]; lengths=set()
                while stack:
                    e,path=stack.pop()
                    for nxt in successors[e]:
                        if nxt==terminal: lengths.add(len(path))
                        elif nxt not in path: stack.append((nxt,path+(nxt,)))
                # Encoding B: direct number of components in the suffix.
                assert lengths=={terminal-start},(word,start,lengths)
                starts+=1
            patterns+=1; maximum=max(maximum,len(runs))
    return dict(patterns=patterns,component_starts=starts,maximum_components=maximum,all_equal=True)


def replenishment():
    rng=random.Random(107200); steps=0; rounds_total=0
    for case in range(150):
        offsets=rng.choice([[0]*6,[0,0],[2,2,0],[2,0,0],[0],[0,0,0]])
        n=len(offsets); D=max(offsets)
        lengths=[rng.randrange(1,33) for _ in offsets]
        cells=[[-8]*l for l in lengths]
        x=[0]
        for _ in range(69): x.append(x[-1]+rng.choice([8,8,8,9,15,40,81]))
        request=[{xx+d for xx in x} for d in offsets]
        stock=[50]*n; next_round=[0]*n; served=[[] for _ in offsets]
        ready_pred=[[] for _ in offsets]
        previous=[None]*n; event_pending=set()
        for t in range(x[-1]+D+n+2):
            for i in range(n):
                j=next_round[i]
                if j<len(x):
                    ri=x[j]+offsets[i]+1
                    if previous[i] is not None: ri=max(ri,previous[i]+8)
                    if t==ri:
                        event_pending.add(i); ready_pred[i].append(t)
            for i,path in enumerate(cells):
                if path[-1] is not None and t-path[-1]>=8 and stock[i]<50:
                    path[-1]=None; stock[i]+=1
                for p in range(len(path)-2,-1,-1):
                    if path[p] is not None and t-path[p]>=8 and path[p+1] is None:
                        path[p]=None; path[p+1]=t
            available=[i for i in range(n) if cells[i][0] is None]
            assert set(available)==event_pending,(case,t,available,event_pending)
            # The choice is deliberately arbitrary every step, covering even
            # more choices than any fixed retained round-robin history.
            if available:
                i=rng.choice(available); cells[i][0]=t
                served[i].append(t); previous[i]=t; next_round[i]+=1; event_pending.remove(i)
            for i in range(n):
                if t in request[i]:
                    assert stock[i]==50,(case,t,i,stock[i])
                    stock[i]-=1
            steps+=1
        for i in range(n):
            assert len(served[i])==len(x)
            assert all(s<=xx+D+n for s,xx in zip(served[i],x))
        rounds_total+=len(x)
    return dict(cases=150,rounds=rounds_total,steps=steps,recurrence_equal=True,deadline_violations=0)


def controls():
    f=BridgeFactory(107900,4,'mixed'); b=EngineB(f)
    r=next(r for r in f.rs if r.cells[0] is not None)
    b.cargo[r.index][0]=0
    detected_age=False
    try: b.compare(f)
    except AssertionError: detected_age=True
    f=BridgeFactory(107901,3,'all_bridge')
    e=next(iter(f.backward)); ri,a,z=f.components[e]
    f.prev[ri][a]='different-physical-unit'
    detected_origin=False
    try: f.selected_receiver(e)
    except AssertionError: detected_origin=True
    assert detected_age and detected_origin
    # All receiving groups for a bridge axis contain only the same route.
    f=BridgeFactory(107902,8,'mixed')
    for receiver,senders in f.inputs.items():
        if receiver[0]=='e':
            expected=f.components[receiver[1]][0]
            assert all(f.components[e][0]==expected for e in senders)
    return dict(age_mutation_detected=detected_age,wrong_origin_detected=detected_origin,axis_group_locality=True)


if __name__=='__main__':
    ans={'layers':layer_enumeration(),'replenishment':replenishment(),'controls':controls()}
    (HERE/'transport_probes.json').write_text(json.dumps(ans,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(ans,ensure_ascii=False))
