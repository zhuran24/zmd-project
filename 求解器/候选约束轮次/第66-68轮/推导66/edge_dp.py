#!/usr/bin/env python3
"""Necessary 1-D boundary relaxations; all geometry uses half-open rectangles."""
import json, time, hashlib
from pathlib import Path
from functools import lru_cache
ROOT = Path(__file__).resolve().parent
COUNTS = {"粉碎机":68,"精炼炉":51,"配件机":6,"塑形机":6,"种植机":32,"采种机":16,"研磨机":32,"封装机":3,"灌装机":3}
def cells(r):
    x,y,w,h=r
    return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}
def overlaps(a,b):
    x,y,w,h=a; X,Y,W,H=b
    return x<X+W and X<x+w and y<Y+H and Y<y+h
def port_sides(r,axis,core=False):
    x,y,w,h=r
    if axis==0:  # ports on west/east
        offsets=(1,4,7) if core else range(h)
        return [[(x-1,y+k) for k in offsets],[(x+w,y+k) for k in offsets]]
    offsets=(1,4,7) if core else range(w)
    return [[(x+k,y-1) for k in offsets],[(x+k,y+h) for k in offsets]]
def old_pole_loss(p,r):
    x,y,_,_=p; a,b,w,h=r
    edge=int(x in (1,68))+int(y in (1,68))
    loss=(0,9,15)[edge]
    # Rule 115. Never add losses for one pole; take their maximum.
    costs=(10,9,9,6,5,4,1)
    if y-5>=b and y+7<=b+h:
        g=a-(x+2) if x+2<=a else x-(a+w)
        if 0<=g<=6: loss=max(loss,costs[g])
    if x-5>=a and x+7<=a+w:
        g=b-(y+2) if y+2<=b else y-(b+h)
        if 0<=g<=6: loss=max(loss,costs[g])
    return loss
def patterns():
    ans=[]
    for gl,gb in [(0,k) for k in range(24)]+[(k,0) for k in range(1,24)]:
        ports=[]; bodies=set()
        for axis,g in [(0,gl),(1,gb)]:
            starts=list(range(0,3*g,3))+list(range(3*g+1,70,3))
            assert len(starts)==23
            for s in starts:
                rr=(0,s,1,3) if axis==0 else (s,0,3,1)
                assert not bodies.intersection(cells(rr))
                bodies.update(cells(rr))
                ports.append((1,s+1) if axis==0 else (s+1,1))
        ans.append(dict(gl=gl,gb=gb,ports=ports,bodies=sorted(bodies)))
    return ans
PATTERNS=patterns()
def legal_patterns(r):
    a,b,w,h=r; result=[]
    for i,p in enumerate(PATTERNS):
        if a==4 and sum(b<=y<b+h for x,y in p['ports'] if x==1)>6: continue
        if b==4 and sum(a<=x<a+w for x,y in p['ports'] if y==1)>6: continue
        result.append(i)
    return result

def _options(r,side,outer,corner):
    """Each option projects a physically possible single body onto one line.
    No machine inventory limit, cross-line body collision, or routing imposed.
    The unique unused warehouse cell cannot carry active throughput, so active
    machine/core ports cannot use row/column 0 (rules 28,34,94).
    """
    a,b,w,h=r
    horizontal=side in ('S','N')
    if outer:
        start,end=1,70
        line=69
    else:
        start,end=(a,a+w) if horizontal else (b,b+h)
        line={'W':a-1,'E':a+w,'S':b-1,'N':b+h}[side]
    opts=[set() for _ in range(end-start)]
    def available(pt):
        x,y=pt
        return 1<=x<70 and 1<=y<70 and not (a<=x<a+w and b<=y<b+h)
    # kind,length along line,depth,port axis along physical x/y
    shapes=[]
    for W,H,axes in [(3,3,(0,1)),(5,5,(0,1)),(6,4,(1,)),(4,6,(0,))]:
        for axis in axes: shapes.append(('M',W,H,axis))
    shapes += [('C',9,9,axis) for axis in (0,1)]+[('P',2,2,None)]
    cornerbody=(68,68,2,2)
    for kind,W,H,axis in shapes:
        length,depth=(W,H) if horizontal else (H,W)
        for u in range(max(1,start-length+1),min(70-length,end-1)+1):
            if outer:
                rr=(u,70-H,W,H) if horizontal else (70-W,u,W,H)
            elif side=='W': rr=(a-W,u,W,H)
            elif side=='E': rr=(a+w,u,W,H)
            elif side=='S': rr=(u,b-H,W,H)
            else: rr=(u,b+h,W,H)
            x,y,_,_=rr
            if x<1 or y<1 or x+W>70 or y+H>70 or overlaps(rr,r): continue
            if outer:
                if corner and overlaps(rr,cornerbody) and rr!=cornerbody: continue
                if not corner and rr==cornerbody: continue
            if kind=='M' and not all(any(available(pt) for pt in edge) for edge in port_sides(rr,axis)): continue
            if not EXTRA_ALLOWED(kind,rr,axis,r): continue
            if kind=='C':
                if x<=3 and y<=3: continue
                if not all(available(pt) for edge in port_sides(rr,axis,True) for pt in edge): continue
                # At least two stock input ports overall, relaxed direction.
                ins=port_sides(rr,1-axis)
                if sum(available(edge[k]) for edge in ins for k in range(1,8))<2: continue
            lo,hi=max(start,u),min(end,u+length)
            full=(lo==u and hi==u+length)
            tag=kind if full else 'Z' # truncated blocks have permissive adjacency
            c=int(kind=='C'); p=int(kind=='P')
            loss=pole_loss(rr,r) if p else 0
            if outer and corner and rr==cornerbody:
                c=p=loss=0  # shared corner pole charged once outside both DPs
            opts[lo-start].add((hi-start,tag,c,p,loss))
    # gap costs use exact X definition, including corner weight once per edge.
    gaps=[]
    for u in range(start,end):
        pt=(u,line) if horizontal else (line,u)
        inside=pt in cells(r)
        gaps.append(0 if outer and inside else 1)
        if outer and corner and u>=68: gaps[-1]=None
    return opts,gaps

def frontier(table):
    # Preserve core and pole counts, remove dominated loss/cost tradeoffs.
    out={}
    for c in (0,1):
        for p in range(13):
            best=1000
            for loss in range(60):
                v=table.get((c,p,loss),1000)
                if v<best:
                    out[c,p,loss]=v; best=v
    return out

@lru_cache(None)
def line_table(r,side,outer,corner):
    opts,gaps=_options(r,side,outer,corner)
    # canonicalize options to share translated/reflected equal 1-D problems
    return solve_line(tuple(tuple(sorted(o)) for o in opts),tuple(gaps))

@lru_cache(None)
def solve_line(opts,gaps):
    n=len(opts); dp=[{} for _ in range(n+1)]
    dp[0][('G',0,0,0)]=0
    for pos in range(n):
        for (prev,c,p,l),cost in dp[pos].items():
            if gaps[pos] is not None:
                key=('G',c,p,l); value=cost+gaps[pos]
                if value<dp[pos+1].get(key,1000): dp[pos+1][key]=value
            for end,tag,cc,pp,ll in opts[pos]:
                if (prev,tag) in {('M','M'),('M','C'),('C','M'),('C','P'),('P','C')}: continue
                if c+cc>1 or p+pp>12 or l+ll>59: continue
                key=(tag,c+cc,p+pp,l+ll)
                if cost<dp[end].get(key,1000): dp[end][key]=cost
    out={}
    for (prev,c,p,l),cost in dp[n].items():
        out[c,p,l]=min(cost,out.get((c,p,l),1000))
    return frontier(out)

def combine(tables,P,budget):
    dp={(0,0,0):0}
    for table in tables:
        nxt={}
        for (c,p,l),v in dp.items():
            for (cc,pp,ll),vv in table.items():
                if c+cc>1 or p+pp>P or l+ll>budget: continue
                key=c+cc,p+pp,l+ll
                nxt[key]=min(nxt.get(key,1000),v+vv)
        dp=frontier(nxt)
    return min(dp.values(),default=1000)

POWER = json.loads((ROOT/'power_certificates.json').read_text())
CAPS={int(b):{(row['x'],row['y']):row['cap'] for row in rows} for b,rows in POWER.items()}
def pole_loss(p,r):
    return max(old_pole_loss(p,r),23-CAPS[r[1]][p[0],p[1]])

EXTRA_ALLOWED = lambda kind,rr,axis,r: True
