#!/usr/bin/env python3
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,sys,time
from collections import defaultdict,Counter
from ortools.sat.python import cp_model
from pack_factory import machine,cells,C,BASE,edge
st0=time.time();base=json.loads((BASE/'证据/loose-fixed.json').read_text());l=base['layout'];rect=base['reserved_rectangle']
fixed={u['id'] for u in l['machines']};todo=[m['id'] for m in C['machines'] if m['id'] not in fixed]
ni=Counter(f['target'] for f in C['feeds']);no=Counter(f['source'] for f in C['feeds']);groups=defaultdict(list)
for u in todo:groups[machine(u,0,0,0)['kind'],ni[u],no[u]].append(u)
occ=set(q for u in l['machines']+l['warehouse_outlets']+l['transport']+[l['core'],rect] for q in cells(u));protected=[]
for u in l['machines']:
 s=u['id']
 if not(s.startswith('KB') or len(s)>2 and s[0] in 'SQ' and s[1]=='B'):continue
 opts=[q for q in edge(u,(u['Din']+2)%4,True) if 0<=q[0]<70 and 0<=q[1]<70 and q not in occ]
 if opts:protected.append(opts[len(opts)//2])
hard_occ=occ.copy();occ.update(protected)
model=cp_model.CpModel();cover=defaultdict(list);bygroup=defaultdict(list);options=[]
for g,ids in groups.items():
 k,inc,outc=g;uid=ids[0]
 for d in ([0,1] if inc==outc else range(4)):
  u0=machine(uid,0,0,d);w,h=u0['x1']+1,u0['y1']+1
  for x in range(1,71-w):
   for y in range(1,71-h):
    u=machine(uid,x,y,d);body=cells(u)
    if any(q in occ for q in body):continue
    ip=[q for q in edge(u,d,True) if 0<=q[0]<70 and 0<=q[1]<70 and q not in hard_occ]
    op=[q for q in edge(u,(d+2)%4,True) if 0<=q[0]<70 and 0<=q[1]<70 and q not in hard_occ]
    # Port shortages are minimized explicitly; no silent feasibility claim.
    v=model.NewBoolVar('');bygroup[g].append(v)
    for q in body:cover[q].append(v)
    options.append((dict(kind=k,x0=x,y0=y,x1=x+w-1,y1=y+h-1,Din=d,category=list(g)),v,ip,op))
 print('placements',g,len(bygroup[g]),'elapsed',round(time.time()-st0,1),flush=True)
for g,ids in groups.items():model.Add(sum(bygroup[g])==len(ids))
for q,vs in cover.items():model.AddAtMostOne(vs)
# One Boolean occupied variable per cell keeps port-count constraints sparse.
occvar={q:model.NewBoolVar('') for q in cover}
for q,v in occvar.items():model.Add(v==sum(cover[q]))
hint_layout=json.loads((BASE/'证据/assigned-1.json').read_text())['layout']
hint_keys=set();hint_occ=set()
for hu in hint_layout['machines']:
 uid=hu['id']
 if uid in fixed:continue
 g=(hu['kind'],ni[uid],no[uid]);dd=hu['Din']%2 if g[1]==g[2] else hu['Din']
 hint_keys.add((hu['x0'],hu['y0'],dd,g));hint_occ.update(cells(hu))
for q,vv in occvar.items():model.AddHint(vv,int(q in hint_occ))
for hu,vv,ip,op in options:model.AddHint(vv,int((hu['x0'],hu['y0'],hu['Din'],tuple(hu['category'])) in hint_keys))
print('hint_selected',sum((hu['x0'],hu['y0'],hu['Din'],tuple(hu['category'])) in hint_keys for hu,vv,ip,op in options),flush=True)
shortfalls=[]
for u,v,ip,op in options:
 k,a,b=u['category']
 for pts,need in [(ip,a),(op,b)]:
  deficit=model.NewIntVar(0,need,'');shortfalls.append(deficit)
  model.Add(sum(occvar[q] for q in pts if q in occvar)<=len(pts)-need+deficit).OnlyEnforceIf(v)
  model.Add(deficit==0).OnlyEnforceIf(v.Not())
  active=(u['x0'],u['y0'],u['Din'],tuple(u['category'])) in hint_keys
  dv=max(0,need-len(pts)+sum(q in hint_occ for q in pts)) if active else 0
  model.AddHint(deficit,dv)
model.Minimize(sum(shortfalls))
# No distance objective: this is solely a compact, port-accessible packing attempt.
s=cp_model.CpSolver();s.parameters.num_workers=4;s.parameters.max_time_in_seconds=float(sys.argv[1]) if len(sys.argv)>1 else 180;s.parameters.random_seed=31
print('model',len(options),'build',round(time.time()-st0,1),flush=True)
class CB(cp_model.CpSolverSolutionCallback):
 def on_solution_callback(self):
  z=dict(fixed=l,reserved_rectangle=rect,protected=protected,moving=[u for u,v,ip,op in options if self.Value(v)],todo=todo,groups=[dict(category=list(g),ids=ids) for g,ids in groups.items()],wall=self.WallTime(),port_shortfall=self.ObjectiveValue())
  (BASE/'证据/anonymous-ports-hinted.json').write_text(json.dumps(z,ensure_ascii=False,indent=2));print('INCUMBENT',self.WallTime(),self.ObjectiveValue(),flush=True)
st=s.Solve(model,CB());r=dict(status=s.StatusName(st),wall=s.WallTime(),objective=s.ObjectiveValue(),bound=s.BestObjectiveBound(),workers=4,placement_variables=len(options),build_seconds=round(time.time()-st0-s.WallTime(),1))
(BASE/'证据/anonymous-ports-hinted-result.json').write_text(json.dumps(r,indent=2));print(r,flush=True)
