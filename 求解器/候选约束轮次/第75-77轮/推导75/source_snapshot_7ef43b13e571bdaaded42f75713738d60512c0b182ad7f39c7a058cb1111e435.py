#!/usr/bin/env python3
"""Optimize the minimum common-grid union, with exact M0 constraints and S,J."""
import os
for key in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[key]='1'
os.sched_setaffinity(0,set(range(12)))
import json,time,argparse,hashlib
from pathlib import Path
from collections import defaultdict
from ortools.sat.python import cp_model
import cp72
OUT=Path(__file__).resolve().parent
cp72.ROUNDS=OUT.parents[1]
def main():
    p=argparse.ArgumentParser();p.add_argument('--s',type=int,required=True);p.add_argument('--j',type=int,required=True)
    p.add_argument('--seconds',type=float,default=300);p.add_argument('--workers',type=int,default=2);p.add_argument('--name',required=True)
    p.add_argument('--fixed-bodies');p.add_argument('--hint');p.add_argument('--seed',type=int,default=75)
    p.add_argument('--floor',type=int,default=0);p.add_argument('--stop-at',type=int,default=217)
    a=p.parse_args();start=time.monotonic();m,bs,vs,score,gaps=cp72.build(fixed_j=a.j,cap=a.s,groups=False)
    m.add(score==a.s);m.clear_objective();q=m.new_int_var(a.floor,300,'minimum_union')
    pp=[i for i,b in enumerate(bs) if b['kind']=='p']
    for ax in range(3):
        for ay in range(3):
            touch=defaultdict(list)
            for i in pp:
                b=bs[i];px,py=b['x'],b['y'];groups=set()
                for cx in range(max(2,px-6),min(68,px+7)+1):
                    for cy in range(max(2,py-6),min(68,py+7)+1):
                        if cx+1>=49 and cy+1>=17:continue
                        if cx-1<=px+1 and px<=cx+1 and cy-1<=py+1 and py<=cy+1:continue
                        groups.add(((cx+ax)//3,(cy+ay)//3))
                for g in groups:touch[g].append(vs[i])
            flags=[]
            for g,ps in touch.items():
                flag=m.new_bool_var(f'g{ax},{ay},{g}');flags.append(flag);m.add(flag<=sum(ps))
            m.add(sum(flags)>=q)
    m.maximize(q)
    def key(b):return tuple(b[k] for k in ('kind','x','y','w','h','axis'))
    if a.fixed_bodies:
        chosen={key(b) for b in json.loads(Path(a.fixed_bodies).read_text())['chosen'] if b['kind']!='p'}
        for b,v in zip(bs,vs):
            if b['kind']!='p':m.add(v==int(key(b) in chosen))
    if a.hint:
        chosen={key(b) for b in json.loads(Path(a.hint).read_text())['chosen']}
        for b,v in zip(bs,vs):m.add_hint(v,int(key(b) in chosen))
    metadata=dict(S_branch=a.s,J_branch=a.j,script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),build_seconds=time.monotonic()-start,
                  model_sha256=hashlib.sha256(str(m.proto).encode()).hexdigest(),fixed_bodies=a.fixed_bodies,time_limit=a.seconds,workers=a.workers)
    print('BUILT',metadata,flush=True)
    class Save(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):
            data=dict(metadata,status='FEASIBLE',S=a.s,min_union=self.value(q),seconds=time.monotonic()-start,
                      chosen=[b for b,v in zip(bs,vs) if self.value(v)],warehouse_gaps=[3*self.value(g) for g in gaps])
            (OUT/(a.name+'_best.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
            print('INCUMBENT',data['min_union'],data['seconds'],flush=True)
            if data['min_union']>=a.stop_at:self.stop_search()
    s=cp_model.CpSolver();s.parameters.num_search_workers=a.workers;s.parameters.max_time_in_seconds=a.seconds;s.parameters.log_search_progress=True
    s.parameters.random_seed=a.seed;s.parameters.linearization_level=2
    st=s.solve(m,Save());metadata.update(status=s.status_name(st),seconds=time.monotonic()-start,upper=s.best_objective_bound,stats=s.response_stats())
    if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):metadata['min_union']=round(s.objective_value)
    (OUT/(a.name+'.json')).write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n')
    print(metadata,flush=True)
if __name__=='__main__':main()
