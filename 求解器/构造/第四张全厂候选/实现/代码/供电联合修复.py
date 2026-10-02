#!/usr/bin/env python3
"""固定机身，联合选择供电桩和保留的进路；优先不损失任何已接进路。"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,{6})
import sys,json,hashlib
from pathlib import Path
from collections import defaultdict
from ortools.sat.python import cp_model
B=Path(__file__).resolve().parents[1]
inp=Path(sys.argv[1]);dest=Path(sys.argv[2]);raw=json.loads(inp.read_text());m=cp_model.CpModel()
units=[u for u in raw['units'] if u['type']!=5];machines=[u for u in units if u['type']<=2]
body={(x,y) for u in units for x in range(u['x'],u['x']+u['w']) for y in range(u['y'],u['y']+u['h'])}
body|={(x,y) for x in range(63,69) for y in range(14,20)}
roads={r['r']:r for r in raw['paths'] if r['cells']};kept={k:m.NewBoolVar(f'keep{k}') for k in roads}
use=defaultdict(set)
for k,r in roads.items():
    for q in r['cells']:use[tuple(q[:2])].add(k)
at=defaultdict(list);cover=defaultdict(list);places=[]
for x in range(69):
    for y in range(69):
        cs={(x,y),(x+1,y),(x,y+1),(x+1,y+1)}
        if cs&body:continue
        covered=[u['id'] for u in machines if u['x']+u['w']-1>=x-5 and u['x']<=x+6 and u['y']+u['h']-1>=y-5 and u['y']<=y+6]
        if not covered:continue
        v=m.NewBoolVar(f'p{x}_{y}');places.append((x,y,v))
        for q in cs:at[q].append(v)
        for uid in covered:cover[uid].append(v)
        for k in set().union(*(use[q] for q in cs)):m.Add(v+kept[k]<=1)
for vv in at.values():m.AddAtMostOne(vv)
impossible=[]
for u in machines:
    if not cover[u['id']]:impossible.append(u['id'])
    m.Add(sum(cover[u['id']])>=1)
if '--keep-all' in sys.argv:
    for v in kept.values():m.Add(v==1)
m.Minimize(10000*sum(1-v for v in kept.values())+sum(v for x,y,v in places))
solver=cp_model.CpSolver();solver.parameters.num_workers=1;solver.parameters.max_time_in_seconds=20
ss=solver.Solve(m);result=dict(status=solver.StatusName(ss),wall=solver.WallTime(),no_possible_pole=impossible,input_sha256=hashlib.sha256(inp.read_bytes()).hexdigest(),scope='固定机身和空矩形；供电桩可重排，必要时删除冲突进路。')
if ss in [cp_model.FEASIBLE,cp_model.OPTIMAL]:
    poles=[dict(id=f'POWER{k}',type=5,x=x,y=y,d=0,w=2,h=2) for k,(x,y,v) in enumerate((q for q in places if solver.Value(q[2])))]
    paths=[r for k,r in roads.items() if solver.Value(kept[k])]
    d=dict(raw,units=units+poles,paths=paths,power_distance=0,overlap=0)
    dest.write_text(json.dumps(d,ensure_ascii=False,indent=1));result.update(poles=len(poles),retained_routes=len(paths),removed_routes=[k for k in roads if not solver.Value(kept[k])])
dest.with_name(dest.stem+'-供电结果.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False))
