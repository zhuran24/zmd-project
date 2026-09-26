#!/usr/bin/env python3
"""CP-SAT finite placement relaxation. Sequential positions, <= 12 workers."""
import argparse, hashlib, json, time
from pathlib import Path
from collections import Counter,defaultdict
from ortools.sat.python import cp_model
from filter_positions import ROOT, COUNTS, PATTERNS, cells, overlaps, port_sides, pole_loss

def build(position,boundary_cuts=False,cut_mode="formal"):
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
                    if cut_mode == "formal" and ml+3*(axis==0)>(1 if y==61 else 2)*(x-1): continue
                    if cut_mode == "formal" and mb+3*(axis==1)>(1 if x==61 else 2)*(y-1): continue
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
    J=model.new_int_var(0,12,'J'); model.add(J==sum(edge_poles))
    if cut_mode == "formal":
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
    if cut_mode == "formal":
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
    return model,dict(placements=placements,ts=ts,choices=choices,P=P,J=J,X=X,Y=Y,build_seconds=time.monotonic()-start)
