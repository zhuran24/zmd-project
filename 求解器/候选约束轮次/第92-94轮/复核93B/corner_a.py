"""Independent set-of-cells / CP-SAT corner relaxation, one worker.
Outputs upper bounds and selected local witnesses, NOT playable layouts.
"""
import json, os
from pathlib import Path
from ortools.sat.python import cp_model
OUT=Path(__file__).resolve().parent

def ports(gap):
    blocks=[];x=0
    while x<70:
        if x==gap:x+=1;continue
        blocks.append(tuple(range(x,x+3)));x+=3
    assert len(blocks)==23 and x==70
    return [b[1] for b in blocks]

def solve(gl,gb,mode,rectangle=None):
    left,bottom=ports(gl),ports(gb)
    sources={(1,y) for y in left}|{(x,1) for x in bottom}
    assert len(sources)==46
    fixed=set();side=None;gap=0
    if mode:
        side='L' if 0<gl<69 else 'B';gap=gl if side=='L' else gb
        x,y=(1,gap-1) if side=='L' else (gap-1,1)
        fixed={(x+i,y+j) for i in range(3) for j in range(3)}
    candidates=[]
    forbidden=set(sources)|fixed
    if rectangle:
        rx,ry,rw,rh=rectangle
        forbidden|={(rx+i,ry+j) for i in range(rw) for j in range(rh)}
        if any(rx<=x<rx+rw and ry<=y<ry+rh for x,y in fixed):return None
    for s,(x,y) in enumerate([(1,y) for y in left]+[(x,1) for x in bottom]):
        for off in range(3):
            ax,ay=(2,y-off) if s<23 else (x-off,2)
            cells={(ax+i,ay+j) for i in range(3) for j in range(3)}
            if min(ax,ay)<1 or ax+2>69 or ay+2>69 or cells & forbidden:continue
            candidates.append((s,ax,ay,cells))
    model=cp_model.CpModel();z=[model.new_bool_var(f'm{i}') for i in range(len(candidates))]
    cellmap={};by_source={}
    for i,(s,x,y,cells) in enumerate(candidates):
        by_source.setdefault(s,[]).append(z[i])
        for cell in cells:cellmap.setdefault(cell,[]).append(z[i])
    for vs in cellmap.values():model.add(sum(vs)<=1)
    for vs in by_source.values():model.add(sum(vs)<=1)
    # With g=3, a full row/column of 23 mineral consumers encloses 24 full sources.
    if gl==3:model.add(sum(z[i] for i,c in enumerate(candidates) if c[0]>=23)<=22)
    if gb==3:model.add(sum(z[i] for i,c in enumerate(candidates) if c[0]<23)<=22)
    tangent=0 if not mode else (1 if mode==2 and gap==3 else 2)
    weight=0
    if mode==2:
        weight=model.new_bool_var('w')
        possibilities=[]
        for end in (-2,2):
            if gap==3 and end==-2:continue
            for coord in (2,3):
                cell=(coord,gap+end) if side=='L' else (gap+end,coord)
                if cell in forbidden:continue
                b=model.new_bool_var(f'free_{cell[0]}_{cell[1]}')
                for v in cellmap.get(cell,[]):model.add(v+b<=1)
                possibilities.append(b)
        model.add(weight<=sum(possibilities))
    objective=46+tangent+sum(z)+weight
    model.maximize(objective)
    solver=cp_model.CpSolver();solver.parameters.num_search_workers=1;solver.parameters.max_time_in_seconds=10
    status=solver.solve(model)
    assert status==cp_model.OPTIMAL,(gl,gb,mode,solver.status_name(status))
    return {'left_gap':gl,'bottom_gap':gb,'mode':mode,'options':len(z),'bound':int(solver.objective_value),'best_bound':solver.best_objective_bound,'status':solver.status_name(status),
            'selected':[[s,x,y] for i,(s,x,y,_) in enumerate(candidates) if solver.value(z[i])],
            'weight':0 if mode!=2 else solver.value(weight),'tangent_upper':tangent}

if __name__=='__main__':
    records=[]
    for gl in range(0,70,3):
        for gb in range(0,70,3):
            if gl and gb:continue
            modes=(0,1,2) if 0<max(gl,gb)<69 else (0,)
            records.extend(solve(gl,gb,mode) for mode in modes)
    assert len(records)==135
    assert max(r['bound'] for r in records)==91
    (OUT/'corner_a.json').write_text(json.dumps({'method':'CP-SAT cell disjointness with independently generated sources','cases':records},ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'cases':len(records),'max_N_plus_w':max(r['bound'] for r in records),'all_OPTIMAL':True}))
