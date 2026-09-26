"""Rebuild and verify local rational/grid certificates from rule geometry."""
from geometry_a import *
from fractions import Fraction
from collections import defaultdict
import hashlib,time,shutil

def rational_check(cert,p):
    body0=cells((5,5,2,2))
    def ok(c):
        if c in body0:return False
        return c[0]<=6 if p is None else available((c[0]+p[0]-5,c[1]+p[1]-5))
    objects=[]
    for _,w,h,axis in SPECS:
        for x in range(1-w,12):
            for y in range(1-h,12):
                r=(x,y,w,h);b=cells(r)
                if not all(ok(c) for c in b):continue
                ports=[[c for c in side if ok(c)] for side in sides(r,axis)]
                if all(ports):objects.append((b,ports))
    incidence=defaultdict(list)
    for i,(b,_) in enumerate(objects):
        for c in b:incidence[c].append(i)
    constraints=[(Counter({i:1 for i in incidence[c]}),1) for c in sorted(incidence)]
    for i,(_,ports) in enumerate(objects):
        for ps in ports:
            co=Counter({i:1})
            for c in ps:co.update(incidence[c])
            constraints.append((co,len(ps)))
    total=[Fraction(0) for _ in objects];rhs=Fraction(0)
    for rid,n,d in cert['rows']:
        assert n>=0 and d>0
        co,b=constraints[rid];f=Fraction(n,d);rhs+=f*b
        for i,v in co.items():total[i]+=f*v
    for i,n,d in cert['bounds']:
        assert n>=0 and d>0
        f=Fraction(n,d);total[i]+=f;rhs+=f
    assert min(total)>=1 and rhs==Fraction(*cert['upper'])
    assert rhs.numerator//rhs.denominator==cert['integer_upper']
    return dict(columns=len(objects),rows=len(constraints),upper=str(rhs),floor=rhs.numerator//rhs.denominator)

def main():
    start=time.monotonic()
    sources={'wall_certificate.json':ROUNDS/'第69-71轮/推导69/wall0_certificate.json',
             'strip_certificates.json':ROUNDS/'第69-71轮/推导69/supply_strip_certificates.json',
             'grid_certificates.json':ROUNDS/'第66-68轮/推导66/power_certificates.json'}
    manifest={}
    for name,path in sources.items():
        shutil.copyfile(path,OUT/name)
        manifest[name]={'source':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
    for name in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt']:
        manifest[name]={'source':str(ROOT/name),'sha256':hashlib.sha256((ROOT/name).read_bytes()).hexdigest()}
    dump('input_manifest.json',manifest)
    wall=rational_check(read(OUT/'wall_certificate.json'),None)
    print('wall',wall,flush=True)
    local={};checks=[]
    for cert in read(OUT/'strip_certificates.json'):
        for xy in cert['positions']:
            p=tuple(xy);assert p not in local
            ans=rational_check(cert,p);local[p]=ans['floor'];checks.append(dict(p=p,**ans))
    expected={(x,y) for x in range(43,69) for y in range(1,17) if legal((x,y,2,2))}
    assert set(local)==expected
    print('strip',len(local),flush=True)
    capacities=[];center_count=0
    expected={(x,y) for x in range(1,69) for y in range(1,69) if legal((x,y,2,2))}
    for cert in read(OUT/'grid_certificates.json')['17']:
        p=cert['x'],cert['y'];assert p in expected;expected.remove(p)
        groups=set()
        for r in cert['tiles']:
            assert 1<=r[2]<=3 and 1<=r[3]<=3
            groups.update(cells(r))
        cs=set()
        for x in range(max(2,p[0]-6),min(68,p[0]+7)+1):
            for y in range(max(2,p[1]-6),min(68,p[1]+7)+1):
                r=(x-1,y-1,3,3)
                if legal(r) and not hit(r,(*p,2,2)) and hit(r,supply(p)):cs.add((x,y))
        assert cs<=groups and cert['cap']==min(23,len(cert['tiles']))
        center_count+=len(cs)
        j=edge_j(p);cap=min(23,len(cert['tiles']),local.get(p,23),8 if j==2 else wall['floor'] if j else 23)
        x,y=p
        if 22<=y<=63 and 41<=x<=47:cap=min(cap,(13,14,14,17,18,19,22)[47-x])
        if 54<=x<=63 and 9<=y<=15:cap=min(cap,(13,14,14,17,18,19,22)[15-y])
        capacities.append(dict(p=p,cap=cap,j=int(j>0),t=weight((*p,2,2))))
    assert not expected
    dump('capacities.json',capacities)
    summary=dict(wall=wall,strip_positions=len(local),poles=len(capacities),centers=center_count,
                 usable=sum(c['cap']>=10 for c in capacities),seconds=time.monotonic()-start)
    dump('certificate_checks_a.json',dict(summary=summary,local=checks));print(summary,flush=True)
if __name__=='__main__':main()
