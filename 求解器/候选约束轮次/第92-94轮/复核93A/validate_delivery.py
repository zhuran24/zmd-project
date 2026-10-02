#!/usr/bin/env python3
"""Validate the delivered evidence and emit its manifest. No simulation is imported."""
from pathlib import Path
from fractions import Fraction
from collections import Counter
from datetime import datetime,timezone
import hashlib,json,re,platform
D=Path(__file__).resolve().parent
P=D.parent
report=P/'复核93A.md'
load=lambda name:json.loads((D/name).read_text())
sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
expected_snapshot={
'《明日方舟：终末地》游戏规则.txt':'c8d3a17b8830baba18aea36c4c66f02f8873895188f8821176cc218aa6135f93',
'求解任务.txt':'7bec7a1edf2f46644a6e6a75d588f5ff05202cc32d6b42430677ea39b878309b',
'求解约束.txt':'dfea46c61f29be5a86659bce3642009d2558ace073d6dbd79f5dd3c6475226db',
'求解充分条件.txt':'aa633c7c927227ba4635f97bfb8948e9c3ba84ff1e489dd053b72db82e9ac435',
'不补的设定.txt':'7a0c7d6e495f4f6b5ed6caba24584261925479e06fcad9428760f8a687f2abba'}
for n,h in expected_snapshot.items():assert sha(P/'前提快照'/n)==h,n

A=load('arithmetic_matrix.json');B=load('arithmetic_batches.json')
assert A['status']==B['status']=='PASS'
for key in ['machine_minimum','machine_count','machine_area','mixed_channel_bounds','closed_5_tick_one_port_events','box_conservative_bound','next_8_steps_one_port_events','plant_stock_total_bound','wireless_period_steps','four_group_word_counts','reported_polling_family_count']:
    assert A[key]==B[key],key
for material,value in A['material_flow'].items():
    assert Fraction(value)==Fraction(B['material_counts_per_20_ticks'][material],20),material
assert Fraction(A['total_flow'])==Fraction(B['total_flow_numerator'],B['total_flow_denominator'])
for material in ['荞花','砂叶']:
    assert A['mean_stock_bounds'][material]==B['mean_stock_bound_numerators_per_20_ticks'][material]//20
    assert A['mean_stock_bounds'][material+'种子']==A['mean_stock_bounds'][material]
assert A['machine_count']==217 and A['machine_area']==3291
assert A['recipe_count']==18 and A['species_count']==19
assert A['recycle_slopes']=={f:('1' if f in ['粉碎机','精炼炉'] else '0') for f in A['recycle_slopes']}
assert B['formula_parameter_pairs']==360 and B['formula_indicator_equalities']==38430

DA,DB=load('dense_cells.json'),load('dense_countdown.json')
for a,b,interval,sc in zip(DA,DB,[[145,185],[129,209]],[{'甲汇流':0,'乙汇流':1},{'甲汇流':1,'乙汇流':1}]):
    for k in ['cycle_steps','period_steps','split_counts','split_rates','other_input_count','merger_output_count','core_stock_min','cycle_events']:assert a[k]==b[k],k
    assert a['cycle_steps']==interval and a['split_counts']==sc and a['core_stock_min']==79966
G=load('dense_geometry.json')
assert G['status']=='PASS' and G['occupied_cells']==128 and G['physical_channels']==44 and G['unintended_channels']==0
assert G['long_belt_lengths']==[16,16]

E=load('polling_exhaustive.json')
assert E['status']=='PASS' and E['independent_encodings']==2 and E['cases']==1851008
assert E['trace_agreements']==E['cases'] and E['violations']==0 and E['successes_checked']==13258624
assert E['cases_by_k']==[512,3968,21760,97280,379904,1347584]
assert sum(E['cases_by_k'])==E['cases']==A['reported_polling_family_count']
F=load('additional_checks.json')
assert F['status']=='PASS' and F['subset_channel_cases']==40000 and F['subset_violations']==0
assert F['selected_successes_checked']==181911 and F['mineral_conservation_equalities']==36
assert F['old_LRU_order_counterexample']['next_15_channels']==['A','C','B']*5
assert F['old_term_line_count']==19 and F['actual_candidate_count']==15
C=load('cache_balance.json')
assert C['status']=='PASS' and C['two_encodings_agree'] and C['input_per_20_ticks']==320 and C['output_per_20_ticks']==640
assert Fraction(C['q_items_per_tick'])+Fraction(C['b_items_per_tick'])-Fraction(C['Q_items_per_tick'])==-16

payload=load('final_payload.json')
assert set(payload)=={'status','report_path','verdicts'} and payload['status']=='done'
assert payload['report_path']==str(report)
provided=json.loads((P/'推导92A'/'candidates.json').read_text())
names=[x['name'] for x in provided]
assert len(names)==15 and names==[x['name'] for x in payload['verdicts']]
for v in payload['verdicts']:
    assert set(v)=={'name','verdict','reason','revised_text'}
    assert v['verdict'] in {'未否证','已否证','修正'} and v['reason']
    assert bool(v['revised_text'])==(v['verdict']=='修正')
assert Counter(v['verdict'] for v in payload['verdicts'])=={'未否证':14,'修正':1}
revision=next(v for v in payload['verdicts'] if v['name']=='来源定序')['revised_text']
old=next(v['text'] for v in provided if v['name']=='来源定序')
assert revision==old.replace('选定一组接货物品格','选定一组运输物品格或制造单位的存货物品格（不含缓存格）')
body=report.read_text()
assert '{{' not in body and revision in body
headers=re.findall(r'^### 4\.\d+ (.*?)——(未否证|修正|已否证)$',body,re.M)
assert headers==[(v['name'],v['verdict']) for v in payload['verdicts']]
assert '14 条未否证，1 条修正' in body
assert '按完整循环的收支折算' in body and '不要求每个20 tick子窗口都恰如此' in body
assert (D/'reader_review.md').is_file()
links=re.findall(r'\[[^\]]+\]\(([^)]+)\)',body)
resolved=[]
for link in links:
    assert not link.startswith(('https:','http:'))
    path=(P/link.split('#')[0]).resolve()
    assert path.exists() or path in [D/'validation.json',D/'artifact_manifest.json'],link
    resolved.append(str(path))

validation={'status':'PASS','validated_at_utc':datetime.now(timezone.utc).isoformat(),
 'python_version':platform.python_version(),'candidate_count_in_supplied_list':15,'candidate_count_worded_in_task':16,
 'coverage':'15 supplied candidates plus the noncandidate 接通先后; additional supporting premises sampled',
 'verdict_counts':dict(Counter(v['verdict'] for v in payload['verdicts'])),
 'snapshot_hashes_match_initial_read':True,'independent_arithmetic_agreement':True,
 'independent_dense_trajectory_agreement':True,'dense_geometry_and_blueprint_checks':True,
 'polling_two_encoding_case_agreements':E['cases'],'polling_subset_cases':F['subset_channel_cases'],
 'polling_formula_equalities':B['formula_indicator_equalities'],'reader_pass_completed':True,
 'report_and_payload_full_revision_identical':True,'local_links_checked':len(links),
 'no_full_layout_certificate_claimed':True}
(D/'validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2)+'\n')
files=[p for p in sorted(D.rglob('*')) if p.is_file() and p.name!='artifact_manifest.json']+[report]
manifest={'generated_at_utc':validation['validated_at_utc'],
 'inputs':{str(P/'前提快照'/n):h for n,h in expected_snapshot.items()},
 'derivation_materials':{str(P/'推导92A.md'):sha(P/'推导92A.md'),str(P/'推导92A'/'candidates.json'):sha(P/'推导92A'/'candidates.json')},
 'artifacts':[{'path':str(p),'bytes':p.stat().st_size,'sha256':sha(p)} for p in files],
 'self_hash_excluded':True}
(D/'artifact_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
assert all(Path(p).exists() for p in resolved)
print(json.dumps({'status':'PASS','verdicts':validation['verdict_counts'],'candidate_count':15,
 'local_links_checked':len(links),'artifacts_hashed':len(files),'report_path':str(report)},ensure_ascii=False))
