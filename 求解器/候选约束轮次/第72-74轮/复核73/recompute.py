#!/usr/bin/env python3
"""Independent round 73 checker. Never imports another round's program.

All output paths are confined to this file's directory. Run with python -B.
Rectangles use (x,y,width,height), integer cells, and half-open bounds.
"""
import os
for env in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[env] = '1'
import argparse
import hashlib
import json
import math
import time
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

OUT = Path(__file__).resolve().parent
ROUNDS = OUT.parent.parent
ROOT = ROUNDS.parent.parent
HOLE = (49,17,21,53)
SHAPES = [(3,3,0),(3,3,1),(5,5,0),(5,5,1),(6,4,1),(4,6,0)]
EDGES = [set((69,y) for y in range(1,17)), set((x,69) for x in range(1,49)),
         set((48,y) for y in range(17,70)), set((x,16) for x in range(49,70))]
TARGET = set.union(*EDGES)

def read(rel):
    return json.loads((ROUNDS / rel).read_text())

def save(name,obj):
    (OUT / (name+'.json')).write_text(json.dumps(obj, ensure_ascii=False, indent=2)+'\n')

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def cells(r):
    x,y,w,h = r
    return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}

def intersects(r,s):
    return max(r[0],s[0]) < min(r[0]+r[2],s[0]+s[2]) and max(r[1],s[1]) < min(r[1]+r[3],s[1]+s[3])

def legal(c):
    x,y=c
    return 1<=x<=69 and 1<=y<=69 and not(x>=49 and y>=17)

def sides(r,axis):
    x,y,w,h=r
    return ([[(x-1,j) for j in range(y,y+h)],[(x+w,j) for j in range(y,y+h)]] if axis==0 else
            [[(i,y-1) for i in range(x,x+w)],[(i,y+h) for i in range(x,x+w)]])

def centers(p):
    x,y=p
    supply=(x-5,y-5,12,12)
    pole=(x,y,2,2)
    ans=set()
    for i in range(max(2,x-6),min(68,x+7)+1):
        for j in range(max(2,y-6),min(68,y+7)+1):
            small=(i-1,j-1,3,3)
            if not intersects(small,HOLE) and not intersects(small,pole) and intersects(small,supply):
                ans.add((i,j))
    return ans

def local_domain(p=None):
    """Order used by certificate row numbers, reconstructed from geometry."""
    result=[]
    # Translate actual board cells so the pole's power square starts at zero.
    def ok(c):
        x,y=c
        if 5<=x<7 and 5<=y<7:return False
        if p is None:return x<=6
        return legal((x+p[0]-5,y+p[1]-5))
    for w,h,a in SHAPES:
        for x in range(1-w,12):
            for y in range(1-h,12):
                r=(x,y,w,h)
                if not all(ok(c) for c in cells(r)):continue
                ports=[tuple(c for c in side if ok(c)) for side in sides(r,a)]
                if all(ports):result.append((r,a,ports))
    return result

def rational_check(certificate,p=None):
    bs=local_domain(p)
    occ=defaultdict(list)
    for i,(r,a,ps) in enumerate(bs):
        for c in cells(r):occ[c].append(i)
    cell_order=sorted(occ)
    coef=[Fraction(0) for _ in bs]
    rhs=Fraction(0)
    rowids=set()
    for row,num,den in certificate['rows']:
        assert row not in rowids
        rowids.add(row)
        f=Fraction(num,den)
        assert f>=0
        if row<len(cell_order):
            terms={i:1 for i in occ[cell_order[row]]}; b=1
        else:
            i,side=divmod(row-len(cell_order),2)
            assert i<len(bs)
            port=bs[i][2][side]; b=len(port)
            terms=Counter({i:1})
            for c in port:terms.update(occ.get(c,()))
        rhs+=f*b
        for i,k in terms.items():coef[i]+=k*f
    for i,num,den in certificate['bounds']:
        f=Fraction(num,den)
        assert f>=0 and 0<=i<len(bs)
        coef[i]+=f;rhs+=f
    assert all(c>=1 for c in coef)
    assert rhs==Fraction(*certificate['upper'])
    assert math.floor(rhs)==certificate['integer_upper']
    if 'n' in certificate:assert len(bs)==certificate['n']
    return dict(columns=len(bs),rows=len(cell_order)+2*len(bs),upper=str(rhs),cap=math.floor(rhs))

def certificates():
    wall=rational_check(read('第69-71轮/推导69/wall0_certificate.json'))
    assert wall==dict(columns=550,rows=1352,upper='1846/135',cap=13)
    local={}; cols=rows=0
    for cert in read('第69-71轮/推导69/supply_strip_certificates.json'):
        for p in cert['positions']:
            p=tuple(p);assert p not in local
            result=rational_check(cert,p)
            local[p]=result['cap']; cols+=result['columns'];rows+=result['rows']
    expected={(x,y) for x in range(43,69) for y in range(1,17) if not intersects((x,y,2,2),HOLE)}
    assert set(local)==expected and len(local)==395
    print('rational certificates:',wall,'local',len(local),flush=True)
    group={}; center_count=0
    for cert in read('第66-68轮/推导66/power_certificates.json')['17']:
        p=(cert['x'],cert['y']);assert p not in group
        cs=centers(p); covered=set()
        for x,y,w,h in cert['tiles']:
            assert 1<=w<=3 and 1<=h<=3
            covered.update(cells((x,y,w,h)))
        assert cs<=covered
        assert cert['cap']==min(23,len(cert['tiles']))
        group[p]=cert['cap'];center_count+=len(cs)
    expected={(x,y) for x in range(1,69) for y in range(1,69) if not intersects((x,y,2,2),HOLE)}
    assert set(group)==expected and len(group)==3511
    losses={}
    for p,c in group.items():
        x,y=p;edge=int(x in (1,68))+int(y in (1,68))
        loss=max(23-c,23-local.get(p,23),[0,10,15][edge])
        # Left and bottom side adjacency: whole supply projection contained.
        g=49-(x+2)
        if 0<=g<=6 and 17<=y-5 and y+7<=70:loss=max(loss,[10,9,9,6,5,4,1][g])
        g=17-(y+2)
        if 0<=g<=6 and 49<=x-5 and x+7<=70:loss=max(loss,[10,9,9,6,5,4,1][g])
        losses[p]=loss
    save('capacities',[dict(x=x,y=y,loss=l) for (x,y),l in sorted(losses.items())])
    result=dict(wall=wall,local_positions=len(local),local_columns=cols,local_rows=rows,
                right_edge=[local[(68,y)] for y in range(1,16)],group_positions=len(group),
                center_count=center_count,admissible=sum(l<=13 for l in losses.values()),
                excluded=sum(l>13 for l in losses.values()),corner_losses=[losses[p] for p in [(47,68),(68,15)]])
    # Corrupt a rational bound: exact check must reject it.
    damaged=read('第69-71轮/推导69/wall0_certificate.json');damaged['integer_upper']=12
    try:rational_check(damaged)
    except AssertionError:result['damaged_cap_rejected']=True
    else:raise AssertionError('damaged certificate accepted')
    save('certificates',result);print(json.dumps(result),flush=True)

def get_losses():
    return {(d['x'],d['y']):d['loss'] for d in json.loads((OUT/'capacities.json').read_text())}

def units(project=True):
    """Scan every base anchor, without using a submitted option list."""
    bs=[]
    for w,h,a in SHAPES+[(9,9,0),(9,9,1)]:
        kind={3:'s',5:'m',6:'l',4:'l',9:'c'}[w]
        for x in range(1,71-w):
            for y in range(1,71-h):
                r=(x,y,w,h)
                if intersects(r,HOLE):continue
                body=cells(r)
                if not body&TARGET:continue
                ps=sides(r,a);needs=[1,1]
                if kind=='c':
                    if x<=3 and y<=3:continue
                    if x<2 or y<2 or (x<=3 and a==0) or (y<=3 and a==1):continue
                    if (y==61 and x<=6 and a==0) or (x==61 and y<=6 and a==1):continue
                    take=[side[k] for side in ps for k in (1,4,7)]
                    if not all(map(legal,take)):continue
                    put=[c for side in sides(r,1-a) for c in side[1:-1] if legal(c)]
                    ps=[[c] for c in take]+[put];needs=[1]*6+[2]
                else:ps=[[c for c in side if legal(c)] for side in ps]
                if any(len(side)<n for side,n in zip(ps,needs)):continue
                bs.append(dict(kind=kind,rect=r,axis=a,ports=ps,needs=needs,loss=0,j=0))
    machines=[b['rect'] for b in bs if b['kind']!='c']
    allp=kept=0
    for (x,y),l in sorted(get_losses().items()):
        if l>13:continue
        allp+=1;r=(x,y,2,2);j=int(x in (1,68) or y in (1,68))
        if project and not(j or cells(r)&TARGET or any(intersects(m,(x-5,y-5,12,12)) for m in machines)):continue
        kept+=1;bs.append(dict(kind='p',rect=r,axis=-1,ports=[],needs=[],loss=l,j=j))
    return bs

def warehouses():
    ans=[]
    for gx in range(24):
        for gy in range(24):
            if gx and gy:continue
            ports=set()
            for gap,axis in [(gx,0),(gy,1)]:
                # Build the actual 3-cell rectangles, skipping the sole gap.
                occupied=[v for v in range(70) if v!=3*gap]
                triples=[occupied[i:i+3] for i in range(0,69,3)]
                assert all(t==list(range(t[0],t[0]+3)) for t in triples)
                ports.update((1,t[1]) if axis==0 else (t[1],1) for t in triples)
            assert len(ports)==46
            ans.append(((3*gx,3*gy),ports))
    assert len(ans)==47
    return ans

def witness():
    d=read('第72-74轮/推导72/witness185.json')
    bs=d['chosen']; allcells=set(); actual=[]
    for b in bs:
        r=tuple(b[k] for k in ('x','y','w','h'));body=cells(r)
        assert all(map(legal,body)) and not(body&allcells)
        allcells|=body;actual.append((b['kind'],r,{'h':0,'v':1,'-':-1}[b['axis']]))
    assert len(set(actual))==len(actual)
    domain={(b['kind'],b['rect'],b['axis']):b for b in units(False)}
    assert set(actual)<=set(domain)
    weak=0; free=[]
    for key in actual:
        b=domain[key]
        ns=[len(set(side)-allcells) for side in b['ports']]
        assert all(k>=n for k,n in zip(ns,b['needs']))
        if b['kind']=='l':
            assert max(ns)>=2
            weak+=max(ns)<3
        free.append(dict(kind=key[0],rect=key[1],port_free=ns))
    assert weak<=1
    wpatterns=[gap for gap,ps in warehouses() if not ps&allcells]
    assert tuple(d['warehouse_gaps']) in wpatterns
    poles=[r for k,r,a in actual if k=='p']; ms=[r for k,r,a in actual if k in ('s','m','l')]
    assert len(poles)==10
    counts=[sum(intersects(r,(p[0]-5,p[1]-5,12,12)) for p in poles) for r in ms]
    assert min(counts)>=1
    losses=get_losses(); loss=sum(losses[p[:2]] for p in poles);rep=sum(k-1 for k in counts)
    gaps=[len(e-allcells) for e in EDGES];j=sum(p[0] in (1,68) or p[1] in (1,68) for p in poles)
    score=160-2*j+sum(gaps)
    assert score==d['S']==185 and loss+rep<=13
    result=dict(counts=dict(Counter(k for k,r,a in actual)),S=score,J=j,gaps=gaps,
                X=sum(gaps[:2]),Y=sum(gaps[2:]),loss=loss,repeat=rep,coverage_counts=counts,
                compatible_warehouse_gaps=wpatterns,port_free=free)
    # All subset bounds, each using one common partition for all poles.
    grid=[]
    for a in range(3):
        for b in range(3):
            touches=[{((x+a)//3,(y+b)//3) for x,y in centers(p[:2])} for p in poles]
            caps=[23-losses[p[:2]] for p in poles]
            best=(10**9,None,None,None)
            for mask in range(1<<10):
                union=set();inside=0
                for i in range(10):
                    if mask>>i&1:union|=touches[i];inside+=caps[i]
                bound=sum(caps)-inside+len(union)
                if bound<best[0]:best=(bound,mask,len(union),inside)
            grid.append(dict(a=a,b=b,all_groups=len(set.union(*touches)),upper=best[0],
                             mask=best[1],subset_groups=best[2],subset_capacity=best[3],
                             subset=[poles[i][:2] for i in range(10) if best[1]>>i&1],
                             D=sum(caps)-best[0]))
    result['groups']=grid
    # Transposition preserves bodies, ports, supply and weighted X/Y.
    trans={(y,x) for x,y in allcells}
    assert gaps==[len({(y,x) for x,y in e}-trans) for e in EDGES]
    result['transpose_pass']=True
    result['wrong_S184_rejected']=(score!=184)
    result['duplicate_pole_rejected']=bool(cells(poles[0])&allcells)
    save('witness',result);print(json.dumps({k:v for k,v in result.items() if k not in ('port_free','groups')}),flush=True)
    print('grid bounds',[(g['a'],g['b'],g['upper']) for g in grid],flush=True)

def snapshot():
    paths=[ROOT/n for n in ['《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','候选约束.txt']]
    paths += [ROUNDS/p for p in ['第72-74轮/推导72.md','第72-74轮/推导72/witness185.json',
             '第69-71轮/推导69/wall0_certificate.json','第69-71轮/推导69/supply_strip_certificates.json',
             '第66-68轮/推导66/power_certificates.json']]
    save('input_manifest',[dict(path=str(p),sha256=digest(p),bytes=p.stat().st_size) for p in paths])

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['certificates','witness','snapshot']);a=p.parse_args()
    globals()[a.mode]()
