"""Independent interval-conflict MILP corner relaxation; no A imports.
HiGHS is limited to one thread. Exact integer witnesses are checked afterwards.
"""
import os
os.environ['OMP_NUM_THREADS']='1';os.environ['OPENBLAS_NUM_THREADS']='1'
import json, warnings
from pathlib import Path
import numpy as np
from scipy.optimize import milp, Bounds, LinearConstraint
from scipy.sparse import lil_matrix
OUT=Path(__file__).resolve().parent

def locations(k):
    return [3*i+1+(i>=k) for i in range(23)]

def clash(a,b):
    return abs(a[1]-b[1])<3 and abs(a[2]-b[2])<3

def contains(rect,p):
    return rect[1]<=p[0]<=rect[1]+2 and rect[2]<=p[1]<=rect[2]+2

def run(kl,kb,mode,rectangle=None):
    lp,bp=locations(kl),locations(kb)
    sources=[(1,y) for y in lp]+[(x,1) for x in bp]
    fixed=None;vertical=kl>0;g=3*max(kl,kb)
    if mode:fixed=(-1,1,g-1) if vertical else (-1,g-1,1)
    def meets_rectangle(c):
        if rectangle is None:return False
        x,y,w,h=rectangle
        return c[1]<x+w and x<c[1]+3 and c[2]<y+h and y<c[2]+3
    if fixed and meets_rectangle(fixed):return None
    opts=[]
    for idx,p in enumerate(sources):
        for start in range(p[1]-2,p[1]+1) if idx<23 else range(p[0]-2,p[0]+1):
            candidate=(idx,2,start) if idx<23 else (idx,start,2)
            if not (1<=candidate[1]<=67 and 1<=candidate[2]<=67):continue
            if any(contains(candidate,q) for q in sources):continue
            if fixed and clash(candidate,fixed):continue
            if meets_rectangle(candidate):continue
            opts.append(candidate)
    n=len(opts);pairs=[]
    for i in range(n):
        for j in range(i):
            if opts[i][0]==opts[j][0] or clash(opts[i],opts[j]):pairs.append({i:1,j:1})
    rows=list(pairs);bounds=[1]*len(rows)
    if kl==1:
        rows.append({i:1 for i,o in enumerate(opts) if o[0]>=23});bounds.append(22)
    if kb==1:
        rows.append({i:1 for i,o in enumerate(opts) if o[0]<23});bounds.append(22)
    tangent=(0 if not mode else (1 if mode==2 and g==3 else 2))
    weights=[-1.0]*n
    windex=None
    if mode==2:
        windex=n;weights.append(-1.0);freevars=[]
        for near in [g-2,g+2]:
            if g==3 and near==1:continue
            for transverse in [2,3]:
                p=(transverse,near) if vertical else (near,transverse)
                if p in sources or contains(fixed,p):continue
                if rectangle and rectangle[0]<=p[0]<rectangle[0]+rectangle[2] and rectangle[1]<=p[1]<rectangle[1]+rectangle[3]:continue
                v=len(weights);weights.append(0.0);freevars.append(v)
                for i,o in enumerate(opts):
                    if contains(o,p):rows.append({i:1,v:1});bounds.append(1)
        row={windex:1};row.update({v:-1 for v in freevars});rows.append(row);bounds.append(0)
    matrix=lil_matrix((len(rows),len(weights)))
    for r,coeff in enumerate(rows):
        for c,v in coeff.items():matrix[r,c]=v
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        sol=milp(np.array(weights),integrality=np.ones(len(weights)),bounds=Bounds(0,1),constraints=LinearConstraint(matrix.tocsr(),-np.inf,np.array(bounds)),options={'threads':1,'time_limit':15,'mip_rel_gap':0})
    assert sol.status==0,(kl,kb,mode,sol.message)
    chosen=[round(v) for v in sol.x]
    assert all(sum(chosen[i]*c for i,c in row.items())<=limit for row,limit in zip(rows,bounds))
    score=46+tangent+sum(chosen[:n])+(chosen[windex] if windex is not None else 0)
    assert abs((46+tangent-sol.fun)-score)<1e-7
    return {'left_gap':3*kl,'bottom_gap':3*kb,'mode':mode,'options':n,'bound':score,'status':'OPTIMAL','mip_gap':sol.mip_gap,
            'selected':[list(o) for i,o in enumerate(opts) if chosen[i]],'weight':chosen[windex] if windex is not None else 0,'tangent_upper':tangent}

if __name__=='__main__':
    results=[]
    for kl in range(24):
        for kb in range(24):
            if kl*kb:continue
            for mode in ([0,1,2] if 0<max(kl,kb)<23 else [0]):results.append(run(kl,kb,mode))
    assert len(results)==135 and max(r['bound'] for r in results)==91
    (OUT/'corner_b.json').write_text(json.dumps({'method':'HiGHS pairwise interval conflicts, independent source formula','cases':results},ensure_ascii=False,indent=2)+'\n')
    a=json.loads((OUT/'corner_a.json').read_text())['cases']
    for x,y in zip(a,results):
        for key in ['left_gap','bottom_gap','mode','options','bound']:assert x[key]==y[key],(key,x,y)
    print('135 independently generated A/B models: all OPTIMAL, all bounds equal, maximum N+w=91')
