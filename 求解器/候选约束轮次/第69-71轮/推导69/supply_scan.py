#!/usr/bin/env python3
"""Certified local LP bounds for actual pole positions, canonicalized geometry."""
from pathlib import Path
from fractions import Fraction as F
from collections import defaultdict
import json,time,sys
import numpy as np
from scipy.optimize import linprog
from local_power import SHAPES,cells,matrix
OUT=Path(__file__).resolve().parent
OLD=OUT.parents[1]/'第66-68轮'/'推导66'
base=json.loads((OLD/'power_certificates.json').read_text())['17']
def geom(p,q):
 # local supply begins at (p-5,q-5); only cells [-6,17]^2 can matter
 wall=(max(-6,6-p),min(18,75-p),max(-6,6-q),min(18,75-q))
 hole=(max(-6,54-p),max(-6,22-q),18,18)
 return wall,hole

def generate(key):
 wall,hole=key;xmin,xmax,ymin,ymax=wall;hx,hy,_,_=hole;pole=cells((5,5,2,2))
 def legal(c):return xmin<=c[0]<xmax and ymin<=c[1]<ymax and not(c[0]>=hx and c[1]>=hy) and c not in pole
 bodies=[]
 for w,h,axis in SHAPES:
  for x in range(1-w,12):
   for y in range(1-h,12):
    r=(x,y,w,h)
    if not all(legal(c) for c in cells(r)):continue
    sides=([[(x-1,y+k) for k in range(h)],[(x+w,y+k) for k in range(h)]] if axis==0 else [[(x+k,y-1) for k in range(w)],[(x+k,y+h) for k in range(w)]])
    ports=[[c for c in side if legal(c)] for side in sides]
    if all(ports):bodies.append(dict(rect=r,axis=axis,ports=ports))
 return bodies

def lp_certificate(key):
 bodies=generate(key);rows,rhs,labels,A=matrix(bodies);n=len(bodies)
 if not n:return dict(geom=key,n=0,rows=[],bounds=[],upper=[0,1],integer_upper=0)
 r=linprog(-np.ones(n),A_ub=A,b_ub=rhs,bounds=(0,1),method='highs')
 assert r.success,r.message
 y=[max(F(0),F(float(-v)).limit_denominator(1000000)) for v in r.ineqlin.marginals]
 z=[max(F(0),F(float(-v)).limit_denominator(1000000)) for v in r.upper.marginals]; co=z.copy()
 for row,v in zip(rows,y):
  if v:
   for j,t in row.items():co[j]+=t*v
 for j in range(n):
  if co[j]<1:z[j]+=1-co[j]
 upper=sum(v*int(t) for v,t in zip(y,rhs))+sum(z)
 def enc(a):return [[i,v.numerator,v.denominator] for i,v in enumerate(a) if v]
 return dict(geom=key,n=n,rows=enc(y),bounds=enc(z),upper=[upper.numerator,upper.denominator],integer_upper=upper.numerator//upper.denominator)

def run():
 mode=sys.argv[1] if len(sys.argv)>1 else 'all';groups=defaultdict(list)
 for r in base:
  p,q=r['x'],r['y']
  if mode=='strip' and not (p>=43 and q<=16):continue
  if mode=='edge' and not (p in (1,68) or q in (1,68)):continue
  groups[geom(p,q)].append([p,q])
 path=OUT/('supply_'+mode+'_certificates.json')
 certs=json.loads(path.read_text()) if path.exists() else []
 done={tuple(tuple(x) for x in c['geom']) for c in certs}
 print('MODE',mode,'classes',len(groups),'positions',sum(map(len,groups.values())),'already',len(done),flush=True)
 start=time.monotonic()
 for k,ps in groups.items():
  if k in done:continue
  c=lp_certificate(k);c['positions']=ps;certs.append(c)
  path.write_text(json.dumps(certs,separators=(',',':')))
  print(len(certs),len(groups),ps[0],len(ps),c['integer_upper'],round(time.monotonic()-start,2),flush=True)
if __name__=='__main__':run()
