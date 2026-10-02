#!/usr/bin/env python3
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import json,sys,time
from pathlib import Path
from ortools.sat.python import cp_model
p=Path(sys.argv[1]);out=Path(sys.argv[2]);radius=int(sys.argv[3]) if len(sys.argv)>3 else 3;raw=json.loads(p.read_text());m=cp_model.CpModel();xs=[];ys=[];ix=[];iy=[];cost=[]
for k,u in enumerate(raw['units']):
 movable=u['type']<4
 loX=max(1,u['x']-radius) if movable else u['x'];hiX=min(70-u['w'],u['x']+radius) if movable else u['x']
 loY=max(1,u['y']-radius) if movable else u['y'];hiY=min(70-u['h'],u['y']+radius) if movable else u['y']
 if movable and u['type']<3:
  if u['d']%2:loY=max(loY,2);hiY=min(hiY,69-u['h'])
  else:loX=max(loX,2);hiX=min(hiX,69-u['w'])
 if loX>hiX or loY>hiY:raise ValueError((u['id'],'empty domain'))
 x=m.NewIntVar(loX,hiX,f'x{k}');y=m.NewIntVar(loY,hiY,f'y{k}');xs.append(x);ys.append(y)
 ix.append(m.NewFixedSizeIntervalVar(x,u['w'],f'ix{k}'));iy.append(m.NewFixedSizeIntervalVar(y,u['h'],f'iy{k}'))
 a=m.NewIntVar(0,140,f'cost{k}');b=m.NewIntVar(0,140,f'costy{k}');m.AddAbsEquality(a,x-u['x']);m.AddAbsEquality(b,y-u['y']);cost += [a,b]
 m.AddHint(x,max(loX,min(hiX,u['x'])));m.AddHint(y,max(loY,min(hiY,u['y'])))
ix.append(m.NewFixedSizeIntervalVar(64,6,'emptyx'));iy.append(m.NewFixedSizeIntervalVar(64,6,'emptyy'));m.AddNoOverlap2D(ix,iy);m.Minimize(sum(cost))
class Save(cp_model.CpSolverSolutionCallback):
 def __init__(self):super().__init__();self.n=0
 def on_solution_callback(self):
  self.n+=1;d=json.loads(json.dumps(raw));d['paths']=[];d['overlap']=0;d['repair']={'source':str(p),'radius':radius,'objective':self.ObjectiveValue(),'solution':self.n}
  for k,u in enumerate(d['units']):u['x']=self.Value(xs[k]);u['y']=self.Value(ys[k])
  out.with_suffix('.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));out.with_suffix('.pos').write_text(''.join(f'{u["x"]} {u["y"]} {u["d"]}\n' for u in d['units']))
  print('incumbent',self.n,self.ObjectiveValue(),flush=True)
s=cp_model.CpSolver();s.parameters.num_search_workers=1;s.parameters.max_time_in_seconds=45;s.parameters.random_seed=7;s.parameters.log_search_progress=False;t=time.monotonic();cb=Save();st=s.Solve(m,cb)
r={'status':s.StatusName(st),'wall_seconds':time.monotonic()-t,'solutions':cb.n,'radius':radius,'source':str(p),'objective':s.ObjectiveValue() if cb.n else None,'model_proto_bytes':m.Proto().ByteSize() if hasattr(m.Proto(),'ByteSize') else None}
out.with_suffix('.result.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False))
