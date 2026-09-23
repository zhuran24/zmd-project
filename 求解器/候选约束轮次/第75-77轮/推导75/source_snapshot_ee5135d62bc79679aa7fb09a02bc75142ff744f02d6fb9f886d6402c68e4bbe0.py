"""Independent integer geometry for review 74. No derivation code imports."""
from pathlib import Path
from collections import Counter
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
ROUNDS = OUT.parents[1]
SPECS = [('s',3,3,0),('s',3,3,1),('m',5,5,0),('m',5,5,1),('l',6,4,1),('l',4,6,0)]
LINES = [set((69,y) for y in range(1,17)), set((x,69) for x in range(1,49)),
         set((48,y) for y in range(17,70)), set((x,16) for x in range(49,70))]
WEIGHT = Counter(p for line in LINES for p in line)

def rect(x,y,w,h):
    return frozenset((i,j) for i in range(x,x+w) for j in range(y,y+h))

def legal(p):
    x,y=p
    return 1<=x<=69 and 1<=y<=69 and not (x>=49 and y>=17)

def overlap(r,s):
    x,y,w,h=r; a,b,c,d=s
    return max(x,a)<min(x+w,a+c) and max(y,b)<min(y+h,b+d)

def sides(r,axis):
    x,y,w,h=r
    if axis==0:
        return [[(x-1,j) for j in range(y,y+h)],[(x+w,j) for j in range(y,y+h)]]
    return [[(i,y-1) for i in range(x,x+w)],[(i,y+h) for i in range(x,x+w)]]

def boundary_domain(core_rules=True):
    out=[]
    for kind,w,h,axis in SPECS+[('c',9,9,0),('c',9,9,1)]:
        for y in range(1,71-h):
            for x in range(1,71-w):
                if overlap((x,y,w,h),(49,17,21,53)): continue
                body=rect(x,y,w,h)
                if body.isdisjoint(WEIGHT): continue
                ps=sides((x,y,w,h),axis)
                if kind=='c':
                    if core_rules:
                        if min(x,y)<2 or (x<=3 and y<=3): continue
                        if (axis==0 and x<=3) or (axis==1 and y<=3): continue
                        if (axis==0 and y==61 and x<7) or (axis==1 and x==61 and y<7): continue
                    take=[line[i] for line in ps for i in (1,4,7)]
                    if not all(map(legal,take)): continue
                    other=sides((x,y,w,h),1-axis)
                    put=[line[i] for line in other for i in range(1,8) if legal(line[i])]
                    ps=[[p] for p in take]+[put]; needs=[1]*6+[2]
                else:
                    ps=[[p for p in line if legal(p)] for line in ps]; needs=[1,1]
                if any(len(line)<n for line,n in zip(ps,needs)): continue
                out.append(dict(kind=kind,r=[x,y,w,h],axis=axis,ports=ps,needs=needs))
    return out

def centers(p):
    # Direct inclusive-cell intersection; independent of source range formula.
    x,y=p; pole=rect(x,y,2,2); power=rect(x-5,y-5,12,12)
    result=set()
    for cx in range(max(2,x-7),min(68,x+8)+1):
        for cy in range(max(2,y-7),min(68,y+8)+1):
            small=rect(cx-1,cy-1,3,3)
            if all(map(legal,small)) and small.isdisjoint(pole) and not small.isdisjoint(power):
                result.add((cx,cy))
    return result

def dump(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
