#!/usr/bin/env python3
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,sys,time,copy
from pathlib import Path
from collections import Counter,defaultdict
from ortools.sat.python import cp_model
from scipy.optimize import linear_sum_assignment
BASE=Path(__file__).resolve().parents[1];d=json.loads(Path(sys.argv[1]).read_text());out=Path(sys.argv[2]);limit=float(sys.argv[3]);workers=int(sys.argv[4]);us=d['units'];con=json.loads((BASE/'逻辑接法.json').read_text());ni=Counter(f['target'] for f in con['feeds']);no=Counter(f['source'] for f in con['feeds']);small=[u for u in us if u['type']==0];fixed_units=[u for u in us if u['type']!=0];poles=[u for u in us if u['type']==5]
fixed={(x,y) for u in fixed_units for x in range(u['x'],u['x']+u['w']) for y in range(u['y'],u['y']+u['h'])}|{(x,y) for x in range(64,70) for y in range(64,70)}
def edge(x,y,w,h,di,offsets=None):
 return [(x+w if di==0 else x-1 if di==2 else x+o,y+h if di==1 else y-1 if di==3 else y+o) for o in (offsets if offsets is not None else range(w if di%2 else h))]
def openpts(ps):return [p for p in ps if 0<=p[0]<70 and 0<=p[1]<70 and p not in fixed]
groups=defaultdict(list)
for u in small:groups[ni[u['id']],no[u['id']]].append(u)
m=cp_model.CpModel();cover=defaultdict(list);opts=[];bygroup=defaultdict(list);poses=[]
old={(u['x'],u['y'],u['d'],ni[u['id']],no[u['id']]) for u in small}
for y in range(0,68):
 for x in range(0,68):
  body={(a,b) for a in range(x,x+3) for b in range(y,y+3)}
  if body&fixed:continue
  if not any(x<=p['x']+6 and x+2>=p['x']-5 and y<=p['y']+6 and y+2>=p['y']-5 for p in poles):continue
  for di in range(4):
   a=openpts(edge(x,y,3,3,di));b=openpts(edge(x,y,3,3,(di+2)%4))
   for (inc,outc),members in groups.items():
    if len(a)<inc or len(b)<outc:continue
    v=m.NewBoolVar(f'p{len(opts)}');opts.append(v);bygroup[inc,outc].append(v);poses.append((x,y,di,inc,outc,a,b,body))
    for c in body:cover[c].append(v)
    m.AddHint(v,int((x,y,di,inc,outc) in old))
occ={}
for c,vs in cover.items():
 z=m.NewBoolVar(f'o{c[0]}_{c[1]}');occ[c]=z;m.Add(sum(vs)==z)
for g,members in groups.items():m.Add(sum(bygroup[g])==len(members))
for v,pose in zip(opts,poses):
 x,y,di,inc,outc,a,b,body=pose
 m.Add(sum(occ.get(c,0) for c in a)<=len(a)-inc).OnlyEnforceIf(v);m.Add(sum(occ.get(c,0) for c in b)<=len(b)-outc).OnlyEnforceIf(v)
for u in fixed_units:
 if u['type']==5:continue
 side=u['d'];sides=[]
 if u['type'] in (1,2):sides=[(False,[side],None),(True,[(side+2)%4],None)]
 elif u['type']==3:sides=[(False,[side,(side+2)%4],list(range(1,8))),(True,[(side+1)%4,(side+3)%4],[1,4,7])]
 else:sides=[(True,[side],[1])]
 for isout,ss,offsets in sides:
  need=(no if isout else ni)[u['id']];a=openpts([p for z in ss for p in edge(u['x'],u['y'],u['w'],u['h'],z,offsets)])
  m.Add(sum(occ.get(c,0) for c in a)<=len(a)-need)
# Keep as much of the existing arrangement as possible; names are assigned only after geometry is feasible.
cost=[]
for v,p in zip(opts,poses):
 x,y,di,a,b,*_=p
 cost.append((0 if (x,y,di,a,b) in old else 100)*v)
m.Minimize(sum(cost))
class Save(cp_model.CpSolverSolutionCallback):
 def __init__(self):super().__init__();self.n=0
 def on_solution_callback(self):
  self.n+=1;r=copy.deepcopy(d);chosen=defaultdict(list)
  for v,p in zip(opts,poses):
   if self.Value(v):chosen[p[3],p[4]].append(p)
  coords={};changed=set()
  for g,members in groups.items():
   pp=chosen[g];assert len(pp)==len(members)
   cc=[[abs(u['x']-p[0])+abs(u['y']-p[1])+(u['d']!=p[2]) for p in pp] for u in members];aa,bb=linear_sum_assignment(cc)
   for i,j in zip(aa,bb):coords[members[i]['id']]=pp[j][:3]
  for u in r['units']:
   if u['id'] in coords:
    z=coords[u['id']]
    if (u['x'],u['y'],u['d'])!=z:changed.add(u['id'])
    u['x'],u['y'],u['d']=z
  body={(x,y) for u in r['units'] for x in range(u['x'],u['x']+u['w']) for y in range(u['y'],u['y']+u['h'])}
  for p in r['paths']:
   f=con['feeds'][p['r']]
   if f['source'] in changed or f['target'] in changed or any((z[0],z[1]) in body for z in p['cells']):p['cells']=[]
  r['overlap']=0;r['power_distance']=0;r['small_pack']={'objective':self.ObjectiveValue(),'solution':self.n,'changed':sorted(changed),'groups':{str(g):len(v) for g,v in groups.items()}}
  out.with_suffix('.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));(out.parent/(out.name+f'-solution-{self.n}.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2));print('solution',self.n,'changed',len(changed),'objective',self.ObjectiveValue(),flush=True)
solver=cp_model.CpSolver();solver.parameters.num_search_workers=workers;solver.parameters.max_time_in_seconds=limit;solver.parameters.random_seed=1087;solver.parameters.log_search_progress=True;solver.parameters.stop_after_first_solution=True;cb=Save();meta={'poses':len(poses),'occupancy_cells':len(occ),'workers':workers,'seconds':limit,'groups':{str(g):len(v) for g,v in groups.items()},'source':sys.argv[1]};out.with_suffix('.input.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2));print(meta,flush=True);t=time.monotonic();st=solver.Solve(m,cb);result={**meta,'status':solver.StatusName(st),'wall_seconds':time.monotonic()-t,'solutions':cb.n};out.with_suffix('.result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(result,flush=True)
