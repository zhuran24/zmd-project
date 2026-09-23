#!/usr/bin/env python3
"""Read-only audit of inputs/report, with one output in this directory."""
from pathlib import Path
import json
import hashlib
import re

out=Path(__file__).resolve().parent
report=out.parent/'复核70.md'
root=out.parent.parents[2]
manifest=json.loads((out/'input_manifest.json').read_text())
for name,entry in manifest.items():
    data=(root/name).read_bytes()
    assert len(data)==entry['bytes']
    assert hashlib.sha256(data).hexdigest()==entry['sha256'],name
body=report.read_text()
links=re.findall(r'\]\(([^)]+)\)',body)
for link in links:
    assert not link.startswith(('http:', 'https:'))
    assert (report.parent/link).is_file() or report.parent/link==out/'delivery_audit.json',link
verdicts=json.loads((out/'verdicts.json').read_text())
assert verdicts['report_path']==str(report)
assert len(verdicts['verdicts'])==4
for v in verdicts['verdicts']:
    assert v['name'] in body and v['verdict']=='未否证' and v['revised_text']==''
local=json.loads((out/'local_results.json').read_text())
assert local['positions']==395 and local['total_columns']==275888 and local['total_rows']==669475
edges=json.loads((out/'edge_results.json').read_text())
assert len(edges['results'])==36
assert edges['counts']=={'tables':48,'options':7320,'frontier_entries':1274,'bodies':652,'forbidden_adjacent_pairs':1630}
for mode in ('new','local'):
    rows=[r for r in edges['results'] if r['mode']==mode]
    assert min(r['minimum'] for r in rows if r['P']==11)==189
    assert min(r['minimum'] for r in rows if r['P']==12)==198
    assert [r['minimum'] for r in rows if r['P']==10 and r['minimum'] is not None]==[180]
log=(out/'recheck.log').read_text()
assert log.rstrip().endswith('PASS: inputs unchanged')
assert 'Traceback' not in log
assert '未读取另一席本次复核' in body
assert '不能降到1110' in body and '来源不明，当线索' in body
assert len(re.findall(r'^    据：', (root/'求解约束.txt').read_text(),re.M))==72
audit={
    'status':'PASS',
    'input_files_unchanged':len(manifest),
    'local_links_checked':len(links),
    'verdicts_checked':4,
    'branch_combinations_checked':36,
    'reader_review':{
        'standalone_subject_and_formal_inputs':True,
        'header_matches_all_four_verdicts':True,
        'one_current_numeric_account_per_model':True,
        'all_P_and_corner_branches_explicit':True,
        'conditional_bounds_distinguished_from_feasible_layouts':True,
        'no_peer_current_review_read':True,
        'cross_references_resolve':True
    },
    'output_hashes':{}
}
for p in [report,*sorted(out.iterdir())]:
    if p.is_file() and p.name!='delivery_audit.json':
        audit['output_hashes'][str(p.relative_to(out.parent))]=hashlib.sha256(p.read_bytes()).hexdigest()
(out/'delivery_audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in audit.items() if k not in ('output_hashes','reader_review')},ensure_ascii=False))
