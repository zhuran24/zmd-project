#!/usr/bin/env python3
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import sys,json,time,copy
from pathlib import Path
from collections import Counter
from ortools.sat.python import cp_model
BASE=Path(__file__).resolve().parents[1];raw=json.loads(Path(sys.argv[1]).read_text());out=Path(sys.argv[2]);radius=int(sys.argv[3]);seconds=float(sys.argv[4]);workers=int(sys.argv[5]) if len(sys.argv)>5 else 2
u=raw['units'];con=json.loads((BASE/'逻辑接法.json').read_text());ni=Counter(f['target'] for f in con['feeds']);no=Counter(f['source'] for f in con['feeds']);idx={v['id']:i for i,v in enumerate(u)};poles=[v for v in u if v['type']==5];oldocc={(x,y) for v in u for x in range(v['x'],v['x']+v['w']) for y in range(v['y'],v['y']+v['h'])}
degree=Counter()
for p in raw['paths']:
 if p['cells']:
  f=con['feeds'][p['r']];degree[f['source']]+=1;degree[f['target']]+=1
m=cp_model.CpModel();xs=[];ys=[];ix=[];iy=[];bounds=[];select=[];cost=[];slacks=[];clear_by_side=[];hintclear={}
for k,v in enumerate(u):
 can=v['type']!=4;mr=3 if v['type']==5 else radius;lx=max(1,v['x']-mr) if can else v['x'];hx=min(70-v['w'],v['x']+mr) if can else v['x'];ly=max(1,v['y']-mr) if can else v['y'];hy=min(70-v['h'],v['y']+mr) if can else v['y']
 x=m.NewIntVar(lx,hx,f'x{k}');y=m.NewIntVar(ly,hy,f'y{k}');xs.append(x);ys.append(y);bounds.append((lx,hx,ly,hy));ix.append(m.NewFixedSizeIntervalVar(x,v['w'],f'ix{k}'));iy.append(m.NewFixedSizeIntervalVar(y,v['h'],f'iy{k}'));m.AddHint(x,v['x']);m.AddHint(y,v['y'])
 choices=list(range(4)) if v['type']<2 else [v['d'],(v['d']+2)%4] if v['type']==2 else [0,1] if v['type']==3 else [v['d']]
 sd={d:m.NewBoolVar(f'dir{k}_{d}') for d in choices};select.append(sd);m.AddExactlyOne(list(sd.values()));old_d=v['d']%2 if v['type']==3 else v['d']
 for d,b in sd.items():m.AddHint(b,int(d==old_d));cost.append((0 if d==old_d else 3*(1+degree[v['id']]))*b)
 if can:
  ch=m.NewBoolVar(f'move{k}');m.Add(x==v['x']).OnlyEnforceIf(ch.Not());m.Add(y==v['y']).OnlyEnforceIf(ch.Not());dx=m.NewIntVar(0,70,f'dx{k}');dy=m.NewIntVar(0,70,f'dy{k}');m.AddAbsEquality(dx,x-v['x']);m.AddAbsEquality(dy,y-v['y']);cost.extend([10*(1+degree[v['id']])*ch,dx,dy]);m.AddHint(ch,0)
ix.append(m.NewFixedSizeIntervalVar(64,6,'emptyx'));iy.append(m.NewFixedSizeIntervalVar(64,6,'emptyy'));m.AddNoOverlap2D(ix,iy)
obstacles=[(xs[k],ys[k],v['w'],v['h'],bounds[k]) for k,v in enumerate(u)]+[(64,64,6,6,(64,64,64,64))]
for k,v in enumerate(u):
 if v['type']>=3:continue
 lx,hx,ly,hy=bounds[k];cc=[]
 for j,p in enumerate(u):
  if p['type']!=5:continue
  ax,bx,ay,by=bounds[j]
  if lx>bx+6 or hx+v['w']-1<ax-5 or ly>by+6 or hy+v['h']-1<ay-5:continue
  c=m.NewBoolVar(f'power{k}_{j}');cc.append(c);m.Add(xs[k]<=xs[j]+6).OnlyEnforceIf(c);m.Add(xs[k]+v['w']-1>=xs[j]-5).OnlyEnforceIf(c);m.Add(ys[k]<=ys[j]+6).OnlyEnforceIf(c);m.Add(ys[k]+v['h']-1>=ys[j]-5).OnlyEnforceIf(c)
 m.AddBoolOr(cc)

count_ports=0;count_sep=0
for k,v in enumerate(u):
 per={};clear_by_side.append(per)
 if v['type']==5:continue
 if v['type'] in (0,1,3):sides=range(4)
 elif v['type']==2:sides=[v['d'],(v['d']+2)%4]
 else:sides=[v['d']]
 lx,hx,ly,hy=bounds[k]
 for side in sides:
  offsets=range(1,8) if v['type']==3 else [1] if v['type']==4 else range(v['w'] if side%2 else v['h']);per[side]={}
  for off in offsets:
   dx=v['w'] if side==0 else -1 if side==2 else off;dy=v['h'] if side==1 else -1 if side==3 else off;px=xs[k]+dx;py=ys[k]+dy;plx,phx,ply,phy=lx+dx,hx+dx,ly+dy,hy+dy
   c=m.NewBoolVar(f'clear{k}_{side}_{off}');per[side][off]=c;count_ports+=1;m.Add(px>=0).OnlyEnforceIf(c);m.Add(px<70).OnlyEnforceIf(c);m.Add(py>=0).OnlyEnforceIf(c);m.Add(py<70).OnlyEnforceIf(c)
   ox,oy=v['x']+dx,v['y']+dy;val=int(0<=ox<70 and 0<=oy<70 and (ox,oy) not in oldocc and not(ox>=64 and oy>=64));hintclear[c.Index()]=val;m.AddHint(c,val)
   for j,(ax,ay,w,h,bb) in enumerate(obstacles):
    if j==k:continue
    a,b,e,f=bb
    if phx<a or plx>b+w-1 or phy<e or ply>f+h-1:continue
    pp=[]
    for di,(possible,cond) in enumerate([(plx<=b-1,px<ax),(phx>=a+w,px>=ax+w),(ply<=f-1,py<ay),(phy>=e+h,py>=ay+h)]):
     if possible:
      sep=m.NewBoolVar(f'sep{k}_{side}_{off}_{j}_{di}');m.Add(cond).OnlyEnforceIf(sep);pp.append(sep)
    m.AddBoolOr(pp+[c.Not()]);count_sep+=1
 for outside,need in [(False,ni[v['id']]),(True,no[v['id']])]:
  if not need:continue
  slack=m.NewIntVar(0,need,f'slack{k}_{outside}');slacks.append(slack);m.Add(slack==0);cost.append(10000*slack)
  for d,on in select[k].items():
   if v['type']==4:arr=[per[d][1]]
   elif v['type']==3:
    dirs=[(d+1)%4,(d+3)%4] if outside else [d,(d+2)%4];arr=[per[di][o] for di in dirs for o in ([1,4,7] if outside else range(1,8))]
   else:arr=list(per[(d+2)%4 if outside else d].values())
   m.Add(sum(arr)+slack>=need).OnlyEnforceIf(on)
   old_d=v['d']%2 if v['type']==3 else v['d']
   if d==old_d:m.AddHint(slack,max(0,need-sum(hintclear[a.Index()] for a in arr)))
m.Minimize(sum(cost))
def actual_length(d):
 um={a['id']:a for a in d['units']}
 def pts(a,outside):
  di=a['d'];spec=[(di,[1])] if a['type']==4 else [(z,[1,4,7] if outside else range(1,8)) for z in ([(di+1)%4,(di+3)%4] if outside else [di,(di+2)%4])] if a['type']==3 else [((di+2)%4 if outside else di,range(a['w'] if di%2 else a['h']))]
  return [(a['x']+a['w'] if z==0 else a['x']-1 if z==2 else a['x']+o,a['y']+a['h'] if z==1 else a['y']-1 if z==3 else a['y']+o) for z,offs in spec for o in offs]
 return sum(min(abs(x-z)+abs(y-w)+1 for x,y in pts(um[f['source']],True) for z,w in pts(um[f['target']],False)) for f in con['feeds'])
class Save(cp_model.CpSolverSolutionCallback):
 def __init__(self):super().__init__();self.n=0
 def on_solution_callback(self):
  self.n+=1;d=copy.deepcopy(raw);changed=set()
  for k,v in enumerate(d['units']):
   xx,yy=self.Value(xs[k]),self.Value(ys[k]);dd=next(di for di,z in select[k].items() if self.Value(z));dc=(dd%2!=v['d']%2) if v['type']==3 else dd!=v['d']
   if (xx,yy)!=(v['x'],v['y']) or dc:changed.add(v['id'])
   v['x'],v['y'],v['d']=xx,yy,dd
  body={(x,y) for v in d['units'] for x in range(v['x'],v['x']+v['w']) for y in range(v['y'],v['y']+v['h'])}
  for p in d['paths']:
   f=con['feeds'][p['r']]
   if f['source'] in changed or f['target'] in changed or any((z[0],z[1]) in body for z in p['cells']):p['cells']=[]
  slack=sum(self.Value(z) for z in slacks);ll=actual_length(d);d['overlap']=0;d['power_distance']=0;d['port_pack']={'solution':self.n,'objective':self.ObjectiveValue(),'port_slack':slack,'length_lower_bound':ll,'changed':sorted(changed),'radius':radius}
  (out.parent/(out.name+f'-solution-{self.n:03d}.json')).write_text(json.dumps(d,ensure_ascii=False,indent=2));out.with_suffix('.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));print('solution',self.n,'slack',slack,'length_lower',ll,'changed',len(changed),flush=True)
solver=cp_model.CpSolver();solver.parameters.num_search_workers=workers;solver.parameters.max_time_in_seconds=seconds;solver.parameters.random_seed=1063;solver.parameters.stop_after_first_solution=True;solver.parameters.log_search_progress=True;cb=Save();meta={'source':sys.argv[1],'radius':radius,'workers':workers,'seconds':seconds,'port_candidates':count_ports,'point_rectangle_disjunctions':count_sep,'orientations':'小中四向，大保留长边轴向的两向，协议核心两种轴向'};out.with_suffix('.input.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2));print(meta,flush=True);t=time.monotonic();st=solver.Solve(m,cb);result={**meta,'status':solver.StatusName(st),'wall_seconds':time.monotonic()-t,'solutions':cb.n,'objective':solver.ObjectiveValue() if cb.n else None};out.with_suffix('.result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(result,flush=True)
