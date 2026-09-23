"""Rebuild every column/row, check supplied rational multipliers exactly.
No producer/reviewer programs are imported. JSON is untrusted certificate data.
"""
from geometry import *
from fractions import Fraction as Q
from collections import defaultdict
from math import lcm
import hashlib,time
def local(wall,hole=None):
    lo,hi,bo,to=wall;pole=box(5,5,2,2)
    def ok(c):
        x,y=c
        return lo<=x<hi and bo<=y<to and c not in pole and (hole is None or not(x>=hole[0] and y>=hole[1]))
    uu=[]
    for kind,w,h,a in SHAPES:
        for x in range(1-w,12):
            for y in range(1-h,12):
                bb=box(x,y,w,h)
                if not all(map(ok,bb)):continue
                ss=[[c for c in s if ok(c)] for s in sides(x,y,w,h,a)]
                if all(ss):uu.append((bb,ss,(x,y,w,h,a)))
    occupy=defaultdict(list)
    for i,(bb,ss,_) in enumerate(uu):
        for c in bb:occupy[c].append(i)
    rows=[(Counter({i:1 for i in occupy[c]}),1) for c in sorted(occupy)]
    for i,(bb,ss,_) in enumerate(uu):
        for s in ss:
            cc=Counter({i:1})
            for c in s:cc.update(occupy[c])
            rows.append((cc,len(s)))
    return uu,rows
def verify(cert,uu,rr):
    den=lcm(*(r[2] for r in cert['rows']+cert['bounds']))
    coef=[0]*len(uu);rhs=0
    for idx,n,d in cert['rows']:
        assert n>=0 and d>0
        v=n*(den//d);row,b=rr[idx];rhs+=v*b
        for j,t in row.items():coef[j]+=v*t
    for idx,n,d in cert['bounds']:
        assert n>=0 and d>0
        v=n*(den//d);coef[idx]+=v;rhs+=v
    assert min(coef)>=den
    q=Q(rhs,den)
    assert q==Q(*cert['upper']) and q.numerator//q.denominator==cert['integer_upper']
    return dict(columns=len(uu),rows=len(rr),upper=str(q),integer_upper=cert['integer_upper'])
def main():
    start=time.monotonic();prev=ROUNDS/'第69-71轮/推导69'
    wall=json.loads((prev/'wall0_certificate.json').read_text())
    uu,rr=local((-20,7,-20,32));wr=verify(wall,uu,rr)
    assert (len(uu),len(rr))==(550,1352)
    localcaps={};res=[];positions=set()
    for cert in json.loads((prev/'supply_strip_certificates.json').read_text()):
        uu,rr=local(*cert['geom']);assert len(uu)==cert['n'];r=verify(cert,uu,rr)
        for p,q in cert['positions']:
            assert (p,q) not in positions;positions.add((p,q))
            wall=(max(-6,6-p),min(18,75-p),max(-6,6-q),min(18,75-q))
            hole=(max(-6,54-p),max(-6,22-q),18,18)
            assert [list(wall),list(hole)]==cert['geom']
            # Separately check all six shapes in actual base coordinates.
            actual=[]
            pole=box(p,q,2,2)
            for _,w,h,a in SHAPES:
                for x in range(max(1,p-4-w),min(70-w,p+6)+1):
                    for y in range(max(1,q-4-h),min(70-h,q+6)+1):
                        bb=box(x,y,w,h)
                        if bb&(HOLE|pole):continue
                        ss=[[c for c in s if legal(c) and c not in pole] for s in sides(x,y,w,h,a)]
                        if all(ss):actual.append((x-p+5,y-q+5,w,h,a))
            assert actual==[u[2] for u in uu]
            localcaps[p,q]=cert['integer_upper']
        res.append(r)
    expected={(p,q) for p in range(43,69) for q in range(1,17) if not box(p,q,2,2)&HOLE}
    assert positions==expected and len(positions)==395
    group=json.loads((ROUNDS/'第66-68轮/推导66/power_certificates.json').read_text())['17']
    legalp={(p,q) for p in range(1,69) for q in range(1,69) if not box(p,q,2,2)&HOLE}
    seen=set();total=0;capacities=[]
    for cert in group:
        p,q=cert['x'],cert['y'];assert (p,q) not in seen;seen.add((p,q))
        u=make('p',p,q,2,2,'-');cc=centers(u);total+=len(cc)
        covered=set()
        for x,y,w,h in cert['tiles']:
            assert 1<=w<=3 and 1<=h<=3
            covered.update(box(x,y,w,h))
        assert cc<=covered and cert['cap']==min(23,len(cert['tiles']))
        count=int(p in (1,68))+int(q in (1,68))
        loss=max(23-cert['cap'],23-localcaps.get((p,q),23),15 if count==2 else 10 if count else 0)
        if q-5>=17 and q+7<=70 and 0<=47-p<=6:loss=max(loss,[10,9,9,6,5,4,1][47-p])
        if p-5>=49 and p+7<=70 and 0<=15-q<=6:loss=max(loss,[10,9,9,6,5,4,1][15-q])
        capacities.append(dict(x=p,y=q,loss=loss,cap=23-loss))
    assert seen==legalp and len(seen)==3511 and total==532890
    dump('capacities.json',capacities)
    summary=dict(wall=wr,strip_positions=len(positions),strip_columns=sum(r['columns'] for r in res),strip_rows=sum(r['rows'] for r in res),right_edge=[localcaps[68,q] for q in range(1,16)],grid_positions=len(seen),center_pairs=total,excluded_P10=sum(r['loss']>13 for r in capacities),all_local_certificates=res,seconds=time.monotonic()-start)
    dump('certificates.json',summary);print({k:v for k,v in summary.items() if k!='all_local_certificates'},flush=True)
if __name__=='__main__':main()
