#!/usr/bin/env python3
"""Anonymous exact-cover packing with a connected free corridor skeleton.

This is a placement relaxation, not a complete layout. Manufacturing identities
and all 325 point-to-point routes must still be assigned and independently checked.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
import argparse,json,time
from collections import defaultdict
from ortools.sat.python import cp_model
from joint_cp import BASE,save,D

def run(seconds,workers,seed,out,connected,spines,rect,feasible=False):
    t0=time.monotonic();m=cp_model.CpModel();N=70
    fixed={(0,y) for y in range(1,70)}|{(x,0) for x in range(1,70)}
    poles=[(x,y) for x in (8,22,36,50,64) for y in (8,22,36,50,64) if (x,y) not in [(64,64),(36,36)]]+[(60,60),(38,38)]
    pc={(x+i,y+j) for x,y in poles for i in range(2) for j in range(2)}
    rr={(x,y) for x in range(rect[0],rect[0]+rect[2]) for y in range(rect[1],rect[1]+rect[3])} if rect else set()
    spine={(x,y) for x in range(1,70) for y in range(1,70) if (x in spines or y in spines)}-fixed-pc-rr
    core=(29,29,9,9,0);cc={(x,y) for x in range(29,38) for y in range(29,38)}
    blocked=fixed|pc|rr|cc
    if blocked&spine:raise ValueError('固定单位挡住走廊')
    free={(x,y) for x in range(70) for y in range(70)}-blocked
    occ=defaultdict(list);placements=[];Ts={c:m.new_bool_var('t') for c in free};kin={'小':1,'中':1,'大':3};kout={'小':1,'中':2,'大':1}
    for c in spine:m.add(Ts[c]==1)
    def facing(ax,ay,w,h,s):
        return [(ax+w,ay+j) for j in range(h)] if s==0 else [(ax+i,ay+h) for i in range(w)] if s==1 else [(ax-1,ay+j) for j in range(h)] if s==2 else [(ax+i,ay-1) for i in range(w)]
    def powered(ax,ay,w,h):return any(ax+w-1>=x-5 and ax<=x+6 and ay+h-1>=y-5 and ay<=y+6 for x,y in poles)
    for kind,count in [('小',134),('中',57),('大',39)]:
        vs=[]
        for di in range(4):
            w,h=(3,3) if kind=='小' else (5,5) if kind=='中' else ((4,6) if di%2==0 else (6,4))
            for x in range(1,71-w):
                for y in range(1,71-h):
                    cells=[(i,j) for i in range(x,x+w) for j in range(y,y+h)]
                    if any(c in blocked or c in spine for c in cells) or not powered(x,y,w,h):continue
                    pin=[c for c in facing(x,y,w,h,di) if c in free];pout=[c for c in facing(x,y,w,h,(di+2)%4) if c in free]
                    if len(pin)<kin[kind] or len(pout)<kout[kind]:continue
                    v=m.new_bool_var('');vs.append(v);placements.append((kind,x,y,w,h,di,v))
                    for c in cells:occ[c].append(v)
                    m.add(sum(Ts[c] for c in pin)>=kin[kind]).only_enforce_if(v);m.add(sum(Ts[c] for c in pout)>=kout[kind]).only_enforce_if(v)
        m.add(sum(vs)==count)
    for c in free:m.add(sum(occ[c])+Ts[c]<=1)
    for side in (0,1):
        for j in range(23):m.add(Ts[(1,2+3*j) if side==0 else (2+3*j,1)]==1)
    for s in (1,3):
        for c in [facing(29,29,9,9,s)[z] for z in (1,4,7)]:m.add(Ts[c]==1)
    # The complete free skeleton is connected; each selected additional cell
    # consumes one unit of a fictitious flow originating anywhere on that skeleton.
    flows={}
    if connected:
        for c in free:
            for d,(dx,dy) in enumerate(D):
                n=(c[0]+dx,c[1]+dy)
                if n in free:
                    f=m.new_int_var(0,4900,'');flows[c,d]=f;m.add(f<=4900*Ts[c]);m.add(f<=4900*Ts[n])
        for c in free-spine:
            incoming=[];outgoing=[]
            for d,(dx,dy) in enumerate(D):
                n=(c[0]+dx,c[1]+dy)
                if (c,d) in flows:outgoing.append(flows[c,d]);incoming.append(flows[n,(d+2)%4])
            m.add(sum(incoming)-sum(outgoing)==Ts[c])
    if not feasible:m.minimize(sum(Ts.values()))
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=seconds;solver.parameters.num_workers=workers;solver.parameters.random_seed=seed;solver.parameters.log_search_progress=True
    info={'schema':'s2-anonymous-packing-v1','is_layout':False,'feasibility_only':feasible,'connected':connected,'fixed_spines':spines,'rect':rect,'positions':len(placements),'variables':len(m.proto.variables),'constraints':len(m.proto.constraints),'build_seconds':time.monotonic()-t0,'workers':workers,'seed':seed}
    def extract(s):return dict(units=[dict(kind=k,x0=x,y0=y,x1=x+w-1,y1=y+h-1,Din=di) for k,x,y,w,h,di,v in placements if s.value(v)],core=dict(x0=29,y0=29,x1=37,y1=37,Din=0),poles=poles,transport_reserved=[list(c) for c,v in Ts.items() if s.value(v)],skeleton=[list(c) for c in sorted(spine)])
    class CB(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):save(out,{**info,'status':'FEASIBLE','elapsed':time.monotonic()-t0,**extract(self)})
    save(out,{**info,'status':'RUNNING'});print(json.dumps(info),flush=True);st=solver.solve(m,CB());info.update(status=solver.status_name(st),wall_seconds=solver.wall_time,response_stats=solver.response_stats())
    if st in (cp_model.FEASIBLE,cp_model.OPTIMAL):info.update(extract(solver))
    save(out,info)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=float,default=600);ap.add_argument('--workers',type=int,default=4);ap.add_argument('--seed',type=int,default=1);ap.add_argument('--out',required=True);ap.add_argument('--connected',action='store_true');ap.add_argument('--feasible',action='store_true');ap.add_argument('--spines',default='13,27,41,55,69');ap.add_argument('--rect',default='64,64,6,6');a=ap.parse_args();run(a.seconds,a.workers,a.seed,BASE/a.out,a.connected,[] if a.spines=='none' else list(map(int,a.spines.split(','))),None if a.rect=='none' else list(map(int,a.rect.split(','))),a.feasible)
