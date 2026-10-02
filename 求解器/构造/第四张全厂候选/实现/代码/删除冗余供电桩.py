#!/usr/bin/env python3
"""从既有桩位选覆盖全部机器的最小子集，不移动机器或改动进路。"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
os.sched_setaffinity(0,{6})
import json,sys
from pathlib import Path
from ortools.sat.python import cp_model
B=Path(__file__).resolve().parents[1];d=json.loads(Path(sys.argv[1]).read_text());poles=[u for u in d['units'] if u['type']==5];machines=[u for u in d['units'] if u['type']<=2]
m=cp_model.CpModel();keep={p['id']:m.NewBoolVar(p['id']) for p in poles}
for u in machines:
    cover=[keep[p['id']] for p in poles if u['x']+u['w']-1>=p['x']-5 and u['x']<=p['x']+6 and u['y']+u['h']-1>=p['y']-5 and u['y']<=p['y']+6]
    m.Add(sum(cover)>=1)
m.Minimize(sum(keep.values()));s=cp_model.CpSolver();s.parameters.num_workers=1;s.parameters.max_time_in_seconds=10;ss=s.Solve(m)
assert ss in [cp_model.OPTIMAL,cp_model.FEASIBLE]
deleted=[p for p in poles if not s.Value(keep[p['id']])];ids={p['id'] for p in deleted};d['units']=[u for u in d['units'] if u['id'] not in ids];d['power_distance']=0
pref=B/'实验/删冗余桩初值';pref.with_suffix('.json').write_text(json.dumps(d,ensure_ascii=False,indent=1));pref.with_suffix('.pos').write_text(''.join(f"{u['x']} {u['y']} {u['d']}\n" for u in d['units']))
rr=[p for p in d['paths'] if p['cells']]
with pref.with_suffix('.routes').open('w') as f:
    print(len(rr),file=f)
    for r in rr:
        print(r['r'],len(r['cells']),file=f)
        for x,y,*_ in r['cells']:print(x,y,file=f)
lines=(B/'实验/改规划5初值.txt').read_text().splitlines();n,ne,nr=map(int,lines[0].split());flags={r.split()[0]:r.split()[-1] for r in lines[1:1+n]}
with (B/'实验/改规划6初值.txt').open('w') as f:
    print(len(d['units']),ne,nr,file=f)
    for u in d['units']:print(u['id'],u['type'],u['x'],u['y'],u['d'],flags[u['id']],file=f)
    print('\n'.join(lines[1+n:]),file=f)
out=dict(status=s.StatusName(ss),before=len(poles),after=len(poles)-len(deleted),removed=deleted,scope='只在当前既有桩位中选子集；不证明全图最少桩数。')
(B/'证据/删除冗余供电桩.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False))
