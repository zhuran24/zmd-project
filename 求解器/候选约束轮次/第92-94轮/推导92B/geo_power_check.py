#!/usr/bin/env python3
import os
os.environ.update(OMP_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',MKL_NUM_THREADS='1')
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
from pathlib import Path
from collections import defaultdict,Counter
import json,sys,time
from ortools.sat.python import cp_model
OUT=Path(__file__).resolve().parent

def domain(case,encoding):
    # The side-rectangle uses only the mandatory 12-row strip as forbidden port cells.
    # Its body must lie to its left, but port neighbors outside these 12 rows remain available.
    g=int(case[4:]) if case.startswith('side') else None
    def block(x,y,body=False):
        if 5<=x<=6 and 5<=y<=6:return True
        if case=='edge' and x>6:return True
        if case=='corner' and (x>6 or y>6):return True
        if g is not None and x>=7+g and (body or 0<=y<=11):return True
        return False
    ans=[]
    if encoding=='A':
        for x in range(-6,12):
          for y in range(-6,12):
           for w,h,ax in [(3,3,0),(3,3,1),(5,5,0),(5,5,1),(6,4,1),(4,6,0)]:
            cells={(x+i,y+j) for i in range(w) for j in range(h)}
            if not any(0<=a<=11 and 0<=b<=11 for a,b in cells) or any(block(a,b,True) for a,b in cells):continue
            raw=[[(x-1,y+j) for j in range(h)],[(x+w,y+j) for j in range(h)]] if ax==0 else [[(x+i,y-1) for i in range(w)],[(x+i,y+h) for i in range(w)]]
            sides=[set((a,b) for a,b in r if not block(a,b)) for r in raw]
            if all(sides):ans.append(dict(key=(x,y,w,h,ax),body=sorted(cells),sides=[sorted(s) for s in sides],weight=2 if w==3 else 3))
    else:
      for w,h,ax in [(3,3,0),(3,3,1),(5,5,0),(5,5,1),(6,4,1),(4,6,0)]:
       for x in range(1-w,12):
        for y in range(1-h,12):
         if x<7 and x+w>5 and y<7 and y+h>5:continue
         if case in ('edge','corner') and x+w>7:continue
         if case=='corner' and y+h>7:continue
         if g is not None and x+w>7+g:continue
         cells=[(a,b) for a in range(x,x+w) for b in range(y,y+h)]
         raw=([[(x-1,b) for b in range(y,y+h)],[(x+w,b) for b in range(y,y+h)]] if ax==0 else [[(a,y-1) for a in range(x,x+w)],[(a,y+h) for a in range(x,x+w)]])
         sides=[]
         for side in raw:
          sides.append([p for p in side if not block(*p)])
         if all(sides):ans.append(dict(key=(x,y,w,h,ax),body=cells,sides=sides,weight=2 if w==3 else 3))
    return sorted(ans,key=lambda o:o['key'])

def run(case,objective,threshold,encoding,seconds=120):
 threshold=int(threshold)
 opts=domain(case,encoding);other=domain(case,'B' if encoding=='A' else 'A')
 assert opts==other,(case,'domain differs')
 n=len(opts);occ=defaultdict(list)
 for i,o in enumerate(opts):
  for c in o['body']:occ[c].append(i)
 m=cp_model.CpModel();x=[m.NewBoolVar('x'+str(i)) for i in range(n)]
 if encoding=='A':
  for ids in occ.values():m.Add(sum(x[i] for i in ids)<=1)
  for i,o in enumerate(opts):
   for sd in o['sides']:
    count=Counter({i:1})
    for c in sd:count.update(occ[c])
    m.Add(sum(v*x[j] for j,v in count.items())<=len(sd))
 else:
  free={c:m.NewBoolVar('f'+str(k)) for k,c in enumerate(sorted({c for o in opts for sd in o['sides'] for c in sd}))}
  for c,ids in occ.items():m.Add(sum(x[i] for i in ids)+(free[c] if c in free else 0)<=1)
  for i,o in enumerate(opts):
   for sd in o['sides']:m.Add(sum(free[c] for c in sd)>=x[i])
 # Count models use elementary geometric 24/14/8 bounds. General weight uses the independently proved active count <=23 (both count models excluded 24 first).
 m.Add(sum(x)<= (14 if case=='edge' else 8 if case=='corner' else 23 if objective=='weight' else 24))
 m.Add(sum((1 if objective=='count' else o['weight'])*x[i] for i,o in enumerate(opts))>=threshold)
 s=cp_model.CpSolver();s.parameters.num_workers=1;s.parameters.max_time_in_seconds=seconds
 t=time.monotonic();status=s.Solve(m)
 r=dict(case=case,objective=objective,threshold=threshold,encoding=encoding,domain=n,status=s.StatusName(status),seconds=time.monotonic()-t)
 if status in (cp_model.OPTIMAL,cp_model.FEASIBLE):r['witness']=[o['key'] for i,o in enumerate(opts) if s.Value(x[i])]
 (OUT/f'geo_power_{case}_{objective}_{threshold}_{encoding}.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps(r,ensure_ascii=False),flush=True)
if __name__=='__main__':
 if len(sys.argv)>1:run(*sys.argv[1:5],seconds=float(sys.argv[5]) if len(sys.argv)>5 else 120)
 else:
  for encoding in ['A','B']:
   for case,obj,threshold in [('general','count',24),('general','weight',55),('edge','count',14),('edge','weight',30)]+[(f'side{g}','count',c+1) for g,c in enumerate((13,14,14,17,18,19,22))]:run(case,obj,threshold,encoding,120)

