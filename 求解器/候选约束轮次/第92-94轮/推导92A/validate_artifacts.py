#!/usr/bin/env python3
"""Verify coverage, source identity, paired results, and final payload shape."""
from pathlib import Path
import hashlib
import json
import re

out = Path(__file__).resolve().parent
def read(name): return json.loads((out/name).read_text())
inventory = read('inventory.json')
payload = read('final_payload.json')
report = Path(payload['report_path'])
text = report.read_text()
assert report == out.parent/'推导92A.md'
for p in inventory['snapshots']:
    path = out.parent/'前提快照'/p['name']
    assert hashlib.sha256(path.read_bytes()).hexdigest() == p['sha256'], path
    assert len(path.read_text().splitlines()) == p['lines']
assert len(payload['candidates']) == 15
assert len(inventory['review_ids']) == 15
names = {c['name'] for c in payload['candidates']}
assert len(names) == 15
for entry in inventory['items']:
    assert entry['id'] in text
    if entry['id'] != 'N01':
        assert entry['name'] in names
for c in payload['candidates']:
    assert set(c) == {'name', 'kind', 'text', 'basis', 'derivation', 'relation'}
    assert c['kind'] == '必要条件'
    assert c['text'] in text, c['name']
    assert f'{c["name"]}：{c["text"]}' in text
    assert all(isinstance(v, str) and v for v in c.values())

pa, pb = read('polling_verify_a.json'), read('polling_verify_b.json')
for key in ['cases_by_k', 'cases_total', 'canonical_sha256', 'violations']:
    assert pa[key] == pb[key]
assert pa['violations'] == 0
pf = read('polling_formula_verify.json')
assert pf['violations'] == 0
assert pf['counterexample']['two_independent_implementations_agree']
assert read('clearing_check_fraction.json') == read('clearing_check_integer.json')['result']
oa, ob = read('order_reference.json'), read('order_independent.json')
assert len(oa) == len(ob) == 2
for a, b in zip(oa, ob):
    for key in ['cycle_steps', 'period_steps', 'other_input_count', 'merger_output_count', 'core_stock_min']:
        assert a[key] == b[key], (key, a[key], b[key])
    assert sorted(a['split_counts'].values()) == sorted(b['split_counts'].values())
assert read('order_geometry.json')['verified']
assert read('root_checks.json')['status'] == 'PASS'

# Link targets in the main report are relative to the report's directory.
links = re.findall(r'\[[^\]]*\]\(([^)]+)\)', text)
for link in links:
    if not re.match(r'\w+://', link):
        assert (report.parent/link.split('#')[0]).exists(), link
for path in out.rglob('*'):
    if path.is_file():
        assert path.suffix in {'.py', '.log', '.json', '.md', '.gz'}, path
        assert path.stat().st_size <= 100*1024*1024 or path.suffix == '.gz'

validation = {
    'status': 'PASS', 'premises_unchanged': True,
    'formal_entries_reviewed': len(inventory['review_ids']),
    'literal_match_lines': inventory['exact_match_line_count'],
    'candidates': len(payload['candidates']),
    'candidate_texts_in_report': True,
    'polling_paired_cases_each': pa['cases_total'],
    'polling_paired_trace_sha256': pa['canonical_sha256'],
    'formula_instances': pf['formula_instances'],
    'formula_equalities': pf['scalar_equalities_checked'],
    'clearing_paired_results_equal': True,
    'dense_node_paired_results_equal': True,
    'dense_node_geometry_valid': True,
    'report_sha256': hashlib.sha256(report.read_bytes()).hexdigest(),
    'artifact_extension_and_size_checks': True,
    'linked_targets_exist': True,
    'scope': 'artifact consistency and local proof checks; not a qualified layout certificate',
}
(out/'validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2)+'\n')
manifest = []
for path in sorted(out.iterdir()):
    if path.is_file() and path.name != 'artifact_manifest.json':
        manifest.append({'name': path.name, 'bytes': path.stat().st_size,
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
manifest.append({'name': '../推导92A.md', 'bytes': report.stat().st_size,
                 'sha256': hashlib.sha256(report.read_bytes()).hexdigest()})
(out/'artifact_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(validation, ensure_ascii=False))
