#!/usr/bin/env python3
"""Compact joint placement/routing CP-SAT with <=3 rectilinear segments per route.

Horizontal interiors may intersect vertical interiors: that cell becomes a bridge.
Waypoints (including endpoints) may not be crossed. Parallel interiors may not
overlap. Two NoOverlap2D constraints implement these facts, including every body.
Adjacent bridges are allowed; their reverse channels must be retained on export.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
import argparse,json,time
from pathlib import Path
from collections import defaultdict
from ortools.sat.python import cp_model
from joint_cp import BASE,save

def solve(contract,W,H,limit,workers,seed,out,rect=None,fixed=None,poles=25,regions=False,partial=False,hint=None,alloff=False,vector_hint=None,route_seed=None,seed_control=False):
    st=time.monotonic();m=cp_model.CpModel();spec={u['id']:u for u in contract['machines']};full=bool(contract['warehouse_outlets']);poses={};ix=[];iy=[];horx=[];hory=[];verx=[];very=[];pointsx=[];pointsy=[];ep=[];ln=[];way=[];extras=[]
    groups={};regional={'E1':(1,1,38,38),'E2':(1,1,35,55),'E3':(1,1,55,35),'F1':(1,20,45,70),'F2':(20,1,70,45),'F3':(15,25,70,70),'F4':(25,20,70,70)}
    if full and regions:
        adj=defaultdict(set)
        for e in contract['logical_feeds']:
            if e['source'] in spec and e['target'] in spec:adj[e['source']].add(e['target']);adj[e['target']].add(e['source'])
        for f in regional:
            seen={f};todo=[f]
            while todo:
                for v in adj[todo.pop()]:
                    if v not in seen:seen.add(v);todo.append(v)
            for v in seen:groups[v]=f
    def unit(uid,kind):
        bx,by,xe,ye=regional[groups[uid]] if uid in groups else (0,0,W,H)
        x=m.new_int_var(bx,xe-1,uid+'x');y=m.new_int_var(by,ye-1,uid+'y');di=m.new_int_var(0,3,uid+'di')
        if kind=='machine':
            k=spec[uid]['kind'];dims=[(d,3,3) for d in range(4)] if k=='小' else [(d,5,5) for d in range(4)] if k=='中' else [(d,4,6) if d%2==0 else (d,6,4) for d in range(4)]
        elif kind=='core':dims=[(d,9,9) for d in range(2)]
        else:dims=[(0,2,2)]
        w=m.new_int_var(2,9,'');h=m.new_int_var(2,9,'');m.add_allowed_assignments([di,w,h],dims)
        xx=m.new_int_var(1,xe,'');yy=m.new_int_var(1,ye,'');m.add(xx==x+w);m.add(yy==y+h)
        ix.append(m.new_interval_var(x,w,xx,''));iy.append(m.new_interval_var(y,h,yy,''));poses[uid]=(x,y,w,h,di,kind)
        if fixed and uid in fixed:
            p=fixed[uid];m.add(x==p['x0']);m.add(y==p['y0']);m.add(di==p.get('Din',0))
        if hint and uid in hint:
            p=hint[uid];m.add_hint(x,p['x0']);m.add_hint(y,p['y0']);m.add_hint(di,p.get('Din',0))
    for uid in spec:unit(uid,'machine')
    if full:
        unit('CORE','core')
        slots=[(0,1+3*j,1,3,0) for j in range(23)]+[(1+3*j,0,3,1,1) for j in range(23)]
        left=['WFE1','WFE2']+['WFE'+str(j) for j in range(5,9)]+['WO'+str(j) for j in range(7,13)]+['WFE'+str(j) for j in range(13,21)]+['WFE'+str(j) for j in range(29,32)]
        bottom=['WFE3','WFE4']+['WFE'+str(j) for j in range(9,13)]+['WO'+str(j) for j in range(13,19)]+['WFE'+str(j) for j in range(21,29)]+['WFE32','WFE33','WFE34']
        for uid,(x,y,w,h,d) in zip(left+bottom,slots):
            if route_seed and uid in route_seed['placements']:
                p=route_seed['placements'][uid];x,y,w,h,d=p['x0'],p['y0'],p['x1']-p['x0']+1,p['y1']-p['y0']+1,p['Din']
            ix.append(m.new_fixed_size_interval_var(x,w,''));iy.append(m.new_fixed_size_interval_var(y,h,''));poses[uid]=(x,y,w,h,d,'outlet')
        if poles==25:
            pc=[(x,y) for x in (8,22,36,50,64) for y in (8,22,36,50,64) if (x,y)!=(64,64)]+[(60,60)]
            for i,(x,y) in enumerate(pc):
                ix.append(m.new_fixed_size_interval_var(x,2,''));iy.append(m.new_fixed_size_interval_var(y,2,''));poses['POWER'+str(i)]=(x,y,2,2,0,'pole')
        else:
            for i in range(poles):unit('POWER'+str(i),'pole')
            pc=[poses['POWER'+str(i)][:2] for i in range(poles)]
            for i in range(poles-1):m.add(pc[i][0]+W*pc[i][1]<pc[i+1][0]+W*pc[i+1][1])
        for uid in spec:
            x,y,w,h,*_=poses[uid];bs=[]
            for px,py in pc:
                b=m.new_bool_var('');bs.append(b);m.add(x+w-1>=px-5).only_enforce_if(b);m.add(x<=px+6).only_enforce_if(b);m.add(y+h-1>=py-5).only_enforce_if(b);m.add(y<=py+6).only_enforce_if(b)
            m.add_bool_or(bs)
    if rect:
        x,y,w,h=rect;ix.append(m.new_fixed_size_interval_var(x,w,''));iy.append(m.new_fixed_size_interval_var(y,h,''))
    def endpoint(uid,inbound,active):
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
        px=m.new_int_var(-1,W,'');py=m.new_int_var(-1,H,'');m.add(px==x+dx);m.add(py==y+dy)
        m.add(px>=0).only_enforce_if(active);m.add(px<W).only_enforce_if(active);m.add(py>=0).only_enforce_if(active);m.add(py<H).only_enforce_if(active)
        return px,py,s
    def bit_positive(v):
        b=m.new_bool_var('');m.add(v>=1).only_enforce_if(b);m.add(v==0).only_enforce_if(b.Not());return b
    def conjunction(a,b):
        c=m.new_bool_var('');m.add_bool_and([a,b]).only_enforce_if(c);m.add_bool_or([a.Not(),b.Not()]).only_enforce_if(c.Not());return c
    def point(x,y,present=None):
        if present is None:
            pointsx.append(m.new_fixed_size_interval_var(x,1,''));pointsy.append(m.new_fixed_size_interval_var(y,1,''))
        else:
            pointsx.append(m.new_optional_fixed_size_interval_var(x,1,present,''));pointsy.append(m.new_optional_fixed_size_interval_var(y,1,present,''))
    def inner(a,b,q,horizontal,present):
        low=m.new_int_var(-1,max(W,H),'');high=m.new_int_var(-1,max(W,H),'');m.add_min_equality(low,[a,b]);m.add_max_equality(high,[a,b])
        length=m.new_int_var(0,max(W,H)+1,'');m.add_max_equality(length,[high-low-1,0]);positive=bit_positive(length);on=conjunction(present,positive)
        start=m.new_int_var(0,max(W,H)+1,'');m.add(start==low+1);end=m.new_int_var(0,max(W,H)+2,'');m.add(end==start+length)
        iv=m.new_optional_interval_var(start,length,end,on,'');ivq=m.new_optional_fixed_size_interval_var(q,1,on,'')
        if horizontal:horx.append(iv);hory.append(ivq)
        else:verx.append(ivq);very.append(iv)
    enabled=[];seed_by_id={p['id']:p for p in route_seed.get('seed_paths',[])} if route_seed else {}
    for ei,e in enumerate(contract['logical_feeds']):
        active=m.new_bool_var('route'+str(ei));enabled.append(active)
        if not partial:m.add(active==1)
        elif hint:m.add_hint(active,0)
        if alloff:m.add(active==0)
        if seed_control:m.add(active==int(e['id'] in seed_by_id))
        a=endpoint(e['source'],False,active);b=endpoint(e['target'],True,active);ep.append((a,b));point(a[0],a[1],active);mode=m.new_bool_var('vertical_first'+str(ei));midvars=[];total=m.new_int_var(1,2*W+2*H,'length'+str(ei));usedlength=m.new_int_var(0,2*W+2*H,'usedlength'+str(ei));m.add(usedlength==total).only_enforce_if(active);m.add(usedlength==0).only_enforce_if(active.Not());ln.append(usedlength)
        if seed_control and e['id'] in seed_by_id:
            sd=seed_by_id[e['id']]
            for v,want in zip(a,sd['start']):m.add(v==want)
            for v,want in zip(b,sd['end']):m.add(v==want)
            m.add(mode==sd['mode'])
        for vertical,chosen in [(False,mode.Not()),(True,mode)]:
            selected=conjunction(active,chosen)
            ax,ay=(a[1],a[0]) if vertical else a[:2];bx,by=(b[1],b[0]) if vertical else b[:2];mx=m.new_int_var(0,(H if vertical else W)-1,'');midvars.append(mx)
            if seed_control and e['id'] in seed_by_id and vertical==bool(seed_by_id[e['id']]['mode']):m.add(mx==seed_by_id[e['id']]['middle'])
            d1=m.new_int_var(0,max(W,H)+1,'');dy=m.new_int_var(0,max(W,H)+1,'');d2=m.new_int_var(0,max(W,H)+1,'')
            m.add_abs_equality(d1,mx-ax);m.add_abs_equality(dy,by-ay);m.add_abs_equality(d2,bx-mx);b1=bit_positive(d1);bv=bit_positive(dy);b2=bit_positive(d2)
            m.add(mx==ax).only_enforce_if([selected,bv.Not()]);m.add(total==d1+dy+d2+1).only_enforce_if(chosen)
            def xy(x,y):return (y,x) if vertical else (x,y)
            point(*xy(mx,ay),conjunction(selected,b1));point(*xy(mx,by),conjunction(selected,bv));point(*xy(bx,by),conjunction(selected,b2))
            inner(ax,mx,ay,not vertical,selected);inner(ay,by,mx,vertical,selected);inner(mx,bx,by,not vertical,selected)
        way.append((mode,midvars))
    m.add_no_overlap_2d(ix+pointsx+horx,iy+pointsy+hory);m.add_no_overlap_2d(ix+pointsx+verx,iy+pointsy+very)
    equal=[]
    for pair in contract.get('equal_length',[]):
        matches=[ln[i] for i,e in enumerate(contract['logical_feeds']) if [e['source'],e['target']]==pair]
        if matches:equal.append(matches[0])
    if len(equal)==2:m.add(equal[0]==equal[1])
    if full:m.add(sum(ln)<=2*(W*H-3567-81-138-4*poles-(rect[2]*rect[3] if rect else 0)))
    m.minimize(sum(ln)-100000*sum(enabled) if partial else sum(ln))
    if vector_hint is not None:
        if len(vector_hint)!=len(m.proto.variables):raise ValueError('完整提示变量数不符')
        m.clear_hints()
        for i,v in enumerate(vector_hint):m.add_hint(m.get_int_var_from_proto_index(i),v)
    solver=cp_model.CpSolver();solver.parameters.max_time_in_seconds=limit;solver.parameters.num_workers=workers;solver.parameters.random_seed=seed;solver.parameters.log_search_progress=True
    info={'schema':'s2-polyline-joint-v1','is_layout':False,'partial_search':partial,'all_routes_disabled_control':alloff,'complete_hint':vector_hint is not None,'W':W,'H':H,'machines':len(spec),'routes_count':len(ep),'rect':rect,'fixed_poles':poles==25,'poles':poles if full else 0,'regions':regions,'restrictions':['three segments per route','no bridge on any waypoint','fixed outlet order and corner gaps']+(['regional machine domains'] if regions else []),'workers':workers,'seed':seed,'variables':len(m.proto.variables),'constraints':len(m.proto.constraints),'build_seconds':time.monotonic()-st,'validation':m.validate()}
    def extract(s):
        pp={uid:dict(x0=s.value(x),y0=s.value(y),x1=s.value(x)+s.value(w)-1,y1=s.value(y)+s.value(h)-1,Din=s.value(d),kind=k) for uid,(x,y,w,h,d,k) in poses.items()}
        paths=[]
        for e,(a,b),(mo,mid),length,on in zip(contract['logical_feeds'],ep,way,ln,enabled):
            if not s.value(on):continue
            aa=[s.value(z) for z in a];bb=[s.value(z) for z in b];v=s.value(mo);mx=s.value(mid[v]);pts=[aa[:2],[aa[0],mx],[bb[0],mx],bb[:2]] if v else [aa[:2],[mx,aa[1]],[mx,bb[1]],bb[:2]]
            cells=[pts[0]]
            for u,vv in zip(pts,pts[1:]):
                dx=(vv[0]>u[0])-(vv[0]<u[0]);dy=(vv[1]>u[1])-(vv[1]<u[1]);n=abs(vv[0]-u[0])+abs(vv[1]-u[1]);cells.extend([[u[0]+k*dx,u[1]+k*dy] for k in range(1,n+1)])
            assert len(cells)==s.value(length)
            paths.append(dict(e,start=aa,end=bb,waypoints=pts,cells=cells))
        return {'placements':pp,'paths':paths,'routed':len(paths),'missing_routes':[e['id'] for e,on in zip(contract['logical_feeds'],enabled) if not s.value(on)],'transport_slot_count':sum(s.value(v) for v in ln),'elapsed':time.monotonic()-st}
    class CB(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):save(out,{**info,'status':'FEASIBLE',**extract(self)})
    save(out,{**info,'status':'RUNNING'});print(json.dumps(info,ensure_ascii=False),flush=True)
    ss=solver.solve(m,CB());info.update(status=solver.status_name(ss),wall_seconds=solver.wall_time,response_stats=solver.response_stats())
    if ss in (cp_model.OPTIMAL,cp_model.FEASIBLE):info.update(extract(solver));info['solution_vector']=list(solver.response_proto.solution)
    save(out,info);return info

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['full','plant','plant-fixed'],default='full');ap.add_argument('--size',default='70,70');ap.add_argument('--seconds',type=float,default=600);ap.add_argument('--workers',type=int,default=4);ap.add_argument('--seed',type=int,default=1);ap.add_argument('--out',required=True);ap.add_argument('--rect',default='none');ap.add_argument('--poles',type=int,default=25);ap.add_argument('--regions',action='store_true');ap.add_argument('--partial',action='store_true');ap.add_argument('--all-off',action='store_true');ap.add_argument('--hint');ap.add_argument('--solution-hint');ap.add_argument('--fixed');ap.add_argument('--route-seed');ap.add_argument('--seed-control',action='store_true');a=ap.parse_args();c=json.loads((BASE/'逻辑接法.json').read_text());fixed=None
    if a.mode.startswith('plant'):
        keep={'SA1','SC1','SB1','S1'};c['machines']=[x for x in c['machines'] if x['id'] in keep];c['warehouse_outlets']=[];c['logical_feeds']=[x for x in c['logical_feeds'] if x['source'] in keep and x['target'] in keep]
        if a.mode=='plant-fixed':fixed={'SA1':{'x0':0,'y0':5,'Din':1},'SC1':{'x0':5,'y0':5,'Din':3},'SB1':{'x0':10,'y0':5,'Din':1},'S1':{'x0':11,'y0':1,'Din':1}}
    if a.fixed:fixed=json.loads(Path(a.fixed).read_text())['placements']
    hint=json.loads(Path(a.hint).read_text())['placements'] if a.hint else None
    vector=json.loads(Path(a.solution_hint).read_text())['solution_vector'] if a.solution_hint else None
    route_seed=json.loads(Path(a.route_seed).read_text()) if a.route_seed else None
    solve(c,*map(int,a.size.split(',')),a.seconds,a.workers,a.seed,BASE/a.out,None if a.rect=='none' else list(map(int,a.rect.split(','))),fixed,a.poles,a.regions,a.partial,hint,a.all_off,vector,route_seed,a.seed_control)
