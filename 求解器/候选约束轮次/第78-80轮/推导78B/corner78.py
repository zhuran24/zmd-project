"""Local boundary-source relaxation, two independent finite encodings.

Only writes next to this file. An exploratory upper bound is not a layout.
"""
from pathlib import Path
import json, itertools, os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
from ortools.sat.python import cp_model
OUT=Path(__file__).resolve().parent

def body(r):
    x,y,w,h=r
    return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}

def sources(g,h):
    return [(1,3*k+1+int(k>=g//3),0) for k in range(23)]+[(3*k+1+int(k>=h//3),1,1) for k in range(23)]

def solve(g,h,tangent=False,weighted=False,extra=True):
    src=sources(g,h); occupied={(x,y) for x,y,_ in src}
    fixed=set()
    if tangent:
        assert g or h
        r=(1,g-1,3,3) if g else (h-1,1,3,3)
        fixed=body(r)
    options=[]
    for i,(x,y,a) in enumerate(src):
        for shift in range(3):
            r=(2,y-shift,3,3) if a==0 else (x-shift,2,3,3)
            b=body(r)
            if all(1<=u<=69 and 1<=v<=69 for u,v in b) and not b&(occupied|fixed):options.append((i,r,b))
    m=cp_model.CpModel();vs=[m.new_bool_var(str(k)) for k in range(len(options))]
    for i in range(46):m.add(sum(v for v,(s,r,b) in zip(vs,options) if s==i)<=1)
    by={}
    for k,(_,_,b) in enumerate(options):
        for c in b:by.setdefault(c,[]).append(vs[k])
    for arr in by.values():m.add(sum(arr)<=1)
    # When gap=3, all 23 normal consumers in the opposite inner row/column
    # would seal 24 units/tick of ore into a region with only 23 capacity.
    if extra and g==3:m.add(sum(v for v,(i,r,b) in zip(vs,options) if src[i][2]==1)<=22)
    if extra and h==3:m.add(sum(v for v,(i,r,b) in zip(vs,options) if src[i][2]==0)<=22)
    # At gap 3 the fixed 3x3 body can also receive from the other belt's
    # first source (2,1), or (1,2) after transposition. This interface is
    # NOT omitted: the lower tangent interface and that normal interface
    # are mutually exclusive by the two saturated ore-prefix argument.
    # Their combined contribution <=1, plus the upper tangent <=1, is
    # precisely the same safe bonus 2 used at all other gaps.
    tangent_bonus=2 if tangent else 0
    weight=None
    if weighted:
        # Weighted input can be at either end. Another input neighbour on
        # that same side must be unoccupied. This is the full weight-one
        # extremum of the relaxed [0,1] source rate.
        sides=[[(i,j) for i in range(1,4)] for j in (g-2,g+2)] if g else [[(i,j) for j in range(1,4)] for i in (h-2,h+2)]
        ds=[m.new_bool_var('w'+str(i)) for i in range(2)];m.add(sum(ds)<=1)
        if extra and (g==3 or h==3):
            # The tangent axis of source (1,1) terminates against a
            # warehouse unit's non-port at the outer boundary. A plastic
            # shaper neither accepts ore nor sends material into that dead
            # axis. Thus its source-side interface there is absent.
            m.add(ds[0]==0)
            tangent_bonus=1
        for d,side in zip(ds,sides):
            good=[c for c in side[1:] if 1<=c[0]<=69 and 1<=c[1]<=69 and c not in occupied]
            if not good:m.add(d==0)
            else:m.add(sum(sum(by.get(c,[])) for c in good)+d<=len(good))
        weight=sum(ds)
    # In the g=3 corner, the first left source's north-facing tangent
    # interface and first bottom source's normal interface would feed the
    # same 3x3 unit from a saturated ore prefix. They cannot both be active.
    # The crude +2 side bonus is relaxed to +1 if that first normal is kept.
    bonusvars=[]
    m.maximize(sum(vs)+tangent_bonus+(weight if weight is not None else 0))
    s=cp_model.CpSolver();s.parameters.num_search_workers=1;s.parameters.max_time_in_seconds=20
    st=s.solve(m)
    return dict(gaps=[g,h],tangent=tangent,weighted=weighted,status=s.status_name(st),
      bound=46+int(s.best_objective_bound),value=46+int(s.objective_value),
      chosen=[list(r) for v,(_,r,b) in zip(vs,options) if s.value(v)],options=len(options))

if __name__=='__main__':
    rows=[]
    for g,h in [(0,0)]+[(q,0) for q in range(3,70,3)]+[(0,q) for q in range(3,70,3)]:
        for t,w in [(False,False)]+([(True,False),(True,True)] if (g or h) and max(g,h)<69 else []):
            r=solve(g,h,t,w);rows.append(r)
            if r['bound']>91:print('over 91', {k:v for k,v in r.items() if k!='chosen'},flush=True)
    (OUT/'corner_exploration.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
    print('cases',len(rows),'max',max(r['bound'] for r in rows),flush=True)
