#!/usr/bin/env python3
from pathlib import Path
import json,time
from ortools.sat.python import cp_model
from local_power import generate,matrix
OUT=Path(__file__).resolve().parent
ans=[]
for name,walls,cap in [('open',(-20,32,-20,32),23),('wall',(-20,7,-20,32),13)]:
 b=generate(walls);rows,rhs,labels,A=matrix(b);m=cp_model.CpModel();v=[m.NewBoolVar(str(j)) for j in range(len(b))]
 for row,r in zip(rows,rhs):m.Add(sum(v[j]*n for j,n in row.items())<=int(r))
 m.Add(sum(v)<=cap);m.Maximize(sum(v[j]*(1+(d['rect'][2]>3)) for j,d in enumerate(b)))
 s=cp_model.CpSolver();s.parameters.num_search_workers=2;s.parameters.max_time_in_seconds=120
 status=s.Solve(m);o=dict(name=name,status=s.StatusName(status),value=s.ObjectiveValue(),upper=s.BestObjectiveBound(),seconds=s.WallTime())
 if status in (cp_model.FEASIBLE,cp_model.OPTIMAL):o['witness']=[d for j,d in enumerate(b) if s.Value(v[j])]
 print({k:v for k,v in o.items() if k!='witness'},flush=True);ans.append(o)
 (OUT/'weighted_integer.json').write_text(json.dumps(ans,indent=2))
