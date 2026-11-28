"""Board geometry. A face is the triple (x,y,d), d=0,1,2,3 = E,N,W,S."""
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from collections import defaultdict

V = ((1,0),(0,1),(-1,0),(0,-1))
D = range(4)
def opp(d): return (d+2)%4
def step(p,d,n=1): return (p[0]+V[d][0]*n, p[1]+V[d][1]*n)
def face(p,d): return (*p,d)
def inside(p): return min(p)>=0 and max(p)<70
def bit(p): return 1 << (70*p[1]+p[0]) if inside(p) else 0
def mask(ps): return sum(bit(p) for p in set(ps))
def cells(x,y,w,h): return [(i,j) for i in range(x,x+w) for j in range(y,y+h)]
@lru_cache(None)
def rect(x,y,w,h):
    if x<0 or y<0 or x+w>70 or y+h>70: return 0
    return (((1<<w)-1)*sum(1<<(70*j) for j in range(h))) << (70*y+x)

I = {(1,i) for i in range(1,70)} | {(i,1) for i in range(1,70)}
OUTER = {(0,i) for i in range(70)} | {(i,0) for i in range(70)}
def eligible_x(f):
    x,y,d=f
    return (x==69 and y>=1 and d==0) or (y==69 and x>=1 and d==1)

@lru_cache(None)
def q_windows(f):
    """All 6x6 tiles sharing the side facing this tail and containing its neighbour."""
    x,y,d=f
    tx,ty=step((x,y),d)
    if d in (0,2):
        xx=tx if d==0 else tx-5
        anchors=((xx,ty-k) for k in range(6))
    else:
        yy=ty if d==1 else ty-5
        anchors=((tx-k,yy) for k in range(6))
    return tuple((xx,yy,rect(xx,yy,6,6)) for xx,yy in anchors
                 if 2<=xx<=64 and 2<=yy<=64)

def tilings():
    """Recursively tile a line by 23 triominoes and a singleton in any order."""
    def visit(i,n,spare,starts):
        if i==70:
            if n==23 and spare is not None: yield spare,tuple(starts)
            return
        if i>70: return
        if n<23: yield from visit(i+3,n+1,spare,starts+[i])
        if spare is None: yield from visit(i+1,n,i,starts)
    return sorted(visit(0,0,None,[]))

@dataclass(frozen=True)
class Spec:
    name: str
    orient: int
    w: int
    h: int
    ports: tuple   # offsets (i,j,d,input?) on building side, outward d

def side(w,h,d):
    if d==0: return [(w-1,j) for j in range(h)]
    if d==2: return [(0,j) for j in range(h)]
    if d==1: return [(i,h-1) for i in range(w)]
    return [(i,0) for i in range(w)]

FOUR = {'研磨机','塑形机','封装机','灌装机'}
RAW_IN = {'粉碎机','精炼炉','协议储存箱'}
SPECS=[]
def spec(name,d,w,h,in_edges,out_edges):
    pp=tuple((i,j,k,role) for edges,role in [(in_edges,True),(out_edges,False)]
             for k,loc in edges for i,j in loc)
    SPECS.append(Spec(name,d,w,h,pp))
for name,short,long in [('粉碎机',3,3),('精炼炉',3,3),('配件机',3,3),('塑形机',3,3),
                        ('采种机',5,5),('种植机',5,5),('研磨机',4,6),('封装机',4,6),
                        ('灌装机',4,6),('协议储存箱',3,3)]:
    for d in D:
        w,h=(short,long) if d%2==0 else (long,short)
        spec(name,d,w,h,[(d,side(w,h,d))],[(opp(d),side(w,h,opp(d)))])
for d in D:  # rotations differing by 180 deg have identical port geometry
    axis=d%2
    spec('协议核心',d,9,9,
         [(k,side(9,9,k)[1:8]) for k in D if k%2!=axis],
         [(k,side(9,9,k)[1:8:3]) for k in D if k%2==axis])
spec('供电桩',0,2,2,[],[])
CORE=next(s for s in SPECS if s.name=='协议核心')

# Oriented input/output routes inside a single one-cell inventory.
TRANS=[]
for i in D:
    for j in D:
        if i!=j: TRANS.append(('传送带', (i,j), ((i,j),),False))
    TRANS.append(('分流器',i,tuple((i,j) for j in D if i!=j),False))
    TRANS.append(('汇流器',i,tuple((j,i) for j in D if i!=j),False))
    TRANS.append(('物品准入口',i,((i,opp(i)),),False))
    TRANS.append(('桥接器',i,tuple((j,opp(j)) for j in D),True))
assert len(TRANS)==28

class Board:
    def __init__(self,left,bottom):
        self.gaps=(left[0],bottom[0])
        self.depots=set()
        self.ports={}
        self.heads={}
        for starts,vertical,d in [(left[1],True,0),(bottom[1],False,1)]:
            for s in starts:
                pts=[(0,s+k) if vertical else (s+k,0) for k in range(3)]
                assert not self.depots.intersection(pts)
                self.depots.update(pts)
                self.ports[pts[1]]=d
                a=step(pts[1],d)
                assert a not in self.heads
                self.heads[a]=opp(d)
        self.q,=OUTER-self.depots
        self.obstacles=mask(self.depots|self.heads.keys())
        self.B=set()
        self.poles=[]
        for l in [2,3]:
            for x,y in {(1,i) for i in range(1,72-l)}|{(i,1) for i in range(1,72-l)}:
                r=rect(x,y,l,l)
                if not r or r&self.obstacles: continue
                hit=I.intersection(cells(x,y,l,l))
                if l==3: self.B.update(hit)
                else: self.poles.append(((x,y),hit))
        assert all(len(hit)<=2 for _,hit in self.poles)
        assert len(self.heads)==46 and len(I-self.heads.keys())==91
    def nontransport_ok(self,s,x,y,occupied):
        # Deliberate relaxation for testing local candidates other than the designated core.
        b=rect(x,y,s.w,s.h)
        return b and not (b & occupied)
    def belongs_to_mine(self,p,d):
        return self.heads.get(p)==d

# Generate the exact relative anchors of any solid covering a cell, presenting a port,
# or able to record weight from a face. Weight needs two feeds on the SAME machine.
@lru_cache(None)
def templates(test,d=0):
    result=[]
    for s in SPECS:
        if test=='cover':
            result.extend((s,-i,-j,0,0) for i,j in cells(0,0,s.w,s.h))
        elif test=='interface':
            result.extend((s,V[d][0]-i,V[d][1]-j,role,0)
                          for i,j,k,role in s.ports if k==opp(d))
        elif test=='weight' and s.name in FOUR:
            outside={step((i,j),k) for i,j,k,role in s.ports if role}
            for t in outside:
                for n in (1,2,3):
                    if step(t,d,n) in outside:
                        result.append((s,-t[0],-t[1],opp(s.orient),n))
    return result

def candidates(test,p,d,occupied):
    for s,dx,dy,a,b in templates(test,d):
        x,y=p[0]+dx,p[1]+dy
        r=rect(x,y,s.w,s.h)
        if r and not r&occupied:
            yield s,x,y,a,b,r

def core_placements():
    # This is a superset: only use the necessary orientation restriction at distances 2,3.
    for x,y in product(range(2,62),repeat=2):
        for axis in (0,1):
            if (x<=3 and axis==0) or (y<=3 and axis==1): continue
            heads={}
            fs=[]
            for d in (axis,axis+2):
                pts=[step((x+i,y+j),d) for i,j in side(9,9,d)[1:8:3]]
                if not all(inside(p) for p in pts): break
                heads.update((p,opp(d)) for p in pts)
                tangent=1-axis
                for p,b in zip(pts,pts[1:]):
                    assert step(p,tangent,3)==b
                    fs.extend([face(p,tangent),face(b,opp(tangent))])
            else:
                assert len(set(fs))==8 and all(min(p)>=3 for p in heads)
                yield x,y,axis,heads,fs

def each_board():
    t=tilings()
    for l,b in product(t,repeat=2):
        if l[0] and b[0]: continue
        yield Board(l,b)
