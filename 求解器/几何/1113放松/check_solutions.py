#!/usr/bin/env python3
"""Check saved witnesses by direct cell sets, independently of CP variables."""
import json
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def grid(r):
    x,y,w,h=r
    return {(u,v) for u in range(x,x+w) for v in range(y,y+h)}
def sides(r,axis,core=False):
    x,y,w,h=r
    if axis==0:
        kk=(1,4,7) if core else range(h)
        return [{(x-1,y+k) for k in kk},{(x+w,y+k) for k in kk}]
    kk=(1,4,7) if core else range(w)
    return [{(x+k,y-1) for k in kk},{(x+k,y+h) for k in kk}]
def loss(rr,r):
    x,y,_,_=rr; a,b,w,h=r
    edge=(x in (1,68))+(y in (1,68)); d=[0,9,15][edge]
    cg=[10,9,9,6,5,4,1]
    if b<=y-5 and y+7<=b+h:
        if x+2<=a and 0<=a-x-2<=6:d=max(d,cg[a-x-2])
        if x>=a+w and 0<=x-a-w<=6:d=max(d,cg[x-a-w])
    if a<=x-5 and x+7<=a+w:
        if y+2<=b and 0<=b-y-2<=6:d=max(d,cg[b-y-2])
        if y>=b+h and 0<=y-b-h<=6:d=max(d,cg[y-b-h])
    return d
def check(d):
    s=d['solution']; r=d['rect']; a,b,w,h=r; empty=grid(r)
    occupied=set(); bodies=set(); poles=[]; counts=Counter(); shell=d.get('model')=='boundary_projection'
    patterns=[(0,k) for k in range(24)]+[(k,0) for k in range(1,24)]
    gl,gb=patterns[s['warehouse_pattern']]; warehouse=set(); source_ports=set()
    for axis,g in [(0,gl),(1,gb)]:
        for start in list(range(0,3*g,3))+list(range(3*g+1,70,3)):
            unit={(0,k) for k in range(start,start+3)} if axis==0 else {(k,0) for k in range(start,start+3)}
            assert not unit&warehouse; warehouse|=unit
            source_ports.add((1,start+1) if axis==0 else (start+1,1))
    occupied|=warehouse
    transport=set(map(tuple,s['transport']))
    assert source_ports<=transport
    for p in s['placements']:
        rr=p['rect']; c=grid(rr); kind=p['kind']; counts[kind]+=1
        assert all(0<=x<70 and 0<=y<70 for x,y in c)
        assert not c&empty and not c&occupied
        occupied|=c; bodies|=c
        if kind=='pole':poles.append(rr)
        elif kind=='core':
            assert all(edge<=transport for edge in sides(rr,p['axis'],True))
            x,y,_,_=rr
            ins=({(x+k,y-1) for k in range(1,8)}|{(x+k,y+9) for k in range(1,8)}) if p['axis']==0 else ({(x-1,y+k) for k in range(1,8)}|{(x+9,y+k) for k in range(1,8)})
            assert len(ins&transport)>=2
        else:assert all(edge&transport for edge in sides(rr,p['axis']))
    assert not transport&occupied and not transport&empty
    assert all(0<=x<70 and 0<=y<70 for x,y in transport)
    P=s['P']; J=s['J']; jp=sum(x in (1,68) or y in (1,68) for x,y,_,_ in poles)
    assert 10<=P<=12 and 9*J<=23*P-217
    if shell:
        assert counts['small']<=131 and counts['medium']<=48 and counts['large']<=38 and counts['core']<=1
        assert len(poles)<=P and jp<=J<=jp+P-len(poles)
        assert sum(loss(p,r) for p in poles)+9*(J-jp)<=23*P-217
    else:
        assert counts['small']==131 and counts['medium']==48 and counts['large']==38 and counts['core']==1
        assert P==len(poles) and J==jp
        assert sum(loss(p,r) for p in poles)<=23*P-217
        for p in s['placements']:
            if p['kind'] in ('small','medium','large'):
                assert any(grid(p['rect'])&grid((px-5,py-5,12,12)) for px,py,_,_ in poles)
        q=next(iter(({(0,k) for k in range(70)}|{(k,0) for k in range(70)})-warehouse))
        assert len(transport)>=208+int(q in transport)
        expected={'粉碎机':68,'精炼炉':51,'配件机':6,'塑形机':6,'种植机':32,'采种机':16,'研磨机':32,'封装机':3,'灌装机':3}
        assert Counter(p['machine_type'] for p in s['placements'] if 'machine_type' in p)==expected
    xs=[(69,k) for k in range(1,69)]+[(k,69) for k in range(1,69)]
    X=sum(pt not in bodies|empty for pt in xs)
    if (69,69) not in empty and not any((69,69) in grid(p) for p in poles):X+=2
    ring=([(a-1,k) for k in range(b,b+h)] + ([(a+w,k) for k in range(b,b+h)] if a+w<70 else [])
          +[(k,b-1) for k in range(a,a+w)] + ([(k,b+h) for k in range(a,a+w)] if b+h<70 else []))
    Y=sum(pt not in bodies for pt in ring)
    assert 16*P-2*J+X+Y<=187
    if shell:assert X==s['X'] and Y==s['Y']
    return dict(P=P,J=J,X=X,Y=Y,body_counts=dict(counts),transport_count=len(transport))
def main():
    results=[]
    for path in sorted((ROOT/'results').glob('*.json')):
        data=json.loads(path.read_text())
        if 'solution' in data:
            results.append(dict(file=path.name,status='PASS',model=data.get('model','full'),**check(data)))
    (ROOT/'solution_checks.json').write_text(json.dumps(dict(status='PASS',checked=len(results),results=results),ensure_ascii=False,indent=2))
    print('PASS',len(results),'saved witnesses')
if __name__=='__main__':main()
