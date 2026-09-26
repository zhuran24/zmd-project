"""Second certificate encoder: half-open rectangles and direct column sums.
It does not import any other certificate or geometry implementation.
"""
from pathlib import Path
from fractions import Fraction as F
from math import lcm
import json,time,hashlib
OUT=Path(__file__).resolve().parent;ROUNDS=OUT.parents[1]
SPECS=[(3,3,0),(3,3,1),(5,5,0),(5,5,1),(6,4,1),(4,6,0)]
def read(p):return json.loads(Path(p).read_text())
def intersect(a,b):return a[0]<b[2] and b[0]<a[2] and a[1]<b[3] and b[1]<a[3]
def points(r):return [(x,y) for x in range(r[0],r[2]) for y in range(r[1],r[3])]

def verify(cert,p):
    rects=[];ends=[]
    for w,h,axis in SPECS:
        for x in range(1-w,12):
            for y in range(1-h,12):
                r=(x,y,x+w,y+h)
                if intersect(r,(5,5,7,7)):continue
                if p is None:
                    if x+w>7:continue
                else:
                    q=(x+p[0]-5,y+p[1]-5,x+w+p[0]-5,y+h+p[1]-5)
                    if min(q[:2])<1 or max(q[2:])>70 or intersect(q,(49,17,70,70)):continue
                ps=([(x-1,v) for v in range(y,y+h)],[(x+w,v) for v in range(y,y+h)]) if axis==0 else ([(u,y-1) for u in range(x,x+w)],[(u,y+h) for u in range(x,x+w)])
                def valid(c):
                    if 5<=c[0]<7 and 5<=c[1]<7:return False
                    if p is None:return c[0]<=6
                    u,v=c[0]+p[0]-5,c[1]+p[1]-5
                    return 1<=u<70 and 1<=v<70 and (u<49 or v<17)
                ps=[list(filter(valid,s)) for s in ps]
                if all(ps):rects.append(r);ends.append(ps)
    occupied=sorted(set(c for r in rects for c in points(r)))
    den=lcm(*(d for _,_,d in cert['rows']+cert['bounds']));roww={i:n*(den//d) for i,n,d in cert['rows']}
    boundw={i:n*(den//d) for i,n,d in cert['bounds']}
    assert all(w>=0 for w in roww.values()) and all(w>=0 for w in boundw.values())
    nr=len(occupied);nc=len(rects);coeff=[0]*nc;rhs=0
    # Accumulate sparse cell price and explicit selection price, without
    # constructing the producer's coefficient matrix or row counters.
    prices={c:roww.get(i,0) for i,c in enumerate(occupied)}
    for i,c in enumerate(occupied):rhs+=roww.get(i,0)
    for k,ps in enumerate(ends):
        for side,N in enumerate(ps):
            weight=roww.get(nr+2*k+side,0);rhs+=weight*len(N);coeff[k]+=weight
            for c in N:prices[c]=prices.get(c,0)+weight
    for k,r in enumerate(rects):coeff[k]+=sum(prices.get(c,0) for c in points(r))+boundw.get(k,0)
    rhs+=sum(boundw.values())
    assert all(0<=i<nr+2*nc for i in roww) and all(0<=i<nc for i in boundw)
    assert min(coeff)>=den and F(rhs,den)==F(*cert['upper'])
    assert rhs//den==cert['integer_upper']
    return dict(columns=nc,rows=nr+2*nc,upper=str(F(rhs,den)),cap=rhs//den)

def main():
    t=time.monotonic();wall=verify(read(OUT/'wall0_certificate.json'),None)
    local={};records=[]
    for c in read(OUT/'supply_strip_certificates.json'):
        for p in c['positions']:
            v=verify(c,p);local[tuple(p)]=v['cap'];records.append(dict(p=p,**v))
    expected={(x,y) for x in range(1,69) for y in range(1,69) if not intersect((x,y,x+2,y+2),(49,17,70,70))}
    caps=[];count=0
    for c in read(OUT/'power_certificates.json')['17']:
        x,y=c['x'],c['y'];expected.remove((x,y));centers=[]
        for u in range(max(2,x-6),min(68,x+7)+1):
            for v in range(max(2,y-6),min(68,y+7)+1):
                r=(u-1,v-1,u+2,v+2)
                if intersect(r,(x,y,x+2,y+2)) or intersect(r,(49,17,70,70)):continue
                assert intersect(r,(x-5,y-5,x+7,y+7));centers.append((u,v))
        assert all(1<=w<=3 and 1<=h<=3 for _,_,w,h in c['tiles'])
        for u,v in centers:assert any(a<=u<a+w and b<=v<b+h for a,b,w,h in c['tiles'])
        count+=len(centers)
        edge=(x in (1,68))+(y in (1,68));cap=min(23,len(c['tiles']),local.get((x,y),23),8 if edge==2 else 13 if edge else 23)
        if 22<=y<=63 and 41<=x<=47:cap=min(cap,(13,14,14,17,18,19,22)[47-x])
        if 54<=x<=63 and 9<=y<=15:cap=min(cap,(13,14,14,17,18,19,22)[15-y])
        caps.append(dict(p=[x,y],cap=cap))
    assert not expected
    assert {(tuple(d['p']),d['cap']) for d in caps}=={(tuple(d['p']),d['cap']) for d in read(OUT/'capacities.json')}
    result=dict(wall=wall,local_positions=len(local),local_checks=records,poles=len(caps),centers=count,
      capacities_agree=True,seconds=time.monotonic()-t)
    (OUT/'certificates_independent.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print({k:v for k,v in result.items() if k!='local_checks'},flush=True)
if __name__=='__main__':main()
