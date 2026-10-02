#!/usr/bin/env python3
"""Validate delivered files, schemas, evidence summaries, and snapshot integrity."""
import hashlib
import json
import re
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'推导92C.md'
reply=json.loads((HERE/'reply.json').read_text())
text=REPORT.read_text()
assert reply['report_path']==str(REPORT)
assert set(reply)>={'report_path','candidates','summary'}
assert len(reply['candidates'])==6
for c in reply['candidates']:
    assert set(c)=={'name','kind','text','basis','derivation','relation'}
    assert c['kind']=='充分条件'
    assert c['text'] in text
    assert c['relation']==f'修订正式条目「{c["name"]}」'
assert reply['candidates']==json.loads((HERE/'candidates.json').read_text())
for n in range(1,11):
    assert f'| S{n:02} |' in text

temporary=None
if (HERE/'temporary_update.json').exists():
    temporary=json.loads((HERE/'temporary_update.json').read_text())
    temp_rules=HERE.parent/'临时规则.md'
    assert hashlib.sha256(temp_rules.read_bytes()).hexdigest()==temporary['temporary_rules_sha256']
    assert text.count('#### 按临时规则\n')==10
    assert reply['candidates']==json.loads((HERE/'candidates_temporary.json').read_text())
    assert '首次交付的快照口径记录' in text
    assert '临时第5条' in reply['candidates'][-1]['derivation']
    temp_results=json.loads((HERE/'temporary_results.json').read_text())
    assert temp_results['temporary_rules_sha256']==temporary['temporary_rules_sha256']
    assert temp_results['S06_S07']['order_cases']==[4,720]
    assert temp_results['S08']['complete_states_compared']==25600
    assert temp_results['S10']['pure_belt_cases']==256
    assert temp_results['rebuild_robust_properties']['complete_states_compared']==12800
    assert temp_results['rebuild_robust_properties']['two_encodings_agree']

links=[]
for target in re.findall(r'\]\(([^)]+)\)',text):
    if '://' in target or target.startswith('#'):
        continue
    p=REPORT.parent/target.split('#')[0]
    assert p.exists(), ('broken link',target)
    links.append(target)
snap=json.loads((HERE/'s01_s05_results.json').read_text())['snapshot_hashes']
for name,digest in snap.items():
    assert hashlib.sha256((HERE.parent/'前提快照'/name).read_bytes()).hexdigest()==digest

e1=json.loads((HERE/'s01_s05_results.json').read_text())
e2=json.loads((HERE/'s06_s07_results.json').read_text())
e3=json.loads((HERE/'s08_s09_independent.json').read_text())
e4=json.loads((HERE/'s10_results.json').read_text())
assert e1['S02']['independent_encodings_equal'] and e1['S02']['received']==50
assert e1['arithmetic']['S01_max_arrivals_between_transmissions']==15
assert [r['arbitrary_origin_bound'] for r in e1['arithmetic']['S03']]==[24,300,120]
assert e2['order_sweep']['s06']==4 and e2['order_sweep']['s07']==720
assert e2['finite50']['first_empty_step']==e2['finite50']['independent_final_finish']==400
assert e2['finite400_plant_unit']['identical']
assert e2['corrected_s06']['timestamp_vs_queue_identical']
assert e3['stepwise_equal_states']==160*160 and e3['S08_violations']==0
assert e3['saturation_constant_counted']==e3['saturation_constant_symbolic']==176
assert e4['loop']['cases']==4*4*2*2*8*2==1024
assert e4['loop']['all_step_states_identical'] and e4['loop']['cycle_periods_steps']==[8]
assert e4['wrong_slot_fixed_point']['stable_from_step']==8
assert e4['wrong_slot_fixed_point']['two_encodings_agree']

items=[]
json_count=0
for p in sorted(HERE.iterdir()):
    assert p.is_file(), ('unexpected directory',str(p))
    assert p.suffix in {'.py','.md','.json','.log'}, p.name
    assert p.stat().st_size<100*1024*1024
    if p.suffix=='.json':
        json.loads(p.read_text())
        json_count+=1
    if p.name not in {'artifact_manifest.json','validation.json'}:
        items.append(dict(path=p.name,bytes=p.stat().st_size,
                          sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
summary=dict(status='pass',candidate_count=6,confirmed_count=4,
             report_bytes=REPORT.stat().st_size,links_checked=len(links),
             json_files_parsed=json_count,snapshot_hashes_unchanged=True,
             result_summaries_consistent=True,all_candidate_texts_in_report=True,
             independent_review=['S01-S05 arithmetic and proof','S07 inventory bound','S08 saturation proof'],
             unresolved=['S07 indefinite guarantee','S08 original bridge/gate scope',
                         'S09 original no-gap/full-rate scope','S10 original multi-outlet/bridge scope'])
if temporary is not None:
    summary['authoritative_scope']='temporary_rules'
    summary['temporary_sections_checked']=10
    summary['temporary_rules_hash_unchanged']=True
    summary['temporary_candidates_match']=True
    summary['history_reset_assumed']=False
    summary['temporary_results_consistent']=True
(HERE/'validation.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
(HERE/'artifact_manifest.json').write_text(json.dumps(dict(
    report=dict(path=str(REPORT),sha256=hashlib.sha256(REPORT.read_bytes()).hexdigest()),
    files=items),ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
