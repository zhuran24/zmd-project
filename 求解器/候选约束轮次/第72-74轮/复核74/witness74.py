"""Coordinate-only witness audit and all-subset common-grid bound."""
from geometry74 import *
from collections import defaultdict
import copy

def audit(raw,caps):
    chosen=[]; occupied=set(); mapping={(u['kind'],tuple(u['r']),u['axis']):u for u in boundary_domain()}
    for b in raw['chosen']:
        kind=b['kind']; r=(b['x'],b['y'],b['w'],b['h']);a={'h':0,'v':1,'-':-1}[b['axis']]
        if kind=='p':
            assert r[2:]==(2,2);u=dict(kind=kind,r=r,axis=a,**caps[r[:2]])
        else:u=mapping[kind,r,a]
        body=rect(*r);assert all(map(legal,body)) and body.isdisjoint(occupied)
        occupied.update(body);chosen.append(u)
    gaps=raw['warehouse_gaps'];assert all(k in range(0,70,3) for k in gaps) and 0 in gaps
    for axis,gap in enumerate(gaps):
        for i in range(23):
            a=3*i+(3*i>=gap); c=(1,a+1) if axis==0 else (a+1,1)
            assert c not in occupied
    weak=0;port_info=[]
    for u in chosen:
        if u['kind']=='p':continue
        free=[sorted(set(s)-occupied) for s in u['ports']]
        assert all(len(s)>=n for s,n in zip(free,u['needs']))
        if u['kind']=='l':
            m=max(map(len,free)); assert m>=2; weak+=m==2
        port_info.append(dict(kind=u['kind'],r=u['r'],free=free))
    assert weak<=1
    poles=[u for u in chosen if u['kind']=='p'];assert len(poles)==10
    cover=[]
    for u in chosen:
        if u['kind'] not in ('s','m','l'):continue
        actual=[p['r'][:2] for p in poles if overlap(u['r'],(p['r'][0]-5,p['r'][1]-5,12,12))]
        assert actual;cover.append(dict(r=u['r'],poles=actual,k=len(actual)))
    loss=sum(p['loss'] for p in poles);repeat=sum(x['k']-1 for x in cover)
    assert loss+repeat<=13
    gs=[len(line-occupied) for line in LINES];J=sum(p['j'] for p in poles)
    S=160-2*J+sum(gs);assert S==raw['S']
    assert all(sum(u['kind']==k for u in chosen)<=n for k,n in [('s',131),('m',48),('l',38),('c',1)])
    return dict(S=S,J=J,gaps=gs,X=sum(gs[:2]),Y=sum(gs[2:]),loss=loss,repeat=repeat,
                counts=dict(Counter(u['kind'] for u in chosen)),cover=cover,ports=port_info,
                poles=[dict(p=p['r'][:2],cap=p['cap'],loss=p['loss']) for p in poles])

def maximum_matching(groups,caps):
    copies=[i for i,c in enumerate(caps) for _ in range(c)]
    mate={}
    def augment(k,seen):
        for g in sorted(groups[copies[k]]):
            if g in seen:continue
            seen.add(g)
            if g not in mate or augment(mate[g],seen):mate[g]=k;return True
        return False
    for k in range(len(copies)):augment(k,set())
    pairs=[dict(pole=copies[k],group=list(g)) for g,k in sorted(mate.items())]
    assert all(tuple(d['group']) in groups[d['pole']] for d in pairs)
    assert all(sum(d['pole']==i for d in pairs)<=c for i,c in enumerate(caps))
    return pairs

def main():
    caps={tuple(d['p']):d for d in json.loads((OUT/'capacities.json').read_text())}
    raw=json.loads((ROUNDS/'第72-74轮/推导72/witness185.json').read_text())
    result=audit(raw,caps);dump('witness_audit.json',result)
    # Mutations must fail without trusting reported totals or precomputed ports.
    bad=copy.deepcopy(raw);bad['S']=184
    try:audit(bad,caps)
    except AssertionError: pass
    else:raise AssertionError('wrong S accepted')
    bad=copy.deepcopy(raw);bad['chosen'].append(next(b for b in bad['chosen'] if b['kind']=='p'))
    try:audit(bad,caps)
    except AssertionError: pass
    else:raise AssertionError('duplicate pole accepted')
    poles=[tuple(p['p']) for p in result['poles']]; capacities=[caps[p]['cap'] for p in poles]
    records=[]
    for a in range(3):
        for b in range(3):
            groups=[{((x+a)//3,(y+b)//3) for x,y in centers(p)} for p in poles]
            best=10000;minimizers=[]
            for mask in range(1<<len(poles)):
                selected=[i for i in range(len(poles)) if mask>>i&1]
                union=set().union(*(groups[i] for i in selected))
                bound=len(union)+sum(c for i,c in enumerate(capacities) if i not in selected)
                if bound<best:best=bound;minimizers=[]
                if bound==best:minimizers.append(dict(mask=mask,I=[poles[i] for i in selected],union=len(union),capacity=sum(capacities[i] for i in selected)))
            pairs=maximum_matching(groups,capacities);assert len(pairs)==best
            records.append(dict(a=a,b=b,total_union=len(set.union(*groups)),upper=best,D=sum(capacities)-best,
                                cuts=minimizers,matching=pairs))
    assert [r['upper'] for r in records]==[184,190,190,189,195,192,184,191,192]
    dump('common_grid_audit.json',dict(poles=poles,capacities=capacities,loss=sum(23-c for c in capacities),records=records))
    print('witness', {k:v for k,v in result.items() if k not in ('cover','ports','poles')})
    print('common grid',[(r['a'],r['b'],r['total_union'],r['upper']) for r in records])

if __name__=='__main__':main()
