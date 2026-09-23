"""Round 76 independent geometry. Coordinates are integer occupied cells."""
from pathlib import Path
from collections import Counter
import json
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
ROUNDS = OUT.parents[1]
SHAPES = [('s',3,3,'h'),('s',3,3,'v'),('m',5,5,'h'),('m',5,5,'v'),('l',6,4,'v'),('l',4,6,'h')]
def box(x,y,w,h):
    return frozenset((i,j) for i in range(x,x+w) for j in range(y,y+h))
HOLE = box(49,17,21,53)
LINES = [box(69,1,1,16),box(1,69,48,1),box(48,17,1,53),box(49,16,21,1)]
WEIGHT = Counter(c for line in LINES for c in line)
def legal(c):
    x,y=c
    return 1<=x<=69 and 1<=y<=69 and c not in HOLE
def sides(x,y,w,h,axis):
    if axis=='h': return [[(x-1,j) for j in range(y,y+h)],[(x+w,j) for j in range(y,y+h)]]
    return [[(i,y-1) for i in range(x,x+w)],[(i,y+h) for i in range(x,x+w)]]
def make(kind,x,y,w,h,axis):
    return dict(kind=kind,x=x,y=y,w=w,h=h,axis=axis)
def body(b): return box(*(b[k] for k in ('x','y','w','h')))
def ports(b):
    x,y,w,h,a=(b[k] for k in ('x','y','w','h','axis'))
    if b['kind']=='p': return []
    ss=sides(x,y,w,h,a)
    if b['kind']!='c': return [list(filter(legal,s)) for s in ss]
    take=[[s[t]] for s in ss for t in (1,4,7)]
    put=sides(x,y,w,h,'v' if a=='h' else 'h')
    return take+[[c for s in put for c in s[1:8] if legal(c)]]
def powered(m,p):
    # Half-open rectangles: pole (p,q) powers [p-5,p+7) x [q-5,q+7).
    return (m['x']<p['x']+7 and p['x']-5<m['x']+m['w']
            and m['y']<p['y']+7 and p['y']-5<m['y']+m['h'])
def edge(p): return int(p['x'] in (1,68) or p['y'] in (1,68))
def bands():
    result=[]
    for a,b in [(0,k) for k in range(24)]+[(k,0) for k in range(1,24)]:
        ff=set()
        for gap,axis in ((a,0),(b,1)):
            # Partition 70 cells minus gap 3*gap into consecutive triples.
            row=[i for i in range(70) if i!=3*gap]
            for t in range(0,69,3):
                triple=row[t:t+3]; assert triple[-1]-triple[0]==2
                ff.add((1,triple[1]) if axis==0 else (triple[1],1))
        assert len(ff)==46
        result.append(((3*a,3*b),frozenset(ff)))
    return result
def centers(p,forbidden=None):
    forbidden=body(p) if forbidden is None else forbidden
    px,py=p['x'],p['y']
    return {(x,y) for x in range(max(2,px-6),min(68,px+7)+1)
            for y in range(max(2,py-6),min(68,py+7)+1)
            if not box(x-1,y-1,3,3)&(HOLE|forbidden)}
def domains(P=10,full=False):
    caps=json.loads((OUT/'capacities.json').read_text())
    units=[]
    for kind,w,h,a in SHAPES+[('c',9,9,'h'),('c',9,9,'v')]:
        for x in range(1,71-w):
            for y in range(1,71-h):
                bb=box(x,y,w,h)
                if bb&HOLE or not any(c in WEIGHT for c in bb):continue
                u=make(kind,x,y,w,h,a);ss=ports(u)
                if kind=='c':
                    if x<2 or y<2 or (x<=3 and y<=3):continue
                    if (x<=3 and a=='h') or (y<=3 and a=='v'):continue
                    if (y==61 and x<=6 and a=='h') or (x==61 and y<=6 and a=='v'):continue
                    if any(not legal(c) for s in ss[:6] for c in s) or len(ss[-1])<2:continue
                if any(not s for s in ss):continue
                units.append(u)
    machines=[u for u in units if u['kind']!='c']
    poles=[]
    for r in caps:
        if r['loss']>23*P-217:continue
        u=make('p',r['x'],r['y'],2,2,'-');u['loss']=r['loss']
        if full or edge(u) or any(c in WEIGHT for c in body(u)) or any(powered(m,u) for m in machines):poles.append(u)
    return units+poles
def dump(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')
