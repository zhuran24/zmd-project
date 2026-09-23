#!/usr/bin/env python3
"""Independent HiGHS formulation. Does not import cp72 or prior model code."""
import os
for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
import json,time,argparse,warnings,hashlib
from pathlib import Path
from collections import defaultdict
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import coo_array
OUT=Path(__file__).resolve().parent;ROUNDS=OUT.parents[1]
def footprint(r):
    x,y,w,h=r
    return [(u,v) for u in range(x,x+w) for v in range(y,y+h)]
def valid(r):
    x,y,w,h=r
    return x>=1 and y>=1 and x+w<=70 and y+h<=70 and (x+w<=49 or y+h<=17)
def open_cell(p):return valid((*p,1,1))
def measured(p):
    x,y=p
    return int(x==69 and 1<=y<=16)+int(y==69 and 1<=x<=48)+int(x==48 and 17<=y<=69)+int(y==16 and 49<=x<=69)
def get_domain(strip=False):
    bs=[]
    for k,w,h,a in [('s',3,3,'h'),('s',3,3,'v'),('m',5,5,'h'),('m',5,5,'v'),('l',6,4,'v'),('l',4,6,'h'),('c',9,9,'h'),('c',9,9,'v')]:
        for x in range(1,71-w):
            for y in range(1,71-h):
                r=(x,y,w,h)
                if not valid(r):continue
                if not any(measured(p) or (strip and p[0]>=49 and p[1]<17) for p in footprint(r)):continue
                if a=='h':sides=[[(x-1,y+t) for t in range(h)],[(x+w,y+t) for t in range(h)]]
                else:sides=[[(x+t,y-1) for t in range(w)],[(x+t,y+h) for t in range(w)]]
                if k=='c':
                    if min(x,y)<2 or (x<=3 and a=='h') or (y<=3 and a=='v') or (x<=3 and y<=3):continue
                    if (y==61 and x<7 and a=='h') or (x==61 and y<7 and a=='v'):continue
                    take=[e[t] for e in sides for t in (1,4,7)]
                    if not all(map(open_cell,take)):continue
                    put=([(x+t,y-1) for t in range(1,8)]+[(x+t,y+9) for t in range(1,8)] if a=='h' else [(x-1,y+t) for t in range(1,8)]+[(x+9,y+t) for t in range(1,8)])
                    ports=[[p] for p in take]+[[p for p in put if open_cell(p)]];need=[1]*6+[2]
                else:ports=[[p for p in s if open_cell(p)] for s in sides];need=[1,1]
                if all(len(e)>=n for e,n in zip(ports,need)):bs.append(dict(kind=k,x=x,y=y,w=w,h=h,axis=a,ports=ports,needs=need,j=0,loss=0))
    gr=json.loads((ROUNDS/'第66-68轮/推导66/power_certificates.json').read_text())['17'];group={(g['x'],g['y']):g['cap'] for g in gr}
    local={}
    for cert in json.loads((ROUNDS/'第69-71轮/推导69/supply_strip_certificates.json').read_text()):
        for xy in cert['positions']:local[tuple(xy)]=cert['integer_upper']
    for x in range(1,69):
        for y in range(1,69):
            if not valid((x,y,2,2)):continue
            e=int(x==1 or x==68)+int(y==1 or y==68)
            capacity=min(group[x,y],local.get((x,y),23),8 if e==2 else 13 if e else 23)
            if 22<=y<=63 and 41<=x<=47:capacity=min(capacity,[13,14,14,17,18,19,22][47-x])
            if 54<=x<=63 and 9<=y<=15:capacity=min(capacity,[13,14,14,17,18,19,22][15-y])
            if capacity>=10:bs.append(dict(kind='p',x=x,y=y,w=2,h=2,axis='-',ports=[],needs=[],j=int(e>0),loss=23-capacity))
    return bs
class Matrix:
    def __init__(self):self.lb=[];self.ub=[];self.integrality=[];self.rr=[];self.cc=[];self.vv=[];self.lo=[];self.hi=[];self.labels=[]
    def var(self,lo=0,hi=1,integer=1):
        n=len(self.lb);self.lb.append(lo);self.ub.append(hi);self.integrality.append(integer);return n
    def row(self,pairs,lo=-np.inf,hi=np.inf,label=''):
        r=len(self.lo);d=defaultdict(int)
        for c,v in pairs:d[c]+=v
        for c,v in d.items():
            if v:self.rr.append(r);self.cc.append(c);self.vv.append(v)
        self.lo.append(lo);self.hi.append(hi);self.labels.append(label)
    def matrix(self):return coo_array((np.array(self.vv,dtype=float),(np.array(self.rr,dtype=np.int32),np.array(self.cc,dtype=np.int32))),shape=(len(self.lo),len(self.lb))).tocsc()
def build(strip=False,fixed_j=None,cap=None,project=False,groups=False):
    bs=get_domain(strip)
    if project:
        machines=[b for b in bs if b['kind'] in ('s','m','l')]
        bs=[p for p in bs if p['kind']!='p' or p['j'] or any(measured(c) for c in footprint((p['x'],p['y'],2,2))) or any(p['x']-5<d['x']+d['w'] and d['x']<p['x']+7 and p['y']-5<d['y']+d['h'] and d['y']<p['y']+7 for d in machines)]
    m=Matrix();vs=[m.var() for _ in bs];inc=defaultdict(list)
    for i,b in enumerate(bs):
        for p in footprint(tuple(b[k] for k in ('x','y','w','h'))):inc[p].append(i)
    occ={p:m.var(integer=0) for p in inc}
    for p,v in occ.items():m.row([(v,1)]+[(i,-1) for i in inc[p]],0,0,'occupancy')
    for i,b in enumerate(bs):
        for ps,need in zip(b['ports'],b['needs']):m.row([(i,need)]+[(occ[p],1) for p in ps if p in occ],hi=len(ps),label='port')
    gaps=[[m.var() for _ in range(24)] for _ in range(2)]
    for axis in range(2):
        m.row([(v,1) for v in gaps[axis]],1,1,'one warehouse gap')
        for k,g in enumerate(gaps[axis]):
            spans=[(3*i,3*i+3) if i<k else (3*i+1,3*i+4) for i in range(23)]
            for a,z in spans:
                p=(1,a+1) if axis==0 else (a+1,1)
                if p in occ:m.row([(g,1),(occ[p],1)],hi=1,label='mineral neighbor')
    m.row([(gaps[0][0],1),(gaps[1][0],1)],lo=1,label='common corner')
    exceptions=[]
    for i,b in enumerate(bs):
        if b['kind']!='l':continue
        dirs=[m.var(),m.var()];ex=m.var();exceptions.append(ex)
        m.row([(d,1) for d in dirs]+[(i,-1)],0,0,'large input orientation');m.row([(ex,1),(i,-1)],hi=0)
        for ps,di in zip(b['ports'],dirs):m.row([(occ[p],1) for p in ps if p in occ]+[(di,3),(ex,-1)],hi=len(ps),label='large inputs')
    m.row([(e,1) for e in exceptions],hi=1,label='one two-channel large')
    pp=[i for i,b in enumerate(bs) if b['kind']=='p'];mm=[i for i,b in enumerate(bs) if b['kind'] in ('s','m','l')]
    m.row([(i,1) for i in pp],0 if project else 10,10,'ten poles')
    if fixed_j is not None:m.row([(i,bs[i]['j']) for i in pp],fixed_j,fixed_j,'J branch')
    for k,n in [('s',131),('m',48),('l',38),('c',1)]:m.row([(i,1) for i,b in enumerate(bs) if b['kind']==k],hi=n,label='count')
    repeats=[]
    for i in mm:
        b=bs[i];x,y,w,h=(b[k] for k in ('x','y','w','h'))
        cover=[j for j in pp if bs[j]['x']-5<x+w and x<bs[j]['x']+7 and bs[j]['y']-5<y+h and y<bs[j]['y']+7]
        z=m.var(0,9,1);repeats.append(z)
        m.row([(j,1) for j in cover]+[(i,-1)],lo=0,label='power coverage')
        m.row([(j,1) for j in cover]+[(i,9),(z,-1)],hi=10,label='actual duplication')
        m.row([(z,1),(i,1)]+[(j,-1) for j in cover],hi=0,label='exact selected duplication')
        m.row([(z,1),(i,-9)],hi=0,label='inactive repeat zero')
    m.row([(z,1) for z in repeats]+[(i,bs[i]['loss']) for i in pp],hi=13,label='capacity plus duplication')
    lines=[{(69,y) for y in range(1,17)},{(x,69) for x in range(1,49)},{(48,y) for y in range(17,70)},{(x,16) for x in range(49,70)}]
    tabs=json.loads((ROUNDS/'第69-71轮/推导69/new_edge_local_certificate.json').read_text())['cases'][0]['lines']
    for line,tab in zip(lines,tabs):
        meet=[i for i,b in enumerate(bs) if line.intersection(footprint(tuple(b[k] for k in ('x','y','w','h'))))]
        options=[(state,value) for state,value in tab['frontier'] if state[2]<=13];ss=[m.var() for _ in options]
        m.row([(v,1) for v in ss],1,1,'one projection state')
        for dimension,k in [(0,'c'),(1,'p')]:m.row([(i,1) for i in meet if bs[i]['kind']==k]+[(v,-state[dimension]) for v,(state,g) in zip(ss,options)],0,0,'projection count')
        m.row([(i,bs[i]['loss']) for i in meet if bs[i]['kind']=='p']+[(v,-state[2]) for v,(state,g) in zip(ss,options)],lo=0,label='projection loss floor')
        m.row([(i,len(line.intersection(footprint(tuple(bs[i][k] for k in ('x','y','w','h')))))+2*bs[i]['j']) for i in meet]+[(v,g) for v,(state,g) in zip(ss,options)],hi=len(line),label='projection gap floor')
    if groups:
        assert not project
        for a in range(3):
            for b in range(3):
                incid=defaultdict(list)
                for i in pp:
                    p=bs[i];px,py=p['x'],p['y'];reachable=set()
                    for cx in range(2,69):
                        if not(px-6<=cx<=px+7):continue
                        for cy in range(max(2,py-6),min(68,py+7)+1):
                            r=(cx-1,cy-1,3,3)
                            if not valid(r):continue
                            if cx-1<px+2 and px<cx+2 and cy-1<py+2 and py<cy+2:continue
                            reachable.add(((cx+a)//3,(cy+b)//3))
                    for g in reachable:incid[g].append(i)
                flags=[]
                for indices in incid.values():
                    v=m.var();flags.append(v);m.row([(v,1)]+[(i,-1) for i in indices],hi=0,label='global center group available')
                m.row([(v,1) for v in flags],lo=217,label='217 distinct center groups')
    objective=np.zeros(len(m.lb))
    for i,b in enumerate(bs):objective[i]=-sum(measured(p) for p in footprint(tuple(b[k] for k in ('x','y','w','h'))))-2*b['j']
    constant=160+16+48+53+21
    if cap is not None:m.row([(i,int(v)) for i,v in enumerate(objective) if v],hi=cap-constant,label='S cap')
    # No imported R69 lower bound: independently solve or certify a threshold.
    return m,bs,objective,constant,gaps
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--seconds',type=float,default=300);p.add_argument('--j',type=int);p.add_argument('--cap',type=int);p.add_argument('--strip',action='store_true');p.add_argument('--name',default='mip72');p.add_argument('--project',action='store_true');p.add_argument('--groups',action='store_true');a=p.parse_args()
    start=time.monotonic();m,bs,obj,constant,gaps=build(a.strip,a.j,a.cap,a.project,a.groups);A=m.matrix();built=time.monotonic()-start
    print('BUILT',len(bs),'units',A.shape,'matrix',A.nnz,'nonzeros',flush=True)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore');r=milp(obj,integrality=m.integrality,bounds=Bounds(m.lb,m.ub),constraints=LinearConstraint(A,m.lo,m.hi),options={'time_limit':a.seconds,'threads':1,'mip_rel_gap':0.0,'disp':True})
    out=dict(solver='SciPy HiGHS',version=__import__('scipy').__version__,status=int(r.status),message=r.message,seconds=time.monotonic()-start,build_seconds=built,branch_J=a.j,strip=a.strip,project=a.project,groups=a.groups,cap=a.cap,domain_count=len(bs),domain_sha256=hashlib.sha256(json.dumps(bs,sort_keys=True).encode()).hexdigest(),matrix_sha256=hashlib.sha256(A.data.tobytes()+A.indices.tobytes()+A.indptr.tobytes()+np.array(m.lo).tobytes()+np.array(m.hi).tobytes()).hexdigest(),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    if getattr(r,'mip_dual_bound',None) is not None:out['lower']=float(r.mip_dual_bound+constant)
    if r.x is not None:
        vals=r.x.copy();integer=np.array(m.integrality)==1;vals[integer]=np.rint(vals[integer]);act=A@vals
        assert max(np.max(np.array(m.lo)-act),np.max(act-np.array(m.hi)))<1e-5
        out.update(S=round(obj@vals+constant),warehouse_gaps=[3*next(k for k,g in enumerate(gs) if vals[g]>.5) for gs in gaps],chosen=[b for i,b in enumerate(bs) if vals[i]>.5])
    (OUT/(a.name+'.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='chosen'},ensure_ascii=False),flush=True)
