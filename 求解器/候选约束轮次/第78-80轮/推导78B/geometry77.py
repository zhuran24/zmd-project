"""Review 77: cell geometry rebuilt from the three official input files.
No derivation/reviewer scripts are imported. Coordinates are inclusive cells.
"""
from pathlib import Path
import json
from collections import Counter

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
ROUNDS = OUT.parents[1]
SPECS = [('s',3,3,0),('s',3,3,1),('m',5,5,0),('m',5,5,1),
         ('l',6,4,1),('l',4,6,0)]
LINES = [[(69,y) for y in range(1,17)],[(x,69) for x in range(1,49)],
         [(48,y) for y in range(17,70)],[(x,16) for x in range(49,70)]]
WEIGHTS = Counter(c for line in LINES for c in line)
def read(path): return json.loads(Path(path).read_text())
def save(name,data): (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def cells(r):
    x,y,w,h=r
    return frozenset((i,j) for i in range(x,x+w) for j in range(y,y+h))
def hit(r,s):
    x,y,w,h=r; u,v,a,b=s
    return x<=u+a-1 and u<=x+w-1 and y<=v+b-1 and v<=y+h-1
def allowed(c):
    x,y=c
    return 1<=x<=69 and 1<=y<=69 and (x<49 or y<17)
def rect_allowed(r):
    x,y,w,h=r
    return x>=1 and y>=1 and x+w<=70 and y+h<=70 and not hit(r,(49,17,21,53))
def edges(r,axis):
    x,y,w,h=r
    if axis==0:return [[(x-1,j) for j in range(y,y+h)],[(x+w,j) for j in range(y,y+h)]]
    return [[(i,y-1) for i in range(x,x+w)],[(i,y+h) for i in range(x,x+w)]]
def power(p):return (p[0]-5,p[1]-5,12,12)
def edge_count(p):return int(p[0] in (1,68))+int(p[1] in (1,68))
def centers(p, forbidden=frozenset()):
    ans=set()
    for x in range(max(2,p[0]-6),min(68,p[0]+7)+1):
        for y in range(max(2,p[1]-6),min(68,p[1]+7)+1):
            r=(x-1,y-1,3,3)
            if rect_allowed(r) and not hit(r,(*p,2,2)) and not cells(r)&forbidden:
                assert hit(r,power(p))
                ans.add((x,y))
    return ans
def domain(capacities):
    units=[]
    for kind,w,h,axis in SPECS+[('c',9,9,0),('c',9,9,1)]:
        for y in range(1,71-h):
            for x in range(1,71-w):
                r=(x,y,w,h)
                if not rect_allowed(r) or not any(c in WEIGHTS for c in cells(r)):continue
                sides=edges(r,axis)
                if kind=='c':
                    if min(x,y)<2 or max(x,y)<=3:continue
                    if (axis==0 and (x<=3 or (y+h==70 and x<7))):continue
                    if (axis==1 and (y<=3 or (x+w==70 and y<7))):continue
                    take=[side[k] for side in sides for k in (1,4,7)]
                    if not all(allowed(c) for c in take):continue
                    puts=[side[k] for side in edges(r,1-axis) for k in range(1,8)]
                    ports=[([c],1) for c in take]+[([c for c in puts if allowed(c)],2)]
                else:ports=[([c for c in side if allowed(c)],1) for side in sides]
                if any(len(ps)<n for ps,n in ports):continue
                units.append(dict(kind=kind,r=r,axis=axis,ports=ports,loss=0,j=0))
    for row in capacities:
        if row['cap']<10:continue
        p=tuple(row['p'])
        units.append(dict(kind='p',r=(*p,2,2),axis=-1,ports=[],loss=23-row['cap'],j=int(edge_count(p)>0)))
    return units
