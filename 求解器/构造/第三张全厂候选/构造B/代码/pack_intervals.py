#!/usr/bin/env python3
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import sys,json,time
from collections import Counter
from pathlib import Path
from ortools.sat.python import cp_model
from pack_factory import fixed,machine,cells,C,MC,BASE
mode=sys.argv[1] if len(sys.argv)>1 else 'loose';limit=float(sys.argv[2]) if len(sys.argv)>2 else 180
l=fixed()
if mode=='loose':
 def retain(u):
  s=u['id']
  return s.startswith('T') or s.startswith('KB') or len(s)>2 and s[0] in ['S','Q'] and s[1] in 'ABC'
 l['machines']=[u for u in l['machines'] if retain(u)]
 # Keep exactly warehouse -> T and T -> KB, and all 57 seed/plant routes.
 reject=set()
 for b in range(1,18):
  v=b>=10;base=16+6*(b-1) if not v else 22+6*(b-10)
  for x,y in [(9,1),(9,4),(14,1)]:reject.add((y+base,x) if v else (x,y+base))
 l['transport']=[t for t in l['transport'] if (t['x'],t['y']) not in reject]
reserve=dict(x0=18,y0=18,x1=23,y1=23)
(BASE/f'证据/{mode}-fixed.json').write_text(json.dumps(dict(layout=l,reserved_rectangle=reserve),ensure_ascii=False,indent=2))
fixedby={u['id']:u for u in l['machines']+l['warehouse_outlets']+[l['core']]}
todo=[m['id'] for m in C['machines'] if m['id'] not in fixedby]
model=cp_model.CpModel();ix=[];iy=[];rows={};costs=[]
for u in l['machines']+l['warehouse_outlets']+l['transport']+[l['core'],reserve]:
 cc=cells(u);xs=[c[0] for c in cc];ys=[c[1] for c in cc]
 ix.append(model.NewFixedSizeIntervalVar(2*min(xs),2*(max(xs)-min(xs)+1),''));iy.append(model.NewFixedSizeIntervalVar(2*min(ys),2*(max(ys)-min(ys)+1),''))
for uid in todo:
 x=model.NewIntVar(1,66,uid+'x');y=model.NewIntVar(1,66,uid+'y');d=model.NewIntVar(0,3,uid+'d');w=model.NewIntVar(3,6,'');h=model.NewIntVar(3,6,'');dx=model.NewBoolVar('');dy=model.NewBoolVar('')
 cases=[]
 for dd in range(4):
  u=machine(uid,0,0,dd);cases.append((dd,u['x1']+1,u['y1']+1,int(dd%2==0),int(dd%2==1)))
 model.AddAllowedAssignments([d,w,h,dx,dy],cases)
 # Only moving machines get the half-cell port envelope. This is a declared search restriction.
 ax=model.NewIntVar(1,138,'');ay=model.NewIntVar(1,138,'');ww=model.NewIntVar(6,14,'');hh=model.NewIntVar(6,14,'');ex=model.NewIntVar(1,140,'');ey=model.NewIntVar(1,140,'')
 model.Add(ax==2*x-dx);model.Add(ay==2*y-dy);model.Add(ww==2*w+2*dx);model.Add(hh==2*h+2*dy);model.Add(ex==ax+ww);model.Add(ey==ay+hh)
 ix.append(model.NewIntervalVar(ax,ww,ex,''));iy.append(model.NewIntervalVar(ay,hh,ey,''))
 cx=model.NewIntVar(0,140,'');cy=model.NewIntVar(0,140,'');model.Add(cx==2*x+w);model.Add(cy==2*y+h)
 rows[uid]=(x,y,d,w,h,cx,cy)
model.AddNoOverlap2D(ix,iy)
for f in C['feeds']:
 a,b=f['source'],f['target']
 if a not in rows and b not in rows:continue
 def ctr(s):
  if s in rows:return rows[s][-2:]
  u=fixedby[s];return(u['x0']+u['x1']+1,u['y0']+u['y1']+1)
 aa,bb=ctr(a),ctr(b);dx=model.NewIntVar(0,140,'');dy=model.NewIntVar(0,140,'');model.AddAbsEquality(dx,aa[0]-bb[0]);model.AddAbsEquality(dy,aa[1]-bb[1]);costs.extend([dx,dy])
model.Minimize(sum(costs));s=cp_model.CpSolver();s.parameters.num_workers=4;s.parameters.max_time_in_seconds=limit;s.parameters.random_seed=7
print('model',mode,len(rows),len(model.Proto().variables),len(model.Proto().constraints),flush=True)
class CB(cp_model.CpSolverSolutionCallback):
 def on_solution_callback(self):
  ll={**l,'machines':l['machines']+[machine(uid,self.Value(v[0]),self.Value(v[1]),self.Value(v[2])) for uid,v in rows.items()]}
  out=dict(layout=ll,reserved_rectangle=reserve,mode=mode,objective=self.ObjectiveValue(),wall=self.WallTime())
  (BASE/f'证据/{mode}-packed.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
  print('INCUMBENT',self.WallTime(),self.ObjectiveValue(),flush=True)
st=s.Solve(model,CB());r=dict(status=s.StatusName(st),wall=s.WallTime(),objective=s.ObjectiveValue(),bound=s.BestObjectiveBound(),mode=mode,workers=4)
(BASE/f'证据/{mode}-packing-result.json').write_text(json.dumps(r,indent=2));print(r,flush=True)
