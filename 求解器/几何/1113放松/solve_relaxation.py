#!/usr/bin/env python3
"""CP-SAT finite placement relaxation. Sequential positions, <= 12 workers."""
import argparse, hashlib, json, time
from pathlib import Path
from collections import Counter,defaultdict
from ortools.sat.python import cp_model
from filter_positions import ROOT, COUNTS, PATTERNS, cells, overlaps, port_sides, pole_loss

def build(position,boundary_cuts=False):
    start=time.monotonic(); r=tuple(position['rect']); blocked=cells(r)
    model=cp_model.CpModel()
    ts={pt:model.new_bool_var(f't_{pt[0]}_{pt[1]}') for pt in cells((0,0,70,70))-blocked}
    occupied=defaultdict(list); placements=[]; groups=defaultdict(list)
    def free_port(pt): return pt in ts and pt[0]>=1 and pt[1]>=1
    def make(kind,rr,axis=None):
        var=model.new_bool_var(f'{kind}_{rr[0]}_{rr[1]}_{axis}')
        placements.append((kind,rr,axis,var))
        groups[kind].append(var)
        for pt in cells(rr): occupied[pt].append(var)
        return var
    # Warehouse gap is a decision: all 47 joint patterns unless a corridor cut excludes it.
    choices={i:model.new_bool_var(f'warehouse_pattern_{i}') for i in position['patterns']}
    model.add_exactly_one(list(choices.values()))
    warehouse=defaultdict(list)
    for i,var in choices.items():
        for pt in PATTERNS[i]['bodies']: warehouse[tuple(pt)].append(var)
        for pt in PATTERNS[i]['ports']: model.add_implication(var,ts[tuple(pt)])
    # All nine types have only three distinct geometric signatures in this relaxation.
    # Counts partition exactly into 131 small, 48 medium, 38 large; labels are restored on export.
    for kind,W,H,axes in [('small',3,3,(0,1)),('medium',5,5,(0,1)),('large',6,4,(1,)),('large',4,6,(0,))]:
        for x in range(1,71-W):
            for y in range(1,71-H):
                rr=(x,y,W,H)
                if overlaps(rr,r): continue
                for axis in axes:
                    sides=[[ts[pt] for pt in edge if free_port(pt)] for edge in port_sides(rr,axis)]
                    if not all(sides): continue
                    var=make(kind,rr,axis)
                    for edge in sides: model.add_bool_or(edge).only_enforce_if(var)
    for kind,n in [('small',131),('medium',48),('large',38)]: model.add(sum(groups[kind])==n)
    # Core occupies 9x9. Six mandatory output cells, >=2 input cells (no storage boxes).
    for x in range(2,62):
        for y in range(2,62):
            rr=(x,y,9,9)
            if overlaps(rr,r) or (x<=3 and y<=3): continue
            for axis in (0,1):
                out=[pt for edge in port_sides(rr,axis,True) for pt in edge]
                if not all(free_port(pt) for pt in out): continue
                ins=[edge[k] for edge in port_sides(rr,1-axis) for k in range(1,8) if free_port(edge[k])]
                if len(ins)<2: continue
                allowed=[]
                for i in choices:
                    ports=PATTERNS[i]['ports']
                    ml=sum(y<=yy<y+9 for xx,yy in ports if xx==1)
                    mb=sum(x<=xx<x+9 for xx,yy in ports if yy==1)
                    if ml+3*(axis==0)>(1 if y==61 else 2)*(x-1): continue
                    if mb+3*(axis==1)>(1 if x==61 else 2)*(y-1): continue
                    allowed.append(choices[i])
                if not allowed: continue
                var=make('core',rr,axis)
                for pt in out: model.add_implication(var,ts[pt])
                model.add(sum(ts[pt] for pt in ins)>=2).only_enforce_if(var)
                if len(allowed)<len(choices): model.add_bool_or(allowed).only_enforce_if(var)
    model.add(sum(groups['core'])==1)
    poles={}; losses=[]; edge_poles=[]
    for x in range(1,69):
        for y in range(1,69):
            rr=(x,y,2,2)
            if overlaps(rr,r): continue
            var=make('pole',rr); poles[x,y]=var
            losses.append(pole_loss(rr,r)*var)
            if x in (1,68) or y in (1,68): edge_poles.append(var)
    P=model.new_int_var_from_domain(cp_model.Domain.from_values(position['allowed_P']),'P')
    model.add(P==sum(poles.values()))
    J=model.new_int_var(0,6,'J'); model.add(J==sum(edge_poles))
    model.add(9*J<=23*P-217)
    model.add(sum(losses)<=23*P-217)
    # Integral image of pole origins: exact OR coverage without per-machine assignments.
    pref={}
    for x in range(70):
        for y in range(70):
            if x==0 or y==0: pref[x,y]=0; continue
            v=model.new_int_var(0,12,f'power_prefix_{x}_{y}'); pref[x,y]=v
            model.add(v==pref[x-1,y]+pref[x,y-1]-pref[x-1,y-1]+poles.get((x-1,y-1),0))
    for kind,(x,y,w,h),axis,var in placements:
        if kind not in ('small','medium','large'): continue
        lx,ly=max(1,x-6),max(1,y-6)
        ux,uy=min(68,x+w+4),min(68,y+h+4)
        model.add(pref[ux+1,uy+1]-pref[lx,uy+1]-pref[ux+1,ly]+pref[lx,ly]>=var)
    structural={}
    for pt in ts:
        v=model.new_bool_var(f'body_{pt[0]}_{pt[1]}'); structural[pt]=v
        model.add(v==sum(occupied[pt]))
        model.add(v+ts[pt]+sum(warehouse[pt])<=1)
    model.add(sum(ts.values())>=208)
    # Extra boundary transport q triggers 209 (formal Transportation minimum).
    for i,var in choices.items():
        bodies=set(map(tuple,PATTERNS[i]['bodies']))
        q=next(iter(({(0,k) for k in range(70)}|{(k,0) for k in range(70)})-bodies))
        model.add(sum(ts.values())>=208+ts[q]).only_enforce_if(var)
    a,b,w,h=r
    xcells=([(69,k) for k in range(1,69)]+[(k,69) for k in range(1,69)])
    X=sum(1-structural[pt] for pt in xcells if pt not in blocked)
    if (69,69) not in blocked:
        X += 2*(1-sum(p for (px,py),p in poles.items() if px<=69<px+2 and py<=69<py+2))
    ring=([(a-1,k) for k in range(b,b+h)] + ([(a+w,k) for k in range(b,b+h)] if a+w<70 else [])
          +[(k,b-1) for k in range(a,a+w)] + ([(k,b+h) for k in range(a,a+w)] if b+h<70 else []))
    Y=sum(1-structural[pt] for pt in ring)
    model.add(16*P-2*J+X+Y<=187)
    model.add(14*P<=187)
    if boundary_cuts:
        for branch in position['branches']:
            if not branch['keep']: continue
            chosen=model.new_bool_var(f'P_is_{branch["P"]}')
            model.add(P==branch['P']).only_enforce_if(chosen)
            model.add(P!=branch['P']).only_enforce_if(chosen.Not())
            model.add(X>=branch['X_lower']).only_enforce_if(chosen)
            model.add(Y>=branch['Y_lower']).only_enforce_if(chosen)
    return model,dict(placements=placements,ts=ts,choices=choices,P=P,J=J,build_seconds=time.monotonic()-start)

def run(position,limit,stage,workers=8,probing=2,boundary_cuts=False):
    tag=position['id']; model,meta=build(position,boundary_cuts)
    error=model.validate()
    if error: raise RuntimeError(error)
    solver=cp_model.CpSolver(); solver.parameters.max_time_in_seconds=limit
    solver.parameters.num_search_workers=workers
    solver.parameters.random_seed=20260922
    solver.parameters.cp_model_probing_level=probing
    solver.parameters.log_search_progress=True
    solver.parameters.log_to_stdout=False
    path=ROOT/'logs'/f'{tag}_{stage}.log'
    with path.open('w') as log:
        solver.log_callback=lambda message: log.write(message+'\n')
        start=time.monotonic(); status=solver.solve(model); elapsed=time.monotonic()-start
    name=solver.status_name(status)
    if status==cp_model.MODEL_INVALID: raise RuntimeError(solver.response_stats())
    result=dict(id=tag,rect=position['rect'],allowed_P=position['allowed_P'],stage=stage,time_limit=limit,workers=workers,probing=probing,boundary_cuts=boundary_cuts,
                solver_status=name,status='FEASIBLE' if status in (cp_model.OPTIMAL,cp_model.FEASIBLE) else name,
                solve_seconds=elapsed,solver_wall_seconds=solver.wall_time,build_seconds=meta['build_seconds'],
                branches=solver.num_branches,conflicts=solver.num_conflicts,response_stats=solver.response_stats(),
                model_stats=model.model_stats(),log_path=str(path))
    if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
        chosen=[dict(kind=k,rect=rr,axis=ax) for k,rr,ax,v in meta['placements'] if solver.value(v)]
        # Assign all nine prescribed names to geometrically exchangeable placements.
        names={'small':['粉碎机']*68+['精炼炉']*51+['配件机']*6+['塑形机']*6,
               'medium':['种植机']*32+['采种机']*16,'large':['研磨机']*32+['封装机']*3+['灌装机']*3}
        for p in chosen:
            if p['kind'] in names: p['machine_type']=names[p['kind']].pop()
        result['solution']=dict(placements=chosen,transport=[pt for pt,v in meta['ts'].items() if solver.value(v)],
                                warehouse_pattern=next(i for i,v in meta['choices'].items() if solver.value(v)),
                                P=solver.value(meta['P']),J=solver.value(meta['J']))
    (ROOT/'results'/f'{tag}_{stage}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k not in ('solution','response_stats','model_stats')},ensure_ascii=False),flush=True)
    return result

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--stage',default='short'); ap.add_argument('--seconds',type=float,default=5)
    ap.add_argument('--workers',type=int,default=8); ap.add_argument('--only'); ap.add_argument('--unknown-only',action='store_true')
    ap.add_argument('--probing',type=int,default=2)
    ap.add_argument('--boundary-cuts',action='store_true')
    args=ap.parse_args(); assert 1<=args.workers<=12
    positions=json.loads((ROOT/'positions.json').read_text())['candidates']
    for position in positions:
        if args.only and position['id'] not in args.only.split(','): continue
        if (ROOT/'results'/f"{position['id']}_{args.stage}.json").exists(): continue
        if args.unknown_only:
            earlier=[json.loads(p.read_text()) for p in (ROOT/'results').glob(position['id']+'_*.json')]
            if any(p['status']!='UNKNOWN' for p in earlier): continue
        run(position,args.seconds,args.stage,args.workers,args.probing,args.boundary_cuts)
if __name__=='__main__': main()
