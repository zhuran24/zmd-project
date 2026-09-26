#!/usr/bin/env python3
"""Final artifact consistency checks for review 84, not a proof checker."""
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
def read(name): return json.loads((HERE/name).read_text())
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    candidates=json.loads((BASE/'修正版清单.json').read_text())
    results=read('verdicts.json')
    report=(BASE/'复核84.md').read_text()
    a=read('accounts.json'); g=read('state_graph.json'); p=read('local_probes.json')
    c=read('cache_witness.json'); s=read('skeleton_probes.json'); geo=read('geometry_witnesses.json')
    assert len(candidates)==len(results['results'])==18
    assert [x['name'] for x in candidates]==[x['name'] for x in results['results']]
    assert [x['id'] for x in results['results']]==list(range(1,19))
    assert Counter(x['verdict'] for x in results['results'])=={'未否证':12,'修正':6}
    assert len(re.findall(r'^### \d+\.',report,re.M))==18
    for x in results['results']:
        assert x['name'] in report and x['reason'] in report
        assert bool(x['revised_text']) == (x['verdict']=='修正')
        if x['revised_text']: assert x['revised_text'] in report
    hashes={p.name:digest(p) for p in (BASE/'前提快照').glob('*.txt') if p.name!='来源提交.txt'}
    assert hashes==a['snapshot_hashes']
    assert digest(BASE/'修正版清单.json')==a['candidate_hash']
    assert len([l for l in (BASE/'前提快照/求解约束.txt').read_text().splitlines()
                if '：' in l and not l.startswith((' ','\t')) and l.split('：',1)[1]])==71
    for target in re.findall(r'\]\(([^)]+)\)',report):
        assert (BASE/target).exists(),target
    assert g['plant_graph']['lower_bound_violations']==g['plant_graph']['C_empty_cycle_states_phi_ge_4']==0
    assert len(p['A_full_stock'])==12 and len(p['D_plant'])==96
    assert sum(x['cycle'] is not None for x in p['D_plant'])==73
    assert p['quota_loop']['cycle']['X_empty_ticks']==4
    assert p['phase_counterexample']['completion_times']=={'F0':['1','2','3'],'Fhalf':['3/2','5/2','7/2']}
    assert c['phi0']==211 and c['minimum_phi']==209.5 and c['bound']==210
    assert len(s['skeleton'])==3 and all(x['cycle'] for x in s['skeleton'])
    assert s['skeleton'][2]['cycle']['rates']['battery']=='3/25'
    assert geo['plant_merger_counterexample']['checks']['all_automatic_port_contacts_match']
    assert geo['old_cache_counterexample']['checks']['manufacturers_powered']
    now=datetime.now(timezone.utc)
    start=datetime(2026,9,26,10,32,32,tzinfo=timezone.utc)
    elapsed=(now-start).total_seconds()
    assert 0 <= elapsed < 10800
    audit={'checked_utc':now.isoformat(),'elapsed_seconds_since_start':elapsed,'candidate_count':18,
           'verdicts':dict(Counter(x['verdict'] for x in results['results'])),
           'snapshot_hashes_unchanged':True,'relative_report_links_resolve':True,
           'reader_audit':['Standalone premises and numbering explicit','Scope and geometry limits stated',
                           'All six replacement clauses included','Counts and cross-references consistent',
                           'No unresolved-only verdict','Truncated probes not counted as passed cycles'],
           'report_sha256':digest(BASE/'复核84.md'),
           'artifact_sha256':{p.name:digest(p) for p in sorted(HERE.iterdir()) if p.is_file() and p.name!='delivery_audit.json'}}
    (HERE/'delivery_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in audit.items() if k not in ('artifact_sha256','reader_audit')},ensure_ascii=False))


if __name__=='__main__': main()
