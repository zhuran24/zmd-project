#!/usr/bin/env python3
"""Read-only consistency check of independent computations and their witnesses."""
from pathlib import Path
from collections import Counter
import hashlib,json

BASE=Path('/home/zhuran24/zmd-research-fresh/求解器/候选约束轮次/第60-62轮/复核62')

def main():
    cache={};intervals=0
    for line in (BASE/'interval_cache.jsonl').read_text().splitlines():
        r=json.loads(line);cache[r['key']]=r
        selected=[r['tokens'][i] for i in r['chosen_indices']]
        covered=set();p=0;c=0;loss=0
        for s,l,rr,k,f,d in selected:
            span={(s,j) for j in range(l,rr)}
            assert not span&covered and not span&set(map(tuple,r['fixed']))
            covered |= span;p+=k=='P';c+=k=='C';loss+=d
        for t in selected:
            for u in selected:
                if t[0]==u[0] and t[2]==u[1] and t[4] and u[4]:
                    assert (t[3],u[3]) not in {('M','M'),('M','C'),('C','M'),('C','P'),('P','C')}
        assert p<=r['P'] and c<=1 and loss<=r['loss_budget']
        value=sum(r['lengths'])-len(covered)-len(r['fixed'])+r['corner_cost']
        assert value==r['minimum'] and abs(r['dual']-value)<1e-6 and r['status']==0
        intervals+=1
    scan=json.loads((BASE/'filter_results.json').read_text())
    assert len(scan['records'])==len({tuple(r['R']) for r in scan['records']})==1800
    branch_count=0
    for r in scan['records']:
        if 'bounds' not in r: continue
        for b in r['bounds']:
            assert b['Y']==cache[b['Y_model']]['minimum']
            assert b['X']==min(cache[k]['minimum'] for val,k,corner in b['X_models'])
            assert all(val==cache[k]['minimum'] for val,k,corner in b['X_models'])
            p=b['P'];allow=187-16*p+2*((23*p-217)//9)
            assert allow==b['allowance'] and b['pass']==(b['X']+b['Y']<=allow)
            branch_count+=b['pass']
    expected=set()
    for b in list(range(5,15))+[17]: expected|={(49,b,21,53),(b,49,53,21)}
    ours={tuple(r['R']) for r in scan['survivors']}
    prior_survivors={(49,b,21,53) for b in (6,7,9,17)}|{(b,49,53,21) for b in (6,7,9,17)}
    mip=json.loads((BASE/'candidate_summary.json').read_text())
    cp=json.loads((BASE/'cp_certification_summary.json').read_text())
    assert {tuple(r['R']) for r in mip}==expected=={tuple(r['R']) for r in cp}
    for r in mip:
        assert r['status']==0 and r['gap']<1e-9 and abs(r['lower_bound']-r['objective'])<1e-6
        proof=next(c for c in cp if c['R']==r['R'])
        assert proof['cap']==r['objective']-1
    actual_survivors={tuple(r['R']) for r in mip if r['objective']<=187}
    before=json.loads((BASE/'input_manifest.json').read_text())['inputs']
    final={p:{'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest(),'bytes':Path(p).stat().st_size} for p in before}
    changed=[p for p in before if before[p]!=final[p]]
    (BASE/'input_manifest_final.json').write_text(json.dumps({'inputs':final,'changed_since_start':changed},ensure_ascii=False,indent=2))
    result={'interval_models_checked':intervals,'distinct_interval_models':len(cache),'counts':scan['counts'],
            'position_P_branches':branch_count,'original22_missing':sorted(expected-ours),'extra_vs_original22':sorted(ours-expected),
            'retained8_missing':sorted(prior_survivors-actual_survivors),'retained8_extra':sorted(actual_survivors-prior_survivors),
            'mip_optimal_positions':len(mip),'cp_statuses':dict(Counter(r['status'] for r in cp)),
            'final_input_changes':changed,'witness_check':json.loads((BASE/'witness_checks.json').read_text())['all_passed'],
            'geometry_check':json.loads((BASE/'geometry_checks.json').read_text())['all_passed']}
    (BASE/'verification_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__': main()
