#!/usr/bin/env python3
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import sys,json,copy,time
from pathlib import Path
from collections import defaultdict,Counter,deque
from scipy.optimize import linear_sum_assignment
from ortools.sat.python import cp_model
BASE=Path(__file__).resolve().parents[1];raw=json.loads(Path(sys.argv[1]).read_text());out=Path(sys.argv[2]);seconds=float(sys.argv[3]);workers=int(sys.argv[4]);u=raw['units'];con=json.loads((BASE/'逻辑接法.json').read_text());ni=Counter(f['target'] for f in con['feeds']);no=Counter(f['source'] for f in con['feeds']);idx={a['id']:j for j,a in enumerate(u)};D=[(1,0),(0,1),(-1,0),(0,-1)]
body={(x,y) for a in u for x in range(a['x'],a['x']+a['w']) for y in range(a['y'],a['y']+a['h'])}|{(x,y) for x in range(64,70) for y in range(64,70)};comp={};sizes=[]
for x in range(70):
 for y in range(70):
  if (x,y) in body or (x,y) in comp:continue
  c=len(sizes);n=0;q=deque([(x,y)]);comp[x,y]=c
  while q:
   a,b=q.popleft();n+=1
   for dx,dy in D:
    p=(a+dx,b+dy)
    if 0<=p[0]<70 and 0<=p[1]<70 and p not in body and p not in comp:comp[p]=c;q.append(p)
  sizes.append(n)
slots=defaultdict(list)
for j,a in enumerate(u):
 if a['type']!=5:slots[a['type']].append(j)
ports=[];tokenmap={};poses={};inrows={};outrows={}
def port(si,side,off):
 a=u[si];x=a['x']+a['w'] if side==0 else a['x']-1 if side==2 else a['x']+off;y=a['y']+a['h'] if side==1 else a['y']-1 if side==3 else a['y']+off
 if (x,y) not in comp:return None
 key=(si,side,off)
 if key not in tokenmap:tokenmap[key]=len(ports);ports.append({'slot':si,'side':side,'offset':off,'x':x,'y':y,'component':comp[x,y]})
 return tokenmap[key]
for ty,ss in slots.items():
 pp=[];ir=[];orr=[]
 for local,si in enumerate(ss):
  a=u[si];dirs=range(4) if ty<2 else [1,3] if ty==2 and a['w']==6 else [0,2] if ty==2 else [0,1] if ty==3 else [a['d']]
  for di in dirs:
   ins=[];outs=[]
   if ty==4:spec=[(di,True,[1])]
   elif ty==3:spec=[(s,s%2!=di%2,[1,4,7] if s%2!=di%2 else range(1,8)) for s in range(4)]
   else:spec=[(di,False,range(a['w'] if di%2 else a['h'])),((di+2)%4,True,range(a['w'] if di%2 else a['h']))]
   pi=len(pp)
   for side,isout,ofs in spec:
    for off in ofs:
     t=port(si,side,off)
     if t is not None:(outs if isout else ins).append(t)
   pp.append({'slot':si,'local_slot':local,'d':di,'in':ins,'out':outs})
   for t in ins:p=ports[t];ir.append((pi,t,p['x'],p['y'],p['component'],p['side']))
   for t in outs:p=ports[t];orr.append((pi,t,p['x'],p['y'],p['component'],p['side']))
 poses[ty]=pp;inrows[ty]=ir;outrows[ty]=orr
m=cp_model.CpModel();pv={};sv={};defv=[];hints={};minimum=0
for ty,ss in slots.items():
 options=poses[ty];bylocal=defaultdict(list)
 for pi,p in enumerate(options):bylocal[p['local_slot']].append(pi)
 costs=[];choice={}
 for i in ss:
  row=[]
  for sl,si in enumerate(ss):
   vv=[]
   for pi in bylocal[sl]:
    p=options[pi];de=max(0,ni[u[i]['id']]-len(p['in']))+max(0,no[u[i]['id']]-len(p['out']));dist=abs(u[i]['x']-u[si]['x'])+abs(u[i]['y']-u[si]['y']);turn=int(p['d']!=(u[i]['d']%2 if ty==3 else u[i]['d']));vv.append((de*10000000+dist*10+turn,pi,de))
   best=min(vv);row.append(best[0]);choice[i,sl]=best
  costs.append(row)
 aa,bb=linear_sum_assignment(costs)
 for row,sl in zip(aa,bb):i=ss[row];hints[i]=choice[i,sl][1];minimum+=choice[i,sl][2]
 for i in ss:
  p=m.NewIntVar(0,len(options)-1,f'pose{i}');s=m.NewIntVar(0,len(ss)-1,f'slot{i}');pv[i]=p;sv[i]=s;m.AddElement(p,[z['local_slot'] for z in options],s);m.AddHint(p,hints[i]);m.AddHint(s,options[hints[i]]['local_slot'])
  de=m.NewIntVar(0,20,f'def{i}');m.AddElement(p,[max(0,ni[u[i]['id']]-len(z['in']))+max(0,no[u[i]['id']]-len(z['out'])) for z in options],de);defv.append(de)
 m.AddAllDifferent([sv[i] for i in ss])
m.Add(sum(defv)==minimum)
edgevars=[];tokens=[];terms=defaultdict(list);misses=[];lens=[];real_count=len(ports)
for r,f in enumerate(con['feeds']):
 a,b=idx[f['source']],idx[f['target']];ta,tb=u[a]['type'],u[b]['type'];cc=m.NewIntVar(-1,len(sizes)-1,f'component{r}');sx=m.NewIntVar(0,69,f'sx{r}');sy=m.NewIntVar(0,69,f'sy{r}');tx=m.NewIntVar(0,69,f'tx{r}');ty=m.NewIntVar(0,69,f'ty{r}');st=m.NewIntVar(0,real_count+650,f'st{r}');tt=m.NewIntVar(0,real_count+650,f'tt{r}');tokens.extend([st,tt]);ds=real_count+2*r;dt=ds+1;sdir=m.NewIntVar(0,3,f'sdir{r}');tdir=m.NewIntVar(0,3,f'tdir{r}')
 sr=outrows[ta]+[(pi,ds,0,0,-1,0) for pi in range(len(poses[ta]))];tr=inrows[tb]+[(pi,dt,0,0,-1,0) for pi in range(len(poses[tb]))];m.AddAllowedAssignments([pv[a],st,sx,sy,cc,sdir],sr);m.AddAllowedAssignments([pv[b],tt,tx,ty,cc,tdir],tr)
 m.AddHint(st,ds);m.AddHint(tt,dt);m.AddHint(cc,-1);m.AddHint(sx,0);m.AddHint(sy,0);m.AddHint(tx,0);m.AddHint(ty,0)
 active=m.NewBoolVar(f'active{r}');m.Add(cc>=0).OnlyEnforceIf(active);m.Add(cc==-1).OnlyEnforceIf(active.Not());misses.append(active.Not());m.AddHint(active,0)
 dx=m.NewIntVar(0,69,f'dx{r}');dy=m.NewIntVar(0,69,f'dy{r}');ll=m.NewIntVar(0,139,f'length{r}');m.AddAbsEquality(dx,sx-tx);m.AddAbsEquality(dy,sy-ty);m.Add(ll==dx+dy+active);lens.append(ll)
 tiny=m.NewBoolVar(f'tiny{r}');turn=m.NewIntVar(0,1,f'turn{r}');m.AddAllowedAssignments([cc,tiny],[(-1,0)]+[(c,int(n==1)) for c,n in enumerate(sizes)]);m.AddAllowedAssignments([sdir,tdir,turn],[(a,b,int((a+2)%4!=b)) for a in range(4) for b in range(4) if a!=b]).OnlyEnforceIf(tiny);m.Add(turn==0).OnlyEnforceIf(tiny.Not())
 possible={row[4] for row in outrows[ta]}&{row[4] for row in inrows[tb]}
 for c in possible:
  eq=m.NewBoolVar(f'ec{r}_{c}');m.Add(cc==c).OnlyEnforceIf(eq);m.Add(cc!=c).OnlyEnforceIf(eq.Not());v=m.NewIntVar(0,139,f'volume{r}_{c}');m.Add(v==ll+turn).OnlyEnforceIf(eq);m.Add(v==0).OnlyEnforceIf(eq.Not());terms[c].append(v)
 edgevars.append((cc,st,tt,active,ll))
m.AddAllDifferent(tokens)
for c,vs in terms.items():m.Add(sum(vs)<=2*sizes[c])
m.Minimize(100000*sum(misses)+sum(lens))
class Save(cp_model.CpSolverSolutionCallback):
 def __init__(self):super().__init__();self.n=0
 def on_solution_callback(self):
  self.n+=1;d=copy.deepcopy(raw);d['paths']=[dict(r=i,source=[0]*4,target=[0]*4,cells=[]) for i in range(325)];picked={}
  for i,p in pv.items():
   op=poses[u[i]['type']][self.Value(p)];slot=u[op['slot']];q=d['units'][i]
   for key in ['x','y','w','h']:q[key]=slot[key]
   q['d']=op['d'];picked[u[i]['id']]={'physical_slot':slot['id'],'d':op['d']}
  assigned=[]
  for r,(cc,st,tt,act,ll) in enumerate(edgevars):
   active=self.Value(act);a={'r':r,'active':bool(active),'component':self.Value(cc),'length_lower_bound':self.Value(ll)}
   if active:
    ps=ports[self.Value(st)];pt=ports[self.Value(tt)];a['source']=[ps['x'],ps['y'],ps['side'],ps['offset']];a['target']=[pt['x'],pt['y'],pt['side'],pt['offset']]
   assigned.append(a)
  n=sum(z['active'] for z in assigned);d['overlap']=0;d['power_distance']=0;d['slot_assignment']={'is_routed_layout':False,'active_edge_assignments':n,'minimum_port_deficit':minimum,'length_lower_sum':sum(z['length_lower_bound'] for z in assigned),'solution':self.n,'assignment':picked,'ports':assigned}
  p=out.parent/(out.name+f'-solution-{self.n:03d}.json');p.write_text(json.dumps(d,ensure_ascii=False,indent=2));out.with_suffix('.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));print('solution',self.n,'assigned',n,'port_deficit',minimum,flush=True)
solver=cp_model.CpSolver();solver.parameters.num_search_workers=workers;solver.parameters.max_time_in_seconds=seconds;solver.parameters.random_seed=1103;solver.parameters.log_search_progress=True;cb=Save();meta={'source':sys.argv[1],'seconds':seconds,'workers':workers,'components':len(sizes),'port_tokens':len(ports),'minimum_port_deficit':minimum,'pose_options':{str(k):len(v) for k,v in poses.items()}};out.with_suffix('.input.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2));print(meta,flush=True);t=time.monotonic();status=solver.Solve(m,cb);res={**meta,'status':solver.StatusName(status),'wall_seconds':time.monotonic()-t,'solutions':cb.n};out.with_suffix('.result.json').write_text(json.dumps(res,ensure_ascii=False,indent=2));print(res,flush=True)
