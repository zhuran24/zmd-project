"""Fresh exact verification. Only submitted JSON multipliers/tiles are inputs.

The two geometry functions use explicit cells and rectangle inequalities,
respectively. Row labels are reconstructed in the documented certificate order.
"""
import os
os.sched_setaffinity(0,set(range(10)))
import json,time,math,hashlib
from fractions import Fraction
from pathlib import Path
from collections import defaultdict,Counter

OUT=Path(__file__).resolve().parent
SRC=OUT.parent/'推导78B'
SPECS=[(3,3,0),(3,3,1),(5,5,0),(5,5,1),(6,4,1),(4,6,0)]

def cells(x,y,w,h):return {(x+i,y+j) for i in range(w) for j in range(h)}
def overlap(x,y,w,h,u,v,a,b):return x<u+a and u<x+w and y<v+b and v<y+h
def allowed(x,y):return 1<=x<=69 and 1<=y<=69 and not(x>=49 and y>=17)

def enumerate_cells(p):
    pole=cells(5,5,2,2);out=[]
    def legal(c):
        if c in pole:return False
        return c[0]<=6 if p is None else allowed(c[0]+p[0]-5,c[1]+p[1]-5)
    for w,h,a in SPECS:
        for x in range(1-w,12):
            for y in range(1-h,12):
                b=cells(x,y,w,h)
                if not all(legal(c) for c in b):continue
                s=[[(x-1,t) for t in range(y,y+h)],[(x+w,t) for t in range(y,y+h)]] if a==0 else [[(t,y-1) for t in range(x,x+w)],[(t,y+h) for t in range(x,x+w)]]
                s=[tuple(c for c in z if legal(c)) for z in s]
                if all(s):out.append((w,h,a,x,y,b,s))
    return out

def enumerate_intervals(p):
    out=[]
    for w,h,a in SPECS:
        for x in range(-8,13):
            for y in range(-8,13):
                if not overlap(x,y,w,h,0,0,12,12) or overlap(x,y,w,h,5,5,2,2):continue
                if p is None:
                    if x+w>7:continue
                else:
                    xx=x+p[0]-5;yy=y+p[1]-5
                    if xx<1 or yy<1 or xx+w>70 or yy+h>70 or overlap(xx,yy,w,h,49,17,21,53):continue
                sides=[]
                for sign in (-1,1):
                    z=[]
                    for offset in range(h if a==0 else w):
                        xx=x+(-1 if sign<0 else w) if a==0 else x+offset
                        yy=y+offset if a==0 else y+(-1 if sign<0 else h)
                        if 5<=xx<7 and 5<=yy<7:continue
                        if p is None:
                            if xx>6:continue
                        elif not allowed(xx+p[0]-5,yy+p[1]-5):continue
                        z.append((xx,yy))
                    sides.append(tuple(z))
                if all(sides):out.append((w,h,a,x,y,sides))
    return out

def certificate(cert,p):
    one=enumerate_cells(p);two=enumerate_intervals(p)
    assert [(w,h,a,x,y,s) for w,h,a,x,y,b,s in one]==two
    occ=defaultdict(list)
    for i,(_,_,_,_,_,body,_) in enumerate(one):
        for c in body:occ[c].append(i)
    ordered=sorted(occ);rows=[]
    for c in ordered:rows.append(({i:1 for i in occ[c]},1))
    for i,(_,_,_,_,_,_,sides) in enumerate(one):
        for side in sides:
            count=Counter({i:1})
            for c in side:count.update(occ.get(c,[]))
            rows.append((dict(count),len(side)))
    den=math.lcm(*(d for _,n,d in cert['rows']+cert['bounds']))
    coeff=[0]*len(one);rhs=0
    for index,num,d in cert['rows']:
        assert num>=0 and d>0
        row,b=rows[index];k=num*(den//d);rhs+=k*b
        for i,a in row.items():coeff[i]+=k*a
    for i,num,d in cert['bounds']:
        assert num>=0 and d>0
        k=num*(den//d);coeff[i]+=k;rhs+=k
    assert min(coeff)>=den
    assert Fraction(rhs,den)==Fraction(*cert['upper'])
    assert rhs//den==cert['integer_upper']
    if 'n' in cert:assert len(one)==cert['n']
    # Second coefficient summation by columns, without using first row maps.
    row_mult={i:Fraction(n,d) for i,n,d in cert['rows']}
    bound_mult={i:Fraction(n,d) for i,n,d in cert['bounds']}
    occupied_weights={c:row_mult.get(i,Fraction(0)) for i,c in enumerate(ordered)}
    port_weights=defaultdict(Fraction)
    self_weights=defaultdict(Fraction)
    rhs2=sum(occupied_weights.values())+sum(bound_mult.values())
    for i,d in enumerate(two):
        for sidx,side in enumerate(d[-1]):
            v=row_mult.get(len(ordered)+2*i+sidx,Fraction(0))
            self_weights[i]+=v;rhs2+=v*len(side)
            for c in side:port_weights[c]+=v
    for i,(w,h,a,x,y,sides) in enumerate(two):
        z=bound_mult.get(i,0)+self_weights[i]
        for xx in range(x,x+w):
            for yy in range(y,y+h):z+=occupied_weights.get((xx,yy),0)+port_weights.get((xx,yy),0)
        assert z==Fraction(coeff[i],den) and z>=1
    assert rhs2==Fraction(rhs,den)
    return dict(columns=len(one),rows=len(rows),upper=str(rhs2),integer_upper=rhs//den,min_column=str(Fraction(min(coeff),den)))

def center_sets(p):
    px,py=p;one=set();two=set()
    supply=cells(px-5,py-5,12,12);pole=cells(px,py,2,2)
    for x in range(max(2,px-8),min(68,px+9)+1):
        for y in range(max(2,py-8),min(68,py+9)+1):
            b=cells(x-1,y-1,3,3)
            if b&supply and not b&pole and all(allowed(*c) for c in b):one.add((x,y))
    for x in range(max(2,px-6),min(68,px+7)+1):
        for y in range(max(2,py-6),min(68,py+7)+1):
            if overlap(x-1,y-1,3,3,49,17,21,53):continue
            if overlap(x-1,y-1,3,3,px,py,2,2):continue
            two.add((x,y))
    assert one==two
    return one

def main():
    t=time.monotonic();wall=certificate(json.loads((SRC/'wall0_certificate.json').read_text()),None)
    print('wall',wall,flush=True)
    locals={};audits=[]
    for cert in json.loads((SRC/'supply_strip_certificates.json').read_text()):
        for xy in cert['positions']:
            p=tuple(xy);assert p not in locals
            result=certificate(cert,p);locals[p]=result['integer_upper'];audits.append(dict(p=p,**result))
    expect={(x,y) for x in range(43,69) for y in range(1,17) if not overlap(x,y,2,2,49,17,21,53)}
    assert set(locals)==expect
    print('strip',len(locals),'seconds',time.monotonic()-t,flush=True)
    capacities=[];total=0;checked=[];seen=set()
    for cert in json.loads((SRC/'power_certificates.json').read_text())['17']:
        p=cert['x'],cert['y'];assert p not in seen;seen.add(p)
        cs=center_sets(p);total+=len(cs);covered=set()
        for x,y,w,h in cert['tiles']:
            assert 1<=w<=3 and 1<=h<=3;covered|=cells(x,y,w,h)
        assert cs<=covered and cert['cap']==min(23,len(cert['tiles']))
        # Independently check coverage by interval membership.
        assert all(any(x<=u<x+w and y<=v<y+h for x,y,w,h in cert['tiles']) for u,v in cs)
        x,y=p;edge=int(x in (1,68))+int(y in (1,68))
        caps=[23,len(cert['tiles']),locals.get(p,23),8 if edge==2 else 13 if edge==1 else 23]
        side=[]
        if 17<=y-5 and y+6<=69 and x+1<49:
            g=49-(x+2)
            if 0<=g<=6:side.append((13,14,14,17,18,19,22)[g])
        if 49<=x-5 and x+6<=69 and y+1<17:
            g=17-(y+2)
            if 0<=g<=6:side.append((13,14,14,17,18,19,22)[g])
        cap=min(caps+side);capacities.append(dict(p=p,cap=cap))
        checked.append(dict(p=p,centers=len(cs),tiles=len(cert['tiles']),cap=cap))
    expect={(x,y) for x in range(1,69) for y in range(1,69) if not overlap(x,y,2,2,49,17,21,53)}
    assert seen==expect
    original={tuple(v['p']):v['cap'] for v in json.loads((SRC/'capacities.json').read_text())}
    assert {tuple(v['p']):v['cap'] for v in capacities}==original
    summary=dict(wall=wall,local_positions=len(locals),local_columns=sum(r['columns'] for r in audits),local_rows=sum(r['rows'] for r in audits),poles=len(seen),centers=total,excluded=sum(v['cap']<10 for v in capacities),right_caps=[locals[68,y] for y in range(1,16)],seconds=time.monotonic()-t,all_submitted_capacities_match=True)
    (OUT/'capacities.json').write_text(json.dumps(capacities,separators=(',',':')))
    (OUT/'certificate_checks.json').write_text(json.dumps(dict(summary=summary,local=audits,groups=checked),indent=2))
    print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
