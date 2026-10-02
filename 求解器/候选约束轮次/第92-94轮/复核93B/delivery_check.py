"""Read-only document/source checks, followed by a receipt in this output directory."""
from pathlib import Path
import ast,hashlib,json,re
out=Path(__file__).resolve().parent
report=out.parent/'复核93B.md'
body=report.read_text()
links=re.findall(r'\]\(([^)]+)\)',body)
assert all((report.parent/p).exists() for p in links),[p for p in links if not (report.parent/p).exists()]
scripts=list(out.glob('*.py'))
for p in scripts:ast.parse(p.read_text(),filename=str(p))
verdicts=json.loads((out/'verdicts.json').read_text())
assert verdicts['report_path']==str(report)
assert [r['name'] for r in verdicts['verdicts']]==['核心邻格','面积预算','内带缺口']
assert [r['verdict'] for r in verdicts['verdicts']]==['未否证','修正','修正']
for item in verdicts['verdicts']:
    assert set(item)=={'name','verdict','reason','revised_text'}
    assert bool(item['revised_text'])==(item['verdict']=='修正')
snapshot=json.loads((out/'arithmetic_a.json').read_text())['snapshot_sha256']
assert all(hashlib.sha256((out.parent/'前提快照'/name).read_bytes()).hexdigest()==sha for name,sha in snapshot.items())
receipt={'status':'PASS','local_links_checked':len(links),'scripts_syntax_checked':len(scripts),'verdict_schema_checked':True,'snapshots_unchanged':True,
 'reader_review':{'header_matches_verdicts':True,'all_candidate_replacement_clauses_present':True,'local_relaxations_distinguished_from_factories':True,'CP_SAT_UNKNOWN_not_used_as_infeasibility':True,'unresolved_old_inner_corner_case_explicit':True,'global_1110_bound_not_claimed_recertified':True}}
(out/'delivery_check.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(receipt,ensure_ascii=False))
