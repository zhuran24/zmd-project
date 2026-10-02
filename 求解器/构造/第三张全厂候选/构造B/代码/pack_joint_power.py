#!/usr/bin/env python3
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,sys,time
from collections import Counter,defaultdict
from ortools.sat.python import cp_model
from pack_factory import BASE,C,cells,machine,edge
st0=time.time();z=json.loads((BASE/'证据/powered-fixed.json').read_text());l=z['layout'];l['power_poles']=[];rect=z['reserved_rectangle']
fixed={u['id'] for u in l['machines']};todo=[m['id'] for m in C['machines'] if m['id'] not in fixed];counts=Counter(machine(u,0,0,0)['kind'] for u in todo)
occ=set(q for u in l['machines']+l['warehouse_outlets']+l['transport']+[l['core'],rect] for q in cells(u));protected=[]
for u in l['machines']:
 s=u['id']
 if s.startswith('KB') or len(s)>2 and s[0] in 'SQ' and s[1]=='B':
  opts=[q for q in edge(u,(u['Din']+2)%4,True) if 0<=q[0]<70 and 0<=q[1]<70 and q not in occ]
  if opts:protected.append(opts[len(opts)//2])
occ.update(protected)
model=cp_model.CpModel();cover=defaultdict(list);poles=[];choices=[];bykind=defaultdict(list)
for x in range(1,69):
 for y in range(1,69):
  cc=[(x,y),(x+1,y),(x,y+1),(x+1,y+1)]
  if any(q in occ for q in cc):continue
  v=model.NewBoolVar('p');poles.append((x,y,v))
  for q in cc:cover[q].append(v)
def powerlist(u):return [v for x,y,v in poles if u['x0']<=x+6 and u['x1']>=x-5 and u['y0']<=y+6 and u['y1']>=y-5]
for u in l['machines']:model.Add(sum(powerlist(u))>=1)
for kind in ['小','大']:
 for di in [0,1]:
  w,h=(3,3) if kind=='小' else (4,6) if di==0 else (6,4)
  for x in range(1,71-w):
   for y in range(1,71-h):
    cc=[(a,b) for a in range(x,x+w) for b in range(y,y+h)]
    if any(q in occ for q in cc):continue
    u=dict(kind=kind,x0=x,y0=y,x1=x+w-1,y1=y+h-1,Din=di);pp=powerlist(u)
    if not pp:continue
    v=model.NewBoolVar('m');bykind[kind].append(v);choices.append((u,v));model.Add(sum(pp)>=v)
    for q in cc:cover[q].append(v)
for q,vs in cover.items():model.AddAtMostOne(vs)
for kind,n in counts.items():model.Add(sum(bykind[kind])==n)
model.Minimize(sum(v for x,y,v in poles));s=cp_model.CpSolver();s.parameters.num_workers=4;s.parameters.max_time_in_seconds=float(sys.argv[1]) if len(sys.argv)>1 else 180;s.parameters.random_seed=61
print('joint power',len(choices),'machine candidates',len(poles),'pole candidates','build',time.time()-st0,flush=True)
class CB(cp_model.CpSolverSolutionCallback):
 def on_solution_callback(self):
  ll={**l,'power_poles':[dict(id=f'POWER{k}',x0=x,y0=y,x1=x+1,y1=y+1,orientation=0) for k,(x,y,v) in enumerate(poles) if self.Value(v)]}
  out=dict(fixed=ll,reserved_rectangle=rect,moving=[u for u,v in choices if self.Value(v)],todo=todo,protected=protected,wall=self.WallTime(),pole_count=self.ObjectiveValue())
  (BASE/'证据/joint-powered.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print('INCUMBENT',self.WallTime(),self.ObjectiveValue(),flush=True)
st=s.Solve(model,CB());r=dict(status=s.StatusName(st),seconds=s.WallTime(),objective=s.ObjectiveValue(),bound=s.BestObjectiveBound(),machine_candidates=len(choices),pole_candidates=len(poles),workers=4)
(BASE/'证据/joint-powered-result.json').write_text(json.dumps(r,indent=2));print(r,flush=True)
