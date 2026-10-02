#!/usr/bin/env python3
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import json,sys,hashlib
from pathlib import Path
BASE=Path(__file__).resolve().parents[1];seat=sys.argv[1];p=Path(sys.argv[2]);d=json.loads(p.read_text());sys.path.insert(0,str(BASE/f'旧检查器{seat}'))
# Geometry only, never the old formal-constraint ledger or old runtime contract.
d['design']['class']='n_restricted'
if seat=='A':
 from geometry import Geometry
 class R:
  def __init__(self):self.records=[]
  def check(self,code,ok,basis,detail):self.records.append(dict(code=code,ok=bool(ok),basis=basis,detail=detail))
  def na(self,*a):pass
  def blocked(self,*a):pass
  def alias(self,*a):pass
 r=R();g=Geometry(d,r).build();edges=g.channels;maximum=g.maximum;power=g.power;records=r.records;occupied=len(g.occ)
else:
 from geometry import Checks,Geometry,structural,check_rectangle
 r=Checks();g=Geometry(d['layout'],r);structural(d,g,r);maximum=check_rectangle(d,g,r);edges=g.edges;power=g.powered;records=r.records;occupied=len(g.occ)
 def cn(e):return tuple(e[k][z] for k in ['from','to'] for z in ['unit','side','offset'])
actual={(*a,*b) for a,b in edges};declared={tuple(e[k][z] for k in ['from','to'] for z in ['unit','side','offset']) for e in d['design']['physical_channels']}
r=dict(checker=seat,candidate_sha256=hashlib.sha256(p.read_bytes()).hexdigest(),scope='适配后的独立几何组件；不是旧CLI静态通过，也不是77条与动态运行认证。',occupied_cells=occupied,channels=len(edges),channels_equal_claimed=actual==declared,maximum_empty_rectangle=maximum,powered_machines=sum(bool(v) for v in power.values()),unpowered=[u for u,v in power.items() if not v],records=records,static_certified=False)
(BASE/f'证据/旧检查器{seat}-几何.json').write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in r.items() if k!='records'},ensure_ascii=False))
