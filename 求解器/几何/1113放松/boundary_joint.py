#!/usr/bin/env python3
"""Necessary projection of the full model to bodies touching X or Gamma.

Unlike independent 1-D X/Y optimization, selected bodies are shared, have their
real 2-D footprint and ports, and share a single core and a single pole budget.
Off-boundary machines/core/poles are existentially relaxed, never forbidden.
"""
import json,time
from collections import defaultdict
from ortools.sat.python import cp_model
from filter_positions import ROOT,cells,overlaps,port_sides,PATTERNS,pole_loss

def build(position):
    r=tuple(position['rect']); a,b,w,h=r; blocked=cells(r)
    xc=[(69,k) for k in range(1,69)]+[(k,69) for k in range(1,69)]+[(69,69)]
    ring=([(a-1,k) for k in range(b,b+h)] + ([(a+w,k) for k in range(b,b+h)] if a+w<70 else [])
          +[(k,b-1) for k in range(a,a+w)] + ([(k,b+h) for k in range(a,a+w)] if b+h<70 else []))
    target=(set(xc)|set(ring))-blocked
    model=cp_model.CpModel(); occ=defaultdict(list); groups=defaultdict(list); records=[]
    ports={}
    def T(pt):
        if pt not in ports: ports[pt]=model.new_bool_var(f't_{pt}')
        return ports[pt]
    def available(pt): return pt[0]>=1 and pt[1]>=1 and pt[0]<70 and pt[1]<70 and pt not in blocked
    patterns={i:model.new_bool_var(f'pat{i}') for i in position['patterns']}
    model.add_exactly_one(list(patterns.values()))
    for i,v in patterns.items():
        for pt in PATTERNS[i]['ports']: model.add_implication(v,T(tuple(pt)))
    poles=[]; js=[]; loss=[]
    for kind,W,H,axes in [('small',3,3,(0,1)),('medium',5,5,(0,1)),('large',6,4,(1,)),('large',4,6,(0,)),('core',9,9,(0,1)),('pole',2,2,(None,))]:
        for x in range(1,71-W):
            for y in range(1,71-H):
                rr=(x,y,W,H)
                if overlaps(rr,r): continue
                body=cells(rr)
                if not body&target: continue
                for axis in axes:
                    if kind=='core':
                        if x<2 or y<2 or (x<=3 and y<=3): continue
                        outs=[pt for edge in port_sides(rr,axis,True) for pt in edge]
                        if not all(available(pt) for pt in outs): continue
                        ins=[edge[k] for edge in port_sides(rr,1-axis) for k in range(1,8) if available(edge[k])]
                        if len(ins)<2: continue
                    elif kind!='pole':
                        sides=[[pt for pt in edge if available(pt)] for edge in port_sides(rr,axis)]
                        if not all(sides): continue
                    v=model.new_bool_var(f'{kind}_{x}_{y}_{axis}'); groups[kind].append(v)
                    records.append((kind,rr,axis,v))
                    for pt in body: occ[pt].append(v)
                    if kind=='core':
                        for pt in outs: model.add_implication(v,T(pt))
                        model.add(sum(T(pt) for pt in ins)>=2).only_enforce_if(v)
                    elif kind=='pole':
                        poles.append(v); loss.append(pole_loss(rr,r)*v)
                        if x in (1,68) or y in (1,68): js.append(v)
                    else:
                        for side in sides: model.add_bool_or([T(pt) for pt in side]).only_enforce_if(v)
    for pt,vv in occ.items(): model.add(sum(vv)+(T(pt) if pt in ports else 0)<=1)
    for kind,n in [('small',131),('medium',48),('large',38),('core',1)]: model.add(sum(groups[kind])<=n)
    P=model.new_int_var_from_domain(cp_model.Domain.from_values(position['allowed_P']),'total_P')
    J=model.new_int_var(0,6,'total_J')
    model.add(sum(poles)<=P); model.add(J>=sum(js)); model.add(J<=sum(js)+P-sum(poles))
    model.add(9*J<=23*P-217)
    model.add(sum(loss)+9*(J-sum(js))<=23*P-217)
    X=sum(1-sum(occ[pt]) for pt in xc[:-1] if pt not in blocked)
    if (69,69) not in blocked:
        X+=2*(1-sum(v for kind,rr,axis,v in records if kind=='pole' and (69,69) in cells(rr)))
    Y=sum(1-sum(occ[pt]) for pt in ring)
    model.add(16*P-2*J+X+Y<=187)
    # Audited 1-D lower bounds are valid additional cuts on these same cells.
    for branch in position['branches']:
        if not branch['keep']: continue
        chosen=model.new_bool_var(f'P_is_{branch["P"]}')
        model.add(P==branch['P']).only_enforce_if(chosen)
        model.add(P!=branch['P']).only_enforce_if(chosen.Not())
        model.add(X>=branch['X_lower']).only_enforce_if(chosen)
        model.add(Y>=branch['Y_lower']).only_enforce_if(chosen)
    return model,dict(records=records,P=P,J=J,X=X,Y=Y,patterns=patterns,ports=ports)

def main():
    positions=json.loads((ROOT/'positions.json').read_text())['candidates']
    for position in positions:
        path=ROOT/'results'/f"{position['id']}_boundary.json"
        if path.exists(): continue
        start=time.monotonic(); model,meta=build(position); buildtime=time.monotonic()-start
        assert not model.validate(),model.validate()
        solver=cp_model.CpSolver(); solver.parameters.max_time_in_seconds=30
        solver.parameters.num_search_workers=2; solver.parameters.random_seed=20260922
        solver.parameters.log_search_progress=True; solver.parameters.log_to_stdout=False
        lp=ROOT/'logs'/f"{position['id']}_boundary.log"
        with lp.open('w') as log:
            solver.log_callback=lambda msg:log.write(msg+'\n')
            start=time.monotonic(); status=solver.solve(model); elapsed=time.monotonic()-start
        out=dict(id=position['id'],rect=position['rect'],model='boundary_projection',stage='boundary',workers=2,time_limit=30,
                 status='FEASIBLE' if status in (cp_model.OPTIMAL,cp_model.FEASIBLE) else solver.status_name(status),
                 solver_status=solver.status_name(status),solve_seconds=elapsed,build_seconds=buildtime,
                 model_stats=model.model_stats(),response_stats=solver.response_stats(),log_path=str(lp))
        if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
            out['solution']=dict(P=solver.value(meta['P']),J=solver.value(meta['J']),X=solver.value(meta['X']),Y=solver.value(meta['Y']),
                placements=[dict(kind=k,rect=rr,axis=ax) for k,rr,ax,v in meta['records'] if solver.value(v)],
                warehouse_pattern=next(i for i,v in meta['patterns'].items() if solver.value(v)),
                transport=[pt for pt,v in meta['ports'].items() if solver.value(v)])
        path.write_text(json.dumps(out,ensure_ascii=False,indent=2))
        print(json.dumps({k:v for k,v in out.items() if k not in ('model_stats','response_stats','solution')},ensure_ascii=False),flush=True)
if __name__=='__main__':main()
