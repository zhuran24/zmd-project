#!/usr/bin/env python3
"""Round 78B native boundary encoding, frozen from cp72; no old edge tables.
The unique boundary pole is required on the left or bottom inner band.
Only these files are written. Run with python -B.
"""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'): os.environ[k]='1'
from pathlib import Path
from collections import defaultdict, Counter
import json, time, argparse, hashlib
from ortools.sat.python import cp_model
OUT=Path(__file__).resolve().parent
ROUNDS=OUT.parents[1]
def cells(x,y,w,h): return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}
HOLE=cells(49,17,21,53)
LINES=[{(69,y) for y in range(1,17)}, {(x,69) for x in range(1,49)},
       {(48,y) for y in range(17,70)}, {(x,16) for x in range(49,70)}]
TARGET=set.union(*LINES)
def legal(c): return 1<=c[0]<70 and 1<=c[1]<70 and c not in HOLE
def caps():
    return {tuple(d['p']):23-d['cap'] for d in json.loads((OUT/'capacities.json').read_text())}
def domain(strip=False):
    target=TARGET | (cells(49,1,21,16) if strip else set())
    result=[]
    for kind,w,h,axis in [('s',3,3,'h'),('s',3,3,'v'),('m',5,5,'h'),('m',5,5,'v'),('l',6,4,'v'),('l',4,6,'h'),('c',9,9,'h'),('c',9,9,'v')]:
        anchors={(i-dx,j-dy) for i,j in target for dx in range(w) for dy in range(h)}
        for x,y in sorted(anchors):
            body=cells(x,y,w,h)
            if not all(map(legal,body)): continue
            if axis=='h': ports=[[(x-1,j) for j in range(y,y+h)],[(x+w,j) for j in range(y,y+h)]]
            else: ports=[[(i,y-1) for i in range(x,x+w)],[(i,y+h) for i in range(x,x+w)]]
            if kind=='c':
                if x<=3 and y<=3: continue
                if x<2 or y<2 or (x<=3 and axis=='h') or (y<=3 and axis=='v'):continue
                if (y==61 and x<=6 and axis=='h') or (x==61 and y<=6 and axis=='v'):continue
                take=[c for e in ports for d,c in enumerate(e) if d in (1,4,7)]
                if not all(map(legal,take)):continue
                put=([(i,j) for i in range(x+1,x+8) for j in (y-1,y+9)] if axis=='h' else [(i,j) for i in (x-1,x+9) for j in range(y+1,y+8)])
                ports=[[c] for c in take]+[[c for c in put if legal(c)]]; needs=[1]*6+[2]
            else: ports=[[c for c in e if legal(c)] for e in ports]; needs=[1,1]
            if any(len(e)<n for e,n in zip(ports,needs)):continue
            result.append(dict(kind=kind,x=x,y=y,w=w,h=h,axis=axis,ports=ports,needs=needs,j=0,loss=0))
    for (x,y),loss in sorted(caps().items()):
        if loss<=13: result.append(dict(kind='p',x=x,y=y,w=2,h=2,axis='-',ports=[],needs=[],j=int(x in (1,68) or y in (1,68)),loss=loss))
    return result
def build(strip=False, fixed_j=None, cap=None, hint=None,project=False,groups=False):
    bs=domain(strip)
    if project:
        machines=[b for b in bs if b['kind'] in ('s','m','l')]
        bs=[p for p in bs if p['kind']!='p' or p['j'] or cells(p['x'],p['y'],2,2)&TARGET or any(d['x']-6<=p['x']<=d['x']+d['w']+4 and d['y']-6<=p['y']<=d['y']+d['h']+4 for d in machines)]
    model=cp_model.CpModel(); vs=[model.new_bool_var('unit'+str(i)) for i in range(len(bs))]
    inc=defaultdict(list)
    for i,b in enumerate(bs):
        for c in cells(b['x'],b['y'],b['w'],b['h']):inc[c].append(vs[i])
    occ={c:model.new_bool_var('cell'+str(c)) for c in sorted(inc)}
    for c,v in occ.items():model.add(v==sum(inc[c]))
    for v,b in zip(vs,bs):
        for e,n in zip(b['ports'],b['needs']):model.add(n*v+sum(occ.get(c,0) for c in e)<=len(e))
    gaps=[model.new_int_var(0,23,'warehouse_gap_'+str(a)) for a in range(2)]
    model.add_allowed_assignments(gaps,[(0,i) for i in range(24)]+[(i,0) for i in range(1,24)])
    for axis in range(2):
        for k in range(24):
            chosen=model.new_bool_var('gap'+str((axis,k)));model.add(gaps[axis]==k).only_enforce_if(chosen);model.add(gaps[axis]!=k).only_enforce_if(chosen.Not())
            ports=[3*i+1+(i>=k) for i in range(23)]
            for t in ports:model.add(occ.get((1,t) if axis==0 else (t,1),0)==0).only_enforce_if(chosen)
    weak=[]
    for i,b in enumerate(bs):
        if b['kind']!='l':continue
        # All 38 large machines require >=2 input channels, at most one <3.
        direction=model.new_bool_var('input_side'+str(i));ex=model.new_bool_var('two_input_exception'+str(i));weak.append(ex);model.add(ex<=vs[i])
        for side in range(2):
            free=len(b['ports'][side])-sum(occ.get(c,0) for c in b['ports'][side])
            model.add(free>=3-ex).only_enforce_if([vs[i],direction if side==0 else direction.Not()])
    model.add(sum(weak)<=1)
    pp=[i for i,b in enumerate(bs) if b['kind']=='p']; mm=[i for i,b in enumerate(bs) if b['kind'] in ('s','m','l')]
    if project:model.add(sum(vs[i] for i in pp)<=10)
    else:model.add(sum(vs[i] for i in pp)==10)
    J=sum(vs[i]*bs[i]['j'] for i in pp)
    if fixed_j is not None:model.add(J==fixed_j)
    for k,n in [('s',131),('m',48),('l',38),('c',1)]:model.add(sum(v for v,b in zip(vs,bs) if b['kind']==k)<=n)
    repeat=[]
    for i in mm:
        b=bs[i]; x,y,w,h=(b[t] for t in ('x','y','w','h'))
        cov=[j for j in pp if x-6<=bs[j]['x']<=x+w+4 and y-6<=bs[j]['y']<=y+h+4]
        n=sum(vs[j] for j in cov)
        model.add(n>=1).only_enforce_if(vs[i])
        z=model.new_int_var(0,9,'repeat'+str(i));repeat.append(z)
        model.add(z==n-1).only_enforce_if(vs[i]);model.add(z==0).only_enforce_if(vs[i].Not())
    model.add(sum(repeat)+sum(vs[i]*bs[i]['loss'] for i in pp)<=13)
    model.add(sum(vs[i] for i in pp if bs[i]['x']==1 or bs[i]['y']==1)==1)
    if groups:
        assert not project
        for ax,ay in [(a,b) for a in range(3) for b in range(3)]:
            touch=defaultdict(list)
            for i in pp:
                p=bs[i];px,py=p['x'],p['y'];body=cells(px,py,2,2);ts=set()
                for cx in range(max(2,px-6),min(68,px+7)+1):
                    for cy in range(max(2,py-6),min(68,py+7)+1):
                        small=cells(cx-1,cy-1,3,3)
                        if small&HOLE or small&body:continue
                        ts.add(((cx+ax)//3,(cy+ay)//3))
                for t in ts:touch[t].append(vs[i])
            active=[]
            for t,ppvars in touch.items():
                g=model.new_bool_var('global_center_group'+str((ax,ay,t)));active.append(g)
                model.add_bool_or(ppvars+[g.Not()])
            model.add(sum(active)>=217)
    # Two corner cells belong to both X and Y and must each be charged twice.
    score=model.new_int_var(0,187 if cap is None else cap,'S')
    model.add(score==160+sum(map(len,LINES))-sum(vs[i]*sum(len(cells(b['x'],b['y'],b['w'],b['h'])&line) for line in LINES) for i,b in enumerate(bs))-2*J)
    model.minimize(score)
    if hint:
        chosen=json.loads(Path(hint).read_text())['chosen'];keys={(b['kind'],b['x'],b['y'],b['w'],b['h'],b['axis']) for b in chosen}
        for b,v in zip(bs,vs):model.add_hint(v,int(tuple(b[k] for k in ('kind','x','y','w','h','axis')) in keys))
    return model,bs,vs,score,gaps
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seconds',type=float,default=300);p.add_argument('--j',type=int);p.add_argument('--cap',type=int);p.add_argument('--strip',action='store_true');p.add_argument('--hint');p.add_argument('--name',default='cp72');p.add_argument('--workers',type=int,default=2);p.add_argument('--seed',type=int,default=72);p.add_argument('--project',action='store_true');p.add_argument('--groups',action='store_true');a=p.parse_args()
    start=time.monotonic();m,bs,vs,score,gaps=build(a.strip,a.j,a.cap,a.hint,a.project,a.groups)
    print('BUILT',len(bs),'units',len(m.proto.variables),'variables',len(m.proto.constraints),'constraints',flush=True)
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=a.seconds;solver.parameters.num_search_workers=a.workers;solver.parameters.random_seed=a.seed;solver.parameters.log_search_progress=True;solver.parameters.linearization_level=2
    st=solver.solve(m)
    out=dict(solver='CP-SAT',version=__import__('ortools').__version__,status=solver.status_name(st),seconds=time.monotonic()-start,branch_J=a.j,strip=a.strip,project=a.project,groups=a.groups,cap=a.cap,lower=solver.best_objective_bound,stats=solver.response_stats(),domain_count=len(bs),domain_sha256=hashlib.sha256(json.dumps(bs,sort_keys=True).encode()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    if st in (cp_model.FEASIBLE,cp_model.OPTIMAL):out.update(S=round(solver.objective_value),warehouse_gaps=[3*solver.value(g) for g in gaps],chosen=[b for b,v in zip(bs,vs) if solver.value(v)])
    (OUT/(a.name+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k not in ('chosen','stats')},ensure_ascii=False),flush=True)
