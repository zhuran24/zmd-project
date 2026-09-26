"""Round 79: independent cell/implication encoding; imports no candidate code."""
import os
os.environ['OMP_NUM_THREADS']='1'
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
os.sched_setaffinity(0,set(range(10)))
import argparse, json, time, hashlib
from pathlib import Path
from collections import defaultdict,Counter
from ortools.sat.python import cp_model

OUT=Path(__file__).resolve().parent

def domain(wall):
    pole={(x,y) for x in (5,6) for y in (5,6)}
    reach={(x,y) for x in range(12) for y in range(12)}
    units=[]
    for size,kind,axes in [((3,3),'s',(0,1)),((5,5),'m',(0,1)),((6,4),'l',(1,)),((4,6),'l',(0,))]:
        w,h=size
        for x in range(-7,13):
            for y in range(-7,13):
                body={(x+i,y+j) for i in range(w) for j in range(h)}
                if not body&reach or body&pole or (wall and any(a>6 for a,b in body)):continue
                for axis in axes:
                    if axis==0:
                        sides=[{(x-1,y+j) for j in range(h)},{(x+w,y+j) for j in range(h)}]
                    else:
                        sides=[{(x+i,y-1) for i in range(w)},{(x+i,y+h) for i in range(w)}]
                    sides=[{c for c in s if c not in pole and (not wall or c[0]<=6)} for s in sides]
                    if any(not s for s in sides):continue
                    units.append(dict(kind=kind,x=x,y=y,w=w,h=h,axis=axis,body=sorted(body),sides=[sorted(s) for s in sides]))
    return units

def solve(wall,threshold,seconds,workers):
    label=('wall' if wall else 'general')+('_opt' if threshold is None else '_ge'+str(threshold))
    start=time.monotonic();items=domain(wall)
    model=cp_model.CpModel();choose=[model.new_bool_var('machine_'+str(i)) for i in range(len(items))]
    bycell=defaultdict(list)
    for i,item in enumerate(items):
        for c in item['body']:bycell[tuple(c)].append(choose[i])
    occupancy={}
    for c,vs in bycell.items():
        occupancy[c]=model.new_bool_var('occupied_'+str(c))
        model.add(sum(vs)==occupancy[c])
    for i,item in enumerate(items):
        for side in item['sides']:
            occupied=[occupancy.get(tuple(c),0) for c in side]
            model.add(sum(occupied)<=len(side)-1).only_enforce_if(choose[i])
    model.add(sum(choose)<=14 if wall else sum(choose)<=23)
    weight=sum((2 if d['kind']=='s' else 3)*v for d,v in zip(items,choose))
    if threshold is None:model.maximize(weight)
    else:model.add(weight>=threshold)
    raw=model.proto.SerializeToString() if hasattr(model.proto,'SerializeToString') else str(model.proto).encode()
    (OUT/(label+'_cp_model.txt')).write_text(str(model.proto))
    (OUT/(label+'_cp_domain.json')).write_text(json.dumps(items,separators=(',',':')))
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=seconds;solver.parameters.num_search_workers=workers
    solver.parameters.log_search_progress=True;solver.parameters.log_to_stdout=False
    with (OUT/(label+'_cp.log')).open('w') as log:
        solver.log_callback=lambda s: log.write(s+'\n')
        status=solver.solve(model)
    result=dict(encoding='cell_boolean_implication',wall=wall,threshold=threshold,options=len(items),status=solver.status_name(status),wall_seconds=time.monotonic()-start,solver_seconds=solver.wall_time,model_sha256=hashlib.sha256(raw).hexdigest(),response=solver.response_stats())
    if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        selected=[d for d,v in zip(items,choose) if solver.value(v)]
        count=Counter(d['kind'] for d in selected)
        result.update(weight=2*count['s']+3*count['m']+3*count['l'],counts=dict(count),witness=selected)
    (OUT/(label+'_cp.json')).write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ('witness','response')},ensure_ascii=False),flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--wall',action='store_true');ap.add_argument('--threshold',type=int);ap.add_argument('--seconds',type=float,default=300);ap.add_argument('--workers',type=int,default=4);a=ap.parse_args()
    solve(a.wall,a.threshold,a.seconds,a.workers)
