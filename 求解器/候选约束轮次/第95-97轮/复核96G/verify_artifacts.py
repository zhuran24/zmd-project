"""Check independently generated numbers and local packing witnesses.

Only JSON from the derivation is compared, after the review calculations;
none of its Python files are imported or executed.
"""
from pathlib import Path
from collections import Counter
from functools import cache
from fractions import Fraction
import hashlib
import json
import platform
import time

OUT=Path(__file__).resolve().parent
ROUND=OUT.parent


def read(name):
    return json.loads((OUT/name).read_text())


def square(x,y,w=3,h=3):
    return {(i,j) for i in range(x,x+w) for j in range(y,y+h)}


@cache
def frame(gl,gb,mode):
    sources=[]
    warehouse=set()
    for axis,g in ((0,gl),(1,gb)):
        starts=list(range(0,g,3))+list(range(g+1,70,3))
        for start in starts:
            warehouse|={(0,t) if axis==0 else (t,0) for t in range(start,start+3)}
            sources.append((axis,start+1))
    ore={(1,s) if axis==0 else (s,1) for axis,s in sources}
    fixed=set()
    possible=[]
    if mode:
        fixed=square(1,gl-1) if gl else square(gb-1,1)
        if gl:
            possible=[(x,y) for x in (2,3) for y in (gl-2,gl+2) if not (gl==3 and y==1)]
        else:
            possible=[(x,y) for y in (2,3) for x in (gb-2,gb+2) if not (gb==3 and x==1)]
    return sources,warehouse,ore,fixed,possible


def witness_check(row):
    gl,gb,mode,b,h=row['key']
    sources,warehouse,ore,fixed,possible=frame(gl,gb,mode)
    rectangle=square(2,b,6,h) if h else set()
    d=sum(b<=s<b+h for axis,s in sources if axis==0) if h else 0
    assert d==row['d']
    if not row['compatible']:
        assert fixed&rectangle
        return
    assert not fixed&rectangle
    taken=set()
    used_sources=set()
    axes=Counter()
    for axis,x,y in row['chosen']:
        assert x>=1 and y>=1 and x+2<70 and y+2<70
        assert x==2 if axis==0 else y==2
        start=y if axis==0 else x
        possible_sources=[(ax,s) for ax,s in sources if ax==axis and start<=s<=start+2]
        assert len(possible_sources)==1
        assert possible_sources[0] not in used_sources
        used_sources.add(possible_sources[0])
        body=square(x,y)
        assert not body&(taken|warehouse|ore|fixed|rectangle)
        taken|=body
        axes[axis]+=1
    if gl==3:
        assert axes[1]<=22
    if gb==3:
        assert axes[0]<=22
    tangent=0 if mode==0 else 1 if mode==2 and max(gl,gb)==3 else 2
    assert tangent==row['tangent']
    bonus=row['bonus']
    assert bonus in (0,1)
    if bonus:
        assert mode==2
        assert any(p not in (taken|rectangle) for p in possible)
    assert row['value']==46+tangent+len(row['chosen'])+bonus
    if 'bound' in row:
        assert row['value']==row['bound']
    assert row['value']+d<=91


def main():
    start=time.monotonic()
    a,b=read('geometry_cells.json'),read('geometry_intervals.json')
    witness_count=0
    for name in ('base','close'):
        ka={tuple(r['key']):r for r in a[name]}
        kb={tuple(r['key']):r for r in b[name]}
        assert ka.keys()==kb.keys()
        for k in ka:
            ra,rb=ka[k],kb[k]
            for field in ('compatible','d','value','options'):
                assert ra.get(field)==rb.get(field),(k,field)
            for r in (ra,rb):
                witness_check(r)
                witness_count+=int(r['compatible'])
    arithmetic_a,arithmetic_b=read('arithmetic_supports.json'),read('arithmetic_vectors.json')
    for key in arithmetic_b:
        assert arithmetic_a[key]==arithmetic_b[key],key
    domain=read('domain_checks.json')
    assert domain['summary']['independent_routes_agree']
    comparisons=[]
    for filename in ('geometry_a.json','geometry_b.json'):
        original=json.loads((ROUND/'推导95G'/filename).read_text())
        assert {tuple(r['key'][:3]):(r['value'],r['options']) for r in a['base']}=={
            tuple(r['key']):(r['bound'],r['options']) for r in original['baseline']}
        assert {tuple(r['key']):(r['value'],r['d']) for r in a['close'] if r['compatible']}=={
            tuple(r[:5]):(r[5],r[6]) for r in original['near']}
        assert {tuple(r['key']) for r in a['close'] if not r['compatible']}=={tuple(r) for r in original['incompatible']}
        for old in original['baseline']:
            if filename=='geometry_a.json':
                chosen=[[int(s>=23),x,y] for s,x,y in old['selected']]
            else:
                chosen=[[int(axis=='B'),x,y] for x,y,w,h,axis in old['selected']]
            r=dict(key=old['key']+[0,0],compatible=True,d=0,value=old['bound'],
                   tangent=old['tangent'],bonus=old['weight'],chosen=chosen)
            witness_check(r)
            witness_count+=1
        comparisons.append(filename)
    origin=json.loads((ROUND/'推导95G/arithmetic_a.json').read_text())
    name_map={'grind':'研磨机','shape':'塑形机','pack':'封装机','fill':'灌装机'}
    for key,cn in name_map.items():
        assert [[int(n),v] for n,v in arithmetic_a['weight_tables_twice'][key].items()]==origin['weight_tables_twice'][cn]
    for k,v in {'machine_count':arithmetic_a['flows']['machines'],
                'manufacturing_area':arithmetic_a['flows']['manufacturing_area'],
                'input_interfaces':arithmetic_a['flows']['input_channels'],
                'output_interfaces':arithmetic_a['flows']['output_channels'],
                'interfaces':arithmetic_a['flows']['interfaces'],
                'weight_twice':2*Fraction(arithmetic_a['omega']),
                'direction_lower_twice':2*Fraction(arithmetic_a['weighted_direction']),
                'area_residual':arithmetic_a['base_area']}.items():
        assert origin[k]==v,k
    inputs=[ROUND/'前提快照'/name for name in ('《明日方舟：终末地》游戏规则.txt','求解任务.txt','求解约束.txt','求解充分条件.txt')]
    inputs += [ROUND/'临时规则.md',ROUND/'推导95G.md']
    inputs += [ROUND.parent/'第92-94轮'/name for name in ('推导92B.md','复核93B.md','复核94B.md')]
    inputs += [ROUND.parent/'第78-80轮/推导78B.md']
    hashes={str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
    if (OUT/'input_manifest.json').exists():
        assert hashes==read('input_manifest.json'),'Review inputs changed after the first manifest'
    (OUT/'input_manifest.json').write_text(json.dumps(hashes,ensure_ascii=False,indent=2)+'\n')
    result=dict(status='PASS',base_cases=len(a['base']),near_total=len(a['close']),
                near_compatible=sum(r['compatible'] for r in a['close']),
                near_invalid=sum(not r['compatible'] for r in a['close']),
                witnesses_checked=witness_count,arithmetic_fields_compared=len(arithmetic_b),
                original_geometries_compared=comparisons,
                near_histogram=dict(Counter(r['value']+r['d'] for r in a['close'] if r['compatible'])),
                base_histogram=dict(Counter(r['value'] for r in a['base'])),
                cpu_workers_per_solver=1,python=platform.python_version(),seconds=time.monotonic()-start,
                scope='Exact finite necessary relaxations; no factory or reachability witness.')
    (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
