"""Round 79: independent interval enumeration and expanded sparse integer rows."""
import os
os.environ['OMP_NUM_THREADS']='1'
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
os.sched_setaffinity(0,set(range(10)))
import argparse,json,time,hashlib,warnings
from collections import defaultdict,Counter
from pathlib import Path
import numpy as np
from scipy.optimize import milp,Bounds,LinearConstraint
from scipy.sparse import coo_matrix,save_npz

OUT=Path(__file__).resolve().parent

def build(wall):
    choices=[]
    for w,h,axis,k in [(3,3,0,'s'),(3,3,1,'s'),(5,5,0,'m'),(5,5,1,'m'),(6,4,1,'l'),(4,6,0,'l')]:
        for yy in range(1-h,12):
            for xx in range(1-w,12):
                if max(xx,5)<min(xx+w,7) and max(yy,5)<min(yy+h,7):continue
                if wall and xx+w>7:continue
                ports=[]
                for side in (0,1):
                    if axis==0:candidates=[(xx-1 if side==0 else xx+w,t) for t in range(yy,yy+h)]
                    else:candidates=[(t,yy-1 if side==0 else yy+h) for t in range(xx,xx+w)]
                    ports.append([p for p in candidates if not(5<=p[0]<7 and 5<=p[1]<7) and (not wall or p[0]<7)])
                if not all(ports):continue
                choices.append(dict(kind=k,x=xx,y=yy,w=w,h=h,axis=axis,sides=ports))
    covering=defaultdict(list)
    for i,d in enumerate(choices):
        for xx in range(d['x'],d['x']+d['w']):
            for yy in range(d['y'],d['y']+d['h']):covering[xx,yy].append(i)
    rows=[];upper=[]
    for c in sorted(covering):rows.append({j:1 for j in covering[c]});upper.append(1)
    for i,d in enumerate(choices):
        for side in d['sides']:
            r=Counter({i:1})
            for c in side:r.update(covering.get(tuple(c),[]))
            rows.append(dict(r));upper.append(len(side))
    rows.append({i:1 for i in range(len(choices))});upper.append(14 if wall else 23)
    return choices,rows,upper

def main(wall,threshold,seconds):
    start=time.monotonic();choices,rows,upper=build(wall);n=len(choices)
    label=('wall' if wall else 'general')+('_opt' if threshold is None else '_ge'+str(threshold))
    weights=np.array([2 if d['kind']=='s' else 3 for d in choices])
    base_rows=len(rows)
    if threshold is not None:rows.append({i:-int(v) for i,v in enumerate(weights)});upper.append(-threshold)
    rr=[];cc=[];vv=[]
    for i,r in enumerate(rows):
        for j,v in r.items():rr.append(i);cc.append(j);vv.append(v)
    mat=coo_matrix((np.array(vv,dtype=float),(rr,cc)),shape=(len(rows),n)).tocsc()
    save_npz(OUT/(label+'_milp_matrix.npz'),mat)
    (OUT/(label+'_milp_rows.json')).write_text(json.dumps(dict(rows=[sorted(r.items()) for r in rows],upper=upper),separators=(',',':')))
    (OUT/(label+'_milp_domain.json')).write_text(json.dumps(choices,separators=(',',':')))
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        res=milp(-weights if threshold is None else np.zeros(n),integrality=np.ones(n),bounds=Bounds(np.zeros(n),np.ones(n)),constraints=LinearConstraint(mat,-np.inf,np.array(upper)),options=dict(time_limit=seconds,mip_rel_gap=0,threads=1,disp=True))
    result=dict(encoding='expanded_integer_linear',wall=wall,threshold=threshold,options=n,base_rows=base_rows,status=int(res.status),message=res.message,wall_seconds=time.monotonic()-start)
    if res.x is not None:
        chosen=np.rint(res.x).astype(int);assert max(mat@chosen-np.array(upper))<1e-7
        selected=[d for d,x in zip(choices,chosen) if x]
        result.update(weight=int(weights@chosen),counts=dict(Counter(d['kind'] for d in selected)),witness=selected)
    (OUT/(label+'_milp.json')).write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k!='witness'}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--wall',action='store_true');p.add_argument('--threshold',type=int);p.add_argument('--seconds',type=float,default=300);a=p.parse_args();main(a.wall,a.threshold,a.seconds)
