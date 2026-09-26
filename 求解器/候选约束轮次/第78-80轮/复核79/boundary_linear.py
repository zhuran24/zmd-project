"""Round 79 second global encoding: full-anchor rectangles and integer rows.
No cell Boolean variables, no producer scripts, no old edge tables.
"""
import os
os.environ['OPENBLAS_NUM_THREADS']='1';os.environ['OMP_NUM_THREADS']='1';os.environ['MKL_NUM_THREADS']='1'
os.sched_setaffinity(0,set(range(10)))
import json,time,argparse,hashlib,warnings
from pathlib import Path
from collections import Counter,defaultdict
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_matrix,save_npz

OUT=Path(__file__).resolve().parent
EDGE=Counter([(69,y) for y in range(1,17)]+[(x,69) for x in range(1,49)]+[(48,y) for y in range(17,70)]+[(x,16) for x in range(49,70)])
def inter(r,s):
    x,y,w,h=r;u,v,a,b=s
    return x<u+a and u<x+w and y<v+b and v<y+h
def good(x,y):return 1<=x<70 and 1<=y<70 and (x<49 or y<17)
def ports(x,y,w,h,a):
    return [[(x-1,y+k) for k in range(h)],[(x+w,y+k) for k in range(h)]] if a==0 else [[(x+k,y-1) for k in range(w)],[(x+k,y+h) for k in range(w)]]

def enumerate_units():
    units=[]
    for k,w,h,a in [('s',3,3,0),('s',3,3,1),('m',5,5,0),('m',5,5,1),('l',6,4,1),('l',4,6,0),('c',9,9,0),('c',9,9,1)]:
        for y in range(1,71-h):
            for x in range(1,71-w):
                r=[x,y,w,h]
                if inter(r,[49,17,21,53]):continue
                score=sum(v for (u,t),v in EDGE.items() if x<=u<x+w and y<=t<y+h)
                if score==0:continue
                p=ports(x,y,w,h,a)
                if k=='c':
                    if x==1 or y==1 or (x<4 and y<4):continue
                    if a==0 and (x<4 or (y==61 and x<7)):continue
                    if a==1 and (y<4 or (x==61 and y<7)):continue
                    take=[s[i] for s in p for i in [1,4,7]]
                    if not all(good(*c) for c in take):continue
                    store=[s[i] for s in ports(x,y,9,9,1-a) for i in range(1,8) if good(*s[i])]
                    pp=[([c],1) for c in take]+[(store,2)]
                else:pp=[([c for c in s if good(*c)],1) for s in p]
                if any(len(s)<need for s,need in pp):continue
                units.append(dict(kind=k,r=r,axis=a,ports=pp,loss=0,j=0,score=score))
    machines=[u for u in units if u['kind']!='c'];pcount=0
    for rec in json.loads((OUT/'capacities.json').read_text()):
        if rec['cap']<10:continue
        x,y=rec['p'];pcount+=1;r=[x,y,2,2];j=int(x==1 or y==1 or x==68 or y==68)
        score=sum(v for (u,t),v in EDGE.items() if x<=u<x+2 and y<=t<y+2)
        supply=[x-5,y-5,12,12]
        if not(j or score or any(inter(supply,m['r']) for m in machines)):continue
        units.append(dict(kind='p',r=r,axis=-1,ports=[],loss=23-rec['cap'],j=j,score=score))
    return units,pcount

def build(cap,exact):
    units,full=enumerate_units();bounds=[(0,1) for u in units];rows=[]
    def var(lo=0,hi=1):bounds.append((lo,hi));return len(bounds)-1
    def add(terms,lo=None,hi=None):
        r=Counter()
        for i,c in terms:r[i]+=c
        rows.append(([(i,c) for i,c in sorted(r.items()) if c],lo,hi))
    occ=defaultdict(list)
    for i,u in enumerate(units):
        x,y,w,h=u['r']
        for xx in range(x,x+w):
            for yy in range(y,y+h):occ[xx,yy].append(i)
    def occupied(ps):return [(i,1) for c in ps for i in occ.get(tuple(c),[])]
    for ls in occ.values():add([(i,1) for i in ls],hi=1)
    for i,u in enumerate(units):
        for side,need in u['ports']:add(occupied(side)+[(i,need)],hi=len(side))
    flags=[]
    for a in (0,1):
        fs=[var() for _ in range(24)];flags.append(fs);add([(f,1) for f in fs],1,1)
        for k,f in enumerate(fs):
            strip=[z for z in range(70) if z!=3*k]
            source=[strip[3*i+1] for i in range(23)]
            for z in source:add(occupied([(1,z) if a==0 else (z,1)])+[(f,1)],hi=1)
    add([(flags[0][0],1),(flags[1][0],1)],lo=1)
    weak=[]
    for i,u in enumerate(units):
        if u['kind']!='l':continue
        dirs=[var(),var()];ex=var();weak.append(ex)
        add([(d,1) for d in dirs]+[(i,-1)],0,0);add([(ex,1),(i,-1)],hi=0)
        for d,(ps,_) in zip(dirs,u['ports']):add(occupied(ps)+[(d,3),(ex,-1)],hi=len(ps))
    add([(x,1) for x in weak],hi=1)
    poles=[i for i,u in enumerate(units) if u['kind']=='p']
    add([(i,1) for i in poles],hi=10)
    add([(i,units[i]['j']) for i in poles],1,1)
    add([(i,1) for i in poles if units[i]['r'][0]==1 or units[i]['r'][1]==1],1,1)
    for k,n in [('s',131),('m',48),('l',38),('c',1)]:add([(i,1) for i,u in enumerate(units) if u['kind']==k],hi=n)
    repeats=[]
    for i,u in enumerate(units):
        if u['kind'] not in ('s','m','l'):continue
        cp=[j for j in poles if inter(u['r'],[units[j]['r'][0]-5,units[j]['r'][1]-5,12,12])]
        add([(j,1) for j in cp]+[(i,-1)],lo=0)
        z=var(0,9);repeats.append(z)
        add([(j,1) for j in cp]+[(z,-1),(i,10)],hi=11)
    add([(z,1) for z in repeats]+[(i,units[i]['loss']) for i in poles],hi=13)
    add([(i,u['score']) for i,u in enumerate(units)],296-cap,296-cap if exact else None)
    return units,full,bounds,rows

def main():
    p=argparse.ArgumentParser();p.add_argument('--cap',type=int,default=186);p.add_argument('--exact',action='store_true');p.add_argument('--engine',choices=['highs','cp'],default='highs');p.add_argument('--seconds',type=float,default=300);a=p.parse_args()
    start=time.monotonic();units,full,bounds,rows=build(a.cap,a.exact);label='boundary_'+('eq' if a.exact else 'le')+str(a.cap)+'_linear_'+a.engine
    raw=json.dumps(dict(bounds=bounds,rows=rows),separators=(',',':'))
    (OUT/(label+'_model.json')).write_text(raw);(OUT/(label+'_domain.json')).write_text(json.dumps(units,separators=(',',':')))
    result=dict(engine=a.engine,cap=a.cap,exact=a.exact,units=len(units),full_poles=full,domain=dict(Counter(u['kind'] for u in units)),variables=len(bounds),rows=len(rows),model_sha256=hashlib.sha256(raw.encode()).hexdigest())
    vals=None
    if a.engine=='highs':
        ii=[];jj=[];vv=[];lower=[];upper=[]
        for i,(terms,lo,hi) in enumerate(rows):
            lower.append(-np.inf if lo is None else lo);upper.append(np.inf if hi is None else hi)
            for j,c in terms:ii.append(i);jj.append(j);vv.append(c)
        A=coo_matrix((np.array(vv,float),(ii,jj)),shape=(len(rows),len(bounds))).tocsc();save_npz(OUT/(label+'_matrix.npz'),A)
        obj=np.zeros(len(bounds));obj[:len(units)]=[-u['score'] for u in units]
        with warnings.catch_warnings():
            warnings.simplefilter('ignore')
            res=milp(obj,integrality=np.ones(len(bounds)),bounds=Bounds(*zip(*bounds)),constraints=LinearConstraint(A,lower,upper),options=dict(threads=1,disp=True,time_limit=a.seconds,mip_rel_gap=0))
        result.update(status={0:'OPTIMAL',1:'UNKNOWN',2:'INFEASIBLE'}.get(res.status,str(res.status)),message=res.message)
        if res.x is not None:vals=list(map(int,np.rint(res.x)))
    else:
        from ortools.sat.python import cp_model
        m=cp_model.CpModel();vs=[m.new_int_var(lo,hi,str(i)) for i,(lo,hi) in enumerate(bounds)]
        for terms,lo,hi in rows:
            exp=sum(c*vs[i] for i,c in terms)
            if lo is not None:m.add(exp>=lo)
            if hi is not None:m.add(exp<=hi)
        solver=cp_model.CpSolver();solver.parameters.num_search_workers=1;solver.parameters.max_time_in_seconds=a.seconds
        solver.parameters.log_search_progress=True;solver.parameters.subsolvers.append('quick_restart');solver.parameters.linearization_level=2
        st=solver.solve(m);result.update(status=solver.status_name(st),stats=solver.response_stats())
        if st in (cp_model.OPTIMAL,cp_model.FEASIBLE):vals=[solver.value(v) for v in vs]
    if vals is not None:
        for (lo,hi),x in zip(bounds,vals):assert lo<=x<=hi
        for terms,lo,hi in rows:
            z=sum(c*vals[i] for i,c in terms);assert (lo is None or z>=lo) and (hi is None or z<=hi)
        result.update(S=296-sum(u['score']*vals[i] for i,u in enumerate(units)),chosen=[u for i,u in enumerate(units) if vals[i]])
    result['seconds']=time.monotonic()-start;(OUT/(label+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ('stats','chosen')}),flush=True)

if __name__=='__main__':main()
