#!/usr/bin/env python3
"""Independent finite exclusion, no optimizer.

Try every disjoint matching whose TOTAL excess distance is at most 4.
Six selected sources (three nearest each corner) suffice. A target further
than distance 5 cannot occur in such a matching. Real fractional assignments
admit an integral matching of no larger cost, by the transportation LP.
"""
import json
from pathlib import Path
from time import perf_counter

HERE=Path(__file__).resolve().parent

def boundary(gap):
    cells=[v for v in range(70) if v!=gap]
    triples=[cells[i:i+3] for i in range(0,69,3)]
    assert all(b==a+1 and c==b+1 for a,b,c in triples)
    return [t[1] for t in triples]

def check(gl,gb,budget=4):
    forced={(1,y) for y in boundary(gl)} | {(x,1) for x in boundary(gb)}
    sources=[(1,y) for y in boundary(gl)[:3]]+[(x,1) for x in boundary(gb)[:3]]
    options=[]
    for sx,sy in sources:
        choices=[]
        # The full base domain is used; no cropped candidate-domain proof.
        for x in range(1,68):
            for y in range(1,68):
                cells={(xx,yy) for xx in range(x,x+3) for yy in range(y,y+3)}
                if cells & forced:
                    continue
                d=min(abs(sx-xx)+abs(sy-yy) for xx,yy in cells)
                if d-1>budget:
                    continue
                mask=sum(1<<(xx*70+yy) for xx,yy in cells)
                choices.append((d-1,mask,x,y))
        options.append(sorted(choices))
    nodes=0
    deadends=0
    def dfs(todo,used,left):
        nonlocal nodes,deadends
        nodes+=1
        if not todo:
            return []
        feasible=[]
        lower=0
        for i in todo:
            opts=[r for r in options[i] if r[0]<=left and not(r[1]&used)]
            if not opts:
                deadends+=1
                return None
            lower+=opts[0][0]
            feasible.append((len(opts),i,opts))
        if lower>left:
            deadends+=1
            return None
        _,i,opts=min(feasible)
        remaining=tuple(j for j in todo if j!=i)
        for cost,mask,x,y in opts:
            tail=dfs(remaining,used|mask,left-cost)
            if tail is not None:
                return [dict(source=sources[i],machine=[x,y],excess=cost)]+tail
        return None
    start=perf_counter()
    witness=dfs(tuple(range(len(sources))),0,budget)
    return dict(gap_left=gl,gap_bottom=gb,sources=sources,budget=budget,
                option_counts=[len(a) for a in options],nodes=nodes,deadends=deadends,
                status='INFEASIBLE' if witness is None else 'FEASIBLE',witness=witness,
                seconds=perf_counter()-start)

def main():
    gaps=[(g,0) for g in range(0,70,3)]+[(0,g) for g in range(3,70,3)]
    rows=[]
    for gl,gb in gaps:
        r=check(gl,gb)
        rows.append(r)
        print(json.dumps(r,ensure_ascii=False),flush=True)
    assert len(rows)==47 and all(r['status']=='INFEASIBLE' for r in rows)
    out=dict(claim='no assignment has total excess <=4',cases=rows,
             total_nodes=sum(r['nodes'] for r in rows),all_infeasible=True)
    (HERE/'verify_corner.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')

if __name__=='__main__':
    main()
