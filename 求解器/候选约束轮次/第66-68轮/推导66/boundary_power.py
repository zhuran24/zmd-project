#!/usr/bin/env python3
"""Boundary geometry with all pole positions and certified power upper bounds.
Numerical MIP results are exploration only; no infeasibility claim from status.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1'
import sys,json,time,hashlib,argparse,warnings
from pathlib import Path
from collections import defaultdict,Counter
import numpy as np
from scipy.optimize import milp,linprog,Bounds,LinearConstraint
from scipy.sparse import coo_array
from power_bound import OUT,ROOT,cells,legal_poles

def measures(b):
    hole=cells(49,b,21,53)
    X=Counter({(69,y):1 for y in range(1,69) if (69,y) not in hole})
    X.update({(x,69):1 for x in range(1,69) if (x,69) not in hole})
    if (69,69) not in hole:X[69,69]=2
    Y=Counter({(48,y):1 for y in range(b,b+53)})
    Y.update({(x,b-1):1 for x in range(49,70)})
    if b+53<70:Y.update({(x,b+53):1 for x in range(49,70)})
    return X,Y

def formal_loss(x,y,b):
    edges=(x in (1,68))+(y in (1,68)); loss=(0,9,15)[edges]
    if b<=y-5 and y+7<=b+53:
      g=49-x-2
      if 0<=g<=6:loss=max(loss,(10,9,9,6,5,4,1)[g])
    if 49<=x-5 and x+7<=70:
      g=b-y-2 if y+2<=b else y-(b+53)
      if 0<=g<=6:loss=max(loss,(10,9,9,6,5,4,1)[g])
    return int(edges>0),loss

def generate(b,extra_strips=False):
    X,Y=measures(b);target=set(X)|set(Y);hole=cells(49,b,21,53)
    if extra_strips:target|=cells(49,1,21,b-1)|cells(49,b+53,21,17-b)
    def legal(c):return 1<=c[0]<70 and 1<=c[1]<70 and c not in hole
    bodies=[]
    for kind,w,h,axis in [('s',3,3,'h'),('s',3,3,'v'),('m',5,5,'h'),('m',5,5,'v'),('l',6,4,'v'),('l',4,6,'h'),('c',9,9,'h'),('c',9,9,'v')]:
      anchors={(cx-dx,cy-dy) for cx,cy in target for dx in range(w) for dy in range(h)}
      for x,y in sorted(anchors):
        if not(1<=x<=70-w and 1<=y<=70-h):continue
        body=cells(x,y,w,h)
        if body&hole:continue
        if kind=='c' and x<=3 and y<=3:continue
        if axis=='h':edges=[[(x-1,j) for j in range(y,y+h)],[(x+w,j) for j in range(y,y+h)]]
        else:edges=[[(i,y-1) for i in range(x,x+w)],[(i,y+h) for i in range(x,x+w)]]
        if kind=='c':
          takes=[c for e in edges for d,c in enumerate(e) if d in (1,4,7)]
          if not all(legal(c) for c in takes):continue
          puts=([ (i,j) for i in range(x+1,x+8) for j in (y-1,y+9)] if axis=='h' else [(i,j) for i in (x-1,x+9) for j in range(y+1,y+8)])
          edges=[ [c] for c in takes]+[[c for c in puts if legal(c)]];needs=[1]*6+[2]
        else:edges=[[c for c in e if legal(c)] for e in edges];needs=[1,1]
        if any(len(e)<n for e,n in zip(edges,needs)):continue
        bodies.append(dict(kind=kind,x=x,y=y,w=w,h=h,axis=axis,ports=edges,needs=needs,j=0,loss=0))
    caps={(r['x'],r['y']):r['cap'] for r in json.loads((OUT/'power_certificates.json').read_text())[str(b)]}
    for x,y in legal_poles(b):
      j,loss=formal_loss(x,y,b)
      bodies.append(dict(kind='p',x=x,y=y,w=2,h=2,axis='-',ports=[],needs=[],j=j,loss=max(loss,23-caps[x,y])))
    return bodies,X,Y

class Model:
 def __init__(self):self.names=[];self.lb=[];self.ub=[];self.integ=[];self.rows=[];self.lo=[];self.hi=[];self.labels=[]
 def var(self,name,lb=0,ub=float('inf'),integer=False):
  i=len(self.names);self.names.append(name);self.lb.append(lb);self.ub.append(ub);self.integ.append(int(integer));return i
 def row(self,pairs,lo=-float('inf'),hi=float('inf'),label=''):
  d=defaultdict(float)
  for i,v in pairs:d[i]+=v
  self.rows.append({i:v for i,v in d.items() if v});self.lo.append(lo);self.hi.append(hi);self.labels.append(label)
 def matrix(self):
  rr=[];cc=[];vv=[]
  for j,r in enumerate(self.rows):
   for i,v in r.items():rr.append(j);cc.append(i);vv.append(v)
  return coo_array((np.array(vv),(np.array(rr,dtype=np.int32),np.array(cc,dtype=np.int32))),shape=(len(self.rows),len(self.names))).tocsc()

def build(b,P,extra=False,cover=True):
    bodies,X,Y=generate(b,extra);m=Model();sv=[m.var('body:'+str(i),0,1,True) for i in range(len(bodies))]
    incidence=defaultdict(list)
    for i,d in enumerate(bodies):
      for c in cells(d['x'],d['y'],d['w'],d['h']):incidence[c].append(i)
    occ={c:m.var('occ:'+str(c),0,1) for c in sorted(incidence)}
    for c,v in occ.items():m.row([(v,1)]+[(sv[i],-1) for i in incidence[c]],0,0,'occupancy')
    for i,d in enumerate(bodies):
      for e,n in zip(d['ports'],d['needs']):m.row([(sv[i],n)]+[(occ[c],1) for c in e if c in occ],hi=len(e),label='port')
    poles=[i for i,d in enumerate(bodies) if d['kind']=='p']
    m.row([(sv[i],1) for i in poles],P,P,'P')
    m.row([(sv[i],bodies[i]['loss']) for i in poles],hi=23*P-217,label='power capacity')
    for kind,lim in [('s',131),('m',48),('l',38),('c',1)]:m.row([(sv[i],1) for i,d in enumerate(bodies) if d['kind']==kind],hi=lim,label='count')
    if cover:
      for i,d in enumerate(bodies):
        if d['kind'] not in ('s','m','l'):continue
        eligible=[j for j in poles if d['x']-6<=bodies[j]['x']<=d['x']+d['w']+4 and d['y']-6<=bodies[j]['y']<=d['y']+d['h']+4]
        m.row([(sv[i],1)]+[(sv[j],-1) for j in eligible],hi=0,label='power coverage')
    weights=X+Y;constant=16*P+sum(weights.values())
    cost={sv[i]:-sum(weights[c] for c in cells(d['x'],d['y'],d['w'],d['h']))-2*d['j'] for i,d in enumerate(bodies)}
    return m,bodies,sv,occ,cost,constant

def solve(b,P,seconds=60,extra=False,cap=False):
    start=time.monotonic();m,bodies,sv,occ,cost,constant=build(b,P,extra)
    if cap:m.row(list(cost.items()),hi=187-constant,label='area budget')
    c=np.zeros(len(m.names))
    if not cap:
      for i,v in cost.items():c[i]=v
    A=m.matrix();built=time.monotonic()-start
    with warnings.catch_warnings():
      warnings.simplefilter('ignore')
      r=milp(c,integrality=m.integ,bounds=Bounds(m.lb,m.ub),constraints=LinearConstraint(A,m.lo,m.hi),options={'time_limit':seconds,'threads':1,'mip_rel_gap':0.0,'disp':False})
    out=dict(b=b,P=P,seconds=time.monotonic()-start,build_seconds=built,status=int(r.status),message=r.message,vars=len(m.names),rows=len(m.rows),extra=extra,cap=cap)
    if getattr(r,'mip_dual_bound',None) is not None:out['numerical_bound']=r.mip_dual_bound+ (constant if not cap else 0)
    if r.x is not None:
      out['objective']=float(r.fun+ (constant if not cap else 0));out['chosen']=[d for i,d in enumerate(bodies) if r.x[sv[i]]>.5]
      out['numerical_max_violation']=max(float(np.max(np.array(m.lo)-A@r.x)),float(np.max(A@r.x-np.array(m.hi))))
    (OUT/f'boundary_power_b{b}_P{P}.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in out.items() if k!='chosen'},ensure_ascii=False),flush=True)
    return out
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('b',type=int);p.add_argument('P',type=int);p.add_argument('--seconds',type=float,default=60);p.add_argument('--extra',action='store_true');p.add_argument('--cap',action='store_true');a=p.parse_args();solve(a.b,a.P,a.seconds,a.extra,a.cap)
