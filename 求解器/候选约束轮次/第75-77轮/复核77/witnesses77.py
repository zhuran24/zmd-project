"""Review 77: independently rebuild witness geometry and residual subset bounds."""
from geometry77 import *
from itertools import product
import copy,time

SOURCE=OUT.parent/'推导75'

def matching(groups,capacities):
    # Unit-capacity bipartite matching after expanding each pole into slots.
    slots=[i for i,n in enumerate(capacities) for _ in range(n)];assigned={}
    def augment(s,seen):
        for g in sorted(groups[slots[s]]):
            if g in seen:continue
            seen.add(g)
            if g not in assigned or augment(assigned[g],seen):
                assigned[g]=s;return True
        return False
    count=sum(augment(s,set()) for s in range(len(slots)))
    assert count==len(assigned)
    pairs=[(slots[s],g) for g,s in sorted(assigned.items())]
    assert all(g in groups[p] for p,g in pairs)
    used=Counter(p for p,g in pairs)
    assert all(used[p]<=capacities[p] for p in range(len(capacities)))
    return count,pairs

def cuts(center_sets,capacities):
    result=[]
    for a,b in product(range(3),repeat=2):
        gs=[{((x+a)//3,(y+b)//3) for x,y in cs} for cs in center_sets]
        labels=sorted(set.union(*gs));index={g:i for i,g in enumerate(labels)}
        bits=[sum(1<<index[g] for g in group) for group in gs]
        union=[0]*(1<<len(gs));cap=[0]*len(union);bounds=[]
        for mask in range(len(union)):
            if mask:
                bit=mask&-mask;p=bit.bit_length()-1;prev=mask^bit
                union[mask]=union[prev]|bits[p];cap[mask]=cap[prev]+capacities[p]
            bounds.append(sum(capacities)-cap[mask]+union[mask].bit_count())
        val=min(bounds);mask=bounds.index(val);matched,pairs=matching(gs,capacities)
        assert val==matched
        result.append(dict(shift=[a,b],union=len(labels),upper=val,mask=mask,
          inside_capacity=cap[mask],inside_groups=union[mask].bit_count(),outside_capacity=sum(capacities)-cap[mask],
          deficiency=sum(capacities)-val,all_1024_bounds=bounds,matching=pairs))
    return result

def inspect(data):
    full=read(OUT/'domain.json');keys={(u['kind'],*u['r'],u['axis']):u for u in full}
    selected=[];occupied=set();counts=Counter()
    for d in data['chosen']:
        axis={'h':0,'v':1,'-':-1}[d['axis']]
        key=(d['kind'],d['x'],d['y'],d['w'],d['h'],axis)
        assert key in keys
        u=keys[key];body=cells(u['r']);assert not occupied&body
        occupied.update(body);selected.append(u);counts[u['kind']]+=1
    assert counts['c']==1 and counts['p']==10
    for k,maxi in [('s',131),('m',48),('l',38)]:assert counts[k]<=maxi
    forced=set();gaps=data['warehouse_gaps'];assert gaps[0]==0 or gaps[1]==0
    for axis,gap in enumerate(gaps):
        assert gap%3==0 and 0<=gap<=69
        for i in range(23):
            q=3*i+1+(i>=gap//3);forced.add((1,q) if axis==0 else (q,1))
    assert len(forced)==46 and not forced&occupied
    weak=0
    for u in selected:
        for ps,n in u['ports']:assert sum(tuple(c) not in occupied for c in ps)>=n
        if u['kind']=='l':
            available=[sum(tuple(c) not in occupied for c in ps) for ps,_ in u['ports']]
            assert max(available)>=2
            weak+=max(available)<3
    assert weak<=1
    machines=[u for u in selected if u['kind'] in ('s','m','l')]
    poles=sorted((u for u in selected if u['kind']=='p'),key=lambda p:p['r'][:2])
    cov=[[hit(u['r'],power(p['r'][:2])) for p in poles] for u in machines]
    assert all(any(row) for row in cov)
    n=[sum(row[i] for row in cov) for i in range(10)]
    capacities=[23-p['loss'] for p in poles];r=[c-v for c,v in zip(capacities,n)]
    assert min(r)>=0
    loss=sum(p['loss'] for p in poles);repeats=sum(n)-len(machines)
    assert loss+repeats<=13
    holes=[sum(c not in occupied for c in line) for line in LINES]
    J=sum(p['j'] for p in poles);S=160-2*J+sum(holes);assert S==data['S']
    positions=[tuple(p['r'][:2]) for p in poles]
    original=cuts([centers(p) for p in positions],capacities)
    assert all(row['upper']>=217 for row in original)
    residual={}
    for include_first in (False,True):
        forbidden=occupied|forced if include_first else occupied
        cs=[centers(p,forbidden) for p in positions]
        # Reconstruct from all 4489 integer centers and rectangle tests, without
        # reusing centers()'s pole-specific ranges or its set membership test.
        remaining=[(x,y) for x in range(2,69) for y in range(2,69)
          if rect_allowed((x-1,y-1,3,3)) and not any((i,j) in forbidden for i in range(x-1,x+2) for j in range(y-1,y+2))]
        other=[{c for c in remaining if hit((c[0]-1,c[1]-1,3,3),power(p))} for p in positions]
        assert cs==other
        rows=cuts(cs,r)
        residual[str(include_first)]=dict(center_counts=list(map(len,cs)),partitions=rows,
          remaining_upper=min(row['upper'] for row in rows),total_upper=len(machines)+min(row['upper'] for row in rows))
        if include_first:
            submitted=read(SOURCE/f'complete_subsets_S{S}_residual.json')
            assert [set(map(tuple,x)) for x in submitted['centers']]==cs
            assert submitted['known_coverage_per_pole']==n and submitted['residual_capacities']==r
            assert submitted['total_manufacturing_upper']==residual[str(include_first)]['total_upper']
        # Transposition independently recomputes all nine partition problems.
        trans=cuts([{(y,x) for x,y in group} for group in cs],r)
        for row in rows:
            a,b=row['shift'];other=next(x for x in trans if x['shift']==[b,a])
            assert row['all_1024_bounds']==other['all_1024_bounds']
    return dict(S=S,K=len(machines),counts=dict(counts),gaps=holes,X=sum(holes[:2]),Y=sum(holes[2:]),J=J,
      loss=loss,repeats=repeats,poles=positions,n=n,capacities=capacities,r=r,original=original,residual=residual)

def local_lemmas():
    # Every relative intersection between a size and a 12x12 supply square.
    cases=0
    for w,h in [(3,3),(5,5),(6,4),(4,6)]:
        for x in range(1-w,12):
            for y in range(1-h,12):
                assert any(hit((i,j,3,3),(0,0,12,12)) for i in range(x,x+w-2) for j in range(y,y+h-2))
                cases+=1
    checked=0
    for a,b in product(range(3),repeat=2):
        groups={}
        for x,y in product(range(-6,7),repeat=2):groups.setdefault(((x+a)//3,(y+b)//3),[]).append((x,y))
        for group in groups.values():
            for x,y in group:
                for u,v in group:
                    assert hit((x-1,y-1,3,3),(u-1,v-1,3,3));checked+=1
    # Empty I, all I and K=217 are covered by the same capacity identity.
    return dict(relative_intersections=cases,same_group_pairs=checked)

def main():
    t=time.monotonic();summary=[]
    for S in (185,186,187):
        data=read(SOURCE/f'complete_subsets_S{S}.json');out=inspect(data)
        save(f'witness_S{S}.json',out)
        summary.append({k:out[k] for k in ('S','K','counts','gaps','X','Y','J','loss','repeats','n','r')})
        summary[-1].update(residual_upper=out['residual']['True']['remaining_upper'],total_upper=out['residual']['True']['total_upper'])
        print(summary[-1],flush=True)
    base=read(SOURCE/'complete_subsets_S185.json');mutation=[]
    for name,change in [('wrong_S',lambda d:d.update(S=184)),('duplicate_pole',lambda d:d['chosen'].append(copy.deepcopy(next(u for u in d['chosen'] if u['kind']=='p')))),
                        ('out_of_base',lambda d:d['chosen'][0].update(x=70))]:
        d=copy.deepcopy(base);change(d)
        try:inspect(d)
        except AssertionError:mutation.append([name,'REJECTED'])
        else:raise AssertionError(name)
    summary=dict(witnesses=summary,lemma_checks=local_lemmas(),mutation_checks=mutation,seconds=time.monotonic()-t)
    save('witness_summary.json',summary);print(summary['lemma_checks'],flush=True)
if __name__=='__main__':main()
