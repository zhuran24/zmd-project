#!/usr/bin/env python3
"""Bounded local search: fixed bodies, ten disjoint pole neighborhoods.
Adds all-subset power capacity conditions as nine exact integral flow networks.
Feasibility proves a relaxation witness; local infeasibility has no global force.
"""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
os.sched_setaffinity(0,set(range(12)))
from pathlib import Path
from collections import defaultdict
import json,time,hashlib,argparse
from ortools.sat.python import cp_model
import cp72
OUT=Path(__file__).resolve().parent;cp72.ROUNDS=OUT.parents[1]
def centers(px,py):
    return [(x,y) for x in range(max(2,px-6),min(68,px+7)+1) for y in range(max(2,py-6),min(68,py+7)+1)
            if not(x+1>=49 and y+1>=17) and not(x-1<=px+1 and px<=x+1 and y-1<=py+1 and py<=y+1)]
def main():
    p=argparse.ArgumentParser();p.add_argument('base');p.add_argument('--radius',type=int,default=3);p.add_argument('--seconds',type=float,default=300);p.add_argument('--workers',type=int,default=4);p.add_argument('--name',required=True)
    a=p.parse_args();start=time.monotonic();base=json.loads(Path(a.base).read_text());S=base['S']
    m,bs,vs,score,gaps=cp72.build(fixed_j=1,cap=S,groups=False);m.add(score==S);m.clear_objective()
    keys={tuple(b[k] for k in ('kind','x','y','w','h','axis')) for b in base['chosen']};sourcep=[b for b in base['chosen'] if b['kind']=='p']
    pp=[i for i,b in enumerate(bs) if b['kind']=='p'];clusters=[]
    for i,b in enumerate(bs):
        if b['kind']!='p':m.add(vs[i]==int(tuple(b[k] for k in ('kind','x','y','w','h','axis')) in keys))
    for p0 in sourcep:
        rad=0 if p0['x'] in (1,68) or p0['y'] in (1,68) else a.radius
        options=[i for i in pp if abs(bs[i]['x']-p0['x'])<=rad and abs(bs[i]['y']-p0['y'])<=rad]
        clusters.append(options);m.add(sum(vs[i] for i in options)==1)
    flattened=[i for c in clusters for i in c];assert len(flattened)==len(set(flattened))
    allowed=set(flattened)
    for i in pp:
        if i not in allowed:m.add(vs[i]==0)
    cs={i:centers(bs[i]['x'],bs[i]['y']) for i in allowed}
    for ax in range(3):
        for ay in range(3):
            global_groups=defaultdict(list);total=[]
            for no,opts in enumerate(clusters):
                can=defaultdict(list)
                for i in opts:
                    for group in {((x+ax)//3,(y+ay)//3) for x,y in cs[i]}:can[group].append(vs[i])
                outgoing=[]
                for group,choices in can.items():
                    f=m.new_bool_var(f'f{ax},{ay},{no},{group}');m.add(f<=sum(choices));outgoing.append(f);global_groups[group].append(f)
                m.add(sum(outgoing)<=sum((23-bs[i]['loss'])*vs[i] for i in opts));total.extend(outgoing)
            for flows in global_groups.values():m.add(sum(flows)<=1)
            m.add(sum(total)>=217)
    for i in allowed:m.add_hint(vs[i],int(tuple(bs[i][k] for k in ('kind','x','y','w','h','axis')) in keys))
    out=dict(scope='local fixed-body M2 with all nine full capacity flows',base=a.base,radius=a.radius,cluster_sizes=list(map(len,clusters)),workers=a.workers,time_limit=a.seconds,
             script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),model_sha256=hashlib.sha256(str(m.proto).encode()).hexdigest(),build_seconds=time.monotonic()-start)
    print('BUILT',out,flush=True)
    solver=cp_model.CpSolver();solver.parameters.num_search_workers=a.workers;solver.parameters.max_time_in_seconds=a.seconds;solver.parameters.linearization_level=2;solver.parameters.log_search_progress=True
    st=solver.solve(m);out.update(status=solver.status_name(st),seconds=time.monotonic()-start,stats=solver.response_stats())
    if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):out.update(S=S,chosen=[b for b,v in zip(bs,vs) if solver.value(v)],warehouse_gaps=[3*solver.value(g) for g in gaps])
    (OUT/(a.name+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print({k:v for k,v in out.items() if k not in ('stats','chosen')},flush=True)
if __name__=='__main__':main()
