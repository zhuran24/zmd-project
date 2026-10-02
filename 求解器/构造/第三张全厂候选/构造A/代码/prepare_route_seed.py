#!/usr/bin/env python3
import os
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:4])
import json
from pathlib import Path
from ortools.sat.python import cp_model
BASE=Path(__file__).resolve().parents[1];r=json.loads((BASE/'实验/routing-sa1.json').read_text());valid=[]
for p in r['paths']:
    cells=p['cells'];turns=[];dirs=[]
    for a,b in zip(cells,cells[1:]):dirs.append((b[0]-a[0],b[1]-a[1]))
    for i in range(1,len(dirs)):
        if dirs[i]!=dirs[i-1]:turns.append(cells[i])
    if len(turns)>2 or (p['source'],p['target'])==('H6','F4'):continue
    if len(turns)==2:mode=0 if dirs[0][0] else 1;mid=turns[0][mode]
    elif len(turns)==1:mode=0;mid=turns[0][0]
    else:mode=0;mid=cells[0][0]
    # A horizontal straight route must set the middle coordinate to its start.
    if len(turns)==0 and cells[0][0]==cells[-1][0]:mid=cells[0][0]
    valid.append(dict(p,mode=mode,middle=mid,noncrossable=[cells[0],*turns,cells[-1]]))
m=cp_model.CpModel();bits=[m.new_bool_var('') for p in valid];conflicts=[]
for i,a in enumerate(valid):
    for j in range(i):
        b=valid[j];shared=set(map(tuple,a['cells']))&set(map(tuple,b['cells']))
        if shared&(set(map(tuple,a['noncrossable']))|set(map(tuple,b['noncrossable']))):m.add(bits[i]+bits[j]<=1);conflicts.append([a['id'],b['id']])
m.maximize(sum(bits));s=cp_model.CpSolver();s.parameters.num_workers=1;s.parameters.max_time_in_seconds=10;st=s.solve(m);assert st==cp_model.OPTIMAL
result=dict(placements=r['placements'],seed_paths=[p for p,b in zip(valid,bits) if s.value(b)],retained_count=int(s.objective_value),original_count=len(r['paths']),conflicts=conflicts,status='SEED_ONLY_NOT_FULL_LAYOUT')
(BASE/'实验/polyline-route-seed.json').write_text(json.dumps(result,ensure_ascii=False,indent=1)+'\n');print(result['retained_count'])
