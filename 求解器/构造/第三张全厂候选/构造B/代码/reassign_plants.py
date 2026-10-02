import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,sys
from pathlib import Path
from collections import deque
from scipy.optimize import linear_sum_assignment
from pack_factory import BASE,C,cells,machine,D
from route_factory import ports
p=Path(sys.argv[1]);d=json.loads(p.read_text());l=d['layout'];r=d['reserved_rectangle'];groups=[('S',j) for j in range(1,14)]+[('Q',j) for j in range(1,7)]
by={u['id']:u for u in l['machines']};out,inc=ports(l);blocked=set(q for u in l['machines']+l['warehouse_outlets']+l['power_poles']+[l['core'],r] for q in cells(u))
cost=[]
for prefix,j in groups:
 crusher=f'S{j}' if prefix=='S' else f'KQ{j}';goals=[q for q,di,ref in inc[crusher] if q not in blocked and 0<=q[0]<70 and 0<=q[1]<70]
 dist={q:0 for q in goals};queue=deque(goals)
 while queue:
  q=queue.popleft()
  for dx,dy in D:
   n=(q[0]+dx,q[1]+dy)
   if 0<=n[0]<70 and 0<=n[1]<70 and n not in blocked and n not in dist:dist[n]=dist[q]+1;queue.append(n)
 row=[]
 for op,oj in groups:
  starts=[q for q,di,ref in out[f'{op}B{oj}'] if q not in blocked and 0<=q[0]<70 and 0<=q[1]<70]
  vals=[dist[q] for q in starts if q in dist]
  row.append(min(vals)+1 if vals else 10000)
 cost.append(row)
ri,ci=linear_sum_assignment(cost);replacement={};mapping=[]
for i,j in zip(ri,ci):
 newp,newj=groups[i];oldp,oldj=groups[j]
 for role in 'ABC':
  newuid=f'{newp}{role}{newj}';old=by[f'{oldp}{role}{oldj}'];replacement[newuid]=machine(newuid,old['x0'],old['y0'],old['Din'])
 mapping.append(dict(logical=f'{newp}{newj}',geometry_from=f'{oldp}{oldj}',relaxed_BK_distance=int(cost[i][j])))
l['machines']=[replacement.get(u['id'],u) for u in l['machines']];d['plant_permutation']=mapping
path=p.with_name(p.stem+'-plants.json');path.write_text(json.dumps(d,ensure_ascii=False,indent=2));print(path,'reachable',sum(q['relaxed_BK_distance']<10000 for q in mapping),'sum',sum(q['relaxed_BK_distance'] for q in mapping))
