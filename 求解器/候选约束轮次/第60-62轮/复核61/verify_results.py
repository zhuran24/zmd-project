#!/usr/bin/env python3
"""Read-only verification of source hashes and completed review artifacts.
Writes only the summary/check JSON next to this script.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
from independent_boundary import verify

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
SOURCE=ROOT/'求解器/几何/1113放松'

def write(name,data): (HERE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')

def main():
    # This also makes the historical witness check independently reproducible.
    hist=[]
    for b in [5,6,7,8,9,10,11,12,13,14,17]:
        for a,y,w,h in [(49,b,21,53),(b,49,53,21)]:
            p=SOURCE/'异源核查/results'/f'minS_edge0_W{w}H{h}_x{a}y{y}.json'
            d=json.loads(p.read_text())
            chosen=[dict(kind=z['kind'],rect=z['rect'],axis={'EW':0,'NS':1,None:None}[z['axis']]) for z in d['bodies']]
            X,Y=verify(tuple(d['rect']),chosen,d['P'],d['J'],d['hidden'],d['hidden_edge'],True)
            assert (X,Y)==(d['X'],d['Y'])
            S=16*d['P']-2*d['J']+X+Y
            assert d['status']=='OPTIMAL' and S==d['bound']
            hist.append(dict(source=str(p.relative_to(ROOT)),claimed_optimum=S,witness_checked=True,
                             note='Witness verification only; optimality uses source solver status.'))
    write('historical_witness_checks.json',hist)
    rows=json.loads((HERE/'sweep.json').read_text())
    assert len(rows)==900 and len({tuple(z['rect']) for z in rows})==900
    assert {tuple(z['rect']) for z in rows}=={(a,b,21,53) for a in range(50) for b in range(18)}
    keep=[]
    for z in rows:
        assert z['status']!='UNKNOWN',z
        if 'workers' in z: assert z['workers']<=4
        if z['status'] in ('OPTIMAL','FEASIBLE'):
            X,Y=verify(tuple(z['rect']),z['witness'],z['P'],z['J'],z['missing'],z['missing_edge'],True)
            assert (X,Y)==(z['X'],z['Y']) and 16*z['P']-2*z['J']+X+Y<=187
            keep.append(z['rect'])
    assert sorted(keep)==[[49,b,21,53] for b in [6,7,9,17]],keep
    original=json.loads((SOURCE/'positions.json').read_text())
    old={tuple(z['rect']):('candidate' if any(q['keep'] for q in z['branches']) else 'dp' if z['patterns'] else 'corridor')
         for z in original['positions']}
    cross=Counter(f"{old.get(tuple(z['rect']),'pre_filter')}|{z['status']}" for z in rows)
    summary=dict(positions=900,status_counts=Counter(z['status'] for z in rows),retained=keep,
                 cross=cross,solver_runs=sum('workers' in z for z in rows),
                 retained_attempt_build_solve_seconds=sum(z.get('seconds',0) for z in rows),
                 timing_note='Sum covers retained attempts only; sweep.log elapsed also includes initial UNKNOWN attempts before retries.',
                 two_orientations_via_transpose=dict(positions=1800,retained=keep+[[r[1],r[0],r[3],r[2]] for r in keep]),
                 all_witnesses_rechecked=True)
    write('verification_summary.json',summary)
    before=json.loads((HERE/'input_manifest.json').read_text())
    changed=[]
    for name,d in before.items():
        p=ROOT/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=d['sha256']: changed.append(name)
    known={str(p.relative_to(ROOT)) for p in SOURCE.rglob('*') if p.is_file()}
    added=sorted(known-set(before))
    integrity=dict(compared_files=len(before),changed=changed,added_to_protected_directory=added,
                   all_unchanged=not changed and not added)
    write('final_integrity.json',integrity)
    assert not changed and not added,integrity
    print(json.dumps(dict(summary=summary,integrity=integrity),ensure_ascii=False,indent=2))

if __name__=='__main__': main()
