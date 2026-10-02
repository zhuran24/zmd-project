#!/usr/bin/env python3
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,sys,time,math
from pathlib import Path
from collections import defaultdict,Counter
from ortools.sat.python import cp_model
BASE=Path(__file__).resolve().parents[1]
C=json.loads((BASE/'依据/S2接法.json').read_text());MC={m['id']:m for m in C['machines']};D=[(1,0),(0,1),(-1,0),(0,-1)]
def machine(uid,x,y,d):
 m=MC[uid];kind='中' if m['model'] in ['种植机','采种机'] else '大' if m['model'] in ['研磨机','封装机','灌装机'] else '小'
 w,h=(5,5) if kind=='中' else (3,3) if kind=='小' else (4,6) if d%2==0 else (6,4)
 return dict(id=uid,model=m['model'],kind=kind,x0=x,y0=y,x1=x+w-1,y1=y+h-1,Din=d,recipe_ids=[m['recipe_id']],settings={'manufacture_on':True})
def cells(u):
 if 'x' in u:return [(u['x'],u['y'])]
 return [(x,y) for x in range(u['x0'],u['x1']+1) for y in range(u['y0'],u['y1']+1)]
def edge(u,d,outside=False):
 if d in [0,2]:res=[(u['x1'] if d==0 else u['x0'],y) for y in range(u['y0'],u['y1']+1)]
 else:res=[(x,u['y1'] if d==1 else u['y0']) for x in range(u['x0'],u['x1']+1)]
 return [(x+D[d][0],y+D[d][1]) for x,y in res] if outside else res

def fixed():
 l=dict(W=70,H=70,machines=[],warehouse_outlets=[],core=dict(id='CORE',x0=7,y0=6,x1=15,y1=14,Din=0,output_items=[dict(side=s,offset=o,item='源矿') for s in [1,3] for o in [1,4,7]]),power_poles=[],storage_boxes=[],transport=[],vin=[],vout=[])
 def belt(x,y,i,o):l['transport'].append(dict(id=f'TR_{x}_{y}',x=x,y=y,type='belt',in_side=i,out_side=o))
 # 17 complete blue-iron chains, 34 true warehouse source paths.
 klist=[f'S{k}' for k in range(1,14)]+[f'KQ{k}' for k in range(1,5)]
 for b in range(1,18):
  vertical=b>=10;start=16+6*(b-1) if b<10 else 22+6*(b-10)
  def xy(x,y):return (y+start,x) if vertical else (x,y+start)
  def sd(d):return (1-d)%4 if vertical else d
  def put(uid,x,y,d):xx,yy=xy(x,y);l['machines'].append(machine(uid,xx,yy,sd(d)))
  for q in range(2):
   j=2*b-1+q;put('T'+str(j),2,3*q,2);put('KB'+str(j),6,3*q,2)
   xx,yy=xy(0,3*q);l['warehouse_outlets'].append(dict(id='OB'+str(j),x0=xx,y0=yy,x1=xx+(2 if vertical else 0),y1=yy+(0 if vertical else 2),Dout=sd(0),item='蓝铁矿'))
   for x in [1,5,9]:xx,yy=xy(x,3*q+1);belt(xx,yy,sd(2),sd(0))
  put('B'+str(b),10,0,2);put('R'+str(b),15,0,2);xx,yy=xy(14,1);belt(xx,yy,sd(2),sd(0))
  put(klist[b-1],15,3,0)
 # Remaining twelve boundary sources, in their actual 3-cell footprints.
 j=7
 for side,coords in [(0,range(1,16,3)),(1,range(1,22,3))]:
  for v in coords:
   l['warehouse_outlets'].append(dict(id='OO'+str(j),x0=0 if side==0 else v,y0=v if side==0 else 0,x1=0 if side==0 else v+2,y1=v+2 if side==0 else 0,Dout=side,item='源矿'));j+=1
 pair=json.loads((BASE/'模块/plant-pairs.json').read_text())[0]
 names=[('S',k) for k in range(1,14)]+[('Q',k) for k in range(1,7)]
 for z in range(9):
  ox=32+13*(z//3);oy=21+16*(z%3)
  for u in pair['machines']:
   which=int(u['id'][1])-1;p,k=names[2*z+which];uid=p+u['id'][2]+str(k)
   l['machines'].append(machine(uid,u['x0']+ox,u['y0']+oy,u['Din']))
  for x,y,a,b in pair['transport']:belt(x+ox,y+oy,a,b)
 # Last seed triplet, placed in the upper left opening.
 p,k=names[-1];ox,oy=18,59
 for id,x,y,d in [('B',0,4,1),('A',6,0,2),('C',6,5,0)]:l['machines'].append(machine(p+id+str(k),x+ox,y+oy,d))
 for x,y,a,b in [(5,9,0,2),(4,9,0,3),(5,5,0,3),(5,4,1,0),(11,4,2,1),(11,5,3,2)]:belt(x+ox,y+oy,a,b)
 return l

def main(limit=120,portclear=True):
 l=fixed();reserve=dict(x0=18,y0=18,x1=23,y1=23);used={}
 for u in l['machines']+l['warehouse_outlets']+[l['core']]+l['transport']:
  for xy in cells(u):
   if xy in used:raise ValueError(('fixed_overlap',xy,used[xy],u['id']))
   if not(0<=xy[0]<70 and 0<=xy[1]<70):raise ValueError(('outside',u))
   used[xy]=u['id']
 for xy in cells(reserve):
  if xy in used:raise ValueError(('rect_overlap',xy))
  used[xy]='EMPTY_RECT'
 fixedby={u['id']:u for u in l['machines']+l['warehouse_outlets']+[l['core']]};todo=[m['id'] for m in C['machines'] if m['id'] not in fixedby]
 print('fixed',len(l['machines']),'todo',len(todo),'blocked',len(used),flush=True)
 # Harmonic locations provide only a construction objective, never constraints.
 centers={u:((v['x0']+v['x1'])/2,(v['y0']+v['y1'])/2) for u,v in fixedby.items()}
 for u in todo:centers[u]=(24,35)
 adj=defaultdict(list)
 for f in C['feeds']:adj[f['source']].append(f['target']);adj[f['target']].append(f['source'])
 for _ in range(300):
  for u in todo:
   ps=[centers[v] for v in adj[u]];centers[u]=(sum(x for x,y in ps)/len(ps),sum(y for x,y in ps)/len(ps))
 model=cp_model.CpModel();cover=defaultdict(list);select=defaultdict(list);choices=[];terms=[]
 indeg=Counter(f['target'] for f in C['feeds']);outdeg=Counter(f['source'] for f in C['feeds'])
 template={}
 for uid in todo:
  opts=[];cx,cy=centers[uid]
  for d in range(4):
   for x in range(1,68):
    for y in range(1,68):
     u=machine(uid,x,y,d)
     if u['x1']>=70 or u['y1']>=70:continue
     body=cells(u)
     if any(q in used for q in body):continue
     ip=[q for q in edge(u,d,True) if 0<=q[0]<70 and 0<=q[1]<70 and q not in used]
     op=[q for q in edge(u,(d+2)%4,True) if 0<=q[0]<70 and 0<=q[1]<70 and q not in used]
     if len(ip)<indeg[uid] or len(op)<outdeg[uid]:continue
     v=model.NewBoolVar(uid+'_'+str(len(opts)));opts.append(v)
     cost=int(10*(abs((u['x0']+u['x1'])/2-cx)+abs((u['y0']+u['y1'])/2-cy)))
     for f in C['feeds']:
      if f['target']==uid and f['source'] in fixedby:
       z=fixedby[f['source']];src=edge(z,z.get('Dout',(z.get('Din',0)+2)%4),True)
       cost+=3*min(abs(a[0]-b[0])+abs(a[1]-b[1]) for a in src for b in ip)
      elif f['source']==uid and f['target'] in fixedby:
       z=fixedby[f['target']];dst=edge(z,z.get('Din',0),True)
       cost+=3*min(abs(a[0]-b[0])+abs(a[1]-b[1]) for a in op for b in dst)
     terms.append(cost*v)
     for q in body:cover[q].append(v)
     choices.append((u,v,ip,op));select[uid].append(v)
  print(uid,len(opts),flush=True);model.AddExactlyOne(opts)
 for q,vs in cover.items():model.AddAtMostOne(vs)
 if portclear:
  for u,v,ip,op in choices:
   model.Add(sum(w for q in ip for w in cover[q])<=len(ip)-indeg[u['id']]).OnlyEnforceIf(v)
   model.Add(sum(w for q in op for w in cover[q])<=len(op)-outdeg[u['id']]).OnlyEnforceIf(v)
 model.Minimize(sum(terms));solver=cp_model.CpSolver();solver.parameters.num_workers=4;solver.parameters.max_time_in_seconds=limit;solver.parameters.random_seed=3
 target=BASE/'证据/packed.json'
 class CB(cp_model.CpSolverSolutionCallback):
  def on_solution_callback(self):
   ll={**l,'machines':l['machines']+[u for u,v,ip,op in choices if self.Value(v)]}
   target.write_text(json.dumps(dict(layout=ll,reserved_rectangle=reserve,objective=self.ObjectiveValue(),wall=self.WallTime()),ensure_ascii=False,indent=2))
   print('INCUMBENT',self.WallTime(),self.ObjectiveValue(),flush=True)
 st=solver.Solve(model,CB());out=dict(status=solver.StatusName(st),wall=solver.WallTime(),objective=solver.ObjectiveValue(),bound=solver.BestObjectiveBound(),placement_variables=len(choices),portclear=portclear)
 (BASE/'证据/packing-result.json').write_text(json.dumps(out,indent=2));print(out,flush=True)
 (BASE/'证据/fixed-partial.json').write_text(json.dumps(dict(layout=l,reserved_rectangle=reserve),ensure_ascii=False,indent=2))
if __name__=='__main__':main(float(sys.argv[1]) if len(sys.argv)>1 else 180,not '--no-portclear' in sys.argv)
