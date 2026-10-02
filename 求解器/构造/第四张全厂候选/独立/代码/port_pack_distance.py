#!/usr/bin/env python3
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,sys,time,copy
from pathlib import Path
from collections import Counter
from ortools.sat.python import cp_model
BASE=Path(__file__).resolve().parents[1]
raw=json.loads(Path(sys.argv[1]).read_text());out=Path(sys.argv[2]);radius=int(sys.argv[3]);limit=float(sys.argv[4]);workers=int(sys.argv[5]) if len(sys.argv)>5 else 2
units=raw['units'];contract=json.loads((BASE/'逻辑接法.json').read_text());ni=Counter(f['target'] for f in contract['feeds']);no=Counter(f['source'] for f in contract['feeds']);degree=Counter()
for p in raw['paths']:
 if p['cells']:
  f=contract['feeds'][p['r']];degree[f['source']]+=1;degree[f['target']]+=1
m=cp_model.CpModel();xs=[];ys=[];bounds=[];ix=[];iy=[];cost=[];flips=[];poles=[u for u in units if u['type']==5];oldocc={}
for k,u in enumerate(units):
 for x in range(u['x'],u['x']+u['w']):
  for y in range(u['y'],u['y']+u['h']):oldocc[x,y]=k
for k,u in enumerate(units):
 movable=u['type']<4
 lx=max(1,u['x']-radius) if movable else u['x'];hx=min(70-u['w'],u['x']+radius) if movable else u['x'];ly=max(1,u['y']-radius) if movable else u['y'];hy=min(70-u['h'],u['y']+radius) if movable else u['y']
 flip=m.NewBoolVar(f'flip{k}') if u['type']<3 else None;flips.append(flip)
 if flip is not None:cost.append(3*(1+degree[u['id']])*flip);m.AddHint(flip,0)
 x=m.NewIntVar(lx,hx,f'x{k}');y=m.NewIntVar(ly,hy,f'y{k}');xs.append(x);ys.append(y);bounds.append((lx,hx,ly,hy));ix.append(m.NewFixedSizeIntervalVar(x,u['w'],f'ix{k}'));iy.append(m.NewFixedSizeIntervalVar(y,u['h'],f'iy{k}'))
 if movable:
  ch=m.NewBoolVar(f'move{k}');m.Add(x==u['x']).OnlyEnforceIf(ch.Not());m.Add(y==u['y']).OnlyEnforceIf(ch.Not());dx=m.NewIntVar(0,70,f'dx{k}');dy=m.NewIntVar(0,70,f'dy{k}');m.AddAbsEquality(dx,x-u['x']);m.AddAbsEquality(dy,y-u['y']);cost.extend([10*(1+degree[u['id']])*ch,dx,dy]);m.AddHint(ch,0)
  if u['type']<3:
   cvs=[]
   for pi,p in enumerate(poles):
    if lx>p['x']+6 or hx+u['w']-1<p['x']-5 or ly>p['y']+6 or hy+u['h']-1<p['y']-5:continue
    c=m.NewBoolVar(f'cov{k}_{pi}');cvs.append(c);m.Add(x<=p['x']+6).OnlyEnforceIf(c);m.Add(x+u['w']-1>=p['x']-5).OnlyEnforceIf(c);m.Add(y<=p['y']+6).OnlyEnforceIf(c);m.Add(y+u['h']-1>=p['y']-5).OnlyEnforceIf(c)
   m.AddBoolOr(cvs)
 m.AddHint(x,u['x']);m.AddHint(y,u['y'])
ix.append(m.NewFixedSizeIntervalVar(64,6,'emptyx'));iy.append(m.NewFixedSizeIntervalVar(64,6,'emptyy'));m.AddNoOverlap2D(ix,iy)
# Each selected port's external grid cell must be empty of every body and the reserved rectangle.
obstacles=[(xs[k],ys[k],u['w'],u['h'],bounds[k]) for k,u in enumerate(units)]+[(64,64,6,6,(64,64,64,64))]
port_count=0;disjunctions=0;slacks=[];hint_free={}
for k,u in enumerate(units):
 if u['type']==5:continue
 sides=[]
 if u['type']<3:sides=[(u['d'],False,list(range(u['w'] if u['d']%2 else u['h']))),((u['d']+2)%4,True,list(range(u['w'] if u['d']%2 else u['h'])))]
 elif u['type']==3:sides=[(s,s%2!=u['d']%2,[1,4,7] if s%2!=u['d']%2 else list(range(1,8))) for s in range(4)]
 elif u['type']==4:sides=[(u['d'],True,[1])]
 groups={False:[],True:[]};lx,hx,ly,hy=bounds[k]
 for side,isout,offsets in sides:
  for off in offsets:
   dx=u['w'] if side==0 else -1 if side==2 else off;dy=u['h'] if side==1 else -1 if side==3 else off
   px=xs[k]+dx;py=ys[k]+dy;plx,phx,ply,phy=lx+dx,hx+dx,ly+dy,hy+dy
   clear=m.NewBoolVar(f'port{k}_{side}_{off}');groups[isout].append(clear);port_count+=1
   m.Add(px>=0).OnlyEnforceIf(clear);m.Add(px<=69).OnlyEnforceIf(clear);m.Add(py>=0).OnlyEnforceIf(clear);m.Add(py<=69).OnlyEnforceIf(clear)
   old=(u['x']+dx,u['y']+dy);oldfree=int(0<=old[0]<70 and 0<=old[1]<70 and old not in oldocc and not(old[0]>=64 and old[1]>=64));m.AddHint(clear,oldfree);hint_free[clear.Index()]=oldfree
   for j,(ox,oy,w,h,bb) in enumerate(obstacles):
    if j==k:continue
    ax,bx,ay,by=bb
    if phx<ax or plx>bx+w-1 or phy<ay or ply>by+h-1:continue
    choices=[]
    conditions=[(plx<=bx-1,px<=ox-1),(phx>=ax+w,px>=ox+w),(ply<=by-1,py<=oy-1),(phy>=ay+h,py>=oy+h)]
    for s,(possible,condition) in enumerate(conditions):
     if possible:
      b=m.NewBoolVar(f'sep{k}_{side}_{off}_{j}_{s}');m.Add(condition).OnlyEnforceIf(b);choices.append(b)
    m.AddBoolOr(choices+[clear.Not()]);disjunctions+=1
 for isout,ports in groups.items():
  need=(no if isout else ni)[u['id']]
  if need:
   slack=m.NewIntVar(0,need,f'slack{k}_{isout}');slacks.append(slack);
   if flips[k] is None:m.Add(sum(ports)+slack>=need)
   else:
    m.Add(sum(ports)+slack>=need).OnlyEnforceIf(flips[k].Not());m.Add(sum(groups[not isout])+slack>=need).OnlyEnforceIf(flips[k])
   cost.append(10000*slack);m.AddHint(slack,max(0,need-sum(hint_free[p.Index()] for p in ports)))

# Exact geometric lower bound, relaxing obstacles and distinct-port assignment.
def descriptors(k,out,flip):
 u=units[k];spec=[]
 if u['type']==4:spec=[(u['d'],1,1)]
 elif u['type']==3:
  if out:spec=[(side,o,o) for side in [(u['d']+1)%4,(u['d']+3)%4] for o in [1,4,7]]
  else:spec=[(side,1,7) for side in [u['d'],(u['d']+2)%4]]
 else:
  side=(u['d']+2*flip+(2 if out else 0))%4;spec=[(side,0,(u['w'] if side%2 else u['h'])-1)]
 ans=[]
 for side,a,b in spec:
  if side==0:ans.append((xs[k]+u['w'],xs[k]+u['w'],ys[k]+a,ys[k]+b))
  elif side==2:ans.append((xs[k]-1,xs[k]-1,ys[k]+a,ys[k]+b))
  elif side==1:ans.append((xs[k]+a,xs[k]+b,ys[k]+u['h'],ys[k]+u['h']))
  else:ans.append((xs[k]+a,xs[k]+b,ys[k]-1,ys[k]-1))
 return ans
index={u['id']:k for k,u in enumerate(units)};lengths=[]
for ri,f in enumerate(contract['feeds']):
 a=index[f['source']];b=index[f['target']];length=m.NewIntVar(1,300,f'length{ri}');lengths.append(length)
 for fa in ([0,1] if flips[a] is not None else [0]):
  for fb in ([0,1] if flips[b] is not None else [0]):
   options=[]
   for ai,aa in enumerate(descriptors(a,True,fa)):
    for bi,bb in enumerate(descriptors(b,False,fb)):
     dx=m.NewIntVar(0,300,f'ldx{ri}_{fa}{fb}_{ai}_{bi}');dy=m.NewIntVar(0,300,f'ldy{ri}_{fa}{fb}_{ai}_{bi}');ll=m.NewIntVar(1,300,f'll{ri}_{fa}{fb}_{ai}_{bi}')
     m.AddMaxEquality(dx,[0,aa[0]-bb[1],bb[0]-aa[1]]);m.AddMaxEquality(dy,[0,aa[2]-bb[3],bb[2]-aa[3]]);m.Add(ll==dx+dy+1);options.append(ll)
   v=m.NewIntVar(1,300,f'lmin{ri}_{fa}{fb}');m.AddMinEquality(v,options);conds=[]
   if flips[a] is not None:conds.append(flips[a] if fa else flips[a].Not())
   if flips[b] is not None:conds.append(flips[b] if fb else flips[b].Not())
   m.Add(length==v).OnlyEnforceIf(conds)
total_length=sum(lengths);excess=m.NewIntVar(0,100000,'length_excess');m.AddMaxEquality(excess,[0,total_length-1700]);cost.extend([50*excess,5*total_length]);m.Minimize(sum(cost))

class Save(cp_model.CpSolverSolutionCallback):
 def __init__(self):super().__init__();self.n=0;self.best=None
 def on_solution_callback(self):
  self.n+=1;d=copy.deepcopy(raw);moved=set()
  for k,u in enumerate(d['units']):
   x,y=self.Value(xs[k]),self.Value(ys[k])
   newd=(u['d']+2*self.Value(flips[k]))%4 if flips[k] is not None else u['d']
   if (x,y,newd)!=(u['x'],u['y'],u['d']):moved.add(u['id'])
   u['x'],u['y'],u['d']=x,y,newd
  body={(x,y) for u in d['units'] for x in range(u['x'],u['x']+u['w']) for y in range(u['y'],u['y']+u['h'])}
  for p in d['paths']:
   f=contract['feeds'][p['r']]
   if f['source'] in moved or f['target'] in moved or any((z[0],z[1]) in body for z in p['cells']):p['cells']=[]
  d['overlap']=0;d['power_distance']=0;d['port_pack']={'radius':radius,'objective':self.ObjectiveValue(),'moved':sorted(moved),'solution':self.n,'port_slack':sum(self.Value(v) for v in slacks),'length_lower_bound':self.Value(total_length)}
  path=out.parent/(out.name+f'-solution-{self.n:03d}.json');path.write_text(json.dumps(d,ensure_ascii=False,indent=2));out.with_suffix('.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));out.with_suffix('.pos').write_text(''.join(f'{u["x"]} {u["y"]} {u["d"]}\n' for u in d['units']))
  self.best=d;print('solution',self.n,'objective',self.ObjectiveValue(),'moved',len(moved),'port_slack',sum(self.Value(v) for v in slacks),'length_lower',self.Value(total_length),flush=True)
solver=cp_model.CpSolver();solver.parameters.num_search_workers=workers;solver.parameters.max_time_in_seconds=limit;solver.parameters.random_seed=983;solver.parameters.log_search_progress=True
for name in ['use_timetabling_in_no_overlap_2d','use_energetic_reasoning_in_no_overlap_2d']:
 if hasattr(solver.parameters,name):setattr(solver.parameters,name,True)
cb=Save();meta={'source':sys.argv[1],'radius':radius,'workers':workers,'port_candidates':port_count,'point_rectangle_disjunctions':disjunctions,'limit_seconds':limit};out.with_suffix('.input.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2));print(meta,flush=True);t=time.monotonic();st=solver.Solve(m,cb)
result={**meta,'status':solver.StatusName(st),'wall_seconds':time.monotonic()-t,'solutions':cb.n,'objective':solver.ObjectiveValue() if cb.n else None}
out.with_suffix('.result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(result,flush=True)
