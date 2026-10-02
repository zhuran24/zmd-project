#!/usr/bin/env python3
"""在联合搜索当前坐标邻域中，精确清除重叠并保留足够端口邻格。

这是摆放必要子问题，成功不表示325路布通；结果随后交给布线器。
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,{6,7,8})
import sys,json,time
from pathlib import Path
from collections import defaultdict,Counter
from ortools.sat.python import cp_model
B=Path(__file__).resolve().parents[1]
D=[(1,0),(0,1),(-1,0),(0,-1)]
def dims(t,d):return (3,3) if t==0 else (5,5) if t==1 else ((4,6) if d%2==0 else (6,4)) if t==2 else (9,9) if t==3 else ((1,3) if d==0 else (3,1)) if t==4 else (2,2)
def ports(x,y,w,h,d,offs=None):
    return [(x+w,y+o) if d==0 else (x+o,y+h) if d==1 else (x-1,y+o) if d==2 else (x+o,y-1) for o in (range(h if d%2==0 else w) if offs is None else offs)]
def solve(src,radius,limit,prefix):
    raw=json.loads(Path(src).read_text());lines=(B/'实验/改规划5初值.txt').read_text().splitlines();n,ne,nr=map(int,lines[0].split())
    by={u['id']:u for u in raw['units']};us=[]
    for line in lines[1:1+n]:
        uid,t,x,y,d,lock=line.split();t,x,y,d,lock=map(int,[t,x,y,d,lock]);u=dict(by[uid])
        if lock and t!=4:u.update(x=x,y=y,d=d)
        u['lock']=bool(lock);u['w'],u['h']=dims(t,u['d']);us.append(u)
    if '--local-units' in sys.argv:
        chosen=set(json.loads(Path(sys.argv[sys.argv.index('--local-units')+1]).read_text()))
        for u in us:
            if u['id'] not in chosen:u['lock']=True
    es=[tuple(map(int,a.split())) for a in lines[1+n:1+n+ne]]
    reserve={tuple(map(int,a.split())) for a in lines[1+n+ne:]}
    rect={(x,y) for x in range(63,69) for y in range(14,20)}
    body=lambda u:{(x,y) for x in range(u['x'],u['x']+u['w']) for y in range(u['y'],u['y']+u['h'])}
    fixedbody=set().union(*(body(u) for u in us if u['lock']))|rect
    if sum(len(body(u)) for u in us if u['lock'])+len(rect)!=len(fixedbody):raise ValueError('固定项重叠')
    nin=Counter(t for s,t in es);nout=Counter(s for s,t in es);adj=defaultdict(list)
    for s,t in es:adj[s].append(t);adj[t].append(s)
    model=cp_model.CpModel();cover=defaultdict(list);opts={};obj=[]
    kept={};existing={};byunit=defaultdict(list)
    if '--preserve-routes' in sys.argv:
        for rr in raw.get('paths',[]):
            if not rr['cells']:continue
            k=rr['r'];v=model.NewBoolVar('keep'+str(k));kept[k]=v;existing[k]=rr
            byunit[es[k][0]].append((v,rr['source'],False));byunit[es[k][1]].append((v,rr['target'],True))
            obj.append(-10000*v)
    if '--preserve-routes' in sys.argv:
        tokens=list(map(int,(B/'实验/保护进路5.txt').read_text().split()));at=1
        for _ in range(tokens[0]):
            rid,length=tokens[at:at+2];at+=2+2*length
            if rid in kept:model.Add(kept[rid]==1)
    free={(x,y):model.NewBoolVar(f'f{x}_{y}') for x in range(70) for y in range(70) if (x,y) not in fixedbody}
    start=time.monotonic()
    for i,u in enumerate(us):
        t=u['type'];ll=[]
        ds=[u['d']] if u['lock'] or t in [4,5] else list(range(4 if t!=3 else 2))
        rad=0 if u['lock'] else radius
        for d in ds:
            w,h=dims(t,d)
            for x in range(max(0 if u['lock'] else 1,u['x']-rad),min(70-w,u['x']+rad)+1):
                for y in range(max(0 if u['lock'] else 1,u['y']-rad),min(70-h,u['y']+rad)+1):
                    q=dict(u,x=x,y=y,w=w,h=h,d=d);cells=body(q)
                    if not u['lock'] and cells&(fixedbody|reserve):continue
                    if t<=2:ip=ports(x,y,w,h,d);op=ports(x,y,w,h,(d+2)%4)
                    elif t==3:
                        ip=sum([ports(x,y,w,h,a,range(1,8)) for a in [d,(d+2)%4]],[])
                        op=sum([ports(x,y,w,h,a,[1,4,7]) for a in [(d+1)%4,(d+3)%4]],[])
                    elif t==4:ip=[];op=ports(x,y,w,h,d,[1])
                    else:ip=[];op=[]
                    ip=[c for c in ip if c in free];op=[c for c in op if c in free]
                    if '--noports' not in sys.argv and '--soft-ports' not in sys.argv and (len(ip)<nin[i] or len(op)<nout[i]):continue
                    v=model.NewBoolVar(f'p{i}_{len(ll)}');ll.append((v,q,ip,op))
                    for keep,endpoint,inbound in byunit[i]:
                        pp=ip if inbound else op;want=tuple(endpoint[:2]);sd=endpoint[2]
                        actual_side=0 if want[0]==x+w else 2 if want[0]==x-1 else 1 if want[1]==y+h else 3
                        good=want in pp and actual_side==sd
                        if not good:model.Add(v+keep<=1)
                    if not u['lock']:
                        for c in cells:cover[c].append(v)
                    move=abs(x-u['x'])+abs(y-u['y'])+(d!=u['d'])
                    cost=move*3
                    for j in adj[i]:
                        z=us[j];cost+=int(abs(x+w/2-z['x']-z['w']/2)+abs(y+h/2-z['y']-z['h']/2))
                    obj.append(cost*v)
                    if x==u['x'] and y==u['y'] and d==u['d']:model.AddHint(v,1)
        model.AddExactlyOne([v for v,q,ip,op in ll]);opts[i]=ll
        print(u['id'],len(ll),flush=True)
    for c,v in free.items():model.Add(v+sum(cover[c])==1)
    for k,keep in kept.items():
        for q in existing[k]['cells']:
            xy=tuple(q[:2])
            if xy in free:model.Add(keep<=free[xy])
            else:model.Add(keep==0)
    for i,ll in opts.items():
        soft='--soft-ports' in sys.argv
        si=model.NewIntVar(0,nin[i],f'defin{i}') if soft else 0
        so=model.NewIntVar(0,nout[i],f'defout{i}') if soft else 0
        if soft:obj.extend([30000*si,30000*so])
        for v,q,ip,op in ll:
            if nin[i] and '--noports' not in sys.argv:model.Add(sum(free[c] for c in ip)+si>=nin[i]).OnlyEnforceIf(v)
            if nout[i] and '--noports' not in sys.argv:model.Add(sum(free[c] for c in op)+so>=nout[i]).OnlyEnforceIf(v)
    # 联合求一条真实进路：方向、端口、机身避让、与保留进路的桥轴占用一起编码。
    focus_active=None;focus_index=None;focus_terms=[];focus_arcs={}
    if '--focus-route' in sys.argv:
        focal=sys.argv[sys.argv.index('--focus-route')+1]
        contract=json.loads((B/'逻辑接法.json').read_text())
        focus_index=next(k for k,e in enumerate(contract['logical_feeds']) if e['id']==focal)
        ss,tt=es[focus_index];focus_active=model.NewBoolVar('focus_real_route');obj.append(-50000*focus_active)
        if '--force-focus' in sys.argv:model.Add(focus_active==1)
        if focus_index in kept:model.Add(kept[focus_index]==0).OnlyEnforceIf(focus_active)
        for unit,inbound in [(ss,False),(tt,True)]:
            supports=defaultdict(list)
            for v,q,ip,op in opts[unit]:
                for cell in (ip if inbound else op):
                    side=0 if cell[0]==q['x']+q['w'] else 2 if cell[0]==q['x']-1 else 1 if cell[1]==q['y']+q['h'] else 3
                    supports[cell,(side+2)%4].append(v)
            vv={key:model.NewBoolVar('terminal') for key in supports}
            model.Add(sum(vv.values())==focus_active)
            for key,v in vv.items():model.Add(v<=sum(supports[key]));model.Add(v<=free[key[0]])
            focus_terms.append(vv)
        for cell in free:
            x,y=cell
            for dx,dy in D:
                other=x+dx,y+dy
                if other not in free:continue
                arc=model.NewBoolVar('wire_arc');focus_arcs[cell,other]=arc
                model.Add(arc<=free[cell]);model.Add(arc<=free[other]);model.Add(arc<=focus_active);obj.append(arc)
        old_at=defaultdict(list)
        for k,rr in existing.items():
            for x,y,ii,oo in rr['cells']:old_at[x,y].append((kept[k],1<<(ii%2) if (ii+2)%4==oo else 3))
        for cell in free:
            ins=[];outs=[]
            for side,(dx,dy) in enumerate(D):
                other=cell[0]+dx,cell[1]+dy
                iv=focus_arcs.get((other,cell),0)+focus_terms[0].get((cell,side),0)
                ov=focus_arcs.get((cell,other),0)+focus_terms[1].get((cell,side),0)
                ins.append(iv);outs.append(ov);model.Add(iv+ov<=1)
            model.Add(sum(ins)==sum(outs));model.Add(sum(ins)<=1)
            for keep,mask in old_at[cell]:
                for axis in (0,1):
                    if mask&(1<<axis):model.Add(ins[axis]+ins[axis+2]+outs[axis]+outs[axis+2]<=2*(1-keep))
    if '--require-power' in sys.argv:
        pole_choices=[(v,q,us[i]['lock']) for i,ll in opts.items() if us[i]['type']==5 for v,q,ip,op in ll]
        for i,ll in opts.items():
            if us[i]['type']>2:continue
            for v,q,ip,op in ll:
                covering=[(pv,locked) for pv,p,locked in pole_choices if q['x']+q['w']-1>=p['x']-5 and q['x']<=p['x']+6 and q['y']+q['h']-1>=p['y']-5 and q['y']<=p['y']+6]
                if not any(locked for pv,locked in covering):model.Add(sum(pv for pv,locked in covering)>=1).OnlyEnforceIf(v)
    model.Minimize(sum(obj));s=cp_model.CpSolver();s.parameters.num_workers=3;s.parameters.max_time_in_seconds=limit;s.parameters.random_seed=19
    dest=Path(prefix)
    def save(sol,status):
        uu=[dict(q) for i,ll in opts.items() for v,q,ip,op in ll if sol.Value(v)]
        for q in uu:q.pop('lock',None)
        retained=[existing[k] for k,v in kept.items() if sol.Value(v)]
        result=dict(schema='port-clear-neighborhood-v1',status=status,source=str(src),radius=radius,elapsed=time.monotonic()-start,objective=sol.ObjectiveValue(),units=uu,paths=retained)
        if focus_active is not None:
            active=bool(sol.Value(focus_active));result['focus_actual_route']=active;result['focus_route']=focal
            if active:
                firstcell,si=next(key for key,v in focus_terms[0].items() if sol.Value(v))
                finish,fo=next(key for key,v in focus_terms[1].items() if sol.Value(v))
                selected={a:z for (a,z),v in focus_arcs.items() if sol.Value(v)}
                at=firstcell;enter=si;cells=[];seen=set()
                while True:
                    if at in seen:raise ValueError('焦点进路成环')
                    seen.add(at)
                    if at==finish:leave=fo
                    else:
                        nxt=selected[at];leave=D.index((nxt[0]-at[0],nxt[1]-at[1]))
                    cells.append([*at,enter,leave])
                    if at==finish:break
                    at=selected[at];enter=(leave+2)%4
                up={q['id']:q for q in uu}
                def terminal(unit,cell,wire_side):
                    u=up[us[unit]['id']];side=(wire_side+2)%4;off=cell[1]-u['y'] if side%2==0 else cell[0]-u['x']
                    return [*cell,side,off]
                result['paths']=[r for r in retained if r['r']!=focus_index]+[dict(r=focus_index,source=terminal(es[focus_index][0],firstcell,si),target=terminal(es[focus_index][1],finish,fo),cells=cells)]
                result['discarded_separate_cycle_arcs']=len(selected)-len(cells)+1

        dest.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=1))
        dest.with_suffix('.pos').write_text(''.join(f"{u['x']} {u['y']} {u['d']}\n" for u in uu))
    class CB(cp_model.CpSolverSolutionCallback):
        def on_solution_callback(self):save(self,'FEASIBLE');print('找到摆放',self.WallTime(),self.ObjectiveValue(),flush=True)
    status=s.Solve(model,CB());result=dict(status=s.StatusName(status),wall=s.WallTime(),variables=len(model.Proto().variables),constraints=len(model.Proto().constraints),radius=radius,source=str(src))
    if status in [cp_model.OPTIMAL,cp_model.FEASIBLE]:save(s,s.StatusName(status))
    dest.with_name(dest.name+'-status.json').write_text(json.dumps(result,ensure_ascii=False,indent=1));print(result,flush=True)
if __name__=='__main__':solve(sys.argv[1],int(sys.argv[2]),float(sys.argv[3]),sys.argv[4])
