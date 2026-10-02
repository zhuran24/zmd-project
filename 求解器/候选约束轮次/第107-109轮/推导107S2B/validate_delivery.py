#!/usr/bin/env python3
"""Readback, identity/hash, aggregate arithmetic, links and artifact checks."""
import ast
import hashlib
import json
import re
from collections import Counter,defaultdict
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'推导107S2B.md'
def read(name): return json.loads((HERE/name).read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
changed=[]
for row in read('inputs.json'):
    if sha(Path(row['path'])) != row['sha256']: changed.append(row['path'])
assert not changed, changed
assert read('arithmetic_a.json')==read('arithmetic_b.json')
assert read('startup_budget_b.json')['independent_equal']
cycles=[read(f'cycle_{s}.json') for s in range(107001,107008)]
for c in cycles:
    assert c['period_steps']==480
    assert c['delivery']=={'高容谷地电池':36,'精选荞愈胶囊':33}
    assert c['ore_counts']==[60]*52 and not any(c['shared_refusals'].values())
    assert c['closure_direct_equal'] and c['step_differences']==c['invariant_violations']==0
assert {c['history'] for c in cycles}=={'keep','clear','mixed'}
graphs=[]
for c in cycles:
    g=read(f"graph_{c['seed']}.json")
    assert g['is_layout'] is False and g['machine_count']==230 and g['route_count']==325
    uses=defaultdict(list)
    for r in g['routes']:
        assert len(r['physical_units'])==r['length']==len(r['types'])
        assert len(set(r['physical_units']))==r['length']
        for p,t in zip(r['physical_units'],r['types']):
            if t=='B': uses[p].append(r['id'])
        assert r['component_layers']==list(range(len(r['component_layers']),0,-1))
    assert all(1<=len(v)<=2 and len(set(v))==len(v) for v in uses.values())
    assert len(uses)==g['bridges'] and sum(len(v)==2 for v in uses.values())==g['double_axis_bridges']
    graphs.append({'seed':c['seed'],'physical_transport_units':g['transport_slots']-g['double_axis_bridges'],
                   'slots':g['transport_slots'],'double_bridges':g['double_axis_bridges'],
                   'scalar_fits_with_11_poles':g['transport_slots']-g['double_axis_bridges']<=1070,
                   'is_layout':False})
startups=read('startup_bridge_results.json')
assert len(startups)==3 and all(x['prepared_state_verified'] and x['provenance_verified'] and x['kit_bound_pass'] for x in startups)
assert all(x['manual_transport_insertions']==x['manual_cache_changes_after_initialization']==0 for x in startups)
probe=read('transport_probes.json')
assert probe['layers']['all_equal'] and probe['replenishment']['recurrence_equal']
assert probe['replenishment']['deadline_violations']==0 and all(probe['controls'].values())
text=REPORT.read_text()
missing=[]
for target in re.findall(r'\]\(([^)]+)\)',text):
    if target.startswith(('http:','https:','#')): continue
    p=REPORT.parent/target.split('#',1)[0]
    if not p.exists() and p.name not in ('validation.json',): missing.append(str(p))
assert not missing,missing
for p in HERE.glob('*.py'): ast.parse(p.read_text(),filename=str(p))
for p in HERE.iterdir():
    assert p.is_file(),p
    assert p.suffix in {'.py','.log','.json','.md','.gz'},p
    assert p.stat().st_size<=100*1024*1024 or p.suffix=='.gz',p
result={'status':'pass','inputs_unchanged':True,'report_path':str(REPORT),'cycles':len(cycles),
        'whole_factory_steps':sum(x['steps_compared'] for x in cycles),
        'whole_factory_rebuilds':sum(x['rebuilds'] for x in cycles),
        'reverse_source_checks':sum(x['reverse_block_checks'] for x in cycles),
        'startup_steps':sum(x['steps_compared'] for x in startups),
        'startup_preparation_steps':sum(x['prepared_at'] for x in startups),
        'startup_rebuilds':sum(x['rebuilds'] for x in startups),
        'all_key_arithmetic_independent_equal':True,'graphs':graphs,
        'report_links_valid':True,'python_syntax_valid':True,'permitted_file_types_only':True,
        'formal_area_dimension_bound':841,'exact_route_area_dimension_bound':833,
        'geometry_certified':False,'global_U':1110,'global_L':0}
(HERE/'validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
files=[REPORT]+sorted(p for p in HERE.iterdir() if p.is_file() and p.name not in ('artifact_manifest.json','validation.log'))
manifest=[{'path':str(p),'sha256':sha(p),'bytes':p.stat().st_size} for p in files]
(HERE/'artifact_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
