#!/usr/bin/env python3
from pathlib import Path
import sys,json,time
OUT=Path(__file__).resolve().parent; OLD=OUT.parents[1]/'第66-68轮'/'推导66'
sys.path.insert(0,str(OLD))
import boundary_power as bp
from ortools.sat.python import cp_model
P=int(sys.argv[1]) if len(sys.argv)>1 else 10
seconds=float(sys.argv[2]) if len(sys.argv)>2 else 120
extra='--strip' in sys.argv
overlap='--overlap' in sys.argv
caps={}
for path in OUT.glob('supply_*_certificates.json'):
 for c in json.loads(path.read_text()):
  for xy in c['positions']:caps[tuple(xy)]=min(caps.get(tuple(xy),23),c['integer_upper'])
orig=bp.generate
def generate(b,extra):
 bodies,X,Y=orig(b,extra)
 for d in bodies:
  if d['kind']=='p':
   d['loss']=max(d['loss'],23-caps.get((d['x'],d['y']),23),10*d['j'])
 return bodies,X,Y
bp.generate=generate
m,bodies,sv,occ,cost,constant=bp.build(17,P,extra)
model=cp_model.CpModel();vs=[model.NewBoolVar(n) for n in m.names]
for row,lo,hi in zip(m.rows,m.lo,m.hi):
 expr=sum(vs[i]*int(v) for i,v in row.items())
 if lo!=-float('inf'):model.Add(expr>=int(lo))
 if hi!=float('inf'):model.Add(expr<=int(hi))
if overlap:
 poles=[i for i,d in enumerate(bodies) if d['kind']=='p']
 charges=[]
 for i,d in enumerate(bodies):
  if d['kind'] not in ('s','m','l'):continue
  eligible=[j for j in poles if d['x']-6<=bodies[j]['x']<=d['x']+d['w']+4 and d['y']-6<=bodies[j]['y']<=d['y']+d['h']+4]
  z=model.NewIntVar(0,P-1,'repeat:'+str(i));charges.append(z)
  model.Add(z==sum(vs[sv[j]] for j in eligible)-1).OnlyEnforceIf(vs[sv[i]])
  model.Add(z==0).OnlyEnforceIf(vs[sv[i]].Not())
 model.Add(sum(charges)+sum(vs[sv[j]]*bodies[j]['loss'] for j in poles)<=23*P-217)
obj=constant+sum(vs[i]*int(v) for i,v in cost.items());model.Add(obj>=180 if P==10 else obj>=189)
model.Add(obj<=187)
model.Minimize(obj)
s=cp_model.CpSolver();s.parameters.num_search_workers=2;s.parameters.max_time_in_seconds=seconds;s.parameters.random_seed=69
start=time.monotonic();status=s.Solve(model)
out=dict(P=P,extra=extra,overlap=overlap,vars=len(m.names),rows=len(m.rows),status=s.StatusName(status),upper=s.ObjectiveValue(),lower=s.BestObjectiveBound(),seconds=time.monotonic()-start,power_positions_with_new_certificate=len(caps))
if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):
 out['chosen']=[d for i,d in enumerate(bodies) if s.Value(vs[sv[i]])]
 print('chosen poles',[d for d in out['chosen'] if d['kind']=='p'],flush=True)
name='search_P'+str(P)+('_strip' if extra else '_edge')+('_overlap' if overlap else '')
(OUT/(name+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2))
print({k:v for k,v in out.items() if k!='chosen'},flush=True)
