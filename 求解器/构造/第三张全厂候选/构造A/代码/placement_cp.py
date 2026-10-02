#!/usr/bin/env python3
"""CP-SAT placement subproblem; endpoint cells reserved, routing not certified."""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
import argparse,json,time
from pathlib import Path
from collections import Counter
from ortools.sat.python import cp_model
from joint_cp import BASE,save

def run(seconds,seed,workers,out,rect,freepoles=False):
    contract=json.loads((BASE/'逻辑接法.json').read_text());spec={u['id']:u for u in contract['machines']};m=cp_model.CpModel();start=time.monotonic()
    poses={};ix=[];iy=[];startx=[];starty=[];endx=[];endy=[];netpoints=[];distances=[]
    def unit(uid,kind):
        k=spec[uid]['kind'] if uid in spec else None
        x=m.new_int_var(1,68,uid+'x');y=m.new_int_var(1,68,uid+'y');di=m.new_int_var(0,3,uid+'di')
        if kind=='machine':dims=[(d,3,3) for d in range(4)] if k=='小' else [(d,5,5) for d in range(4)] if k=='中' else [(d,4,6) if d%2==0 else (d,6,4) for d in range(4)]
        else:dims=[(d,9,9) for d in range(2)]
        w=m.new_int_var(3,9,'');h=m.new_int_var(3,9,'');m.add_allowed_assignments([di,w,h],dims)
        xx=m.new_int_var(1,70,'');yy=m.new_int_var(1,70,'');m.add(xx==x+w);m.add(yy==y+h)
        ix.append(m.new_interval_var(x,w,xx,''));iy.append(m.new_interval_var(y,h,yy,''));poses[uid]=(x,y,w,h,di,kind)
    for uid in spec:unit(uid,'machine')
    unit('CORE','core')
    slots=[(0,1+3*j,1,3,0) for j in range(23)]+[(1+3*j,0,3,1,1) for j in range(23)]
    # This concrete search uses a fixed ordering, recorded in its output.
    left=['WFE1','WFE2']+['WFE'+str(j) for j in range(5,9)]+['WO'+str(j) for j in range(7,13)]+['WFE'+str(j) for j in range(13,21)]+['WFE'+str(j) for j in range(29,32)]
    bottom=['WFE3','WFE4']+['WFE'+str(j) for j in range(9,13)]+['WO'+str(j) for j in range(13,19)]+['WFE'+str(j) for j in range(21,29)]+['WFE32','WFE33','WFE34']
    assert len(left)==len(bottom)==23
    for uid,(x,y,w,h,di) in zip(left+bottom,slots):
        ix.append(m.new_fixed_size_interval_var(x,w,''));iy.append(m.new_fixed_size_interval_var(y,h,''));poses[uid]=(x,y,w,h,di,'outlet')
    polecoords=[(x,y) for x in (8,22,36,50,64) for y in (8,22,36,50,64) if (x,y)!=(64,64)]+[(60,60)]
    for i,(x,y) in enumerate(polecoords):
        ix.append(m.new_fixed_size_interval_var(x,2,''));iy.append(m.new_fixed_size_interval_var(y,2,''));poses['POWER'+str(i)]=(x,y,2,2,0,'pole')
    if rect:
        x,y,w,h=rect;ix.append(m.new_fixed_size_interval_var(x,w,''));iy.append(m.new_fixed_size_interval_var(y,h,''))
    def point(uid,inbound):
        x,y,w,h,di,kind=poses[uid];rows=[]
        if kind=='machine':
            k=spec[uid]['kind']
            for d in range(4):
                ww,hh=(3,3) if k=='小' else (5,5) if k=='中' else ((4,6) if d%2==0 else (6,4));s=d if inbound else (d+2)%4
                for off in range(hh if s%2==0 else ww):
                    dx,dy=[(ww,off),(off,hh),(-1,off),(off,-1)][s];rows.append((d,dx,dy,(s+2)%4))
        elif kind=='core':
            for d in range(2):
                for s in ((d,(d+2)%4) if inbound else ((d+1)%4,(d+3)%4)):
                    for off in (range(1,8) if inbound else (1,4,7)):
                        dx,dy=[(9,off),(off,9),(-1,off),(off,-1)][s];rows.append((d,dx,dy,(s+2)%4))
        else:rows=[(0,1,1,2),(1,1,1,3)]
        dx=m.new_int_var(-1,9,'');dy=m.new_int_var(-1,9,'');s=m.new_int_var(0,3,'');m.add_allowed_assignments([di,dx,dy,s],rows)
        px=m.new_int_var(0,69,'');py=m.new_int_var(0,69,'');m.add(px==x+dx);m.add(py==y+dy)
        qx=m.new_fixed_size_interval_var(px,1,'');qy=m.new_fixed_size_interval_var(py,1,'')
        (endx if inbound else startx).append(qx);(endy if inbound else starty).append(qy)
        return px,py,s
    for e in contract['logical_feeds']:
        a=point(e['source'],False);b=point(e['target'],True);netpoints.append((a,b));d=m.new_int_var(0,138,'');xx=m.new_int_var(0,69,'');yy=m.new_int_var(0,69,'');m.add_abs_equality(xx,a[0]-b[0]);m.add_abs_equality(yy,a[1]-b[1]);m.add(d==xx+yy);distances.append(d)
    m.add_no_overlap_2d(ix+startx,iy+starty);m.add_no_overlap_2d(ix+endx,iy+endy)
    # Fixed poles leave gaps of only two cells in each axis except near the
    # reserved corner; verify the actual coverage rather than assume it.
    for uid in spec:
        x,y,w,h,*_=poses[uid];cov=[]
        for px,py in polecoords:
            b=m.new_bool_var('');cov.append(b);m.add(x+w-1>=px-5).only_enforce_if(b);m.add(x<=px+6).only_enforce_if(b);m.add(y+h-1>=py-5).only_enforce_if(b);m.add(y<=py+6).only_enforce_if(b)
        m.add_bool_or(cov)
    # Bounding wire length is a necessary condition even with crossings.
    m.add(sum(distances)+len(distances)<=2*(4900-3567-81-138-4*len(polecoords)-(rect[2]*rect[3] if rect else 0)))
    m.minimize(sum(distances))
    solver=cp_model.CpSolver();solver.parameters.num_workers=workers;solver.parameters.max_time_in_seconds=seconds;solver.parameters.random_seed=seed;solver.parameters.log_search_progress=True
    info={'schema':'s2-placement-subproblem-v1','is_layout':False,'seed':seed,'workers':workers,'fixed_empty_rectangle':rect,'restrictions':['fixed outlet order and gap at corner','fixed 25 power poles','different first cells and different last cells'],'build_seconds':time.monotonic()-start,'variables':len(m.proto.variables),'constraints':len(m.proto.constraints)}
    def extract(s):
        pp={}
        for uid,(x,y,w,h,di,kind) in poses.items():pp[uid]=dict(x0=s.value(x),y0=s.value(y),x1=s.value(x)+s.value(w)-1,y1=s.value(y)+s.value(h)-1,Din=s.value(di),kind=kind)
        return dict(placements=pp,endpoints=[dict(e,start=[s.value(z) for z in a],end=[s.value(z) for z in b]) for e,(a,b) in zip(contract['logical_feeds'],netpoints)],manhattan_total=sum(s.value(d) for d in distances),elapsed=time.monotonic()-start)
    class CB(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):save(out,{**info,'status':'FEASIBLE',**extract(self)})
    print(json.dumps(info),flush=True);st=solver.solve(m,CB());info.update(status=solver.status_name(st),wall_seconds=solver.wall_time,response_stats=solver.response_stats())
    if st in (cp_model.FEASIBLE,cp_model.OPTIMAL):info.update(extract(solver))
    save(out,info)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--seconds',type=float,default=600);ap.add_argument('--seed',type=int,default=1);ap.add_argument('--workers',type=int,default=4);ap.add_argument('--out',default='实验/placement.json');ap.add_argument('--rect',default='64,64,6,6');a=ap.parse_args()
    run(a.seconds,a.seed,a.workers,BASE/a.out,None if a.rect=='none' else list(map(int,a.rect.split(','))))
