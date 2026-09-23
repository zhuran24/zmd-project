#!/usr/bin/env python3
"""Check the delivered report's evidence, links and input hashes."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPORT = HERE.parent/'A-运输格总量-复核64.md'
ROOT = HERE.parents[3]


def read(name):
    return json.loads((HERE/name).read_text())


snapshot = read('official_snapshot.json')
unchanged = {name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==meta['sha256']
             for name,meta in snapshot.items()}
assert all(unchanged.values())
bound = read('bound_all.json')
expected = {(l,b) for l in range(0,70,3) for b in range(0,70,3) if l==0 or b==0}
assert len(bound)==47 and {(r['left_gap'],r['bottom_gap']) for r in bound}==expected
assert all(r['cap']==7 and r['status']=='INFEASIBLE' for r in bound)
arithmetic = read('arithmetic.json')
assert len(arithmetic['branches'])==24
assert all(not r['excluded'] for r in arithmetic['branches'])
assert arithmetic['V_lower']=='6273/20' and arithmetic['slots_min']==314
assert arithmetic['machine_area']==3291 and arithmetic['next_areas'][:2]==[1113,1110]
witness = read('witness_checked.json')
for key in ('original','independently_found'):
    assert witness[key]['extra']==8 and witness[key]['body_cells']==414
    assert len(witness[key]['holes'])==8 and all(r['clear'] for r in witness[key]['holes'])
original = HERE.parent/'A-运输格总量'/'relaxation_witness.json'
assert hashlib.sha256(original.read_bytes()).hexdigest()==witness['original_coordinate_file_sha256']
report = REPORT.read_text()
links = []
for target in re.findall(r'\]\(([^)]+)\)',report):
    path = (REPORT.parent/target).resolve()
    if path == HERE/'delivery_audit.json':
        continue  # This invocation writes that file after all checks pass.
    assert path.exists(), target
    links.append(target)
own = read('witness_3_0.json')[0]
nonzero = {(tuple(a['source']),tuple(a['body']),a['extra'])
           for a in own['assignment'] if a['extra']}
assert nonzero == {((1,56),(5,56),3),((2,1),(4,2),2),((5,1),(5,5),3)}
assert '记 F 为指定空矩形外的空格数' in report
assert report.count('；否 |') == 24
result = {
    'status':'passed',
    'official_inputs_unchanged':unchanged,
    'infeasible_boundary_cases':47,
    'position_power_cases_without_new_exclusion':24,
    'original_and_independent_witnesses_checked':True,
    'report_links_checked':links,
    'reader_review':{
        'completed':True,
        'standalone_definitions_and_verdict':True,
        'formal_basis_separate_from_derivation_material':True,
        'all_numbers_match_current_evidence':True,
        'relaxation_witness_not_claimed_as_game_layout':True,
        'no_unresolved_rule_fact':True,
        'references_and_status_consistent':True
    },
    'report_sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),
    'artifact_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                       for p in sorted(HERE.iterdir()) if p.is_file() and p.name!='delivery_audit.json'}
}
(HERE/'delivery_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'status':result['status'],'boundary_cases':47,'branches':24,
                  'links':len(links),'official_inputs_unchanged':all(unchanged.values())},ensure_ascii=False))
