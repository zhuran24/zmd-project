#!/usr/bin/env python3
"""Direct grid verification of saved witnesses; does not import either model."""
from pathlib import Path
from collections import Counter
import json,hashlib

BASE=Path('/home/zhuran24/zmd-research-fresh/求解器/候选约束轮次/第60-62轮/复核62')

def check(r):
    a,b,W,H=r['R']
    empty_rect={(i,j) for i in range(a,a+W) for j in range(b,b+H)}
    owner={};counts=Counter();pole_j=0;total_loss=0;transport=set()
    for idx,u in enumerate(r['chosen']):
        x,y,w,h=u['x'],u['y'],u['w'],u['h'];kind=u['kind'];axis=u['axis']
        valid_shapes={'s':[(3,3,'h'),(3,3,'v')],'m':[(5,5,'h'),(5,5,'v')],
                      'l':[(6,4,'v'),(4,6,'h')],'c':[(9,9,'h'),(9,9,'v')],'p':[(2,2,'-')]}
        assert (w,h,axis) in valid_shapes[kind]
        assert 1<=x and 1<=y and x+w<=70 and y+h<=70
        counts[kind]+=1
        for i in range(x,x+w):
            for j in range(y,y+h):
                assert (i,j) not in owner and (i,j) not in empty_rect
                owner[i,j]=idx
        if kind=='p':
            boundary=sum([1 in (x,x+1),69 in (x,x+1),1 in (y,y+1),69 in (y,y+1)])
            pole_j+=bool(boundary)
            capacities=[23]
            if boundary: capacities.append(8 if boundary==2 else 14)
            # Calculate distances to all four sides using inclusive last cells.
            vertical_projection=set(range(y-5,y+7))
            horizontal_projection=set(range(x-5,x+7))
            if vertical_projection.issubset(set(range(b,b+H))):
                if x+1<a: gap=a-(x+1)-1
                elif x>a+W-1: gap=x-(a+W-1)-1
                else: gap=-1
                if gap in range(7): capacities.append([13,14,14,17,18,19,22][gap])
            if horizontal_projection.issubset(set(range(a,a+W))):
                if y+1<b: gap=b-(y+1)-1
                elif y>b+H-1: gap=y-(b+H-1)-1
                else: gap=-1
                if gap in range(7): capacities.append([13,14,14,17,18,19,22][gap])
            loss=23-min(capacities)
            assert u['j']==int(boundary>0) and u['loss']==loss
            total_loss+=loss
    low=0 if r['allow_edge0_ports'] else 1
    def usable(c):
        return low<=c[0]<=69 and low<=c[1]<=69 and c not in empty_rect and c not in owner
    for u in r['chosen']:
        x,y,w,h=u['x'],u['y'],u['w'],u['h']
        if u['kind']=='p': continue
        left=[(x-1,j) for j in range(y,y+h)]
        right=[(x+w,j) for j in range(y,y+h)]
        down=[(i,y-1) for i in range(x,x+w)]
        up=[(i,y+h) for i in range(x,x+w)]
        sides=(left,right) if u['axis']=='h' else (down,up)
        if u['kind']=='c':
            take=[side[k] for side in sides for k in (1,4,7)]
            assert all(usable(c) for c in take)
            transport.update(take)
            storage=(down,up) if u['axis']=='h' else (left,right)
            available=[side[k] for side in storage for k in range(1,8) if usable(side[k])]
            assert len(available)>=2
            transport.update(available[:2])
        else:
            for side in sides:
                available=[c for c in side if usable(c)]
                assert available
                transport.add(available[0])
    P,J,hid=r['P'],r['J'],r['hidden_boundary_poles']
    assert 10<=P<=12 and counts['p']+hid<=P and hid>=0
    assert J==pole_j+hid and total_loss+9*hid<=23*P-217
    assert counts['s']<=131 and counts['m']<=48 and counts['l']<=38 and counts['c']<=1
    X=0;Y=0;overlap=[];xholes=[];yholes=[]
    for i in range(70):
        for j in range(70):
            c=(i,j)
            if c in empty_rect or c in owner: continue
            wx=int(i==69 and 1<=j<=68)+int(j==69 and 1<=i<=68)+2*int(c==(69,69))
            wy=int(any((i+di,j+dj) in empty_rect for di,dj in ((1,0),(-1,0),(0,1),(0,-1))))
            X+=wx;Y+=wy
            if wx: xholes.append([i,j,wx])
            if wy: yholes.append([i,j])
            if wx and wy: overlap.append([i,j,wx+wy])
    assert (X,Y)==(r['X'],r['Y'])
    S=16*P-2*J+X+Y
    assert S==r['S']
    if r['mode']=='joint': assert S==r['objective']
    return {'R':r['R'],'P':P,'J':J,'X':X,'Y':Y,'S':S,'counts':dict(counts),
            'loss':total_loss+9*hid,'loss_budget':23*P-217,'both_X_and_Y_uncovered':overlap,
            'X_holes':xholes,'Y_holes':yholes,'port_witness_cells':sorted(transport),'passed':True}

def main():
    result=[]
    paths=sorted(BASE.glob('mip_*.json'))+sorted(BASE.glob('weak_49_13_*.json'))+sorted(BASE.glob('strict_49_13_*.json'))
    for path in paths:
        r=json.loads(path.read_text())
        if 'chosen' not in r: continue
        c=check(r);c['file']=path.name;c['sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
        result.append(c)
    out={'checked':len(result),'all_passed':all(r['passed'] for r in result),'results':result}
    (BASE/'witness_checks.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
    print(json.dumps({'checked':out['checked'],'all_passed':out['all_passed']}))

if __name__=='__main__':main()
