"""Independent, exact replay of the supplied rational multipliers and tiles.
Only JSON data are read from prior rounds; all columns and rows are rebuilt.
"""
from geometry77 import *
from fractions import Fraction as Q
from collections import defaultdict
import hashlib,time

def columns(p):
    pole=cells((5,5,2,2))
    def valid(c):
        if c in pole:return False
        if p is None:return c[0]<=6
        return allowed((c[0]+p[0]-5,c[1]+p[1]-5))
    ans=[]
    # Certificate row labels use size, axis, x, y lexicographic enumeration.
    for _,w,h,a in SPECS:
        for x in range(-w+1,12):
            for y in range(-h+1,12):
                body=cells((x,y,w,h))
                if not all(valid(c) for c in body):continue
                sides=[[c for c in side if valid(c)] for side in edges((x,y,w,h),a)]
                if all(sides):ans.append((body,sides))
    return ans

def verify(cert,p):
    cols=columns(p); occ=defaultdict(list)
    for k,(body,_) in enumerate(cols):
        for c in body:occ[c].append(k)
    rows=[(Counter({k:1 for k in occ[c]}),1) for c in sorted(occ)]
    for k,(_,sides) in enumerate(cols):
        for side in sides:
            row=Counter({k:1})
            for c in side:row.update(occ[c])
            rows.append((row,len(side)))
    coeff=[Q(0)]*len(cols); rhs=Q(0)
    for i,n,d in cert['rows']:
        assert n>=0 and d>0 and 0<=i<len(rows)
        v=Q(n,d); row,b=rows[i]; rhs+=v*b
        for k,a in row.items():coeff[k]+=v*a
    for i,n,d in cert['bounds']:
        assert n>=0 and d>0 and 0<=i<len(cols)
        coeff[i]+=Q(n,d); rhs+=Q(n,d)
    assert min(coeff)>=1 and rhs==Q(*cert['upper'])
    assert rhs.numerator//rhs.denominator==cert['integer_upper']
    if 'n' in cert:assert len(cols)==cert['n']
    return dict(columns=len(cols),rows=len(rows),upper=str(rhs),min_coefficient=str(min(coeff)))

def main():
    t=time.monotonic(); inputs={}
    for name in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt']:
        inputs[name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
    save('inputs.json',inputs)
    wall=verify(read(OUT/'wall0_certificate.json'),None)
    assert (wall['columns'],wall['rows'],wall['upper'])==(550,1352,'1846/135')
    print('wall',wall,flush=True)
    local={}; audits=[]
    for cert in read(OUT/'supply_strip_certificates.json'):
        for xy in cert['positions']:
            p=tuple(xy); assert p not in local
            audit=verify(cert,p); local[p]=cert['integer_upper'];audits.append(dict(p=p,**audit))
    expected={(x,y) for x in range(43,69) for y in range(1,17) if rect_allowed((x,y,2,2))}
    assert set(local)==expected and len(expected)==395
    print('local 395 passed',flush=True)
    expected={(x,y) for x in range(1,69) for y in range(1,69) if rect_allowed((x,y,2,2))}
    capacities=[]; nc=0
    for cert in read(OUT/'power_certificates.json')['17']:
        p=(cert['x'],cert['y']);assert p in expected;expected.remove(p)
        # Direct 3x3 cell intersection, with a larger candidate window, is a
        # second reconstruction independent of centers()'s clipped range.
        cs=set(); pb=cells((*p,2,2)); supply=cells(power(p))
        for x in range(max(2,p[0]-8),min(68,p[0]+9)+1):
            for y in range(max(2,p[1]-8),min(68,p[1]+9)+1):
                b=cells((x-1,y-1,3,3))
                if all(map(allowed,b)) and b.isdisjoint(pb) and b&supply:cs.add((x,y))
        assert cs==centers(p);nc+=len(cs)
        covered=set()
        for tile in cert['tiles']:
            assert 1<=tile[2]<=3 and 1<=tile[3]<=3
            covered.update(cells(tile))
        assert cs<=covered and cert['cap']==min(23,len(cert['tiles']))
        e=edge_count(p); cap=min(23,len(cert['tiles']),local.get(p,23),8 if e==2 else 13 if e else 23)
        x,y=p
        if 22<=y<=63 and 41<=x<=47:cap=min(cap,(13,14,14,17,18,19,22)[47-x])
        if 54<=x<=63 and 9<=y<=15:cap=min(cap,(13,14,14,17,18,19,22)[15-y])
        capacities.append(dict(p=p,cap=cap))
    assert not expected
    save('capacities.json',capacities)
    save('rational_checks.json',dict(wall=wall,local=audits))
    units=domain(capacities);machines=[b for b in units if b['kind'] in ('s','m','l')]
    projected=[b for b in units if b['kind']!='p' or b['j'] or cells(b['r'])&WEIGHTS.keys() or any(hit(power(b['r'][:2]),m['r']) for m in machines)]
    save('domain.json',units);save('projected_domain.json',projected)
    summary=dict(wall=wall,local_positions=len(local),poles=len(capacities),centers=nc,
      excluded=sum(c['cap']<10 for c in capacities),full_domain=dict(Counter(b['kind'] for b in units)),
      projected_domain=dict(Counter(b['kind'] for b in projected)),right_caps=[local[68,y] for y in range(1,16)],seconds=time.monotonic()-t)
    save('certificate_summary.json',summary);print(summary,flush=True)

if __name__=='__main__':main()
