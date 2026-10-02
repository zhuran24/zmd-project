#!/usr/bin/env python3
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,sys,time
from collections import defaultdict,Counter
from pathlib import Path
from ortools.sat.python import cp_model
from pack_factory import machine,cells,C,MC,BASE,edge
source=Path(sys.argv[3]) if len(sys.argv)>3 else BASE/'证据/loose-fixed.json';d=json.loads(source.read_text());l=d['layout'];reserve=d['reserved_rectangle']
margin=int(sys.argv[1]) if len(sys.argv)>1 else 1;limit=float(sys.argv[2]) if len(sys.argv)>2 else 120
fixedby={u['id']:u for u in l['machines']};todo=[m['id'] for m in C['machines'] if m['id'] not in fixedby]
counts=Counter(machine(u,0,0,0)['kind'] for u in todo)
occ=set(q for u in l['machines']+l['warehouse_outlets']+[l['core'],reserve]+l['transport']+l['power_poles'] for q in cells(u))
# Reserve one feasible external output cell on each fixed KB or outward plant.
protected=[]
for u in l['machines']:
 uid=u['id']
 if not(uid.startswith('KB') or len(uid)>2 and uid[0] in ['Q','S'] and uid[1]=='B'):continue
 options=[q for q in edge(u,(u['Din']+2)%4,True) if 0<=q[0]<70 and 0<=q[1]<70 and q not in occ]
 if options:protected.append(options[len(options)//2])
occ.update(protected)
blocked={(2*x+i,2*y+j) for x,y in occ for i in [0,1] for j in [0,1]}
model=cp_model.CpModel();cover=defaultdict(list);select=defaultdict(list);options=[]
for k in ['小','大']:
 for ori in [0,1]:
  w,h=(3,3) if k=='小' else (4,6) if ori==0 else (6,4)
  for x in range(1,71-w):
   for y in range(1,71-h):
    ax,ay=2*x-(margin if ori==0 else 0),2*y-(margin if ori==1 else 0)
    ww,hh=2*w+(2*margin if ori==0 else 0),2*h+(2*margin if ori==1 else 0)
    if ax<0 or ay<0 or ax+ww>140 or ay+hh>140:continue
    cc=[(a,b) for a in range(ax,ax+ww) for b in range(ay,ay+hh)]
    if any(q in blocked for q in cc):continue
    if l['power_poles'] and not any(x<=p['x0']+6 and x+w-1>=p['x0']-5 and y<=p['y0']+6 and y+h-1>=p['y0']-5 for p in l['power_poles']):continue
    v=model.NewBoolVar('');select[k].append(v)
    for q in cc:cover[q].append(v)
    options.append((dict(kind=k,x0=x,y0=y,x1=x+w-1,y1=y+h-1,Din=ori),v))
for k,n in counts.items():model.Add(sum(select[k])==n)
for q,vs in cover.items():model.AddAtMostOne(vs)
# A deterministic small compactness objective also breaks anonymous packing symmetries.
model.Minimize(sum((u['x0']+u['y0'])*v for u,v in options))
s=cp_model.CpSolver();s.parameters.num_workers=4;s.parameters.max_time_in_seconds=limit;s.parameters.random_seed=11
print('anonymous',margin,'counts',dict(counts),'variables',len(options),'cover',len(cover),flush=True)
class CB(cp_model.CpSolverSolutionCallback):
 def on_solution_callback(self):
  z=dict(fixed=l,reserved_rectangle=reserve,protected=protected,moving=[u for u,v in options if self.Value(v)],todo=todo,margin=margin,objective=self.ObjectiveValue(),wall=self.WallTime())
  (BASE/f'证据/{source.stem}-anonymous-m{margin}.json').write_text(json.dumps(z,ensure_ascii=False,indent=2))
  print('INCUMBENT',self.WallTime(),self.ObjectiveValue(),flush=True)
st=s.Solve(model,CB());r=dict(status=s.StatusName(st),wall=s.WallTime(),objective=s.ObjectiveValue(),bound=s.BestObjectiveBound(),margin=margin,workers=4,variables=len(options))
(BASE/f'证据/{source.stem}-anonymous-m{margin}-result.json').write_text(json.dumps(r,indent=2));print(r,flush=True)
