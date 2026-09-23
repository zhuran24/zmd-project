#!/usr/bin/env python3
"""Finite local powered-machine relaxation. Writes only beside this script."""
from pathlib import Path
import json,time,sys
from collections import defaultdict
import numpy as np
from scipy.optimize import linprog,milp,Bounds,LinearConstraint
from scipy.sparse import coo_matrix
from ortools.sat.python import cp_model
OUT=Path(__file__).resolve().parent
SHAPES=[(3,3,0),(3,3,1),(5,5,0),(5,5,1),(6,4,1),(4,6,0)]
def cells(r):
 x,y,w,h=r
 return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}
def generate(walls):
 # supply [0,12)^2; pole [5,7)^2; wall bounds [xmin,xmax)x[ymin,ymax)
 xmin,xmax,ymin,ymax=walls; pole=cells((5,5,2,2)); bodies=[]
 def available(c):return xmin<=c[0]<xmax and ymin<=c[1]<ymax and c not in pole
 for w,h,axis in SHAPES:
  for x in range(max(1-w,xmin),min(11,xmax-w)+1):
   for y in range(max(1-h,ymin),min(11,ymax-h)+1):
    r=(x,y,w,h); body=cells(r)
    if body&pole:continue
    sides=([[(x-1,y+k) for k in range(h)],[(x+w,y+k) for k in range(h)]] if axis==0 else [[(x+k,y-1) for k in range(w)],[(x+k,y+h) for k in range(w)]])
    ports=[[p for p in side if available(p)] for side in sides]
    if not all(ports):continue
    bodies.append(dict(rect=r,axis=axis,ports=ports))
 return bodies

def matrix(bodies):
 occ=defaultdict(list)
 for j,b in enumerate(bodies):
  for c in cells(b['rect']):occ[c].append(j)
 rows=[];rhs=[];labels=[]
 for c,js in sorted(occ.items()):rows.append({j:1 for j in js});rhs.append(1);labels.append(['cell',*c])
 for j,b in enumerate(bodies):
  for k,port in enumerate(b['ports']):
   row=defaultdict(int);row[j]+=1
   # if selected, at least one neighbor on this port edge remains unoccupied
   for pt in port:
    for n in occ.get(tuple(pt),[]):row[n]+=1
   rows.append(dict(row));rhs.append(len(port));labels.append(['port',j,k])
 rr=[];cc=[];vv=[]
 for i,row in enumerate(rows):
  for j,v in row.items():rr.append(i);cc.append(j);vv.append(v)
 A=coo_matrix((np.array(vv,dtype=float),(rr,cc)),shape=(len(rows),len(bodies))).tocsc()
 return rows,np.array(rhs),labels,A

def run(name,walls,seconds=120):
 start=time.monotonic();bodies=generate(walls);rows,rhs,labels,A=matrix(bodies);n=len(bodies)
 lp=linprog(-np.ones(n),A_ub=A,b_ub=rhs,bounds=(0,1),method='highs')
 result=dict(name=name,walls=walls,n=n,m=len(rows),lp_status=lp.message,lp_upper=-lp.fun if lp.success else None)
 print(result,flush=True)
 model=cp_model.CpModel();vs=[model.NewBoolVar(str(j)) for j in range(n)]
 for row,b in zip(rows,rhs):model.Add(sum(vs[j]*v for j,v in row.items())<=int(b))
 model.Maximize(sum(vs));s=cp_model.CpSolver();s.parameters.max_time_in_seconds=seconds;s.parameters.num_search_workers=2
 status=s.Solve(model); result.update(cp_status=s.StatusName(status),cp_upper=s.BestObjectiveBound(),cp_value=s.ObjectiveValue(),cp_seconds=s.WallTime())
 if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):result['witness']=[bodies[j] for j in range(n) if s.Value(vs[j])]
 print({k:v for k,v in result.items() if k!='witness'},flush=True)
 # Save complete finite domain and linear system for independent certification.
 (OUT/(name+'_model.json')).write_text(json.dumps(dict(walls=walls,bodies=bodies,rows=[list(r.items()) for r in rows],rhs=rhs.tolist(),labels=labels),separators=(',',':')))
 if lp.success:
  (OUT/(name+'_lp.json')).write_text(json.dumps(dict(dual=(-lp.ineqlin.marginals).tolist(),upper_dual=(-lp.upper.marginals).tolist(),primal=lp.x.tolist()),separators=(',',':')))
 result['elapsed']=time.monotonic()-start
 (OUT/(name+'_result.json')).write_text(json.dumps(result,indent=2))
 return result
if __name__=='__main__':
 run('wall0',(-20,7,-20,32),float(sys.argv[1]) if len(sys.argv)>1 else 120)
