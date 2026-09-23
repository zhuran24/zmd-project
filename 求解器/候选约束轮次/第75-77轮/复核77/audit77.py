"""Final data audit: every subset, submitted matching, branch and input hash."""
from geometry77 import *
import hashlib,re

def main():
    sources=OUT.parent/'推导75';checks={}
    for name,digest in read(OUT/'inputs.json').items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    checks['inputs_unchanged']=True
    expected_status={'J0_cap187_cp':'INFEASIBLE','J0_cap187_highs':'INFEASIBLE','J1_cap184_rebuilt_edges':'INFEASIBLE'}
    checks['thresholds']={}
    for name,status in expected_status.items():
        d=read(OUT/(name+'.json'));assert d['status']==status
        checks['thresholds'][name]={k:d[k] for k in ('status','seconds','model_sha256')}
    tabs=next(c for c in read(OUT/'edge_checks.json')['local']['cases'] if c['mask']==[0,0])['lines']
    subsets=0;matchings=0;line_checks=0
    for S in (185,186,187):
        witness=read(OUT/f'witness_S{S}.json');raw=read(sources/f'complete_subsets_S{S}.json')
        own_fixed=read(OUT/f'full_fixed_S{S}.json');assert own_fixed['status']=='OPTIMAL' and own_fixed['S']==S
        # Independently generated frontier cuts also hold at each witness.
        capacities={tuple(d['p']):d['cap'] for d in read(OUT/'capacities.json')}
        for line,tab,gap in zip(LINES,tabs,witness['gaps']):
            line=set(line);cs=ps=loss=J=0
            for u in raw['chosen']:
                r=tuple(u[k] for k in ('x','y','w','h'))
                if not cells(r)&line:continue
                cs+=u['kind']=='c';ps+=u['kind']=='p'
                if u['kind']=='p':loss+=23-capacities[r[:2]];J+=edge_count(r[:2])>0
            assert any(state[0]==cs and state[1]==ps and state[2]<=loss and value<=gap-2*J for state,value in tab['frontier'])
            line_checks+=1
        original=read(sources/f'complete_subsets_S{S}_audit.json')
        residual=read(sources/f'complete_subsets_S{S}_residual.json')
        for is_residual,submitted,own in [(False,original['partitions'],witness['original']),
                    (True,residual['partitions'],witness['residual']['True']['partitions'])]:
            cs=[set(map(tuple,v)) for v in residual['centers']] if is_residual else [centers(tuple(p)) for p in witness['poles']]
            capacity=witness['r'] if is_residual else witness['capacities']
            for given,rebuilt in zip(submitted,own):
                assert given['shift']==rebuilt['shift'] and given['upper']==rebuilt['upper']
                field='all_subset_bounds' if is_residual else 'subset_bounds'
                assert given[field]==rebuilt['all_1024_bounds'];subsets+=len(given[field])
                a,b=given['shift'];groups=[{((x+a)//3,(y+b)//3) for x,y in c} for c in cs]
                for field in ('matching','expanded_slot_matching') if is_residual else ('matching',):
                    pairs=given[field];assert len(pairs)==rebuilt['upper']
                    seen=set();used=Counter()
                    for p,g in pairs:
                        g=tuple(g);assert g in groups[p] and g not in seen;seen.add(g);used[p]+=1
                    assert all(used[p]<=capacity[p] for p in range(10));matchings+=1
        # All producer fixed-model receipts are feasibility completions, not
        # proofs of optimality of the unrestricted model.
        for engine in ('native','highs'):
            d=read(sources/f'complete_replay_{engine}_S{S}.json');assert d['status']=='OPTIMAL'
    checks.update(all_subset_values_rechecked=subsets,submitted_matchings_rechecked=matchings,line_cut_witness_checks=line_checks)
    entries=read(sources/'branches.json')['branches']
    keys=[(tuple(e['position']),e['S'],e['J']) for e in entries]
    expected={(pos,s,j) for pos in ((49,17),(17,49)) for s in (185,186,187) for j in (0,1)}
    assert len(keys)==len(set(keys))==12 and set(keys)==expected
    for e in entries:assert e['result']==('INFEASIBLE' if e['J']==0 else 'FEASIBLE')
    checks['branch_count']=len(keys)
    # Rebuild the domain of the weak global residual model.
    available=[(x,y) for x in range(2,69) for y in range(2,69) if rect_allowed((x-1,y-1,3,3))]
    groups={((x)//3,(y+1)//3) for x,y in available}
    assert (len(available),len(groups))==(3376,403)
    checks['residual_global_domain']=[len(available),len(groups)]
    checks['producer_unresolved']={}
    for n in ['residual_global_A','residual_global_B','residual_global_A_quick','residual_global_B_quick']:
        d=read(sources/(n+'.json'));assert d['status']=='UNKNOWN'
        checks['producer_unresolved'][n]={'status':d['status'],'seconds':d['seconds']}
    checks['source_sha256']={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(OUT.glob('*.py'))}
    save('audit.json',checks);print(json.dumps(checks,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
