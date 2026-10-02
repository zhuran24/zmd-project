#!/usr/bin/env python3
from pathlib import Path
import os,runpy,json,hashlib,time
os.sched_setaffinity(0,{min(os.sched_getaffinity(0))})
for v in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[v]='1'
P=Path(__file__).resolve().parent
cp=runpy.run_path(str(P/'counts_ore_cp_model.py'))['solve']
highs=runpy.run_path(str(P/'counts_ore_highs_model.py'))['solve']
rows=[]
for a,b in [(g,0) for g in range(0,70,3)]+[(0,g) for g in range(3,70,3)]:
 x=cp(a,b,n=23,cutoff=9,budget=7)
 y=highs(a,b)
 rows.append({'gap':[a,b],'cp':x,'highs':y})
 print(json.dumps({'gap':[a,b],'cp_status':x['status'],'highs_status':y['status'],'cp_seconds':x['wall_time'],'highs_seconds':y['seconds']},ensure_ascii=False),flush=True)
 (P/'counts_ore_verify.json').write_text(json.dumps({'cases':rows,'complete':len(rows)==47},ensure_ascii=False,indent=2)+'\n')
 assert x['status']=='INFEASIBLE' and y['status']==2
assert len(rows)==47
print('PASS: 47 configurations independently infeasible at excess <= 7.',flush=True)
