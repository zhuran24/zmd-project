#!/usr/bin/env python3
"""Independent necessary geometry model. No imports from source audit programs.

Coordinates are half-open rectangles. Only bodies meeting the measured cells
are retained; all omitted bodies and their ports are relaxed away.
"""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key] = '1'
import argparse
from collections import defaultdict, Counter
from dataclasses import dataclass, asdict
import hashlib
import json
from pathlib import Path
import time
from ortools.sat.python import cp_model

BASE = Path('/home/zhuran24/zmd-research-fresh/求解器/候选约束轮次/第60-62轮/复核62')

def cells(x,y,w,h):
    return tuple((i,j) for i in range(x,x+w) for j in range(y,y+h))

def intersects(x,y,w,h,R):
    a,b,W,H = R
    return x < a+W and a < x+w and y < b+H and b < y+h

def measures(R):
    a,b,W,H = R
    rect = set(cells(*R))
    X = Counter({(69,j):1 for j in range(1,69) if (69,j) not in rect})
    X.update({(i,69):1 for i in range(1,69) if (i,69) not in rect})
    if (69,69) not in rect:
        X[69,69] = 2
    Y = Counter()
    for i in range(a,a+W):
        for j in (b-1,b+H):
            if 0 <= j < 70: Y[i,j] = 1
    for j in range(b,b+H):
        for i in (a-1,a+W):
            if 0 <= i < 70: Y[i,j] = 1
    return X,Y

def pole_attributes(x,y,R):
    a,b,W,H = R
    edges = (x==1)+(x==68)+(y==1)+(y==68)
    loss = 15 if edges==2 else 9 if edges else 0
    costs = (10,9,9,6,5,4,1)
    if b <= y-5 and y+7 <= b+H:
        for gap in (a-x-2,x-a-W):
            if 0 <= gap <= 6: loss = max(loss,costs[gap])
    if a <= x-5 and x+7 <= a+W:
        for gap in (b-y-2,y-b-H):
            if 0 <= gap <= 6: loss = max(loss,costs[gap])
    return int(edges>0),loss

@dataclass(frozen=True)
class Body:
    kind: str
    x: int
    y: int
    w: int
    h: int
    axis: str
    ports: tuple
    needs: tuple
    j: int
    loss: int

    def footprint(self): return cells(self.x,self.y,self.w,self.h)

def generate(R,mode='joint',edge0=False):
    """edge0=True deliberately ALLOWS row/column 0 port neighbours."""
    X,Y = measures(R)
    target = set(X) | set(Y) if mode=='joint' else set(X if mode=='X' else Y)
    rset = set(cells(*R))
    lower = 0 if edge0 else 1
    def valid(c): return lower <= c[0] < 70 and lower <= c[1] < 70 and c not in rset
    shapes = [('s',3,3,'h'),('s',3,3,'v'),('m',5,5,'h'),('m',5,5,'v'),
              ('l',6,4,'v'),('l',4,6,'h'),('c',9,9,'h'),('c',9,9,'v'),('p',2,2,'-')]
    result = []
    for kind,w,h,axis in shapes:
        # Enumerate anchors from each target cell, then de-duplicate anchors.
        anchors = {(cx-dx,cy-dy) for cx,cy in target for dx in range(w) for dy in range(h)}
        for x,y in sorted(anchors):
            if not (1<=x<=70-w and 1<=y<=70-h) or intersects(x,y,w,h,R): continue
            groups,needs = [],[]
            if kind in ('s','m','l'):
                if axis=='h':
                    sides = [[(x-1,j) for j in range(y,y+h)],[(x+w,j) for j in range(y,y+h)]]
                else:
                    sides = [[(i,y-1) for i in range(x,x+w)],[(i,y+h) for i in range(x,x+w)]]
                groups = [tuple(c for c in side if valid(c)) for side in sides]
                needs = [1,1]
            elif kind=='c':
                if axis=='h':
                    take = [(i,y+d) for i in (x-1,x+9) for d in (1,4,7)]
                    put = [(x+d,j) for j in (y-1,y+9) for d in range(1,8)]
                else:
                    take = [(x+d,j) for j in (y-1,y+9) for d in (1,4,7)]
                    put = [(i,y+d) for i in (x-1,x+9) for d in range(1,8)]
                if not all(valid(c) for c in take): continue
                groups = [(c,) for c in take]+[tuple(c for c in put if valid(c))]
                needs = [1]*6+[2]
            if any(len(g)<n for g,n in zip(groups,needs)): continue
            j,loss = pole_attributes(x,y,R) if kind=='p' else (0,0)
            result.append(Body(kind,x,y,w,h,axis,tuple(groups),tuple(needs),j,loss))
    return result,X,Y

def build(R,mode='joint',edge0=False,fixed_p=None,cap=None):
    bodies,X,Y = generate(R,mode,edge0)
    measure = X+Y if mode=='joint' else X if mode=='X' else Y
    model = cp_model.CpModel()
    selected = [model.new_bool_var(f'b{i}') for i in range(len(bodies))]
    incidence = defaultdict(list)
    for i,body in enumerate(bodies):
        for c in body.footprint(): incidence[c].append(i)
    occ = {}
    for c,indices in sorted(incidence.items()):
        v = model.new_bool_var(f'o{c[0]}_{c[1]}')
        model.add(v == sum(selected[i] for i in indices))
        occ[c] = v
    # An unoccupied legal neighbour may host a transport cell; its direction,
    # material and connection to other neighbours are intentionally omitted.
    for v,body in zip(selected,bodies):
        for group,need in zip(body.ports,body.needs):
            model.add(sum(occ.get(c,0) for c in group) <= len(group)-need).only_enforce_if(v)
    for kind,lim in [('s',131),('m',48),('l',38),('c',1)]:
        model.add(sum(v for v,b in zip(selected,bodies) if b.kind==kind)<=lim)
    P = model.new_int_var(10,12,'P')
    if fixed_p is not None: model.add(P==fixed_p)
    hidden_j = model.new_int_var(0,12,'hidden_boundary_poles')
    poles = [(v,b) for v,b in zip(selected,bodies) if b.kind=='p']
    model.add(sum(v for v,b in poles)+hidden_j <= P)
    J = sum(v*b.j for v,b in poles)+hidden_j
    model.add(sum(v*b.loss for v,b in poles)+9*hidden_j <= 23*P-217)
    holes = sum(measure.values())-sum(v*sum(measure[c] for c in b.footprint()) for v,b in zip(selected,bodies))
    # Individual X/Y optimization uses its own (relaxed) copy of all resources.
    objective = 16*P-2*J+holes if mode=='joint' else holes
    if cap is None: model.minimize(objective)
    else: model.add(objective<=cap)
    return model,bodies,selected,P,hidden_j,J,holes,objective

def solve(R,seconds=300,workers=4,edge0=False,fixed_p=None,cap=None,mode='joint',log_path=None):
    start=time.monotonic()
    model,bodies,selected,P,hj,J,holes,objective=build(R,mode,edge0,fixed_p,cap)
    build_seconds=time.monotonic()-start
    solver=cp_model.CpSolver()
    solver.parameters.num_search_workers=workers
    solver.parameters.max_time_in_seconds=seconds
    solver.parameters.random_seed=62
    solver.parameters.cp_model_probing_level=0
    solver.parameters.linearization_level=2
    fp = None
    if log_path:
        fp=Path(log_path).open('w')
        solver.parameters.log_search_progress=True
        solver.parameters.log_to_stdout=False
        solver.log_callback=lambda s: (fp.write(s+'\n'),fp.flush())
    status=solver.solve(model)
    if fp: fp.close()
    res={'R':R,'mode':mode,'allow_edge0_ports':edge0,'fixed_P':fixed_p,'cap':cap,
         'workers':workers,'seconds_limit':seconds,'status':solver.status_name(status),
         'build_seconds':build_seconds,'solve_seconds':solver.wall_time,
         'bodies':len(bodies),'model_sha256':hashlib.sha256(str(model.proto).encode()).hexdigest(),
         'model_stats':model.model_stats(),'response_stats':solver.response_stats()}
    if cap is None: res['lower_bound']=solver.best_objective_bound
    if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        chosen=[b for v,b in zip(selected,bodies) if solver.value(v)]
        occupied=set(c for b in chosen for c in b.footprint())
        X,Y=measures(R)
        xval=sum(n for c,n in X.items() if c not in occupied)
        yval=sum(n for c,n in Y.items() if c not in occupied)
        res.update({'objective':solver.value(objective),'P':solver.value(P),'J':solver.value(J),
                    'hidden_boundary_poles':solver.value(hj),'X':xval,'Y':yval,
                    'S':16*solver.value(P)-2*solver.value(J)+xval+yval,
                    'chosen':[asdict(b) for b in chosen]})
    return res

def main():
    p=argparse.ArgumentParser()
    p.add_argument('a',type=int);p.add_argument('b',type=int)
    p.add_argument('--W',type=int,default=21);p.add_argument('--H',type=int,default=53)
    p.add_argument('--seconds',type=float,default=300);p.add_argument('--workers',type=int,default=4)
    p.add_argument('--allow-edge0',action='store_true');p.add_argument('--P',type=int)
    p.add_argument('--cap',type=int);p.add_argument('--mode',choices=['joint','X','Y'],default='joint')
    p.add_argument('--name',required=True)
    a=p.parse_args()
    assert 1<=a.workers<=4 and '/' not in a.name
    res=solve((a.a,a.b,a.W,a.H),a.seconds,a.workers,a.allow_edge0,a.P,a.cap,a.mode,BASE/(a.name+'.log'))
    (BASE/(a.name+'.json')).write_text(json.dumps(res,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in res.items() if k not in ('chosen','model_stats','response_stats')},ensure_ascii=False),flush=True)

if __name__=='__main__': main()
