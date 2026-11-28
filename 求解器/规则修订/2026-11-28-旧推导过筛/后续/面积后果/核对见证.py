"""从坐标重数局部见证中的 X0、Y0、端口及桩亏额。"""
import json
from pathlib import Path
from collections import Counter
from 周边联合 import capacity

def check(file):
    d=json.loads(file.read_text())
    x,y,w,h=d['rect']
    def body(a,b,u,v):
        return {(i,j) for i in range(a,a+u) for j in range(b,b+v)}
    q=body(x,y,w,h); occupied=set()
    boards=d['placements']
    for kind,a,b,u,v,axis in boards:
        s=body(a,b,u,v)
        assert a>=1 and b>=1 and a+u<=70 and b+v<=70
        assert not (q|occupied)&s
        occupied.update(s)
    [[gap,side]]=d['pattern']
    g1,g2=(0,gap//3) if side else (gap//3,0)
    ore={(1,3*i+1+int(i>=g1)) for i in range(23)}
    ore.update((3*i+1+int(i>=g2),1) for i in range(23))
    assert not ore & (q|occupied)
    losses=0; categories=Counter()
    for kind,a,b,u,v,axis in boards:
        categories[kind]+=1
        if kind=='P':
            assert not (a in (1,68) or b in (1,68))
            loss=23-capacity(x,y,w,h,a,b)
            for low,pa,span,other,pb,extent in ((x,a,w,y,b,h),(y,b,h,x,a,w)):
                gap_side=max(other-(pb+2),pb-(other+extent))
                if low<=pa-5 and pa+7<=low+span and 0<=gap_side<=6:
                    loss=max(loss,(10,9,9,6,5,4,1)[gap_side])
            losses+=loss
        if axis<0:continue
        for sign in (-1,1):
            side=[(a-1 if sign<0 else a+u,b+i) for i in range(v)] if axis==0 else [
                    (a+i,b-1 if sign<0 else b+v) for i in range(u)]
            if kind=='C':side=[side[k] for k in (1,4,7)]
            usable=[t for t in side if 1<=min(t) and max(t)<=69 and t not in q|occupied]
            assert len(usable)>=(3 if kind=='C' else 1)
    assert losses<=13 and categories['P']<=10 and categories['C']<=1
    assert categories['3']<=dict(base=0,shaper=1,box=1,special=1,mix=2)[d['case']]
    assert categories['5']<=int(d['case']=='special')
    X=sum(t not in q|occupied for i in range(1,70) for t in [(i,69),(69,i)])
    ring={(i+di,j+dj) for i,j in q for di,dj in ((0,1),(1,0),(0,-1),(-1,0))
          if 0<=i+di<70 and 0<=j+dj<70}-q
    Y=len(ring-occupied)
    delta=dict(base=0,shaper=34,box=36,special=136,mix=72)[d['case']]
    assert X==d['X0'] and Y==d['Y0'] and d['K_upper']==0 and d['P']==10 and d['J']==0
    assert gap==6 and d['h']==0 and 4*w*h+160+delta+X+Y<=4558
    print(d['case'],d['rect'],'X0,Y0',X,Y,'桩亏额下界',losses)
if __name__=='__main__':
    root=Path(__file__).resolve().parent
    for stem in ('49_18_21_52_10_0_base','44_28_26_42_10_0_base','42_31_28_39_10_0_base',
        '39_35_31_35_10_0_shaperleft','51_13_19_57_10_0_box',
        '45_27_25_43_10_0_mix','50_17_20_53_10_0_special'):
        check(root/(stem+'.json'))
