"""Joint source/successor transport choices, exact rectangular-contact projection."""
from collections import Counter
from itertools import product
from pathlib import Path
import json
from geometry import *
from local_checks import Case,has_port

def allowed(case,p,**conditions):
    return [v for v in TRANS if case.can_flow(p,orientations=[v],**conditions)]

def route_test(b,o,d,tangents,corner,table):
    tag='corner' if corner else 'ordinary'
    z=step(o,d)
    # No positive raw flow back to the warehouse port.
    case=Case(b,raw=(o,opp(d)))
    assert not allowed(case,o)
    for through in (d,*tangents):
        p=step(o,through)
        case=Case(b,trans=[p],raw=(o,through))
        src=allowed(case,o)
        nxt=allowed(case,p)
        assert src and nxt
        if through!=d: assert all(not tr[-1] for tr in src)
        # The single common link is directed and mandatory. For any source orientation
        # supporting the link, all deliveries on it are ore. For a bridge, just this lane.
        for tr in src:
            if tr[-1]:
                assert [i for i,j in tr[2] if j==through]==[opp(d)]
        # Generate the actual cartesian product, keeping even pairs that could jam farther away.
        for a,c in product(src,nxt):
            table[(tag,'forward' if d==through else 'turn',a[0],c[0])]+=1
        if through!=d:
            # Could the ore go straight from the source into a nontransport *at* p?
            for s,x,y,_,_,r in candidates('cover',p,0,b.obstacles):
                assert s.name=='供电桩'
            assert p not in b.depots
            # If a four-model machine faces the gap, enumerate every real oriented
            # position and test all possible transport orientations, allowing clean
            # from other neighbours. A forward-facing bridge's supplier lies outside
            # on a dead segment, splitter has an ore-only input, one-outlet cannot
            # dispose of the ore elsewhere.
            for s,x,y,role,_,r in candidates('interface',p,d,b.obstacles|bit(p)):
                if role and s.name in FOUR:
                    survivors=allowed(case,p,required_clean=d,check_body=(s,x,y))
                    assert not survivors,(b.gaps,o,p,s,x,y,survivors)
                    table[(tag,'turn:tested machine',s.name,'orientations')]+=len(TRANS)
            continue
        # Forward receiver: exhaust origin transport, all anchors, type and rotation.
        for s,x,y,role,_,r in candidates('interface',o,d,b.obstacles):
            if not role or s.name not in RAW_IN: continue
            machine=(s,x,y)
            casebody=Case(b,solid=machine,raw=(o,d))
            roots=allowed(casebody,o)
            assert roots
            for tr in roots: table[(tag,'body',tr[0],s.name)]+=1

def rect_test():
    # For any position on an orthogonal span, exhibit an exact 6-cell subinterval of
    # that span which contains the contact. Normal direction uses first 6 cells.
    intervals=[(i,j) for i in range(2,70) for j in range(i+5,70)]
    for a,b in intervals:
        for k in range(a,b+1):
            lo=min(k,b-5)
            assert a<=lo<=k<=lo+5<=b
    rects=0
    for x1,x2 in intervals:
        for y1,y2 in intervals:
            assert x1+5<=x2 and y1+5<=y2
            rects+=1
    # Cross-check q_windows by reversing the generation: build every 6x6 tile, all
    # its in-board side contacts, and compare each face's set of anchors.
    inverse=defaultdict(set)
    for x,y in product(range(2,65),repeat=2):
        for k in range(6):
            for p,d in [((x-1,y+k),0),((x+6,y+k),2),((x+k,y-1),1),((x+k,y+6),3)]:
                if inside(p): inverse[face(p,d)].add((x,y))
    for p in product(range(70),repeat=2):
        for d in D: assert {v[:2] for v in q_windows(face(p,d))}==inverse[face(p,d)]
    return rects,len(inverse)

def test():
    table=Counter()
    qs=Counter()
    for b in each_board():
        for o,ind in b.heads.items():
            d=opp(ind)
            ts=((d+1)%4,(d+3)%4)
            if all(b.heads.get(step(o,t,3))==ind for t in ts):
                route_test(b,o,d,ts,False,table)
        if b.q!=(0,0):
            a=(1,1)
            along=opp(b.heads[a])
            p=step(a,along)
            # All 28 possible receiving orientations at a. The rest of the world may
            # receive on any unblocked side, including a hypothetical extra outlet.
            assert not allowed(Case(b),a,extra_raw_in=along)
            route_test(b,p,opp(b.heads[p]),(along,),True,table)
        # Enumerate the open projection, or empty, independently for q.
        avail={d for d in D if inside(step(b.q,d)) and step(b.q,d) not in b.depots}
        for name,orient,routes,bridge in TRANS:
            assert not any(i in avail and j in avail for i,j in routes)
            qs[name]+=1
        qs['空格']+=1
    p=Path(__file__).resolve().parent
    (p/'运输种类配对.json').write_text(json.dumps(
        [[*k,v] for k,v in sorted(table.items())],ensure_ascii=False,indent=1))
    print('q cell choices',dict(qs))
    print('number of relaxed local combinations by case')
    for label in sorted({k[:2] for k in table}):
        print(label,sum(v for k,v in table.items() if k[:2]==label))
    print('all rectangles, and board faces checked by inverse projection',rect_test())

if __name__=='__main__': test()
