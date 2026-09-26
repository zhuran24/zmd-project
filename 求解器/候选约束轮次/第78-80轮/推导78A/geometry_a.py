"""Round 78 A: fresh geometry, inclusive integer cells, no prior script imports."""
from pathlib import Path
from collections import Counter
import json, os
OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[3]
ROUNDS=OUT.parents[1]
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['OMP_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
os.sched_setaffinity(0,sorted(os.sched_getaffinity(0))[:10])
SPECS=[('s',3,3,0),('s',3,3,1),('m',5,5,0),('m',5,5,1),('l',6,4,1),('l',4,6,0)]
EDGES=[[(69,y) for y in range(1,17)],[(x,69) for x in range(1,49)],
       [(48,y) for y in range(17,70)],[(x,16) for x in range(49,70)]]
W=Counter(c for edge in EDGES for c in edge)
def dump(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def read(path):return json.loads(Path(path).read_text())
def cells(r):
    x,y,w,h=r
    return frozenset((a,b) for a in range(x,x+w) for b in range(y,y+h))
def hit(r,s):
    x,y,w,h=r; a,b,c,d=s
    return x<a+c and a<x+w and y<b+d and b<y+h
def legal(r):
    x,y,w,h=r
    return x>=1 and y>=1 and x+w<=70 and y+h<=70 and not hit(r,(49,17,21,53))
def available(c):return 1<=c[0]<=69 and 1<=c[1]<=69 and not(c[0]>=49 and c[1]>=17)
def sides(r,axis):
    x,y,w,h=r
    if axis==0:return [[(x-1,j) for j in range(y,y+h)],[(x+w,j) for j in range(y,y+h)]]
    return [[(i,y-1) for i in range(x,x+w)],[(i,y+h) for i in range(x,x+w)]]
def supply(p):return (p[0]-5,p[1]-5,12,12)
def edge_j(p):return int(p[0] in (1,68))+int(p[1] in (1,68))
def weight(r):return sum(W[c] for c in cells(r))
def boundary_machines():
    result=[]
    for kind,w,h,axis in SPECS:
        for x in range(1,71-w):
            for y in range(1,71-h):
                r=(x,y,w,h)
                if not legal(r) or not weight(r):continue
                ports=[[c for c in side if available(c)] for side in sides(r,axis)]
                if not all(ports):continue
                result.append(dict(kind=kind,r=r,axis=axis,t=weight(r),ports=ports))
    return result
def piece(p,mode='two'):
    x,y=p
    if mode=='two':return 'top' if y>=54 else 'right' if x>=34 else 'bulk'
    if mode=='three':return 'top' if y>=54 else 'right' if x>=34 and y>=22 else 'bottom' if x>=34 else 'bulk'
    raise ValueError(mode)
