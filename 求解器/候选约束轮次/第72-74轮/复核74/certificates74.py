"""Rebuild local columns and exact rational certificates; no optimizer needed."""
from geometry74 import *
from collections import defaultdict
from fractions import Fraction
from math import lcm
import hashlib, time

def read(rel):
    p=ROUNDS/rel
    return json.loads(p.read_text())

def local_columns(p=None):
    # For actual poles, use original base coordinates for all legal decisions.
    # Return supply-origin coordinates only to interpret submitted row numbers.
    pole=rect(5,5,2,2)
    def valid(c):
        if c in pole: return False
        if p is None: return c[0]<=6
        return legal((c[0]+p[0]-5,c[1]+p[1]-5))
    cols=[]
    for _,w,h,axis in SPECS:
        for x in range(1-w,12):
            for y in range(1-h,12):
                b=rect(x,y,w,h)
                if not all(map(valid,b)): continue
                ports=[[c for c in s if valid(c)] for s in sides((x,y,w,h),axis)]
                if all(ports): cols.append((b,ports))
    return cols

def exact_check(cert,cols):
    occ=defaultdict(list)
    for j,(body,_) in enumerate(cols):
        for c in body: occ[c].append(j)
    rows=[(Counter({j:1 for j in occ[c]}),1) for c in sorted(occ)]
    for j,(_,ps) in enumerate(cols):
        for s in ps:
            row=Counter({j:1})
            for c in s: row.update(occ[c])
            rows.append((row,len(s)))
    den=lcm(*(d for _,_,d in cert['rows']+cert['bounds']))
    coeff=[0]*len(cols); total=0
    for i,n,d in cert['rows']:
        assert n>=0 and d>0 and 0<=i<len(rows)
        weight=n*(den//d); row,rhs=rows[i]; total+=weight*rhs
        for j,v in row.items(): coeff[j]+=weight*v
    for j,n,d in cert['bounds']:
        assert n>=0 and d>0 and 0<=j<len(cols)
        weight=n*(den//d); coeff[j]+=weight; total+=weight
    assert coeff and min(coeff)>=den
    upper=Fraction(total,den)
    assert upper==Fraction(*cert['upper'])
    assert upper.numerator//upper.denominator==cert['integer_upper']
    return dict(columns=len(cols),rows=len(rows),upper=str(upper),minimum_coefficient=str(Fraction(min(coeff),den)))

def main():
    start=time.monotonic()
    wall=read('第69-71轮/推导69/wall0_certificate.json')
    wall_result=exact_check(wall,local_columns())
    assert wall_result['columns']==550 and wall_result['rows']==1352
    print('wall',wall_result,flush=True)
    local={}; records=[]
    for cert in read('第69-71轮/推导69/supply_strip_certificates.json'):
        for xy in cert['positions']:
            p=tuple(xy); assert p not in local
            cols=local_columns(p); assert len(cols)==cert['n']
            result=exact_check(cert,cols)
            local[p]=cert['integer_upper']; records.append(dict(p=xy,**result,cap=local[p]))
    expected={(x,y) for x in range(43,69) for y in range(1,17) if not overlap((x,y,2,2),(49,17,21,53))}
    assert set(local)==expected and len(local)==395
    dump('local_certificates.json',dict(wall=wall_result,positions=records,columns=sum(d['columns'] for d in records)))
    print('local positions',len(local),flush=True)
    groups=read('第66-68轮/推导66/power_certificates.json')['17']
    expected={(x,y) for x in range(1,69) for y in range(1,69) if not overlap((x,y,2,2),(49,17,21,53))}
    assert len(groups)==len(expected)==3511
    caps=[]; total_centers=0
    for g in groups:
        p=(g['x'],g['y']); assert p in expected; expected.remove(p)
        cs=centers(p); total_centers+=len(cs); covered=set()
        for x,y,w,h in g['tiles']:
            assert 1<=w<=3 and 1<=h<=3
            covered.update(rect(x,y,w,h))
        assert cs<=covered and g['cap']==min(23,len(g['tiles']))
        x,y=p; edge=int(x in (1,68))+int(y in (1,68))
        c=min(23,g['cap'],local.get(p,23),8 if edge==2 else 13 if edge else 23)
        if 22<=y<=63 and 41<=x<=47: c=min(c,(13,14,14,17,18,19,22)[47-x])
        if 54<=x<=63 and 9<=y<=15: c=min(c,(13,14,14,17,18,19,22)[15-y])
        caps.append(dict(p=list(p),cap=c,loss=23-c,j=int(edge>0)))
    assert not expected
    dump('capacities.json',caps)
    summary=dict(poles=len(caps),centers=total_centers,excluded=sum(c['loss']>13 for c in caps),
                 usable=sum(c['loss']<=13 for c in caps),right_caps=[local[68,y] for y in range(1,16)],seconds=time.monotonic()-start)
    dump('certificate_summary.json',summary); print(summary,flush=True)

if __name__=='__main__': main()
