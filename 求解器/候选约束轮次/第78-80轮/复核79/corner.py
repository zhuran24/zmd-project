"""Independent reconstruction of all 135 corner bounds, two finite encodings."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
os.sched_setaffinity(0,set(range(10)))
import json,time,warnings,itertools
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_matrix
from ortools.sat.python import cp_model

OUT=Path(__file__).resolve().parent
SRC=OUT.parent/'推导78B'

def cells(r):
    x,y,w,h=r
    return {(x+i,y+j) for i in range(w) for j in range(h)}

def cp_run(g,h,fixed,weighted):
    origins=[(1,3*i+1+(3*i>=g),0) for i in range(23)]+[(3*i+1+(3*i>=h),1,1) for i in range(23)]
    forced={(x,y) for x,y,_ in origins};special=cells((1,g-1,3,3) if g else (h-1,1,3,3)) if fixed else set()
    opts=[]
    for src,(x,y,axis) in enumerate(origins):
        for off in range(3):
            r=(2,y-off,3,3) if axis==0 else (x-off,2,3,3);b=cells(r)
            if any(not (1<=u<=69 and 1<=v<=69) for u,v in b) or b&(forced|special):continue
            opts.append((src,r,b))
    model=cp_model.CpModel();v=[model.new_bool_var('normal_'+str(i)) for i in range(len(opts))]
    occupied=defaultdict(list);sourcevars=defaultdict(list)
    for i,(src,r,b) in enumerate(opts):
        sourcevars[src].append(v[i])
        for c in b:occupied[c].append(v[i])
    for a in sourcevars.values():model.add_at_most_one(a)
    for a in occupied.values():model.add_at_most_one(a)
    if g==3:model.add(sum(v[i] for i,(src,_,_) in enumerate(opts) if origins[src][2]==1)<=22)
    if h==3:model.add(sum(v[i] for i,(src,_,_) in enumerate(opts) if origins[src][2]==0)<=22)
    bonus=2 if fixed else 0;wv=[]
    if weighted:
        sides=[[(x,g-2),(x,g+2)] for x in (2,3)] if g else [[(h-2,y),(h+2,y)] for y in (2,3)]
        for end in range(2):
            z=model.new_bool_var('weight_'+str(end));wv.append(z)
            neighbours=[s[end] for s in sides if 1<=s[end][0]<=69 and 1<=s[end][1]<=69 and s[end] not in forced]
            if neighbours:model.add(sum(sum(occupied[c]) for c in neighbours)<=len(neighbours)-1).only_enforce_if(z)
            else:model.add(z==0)
        model.add(sum(wv)<=1)
        if g==3 or h==3:model.add(wv[0]==0);bonus=1
    model.maximize(sum(v)+sum(wv))
    solver=cp_model.CpSolver();solver.parameters.num_search_workers=1;solver.parameters.max_time_in_seconds=30
    st=solver.solve(model);assert st==cp_model.OPTIMAL
    return dict(bound=46+bonus+round(solver.objective_value),status=solver.status_name(st),options=len(opts),chosen=[r for i,(_,r,_) in enumerate(opts) if solver.value(v[i])])

def integer_run(g,h,fixed,weighted):
    sources=[]
    for gap,axis in ((g,0),(h,1)):
        line=[k for k in range(70) if k!=gap]
        for i in range(23):
            chunk=line[3*i:3*i+3];assert chunk==list(range(chunk[0],chunk[0]+3))
            sources.append((1,chunk[1],axis) if axis==0 else (chunk[1],1,axis))
    forced={(x,y) for x,y,a in sources}
    rect=(1,g-1,3,3) if g else (h-1,1,3,3)
    options=[]
    def intersects(r,s):
        x,y,w,h=r;u,v,a,b=s
        return x<u+a and u<x+w and y<v+b and v<y+h
    # Enumerate all edge-normal body anchors independently of source offsets.
    for axis in (0,1):
        for start in range(1,68):
            r=(2,start,3,3) if axis==0 else (start,2,3,3)
            if fixed and intersects(r,rect):continue
            x,y,rw,rh=r
            if any(x<=u<x+rw and y<=v<y+rh for u,v in forced):continue
            matches=[i for i,(u,v,a) in enumerate(sources) if a==axis and ((axis==0 and start<=v<start+3) or (axis==1 and start<=u<start+3))]
            for i in matches:options.append((i,r))
    n=len(options);nv=n+(2 if weighted else 0);rows=[];rhs=[]
    def add(r,b):rows.append(r);rhs.append(b)
    for i in range(n):
        for j in range(i):
            if options[i][0]==options[j][0] or intersects(options[i][1],options[j][1]):add({i:1,j:1},1)
    if g==3:add({i:1 for i,(src,r) in enumerate(options) if sources[src][2]==1},22)
    if h==3:add({i:1 for i,(src,r) in enumerate(options) if sources[src][2]==0},22)
    bonus=2 if fixed else 0
    if weighted:
        add({n:1,n+1:1},1)
        for end in range(2):
            pos=(g-2 if end==0 else g+2) if g else (h-2 if end==0 else h+2)
            neighbours=[(k,pos) if g else (pos,k) for k in (2,3)]
            neighbours=[p for p in neighbours if 1<=p[0]<=69 and 1<=p[1]<=69 and p not in forced]
            rr={n+end:1}
            for i,(_,r) in enumerate(options):
                x,y,rw,rh=r;c=sum(x<=u<x+rw and y<=v<y+rh for u,v in neighbours)
                if c:rr[i]=c
            add(rr,len(neighbours))
        if g==3 or h==3:add({n:1},0);bonus=1
    ii=[];jj=[];vv=[]
    for i,r in enumerate(rows):
        for j,v in r.items():ii.append(i);jj.append(j);vv.append(v)
    A=coo_matrix((np.asarray(vv,float),(ii,jj)),shape=(len(rows),nv)).tocsc()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        res=milp(-np.ones(nv),integrality=np.ones(nv),bounds=Bounds(np.zeros(nv),np.ones(nv)),constraints=LinearConstraint(A,-np.inf,rhs),options=dict(threads=1,time_limit=30,mip_rel_gap=0))
    assert res.status==0,res.message
    point=np.rint(res.x).astype(int);assert all(A@point<=np.array(rhs))
    return dict(bound=46+bonus+int(sum(point)),status=res.message,options=n,chosen=[r for i,(_,r) in enumerate(options) if point[i]])

def main():
    start=time.monotonic();cases=[]
    for g,h in [(0,0)]+[(k,0) for k in range(3,70,3)]+[(0,k) for k in range(3,70,3)]:
        modes=[(False,False)]+([(True,False),(True,True)] if 0<max(g,h)<69 else [])
        for fixed,weighted in modes:
            a=cp_run(g,h,fixed,weighted);b=integer_run(g,h,fixed,weighted)
            assert a['bound']==b['bound'] and a['options']==b['options'],(g,h,fixed,weighted,a,b)
            assert a['bound']<=91
            if fixed and not weighted and max(g,h)>=6:assert a['bound']<=90
            cases.append(dict(gaps=[g,h],tangent=fixed,weighted=weighted,cp=a,milp=b))
    original=json.loads((SRC/'corner_independent.json').read_text())['cases']
    key=lambda c:(*c['gaps'],c['tangent'],c['weighted'])
    submitted={key(c):c['bound'] for c in original}
    assert {key(c):c['cp']['bound'] for c in cases}==submitted
    out=dict(cases=cases,count=len(cases),maximum=max(c['cp']['bound'] for c in cases),all_submitted_match=True,seconds=time.monotonic()-start)
    (OUT/'corner_checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in out.items() if k!='cases'}),flush=True)

if __name__=='__main__':main()
