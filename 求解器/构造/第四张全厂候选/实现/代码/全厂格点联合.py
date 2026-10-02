#!/usr/bin/env python3
"""Joint integer grid model: rectangular units, endpoint selection, labelled paths.

The executable search uses two-axis bridges and allows adjacent bridges.
It does not infer general infeasibility from that restriction or a timeout.
All paths have individual labels, including parallel feeds of the same item.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
os.sched_setaffinity(0,{6,7,8,9,10,11})
import argparse, json, time, hashlib
from pathlib import Path
from collections import defaultdict
from ortools.sat.python import cp_model

BASE=Path(__file__).resolve().parents[1]
D=((1,0),(0,1),(-1,0),(0,-1))
def save(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=1)+'\n');temp.replace(path)

def build(contract,W,H,rect=None,regions=False,fixed=None,limit=60,workers=4,seed=1,out=None,proto=False,polenum=0,near=None,radius=4,no_lp=False,near_paths=None):
    tic=time.monotonic();m=cp_model.CpModel();C=W*H;E=len(contract['logical_feeds'])
    spec={x['id']:x for x in contract['machines']};routes=contract['logical_feeds']
    full=bool(contract.get('warehouse_outlets'))
    vars={};xi=[];yi=[];positions={};allunits={};posemeta={};bounds={}
    groups={}
    if regions and full:
        adj=defaultdict(set)
        for e in routes:
            if e['source'] in spec and e['target'] in spec:
                adj[e['source']].add(e['target']);adj[e['target']].add(e['source'])
        for f in ['E1','E2','E3','F1','F2','F3','F4']:
            todo=[f];seen={f}
            while todo:
                for v in adj[todo.pop()]:
                    if v not in seen:seen.add(v);todo.append(v)
            for v in seen:groups[v]=f
    regional={'E1':(1,1,38,38),'E2':(1,1,35,55),'E3':(1,1,55,35),'F1':(1,20,45,70),'F2':(20,1,70,45),'F3':(15,25,70,70),'F4':(25,20,70,70)}
    empty=set()
    if rect:
        rx,ry,rw,rh=rect;empty={x+W*y for x in range(rx,rx+rw) for y in range(ry,ry+rh)}
    known_occupied=set(empty)
    if fixed:
        for pp in fixed.values():
            known_occupied.update(x+W*y for x in range(pp['x0'],pp['x1']+1) for y in range(pp['y0'],pp['y1']+1))
    if full:known_occupied.update([70*y for y in range(1,70)]+list(range(1,70)))
    def rectunit(uid,kind,subkind=None):
        if kind=='machine':
            k=spec[uid]['kind'];orient=m.new_int_var(0,3,uid+'_Din')
            w=m.new_int_var(3,6,uid+'_w');h=m.new_int_var(3,6,uid+'_h')
            dims=[(i,3,3) for i in range(4)] if k=='小' else [(i,5,5) for i in range(4)] if k=='中' else [(i,4,6) if i%2==0 else (i,6,4) for i in range(4)]
            m.add_allowed_assignments([orient,w,h],dims)
        else:
            size=9 if kind=='core' else 2
            w=h=size;orient=m.new_int_var(0,1,uid+'_Din') if kind=='core' else 0
        bx,by,bxe,bye=regional[groups[uid]] if uid in groups else (0,0,W,H)
        if near and uid in near:
            pp=near[uid];bx=max(0,pp['x0']-radius);by=max(0,pp['y0']-radius);bxe=min(W,pp['x1']+radius+1);bye=min(H,pp['y1']+radius+1)
        x=m.new_int_var(bx,bxe-1,uid+'_x');y=m.new_int_var(by,bye-1,uid+'_y');bounds[uid]=(bx,by,bxe,bye)
        xe=m.new_int_var(1,W,uid+'_xe');ye=m.new_int_var(1,H,uid+'_ye')
        m.add(xe==x+w);m.add(ye==y+h)
        m.add(xe<=bxe);m.add(ye<=bye)
        xi.append(m.new_interval_var(x,w,xe,uid+'_ix'));yi.append(m.new_interval_var(y,h,ye,uid+'_iy'))
        positions[uid]=(x,y,w,h,orient);posemeta[uid]=kind
        if fixed and uid in fixed:
            p=fixed[uid]
            m.add(x==p['x0']);m.add(y==p['y0']);m.add(orient==p.get('Din',0))
        return x,y,w,h,orient
    for uid in spec:rectunit(uid,'machine')
    if full:
        rectunit('CORE','core')
        # Every 3-cell outlet fits one of the 46 fixed slots; assignment is variable.
        slots=[]
        for side in (0,1):
            for j in range(23):slots.append((len(slots),0 if side==0 else 1+3*j,1+3*j if side==0 else 0,1 if side==0 else 3,3 if side==0 else 1,side))
        choices=[]
        for u in contract['warehouse_outlets']:
            uid=u['id'];slot=m.new_int_var(0,45,uid+'_slot');choices.append(slot)
            x=m.new_int_var(0,69,uid+'_x');y=m.new_int_var(0,69,uid+'_y');w=m.new_int_var(1,3,uid+'_w');h=m.new_int_var(1,3,uid+'_h');side=m.new_int_var(0,1,uid+'_Dout')
            m.add_allowed_assignments([slot,x,y,w,h,side],slots)
            positions[uid]=(x,y,w,h,side);posemeta[uid]='outlet'
            bounds[uid]=(0,0,W,H)
            if fixed and uid in fixed:
                p=fixed[uid];m.add(x==p['x0']);m.add(y==p['y0']);m.add(side==p.get('Dout',p.get('Din')))
        m.add_all_different(choices)
        # Occupancy is the same for every slot permutation.
        for j in range(23):
            for x,y,w,h in [(0,1+3*j,1,3),(1+3*j,0,3,1)]:
                xi.append(m.new_fixed_size_interval_var(x,w,''));yi.append(m.new_fixed_size_interval_var(y,h,''))
    for i in range(polenum):rectunit('POWER'+str(i),'pole')
    if polenum:
        for uid in spec:
            x,y,w,h,_=positions[uid];covers=[]
            for i in range(polenum):
                px,py,*_=positions['POWER'+str(i)];b=m.new_bool_var('');covers.append(b)
                m.add(x+w-1>=px-5).only_enforce_if(b);m.add(x<=px+6).only_enforce_if(b)
                m.add(y+h-1>=py-5).only_enforce_if(b);m.add(y<=py+6).only_enforce_if(b)
            m.add_bool_or(covers)
        if not fixed or not any('POWER'+str(i) in fixed for i in range(polenum)):
            for i in range(polenum-1):
                x,y,*_=positions['POWER'+str(i)];nx,ny,*_=positions['POWER'+str(i+1)]
                m.add(x+W*y<nx+W*ny)
    if rect:
        x,y,w,h=rect;xi.append(m.new_fixed_size_interval_var(x,w,''));yi.append(m.new_fixed_size_interval_var(y,h,''))
    belt=[];bridge=[];active=[];lh=[];lv=[]
    for c in range(C):
        b=m.new_bool_var('belt'+str(c));r=m.new_bool_var('bridge'+str(c));t=m.new_bool_var('T'+str(c))
        m.add(b+r==t)
        if c in known_occupied:m.add(t==0)
        belt.append(b);bridge.append(r);active.append(t)
        lh.append(m.new_int_var(0,E,'H'+str(c)));lv.append(m.new_int_var(0,E,'V'+str(c)))
        m.add(lh[-1]==lv[-1]).only_enforce_if(b)
        m.add(lh[-1]==0).only_enforce_if(t.Not());m.add(lv[-1]==0).only_enforce_if(t.Not())
        xi.append(m.new_optional_fixed_size_interval_var(c%W,1,t,''));yi.append(m.new_optional_fixed_size_interval_var(c//W,1,t,''))
    m.add_no_overlap_2d(xi,yi)
    def array(prefix):
        labels=[m.new_int_var(0,E,prefix+str(i)) for i in range(4*C)]
        bs=[m.new_bool_var('') for i in range(4*C)]
        for lab,b in zip(labels,bs):m.add(lab>=1).only_enforce_if(b);m.add(lab==0).only_enforce_if(b.Not())
        return labels,bs
    starts,sb=array('start');ends,eb=array('end');arcs,ab=array('arc')
    m.add(sum(sb)==E);m.add(sum(eb)==E)
    def endpoint(uid,inbound,lid):
        x,y,w,h,ori=positions[uid];kind=posemeta[uid];rows=[]
        if kind=='machine':
            kk=spec[uid]['kind']
            for di in range(4):
                ww,hh=(3,3) if kk=='小' else (5,5) if kk=='中' else ((4,6) if di%2==0 else (6,4))
                side=di if inbound else (di+2)%4
                for off in range(hh if side%2==0 else ww):
                    dx,dy=[(ww,off),(off,hh),(-1,off),(off,-1)][side]
                    rows.append((di,dx,dy,(side+2)%4))
        elif kind=='outlet':rows=[(0,1,1,2),(1,1,1,3)]
        else:
            for di in (0,1):
                sides=(di,(di+2)%4) if inbound else ((di+1)%4,(di+3)%4)
                for side in sides:
                    for off in (range(1,8) if inbound else (1,4,7)):
                        dx,dy=[(9,off),(off,9),(-1,off),(off,-1)][side]
                        rows.append((di,dx,dy,(side+2)%4))
        dx=m.new_int_var(-1,9,'');dy=m.new_int_var(-1,9,'');side=m.new_int_var(0,3,'')
        m.add_allowed_assignments([ori,dx,dy,side],rows)
        xx=m.new_int_var(0,W-1,'');yy=m.new_int_var(0,H-1,'')
        bx,by,bxe,bye=bounds[uid]
        allowed=set()
        def allow(px,py,side):
            if 0<=px<W and 0<=py<H and px+W*py not in known_occupied:allowed.add(4*(px+W*py)+side)
        if kind=='outlet':
            if fixed and uid in fixed:
                pp=fixed[uid];dd=pp.get('Dout',pp.get('Din'));allow(pp['x0']+1,pp['y0']+1,2 if dd==0 else 3)
            else:
                for jj in range(23):allow(1,2+3*jj,2);allow(2+3*jj,1,3)
        else:
            for di,ddx,ddy,sd in rows:
                if kind=='core':ww=hh=9
                else:
                    kk=spec[uid]['kind'];ww,hh=(3,3) if kk=='小' else (5,5) if kk=='中' else ((4,6) if di%2==0 else (6,4))
                if fixed and uid in fixed:
                    pp=fixed[uid]
                    if di!=pp.get('Din',0):continue
                    allow(pp['x0']+ddx,pp['y0']+ddy,sd)
                else:
                    for ax0 in range(bx,bxe-ww+1):
                        for ay0 in range(by,bye-hh+1):allow(ax0+ddx,ay0+ddy,sd)
        if not allowed:
            m.add(False);allowed={0}
        idx=m.new_int_var_from_domain(cp_model.Domain.from_values(sorted(allowed)),'')
        m.add(xx==x+dx);m.add(yy==y+dy);m.add(idx==4*(xx+W*yy)+side)
        m.add_element(idx, ends if inbound else starts,lid)
        return xx,yy,idx
    endpoints=[];distances=[]
    for i,e in enumerate(routes,1):
        a=endpoint(e['source'],False,i);b=endpoint(e['target'],True,i);endpoints.append((a,b))
        dd=[]
        for j in range(2):z=m.new_int_var(0,max(W,H),'');m.add_abs_equality(z,a[j]-b[j]);dd.append(z)
        distances+=dd
    for c in range(C):
        x,y=c%W,c//W;ins=[];outs=[];axisin=[[],[]]
        for d,(dx,dy) in enumerate(D):
            n=(x+dx)+W*(y+dy);k=4*c+d;valid=0<=x+dx<W and 0<=y+dy<H
            if valid:
                j=4*n+(d+2)%4
                m.add(ab[k]+ab[j]<=1)
                inv=sb[k]+ab[j];ov=eb[k]+ab[k]
                m.add(inv<=active[c]);m.add(ov<=active[c])
                m.add(ab[k]<=active[n])
                # S2B允许相邻桥，弧只表示前向通道；导出时补真实逆向边。
                # The active label at this side belongs to the corresponding axis.
                ax=lh[c] if d%2==0 else lv[c]
                m.add(arcs[j]==ax).only_enforce_if(ab[j]);m.add(arcs[k]==ax).only_enforce_if(ab[k])
            else:
                m.add(ab[k]==0);inv=sb[k];ov=eb[k];ax=lh[c] if d%2==0 else lv[c]
                m.add(inv<=active[c]);m.add(ov<=active[c])
            m.add(starts[k]==ax).only_enforce_if(sb[k]);m.add(ends[k]==ax).only_enforce_if(eb[k])
            # A belt cannot receive and send through the same side.
            m.add(inv+ov<=1)
            ins.append(inv);outs.append(ov);axisin[d%2].append(inv)
        m.add(sum(ins)==belt[c]+2*bridge[c]);m.add(sum(outs)==belt[c]+2*bridge[c])
        for d in range(4):m.add(ins[d]==outs[(d+2)%4]).only_enforce_if(bridge[c])
        for ax in (0,1):m.add(sum(axisin[ax])==1).only_enforce_if(bridge[c])
        m.add(lh[c]!=lv[c]).only_enforce_if(bridge[c])
    # Geometric wire-length lower bound, valid because every route is nonempty.
    m.add(sum(belt)+2*sum(bridge)>=sum(distances)+E)
    lengths=[]
    for pair in contract.get('equal_length',[]):
        hits=[i for i,e in enumerate(routes,1) if [e['source'],e['target']]==pair]
        if not hits:continue
        lid=hits[0];bits=[]
        for c in range(C):
            bh=m.new_bool_var('');bv=m.new_bool_var('');usedv=m.new_bool_var('')
            m.add(lh[c]==lid).only_enforce_if(bh);m.add(lh[c]!=lid).only_enforce_if(bh.Not())
            m.add(lv[c]==lid).only_enforce_if(bv);m.add(lv[c]!=lid).only_enforce_if(bv.Not())
            m.add_bool_and([bv,bridge[c]]).only_enforce_if(usedv);m.add_bool_or([bv.Not(),bridge[c].Not()]).only_enforce_if(usedv.Not())
            bits.extend([bh,usedv])
        lengths.append(sum(bits))
    if len(lengths)==2:m.add(lengths[0]==lengths[1])
    if os.environ.get('FULL_FEASIBILITY_ONLY')!='1':m.minimize(sum(active)*10000+sum(distances))
    if near_paths is not None:
        hints={}
        def hint(v,value):
            if isinstance(v,int):return
            idx=v.index
            if idx in hints and hints[idx]!=value:raise ValueError('提示内部冲突')
            hints[idx]=int(value)
        for uid,p in near.items():
            if uid not in positions:continue
            x,y,w,h,di=positions[uid];hint(x,p['x0']);hint(y,p['y0']);hint(di,p['Din'])
        path_by_id={p['id']:p for p in near_paths};cell_uses=defaultdict(list)
        for lid,(e,(a,b)) in enumerate(zip(routes,endpoints),1):
            if e['id'] not in path_by_id:continue
            p=path_by_id[e['id']];cells=p['cells'];sx,sy,si=p['start'];tx,ty,so=p['end'];sk=4*(sx+W*sy)+si;tk=4*(tx+W*ty)+so
            for vv,value in zip(a,[sx,sy,sk]):hint(vv,value)
            for vv,value in zip(b,[tx,ty,tk]):hint(vv,value)
            hint(starts[sk],lid);hint(sb[sk],1);hint(ends[tk],lid);hint(eb[tk],1)
            for j,(x,y) in enumerate(cells):
                c=x+W*y;incoming=si if j==0 else D.index((cells[j-1][0]-x,cells[j-1][1]-y));cell_uses[c].append((lid,incoming%2))
                if j+1<len(cells):
                    nx,ny=cells[j+1];dd=D.index((nx-x,ny-y));hint(arcs[4*c+dd],lid);hint(ab[4*c+dd],1)
        for c,uses in cell_uses.items():
            hint(active[c],1);hint(belt[c],int(len(uses)==1));hint(bridge[c],int(len(uses)==2))
            if len(uses)==1:hint(lh[c],uses[0][0]);hint(lv[c],uses[0][0])
            else:
                for lid,ax in uses:hint(lh[c] if ax==0 else lv[c],lid)
        for idx,value in hints.items():m.add_hint(m.get_int_var_from_proto_index(idx),value)
    # Hints are optional only; regions are currently not used by this exact model.
    if out and proto:m.export_to_file(str(Path(out).with_suffix('.pbtxt')))
    info={'schema':'joint-cp-run-v1','W':W,'H':H,'routes':E,'machines':len(spec),'fixed_rectangle':rect,'bridge_restriction':'two used axes; adjacent bridges allowed','near_placement_radius':radius if near else None,'hinted_routes':len(near_paths) if near_paths else 0,'no_lp':no_lp,'feasibility_only':os.environ.get('FULL_FEASIBILITY_ONLY')=='1','power_poles':polenum,'seed':seed,'workers':workers,'build_seconds':time.monotonic()-tic,'variables':len(m.proto.variables),'constraints':len(m.proto.constraints),'validation':m.validate()}
    if out:save(out,{**info,'status':'RUNNING'})
    print(json.dumps(info,ensure_ascii=False),flush=True)
    solver=cp_model.CpSolver();solver.parameters.num_search_workers=workers;solver.parameters.max_time_in_seconds=limit;solver.parameters.random_seed=seed;solver.parameters.log_search_progress=True
    if no_lp:solver.parameters.linearization_level=0
    solve_start=time.monotonic()
    def extract(s):
        pp={}
        for uid,(x,y,w,h,ori) in positions.items():pp[uid]={'x0':s.value(x),'y0':s.value(y),'x1':s.value(x)+s.value(w)-1,'y1':s.value(y)+s.value(h)-1,'Din':s.value(ori),'kind':posemeta[uid]}
        ts=[]
        for c in range(C):
            if s.value(active[c]):
                incoming=[];outgoing=[]
                for d,(dx,dy) in enumerate(D):
                    x,y=c%W,c//W;n=x+dx+W*(y+dy);valid=0<=x+dx<W and 0<=y+dy<H;k=4*c+d
                    if s.value(sb[k]) or (valid and s.value(ab[4*n+(d+2)%4])):incoming.append(d)
                    if s.value(eb[k]) or s.value(ab[k]):outgoing.append(d)
                ts.append({'x':c%W,'y':c//W,'type':'bridge' if s.value(bridge[c]) else 'belt','in':incoming,'out':outgoing,'H':s.value(lh[c]),'V':s.value(lv[c])})
        return {'placements':pp,'transport':ts,'routes':[dict(e,start_index=s.value(a[2]),end_index=s.value(b[2])) for e,(a,b) in zip(routes,endpoints)]}
    class CB(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):
            data={**info,'status':'FEASIBLE','elapsed':time.monotonic()-solve_start,'objective':self.objective_value,**extract(self)}
            if out:save(out,data)
    try:status=solver.solve(m,CB())
    except MemoryError:
        info.update(status='MEMORY_LIMIT',wall_seconds=time.monotonic()-solve_start)
        if out:save(out,info)
        return info
    info.update(status=solver.status_name(status),wall_seconds=time.monotonic()-solve_start,response_stats=solver.response_stats())
    if status in (cp_model.FEASIBLE,cp_model.OPTIMAL):info.update(extract(solver))
    if out:save(out,info)
    return info

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--mode',default='full',choices=['full','plant']);ap.add_argument('--size',default='70,70');ap.add_argument('--rect',default='none');ap.add_argument('--seconds',type=float,default=300);ap.add_argument('--workers',type=int,default=4);ap.add_argument('--seed',type=int,default=1);ap.add_argument('--out',required=True);ap.add_argument('--proto',action='store_true');ap.add_argument('--poles',type=int,default=0);ap.add_argument('--regions',action='store_true');ap.add_argument('--fixed');ap.add_argument('--near');ap.add_argument('--radius',type=int,default=4);ap.add_argument('--memory-gb',type=int,default=12);ap.add_argument('--no-lp',action='store_true');ap.add_argument('--hint-routes',action='store_true')
    a=ap.parse_args();contract=json.loads((BASE/'逻辑接法.json').read_text())
    if a.mode=='plant':
        keep={'SA1','SC1','SB1','S1'};contract['machines']=[x for x in contract['machines'] if x['id'] in keep];contract['warehouse_outlets']=[];contract['logical_feeds']=[x for x in contract['logical_feeds'] if x['source'] in keep and x['target'] in keep]
    import resource
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    resource.setrlimit(resource.RLIMIT_AS,(a.memory_gb*1024**3,a.memory_gb*1024**3))
    fixed=json.loads(Path(a.fixed).read_text()).get('placements') if a.fixed else None
    near=json.loads(Path(a.near).read_text()).get('placements') if a.near else None
    if near and not fixed:fixed={uid:p for uid,p in near.items() if p['kind'] in ('outlet','pole')}
    near_paths=json.loads(Path(a.near).read_text()).get('paths') if a.hint_routes and a.near else None
    r=build(contract,*map(int,a.size.split(',')),rect=None if a.rect=='none' else list(map(int,a.rect.split(','))),regions=a.regions,fixed=fixed,limit=a.seconds,workers=a.workers,seed=a.seed,out=BASE/a.out,proto=a.proto,polenum=a.poles,near=near,radius=a.radius,no_lp=a.no_lp,near_paths=near_paths)
    print(json.dumps({k:v for k,v in r.items() if k not in ('transport','placements','routes','response_stats')},ensure_ascii=False),flush=True)
