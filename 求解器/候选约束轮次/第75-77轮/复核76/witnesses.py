"""Independent coordinate, all-subset, residual and matching verification."""
from geometry import *
from fractions import Fraction as Q
from itertools import product
import copy,hashlib
def subset_bound(cs,capacities):
    """Enumerate all subsets, independently certify equality by slot matching."""
    rows=[]
    for a,b in product(range(3),repeat=2):
        gs=[{((x+a)//3,(y+b)//3) for x,y in cc} for cc in cs]
        univers=sorted(set.union(*gs));idx={g:i for i,g in enumerate(univers)}
        bits=[sum(1<<idx[g] for g in s) for s in gs]
        unions=[0]*(1<<len(cs));sums=[0]*(1<<len(cs));bounds=[]
        for mask in range(len(unions)):
            if mask:
                bit=mask&-mask;p=bit.bit_length()-1;rest=mask^bit
                unions[mask]=unions[rest]|bits[p];sums[mask]=sums[rest]+capacities[p]
            bounds.append(sum(capacities)-sums[mask]+unions[mask].bit_count())
        best=min(bounds);mask=bounds.index(best)
        # Expand pole capacity into individual slots and run augmenting paths.
        owners={};slots=[p for p,c in enumerate(capacities) for _ in range(c)]
        def augment(s,visited):
            for g in sorted(gs[slots[s]]):
                if g in visited:continue
                visited.add(g)
                if g not in owners or augment(owners[g],visited):owners[g]=s;return True
            return False
        for s in range(len(slots)):augment(s,set())
        matched=[[slots[s],list(g)] for g,s in sorted(owners.items())]
        assert len(owners)==best and len(set(owners.values()))==len(owners)
        assert all(sum(p==i for p,g in matched)<=capacities[i] for i in range(len(cs)))
        rows.append(dict(shift=[a,b],bound=best,mask=mask,inside=[i for i in range(len(cs)) if mask>>i&1],outside_capacity=sum(capacities)-sums[mask],inside_union=unions[mask].bit_count(),all_union=len(univers),D=sum(capacities)-best,bounds=bounds,matching=matched))
    return rows
def verify_point(data,capacities):
    units=[{k:u[k] for k in ('kind','x','y','w','h','axis')} for u in data['chosen']]
    allowed={(k,w,h,a) for k,w,h,a in SHAPES+[('c',9,9,'h'),('c',9,9,'v'),('p',2,2,'-')]}
    occupied=set()
    for u in units:
        assert (u['kind'],u['w'],u['h'],u['axis']) in allowed
        bb=body(u);assert all(map(legal,bb)) and not bb&occupied
        occupied.update(bb)
    weak=0
    for u in units:
        ss=ports(u);free=[len(set(s)-occupied) for s in ss]
        assert all(f>=1 for f in free)
        if u['kind']=='c':assert all(f==1 for f in free[:6]) and free[-1]>=2
        if u['kind']=='l':assert max(free)>=2;weak+=max(free)<3
    assert weak<=1
    gaps=tuple(data['warehouse_gaps']);ff=dict(bands())[gaps];assert not occupied&ff
    machines=[u for u in units if u['kind'] in ('s','m','l')];ps=sorted([u for u in units if u['kind']=='p'],key=lambda u:(u['x'],u['y']))
    assert len(ps)==10 and len(machines)==21
    caps=[capacities[p['x'],p['y']] for p in ps]
    count=[sum(powered(m,p) for m in machines) for p in ps]
    hits=[sum(powered(m,p) for p in ps) for m in machines];assert min(hits)>=1
    loss=sum(23-c for c in caps);repeat=sum(hits)-len(machines);assert loss+repeat<=13
    gaps4=[len(line-occupied) for line in LINES];J=sum(map(edge,ps));S=160-2*J+sum(gaps4);assert S==data['S']
    old=subset_bound([centers(p) for p in ps],caps);assert min(r['bound'] for r in old)>=217
    residual_caps=[c-n for c,n in zip(caps,count)];assert min(residual_caps)>=0
    residual=[]
    for with_first in (False,True):
        F=occupied|ff if with_first else occupied
        cc=[centers(p,F) for p in ps]
        # Second geometry implementation: exhaustive entire base via set dilation.
        forbidden_centers={(x+dx,y+dy) for x,y in F|HOLE for dx in (-1,0,1) for dy in (-1,0,1)}
        usable={(x,y) for x in range(2,69) for y in range(2,69)}-forbidden_centers
        for p,c in zip(ps,cc):
            actual={q for q in usable if powered(make('s',q[0]-1,q[1]-1,3,3,'h'),p)}
            assert c==actual
        rows=subset_bound(cc,residual_caps);b=min(r['bound'] for r in rows)
        assert all(loss+repeat+r['D']==230-len(machines)-r['bound'] for r in rows)
        residual.append(dict(with_first=with_first,centers=[sorted(c) for c in cc],partitions=rows,remaining_upper=b,total_upper=b+len(machines)))
    return dict(S=S,counts=dict(Counter(u['kind'] for u in units)),gaps=gaps4,X=sum(gaps4[:2]),Y=sum(gaps4[2:]),J=J,loss=loss,repeat=repeat,positions=[[p['x'],p['y']] for p in ps],caps=caps,known_counts=count,residual_caps=residual_caps,old=old,residual=residual)
def structural_checks():
    # Every intersecting relative rectangle admits a contained, intersecting 3x3.
    checked=0
    for w,h in [(3,3),(5,5),(6,4),(4,6)]:
        for x in range(1-w,12):
            for y in range(1-h,12):
                assert any(box(i,j,3,3)&box(0,0,12,12) for i in range(x,x+w-2) for j in range(y,y+h-2))
                checked+=1
    pairs=0
    for a,b in product(range(3),repeat=2):
        for x,y in product(range(-4,5),repeat=2):
            for dx,dy in product(range(-2,3),repeat=2):
                xx,yy=x+dx,y+dy
                if ((x+a)//3,(y+b)//3)==((xx+a)//3,(yy+b)//3):
                    assert box(x-1,y-1,3,3)&box(xx-1,yy-1,3,3);pairs+=1
    rates=[Q(68),Q(51),Q(63,2),Q(11,2),Q(6),Q(32),Q(16),Q(3,5),Q(11,20)]
    ns=[68,51,32,6,6,32,16,3,3];speeds=[Q(1)]*7+[Q(1,5)]*2
    lower=[r-(n-1)*v for r,n,v in zip(rates,ns,speeds)];assert min(lower)>0
    return dict(intersecting_relative_rectangles=checked,same_group_pairs=pairs,machine_count=sum(ns),area=131*9+48*25+38*24,minimum_machine_rates=list(map(str,lower)),area_budget=4639-4*1113,counted_cells=sum(map(len,LINES)),physical_cells=len(WEIGHT),band_patterns=len(bands()))
def main():
    caps={(r['x'],r['y']):r['cap'] for r in json.loads((OUT/'capacities.json').read_text())};summaries=[];src=ROUNDS/'第75-77轮/推导75'
    for S in (185,186,187):
        data=json.loads((src/f'complete_subsets_S{S}.json').read_text());r=verify_point(data,caps)
        # Check supplied transpose is exactly the geometric bijection.
        tr=json.loads((src/f'complete_subsets_S{S}_transpose.json').read_text())
        def key(u):return tuple(u[k] for k in ('kind','x','y','w','h','axis'))
        transformed={(u['kind'],u['y'],u['x'],u['h'],u['w'],{'h':'v','v':'h','-':'-'}[u['axis']]) for u in data['chosen']}
        assert transformed=={key(u) for u in tr['chosen']}
        dump(f'witness_{S}.json',r)
        summaries.append({k:v for k,v in r.items() if k not in ('old','residual')}|dict(old_unions=[t['all_union'] for t in r['old']],old_upper=[t['bound'] for t in r['old']],residual_upper=[v['remaining_upper'] for v in r['residual']],total_upper=[v['total_upper'] for v in r['residual']],transpose=True))
    # Mutations must fail, not merely produce another claimed result.
    tests=[];data=json.loads((src/'complete_subsets_S185.json').read_text())
    for name in ('wrong_S','duplicate_pole','outside_base'):
        bad=copy.deepcopy(data)
        if name=='wrong_S':bad['S']=184
        elif name=='duplicate_pole':bad['chosen'].append(next(u for u in bad['chosen'] if u['kind']=='p'))
        else:bad['chosen'][0]['x']=-1
        try:verify_point(bad,caps)
        except AssertionError:tests.append(name)
        else:raise AssertionError(name+' was accepted')
    result=dict(structural=structural_checks(),witnesses=summaries,rejected_mutations=tests)
    dump('witness_summary.json',result);print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
