"""Check file integrity, 14-item schema, preserved quotations and report links."""
import ast
import hashlib
import json
import re
import sys
from datetime import datetime,timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
src=json.loads((BASE/'修正版清单.json').read_text())
out=json.loads((HERE/'verdicts.json').read_text())
report=(BASE/'复核86.md').read_text()
assert len(src)==len(out)==14
assert [x['index'] for x in out]==list(range(14))
assert len(set(x['name'] for x in out))==14
for i,(a,b) in enumerate(zip(src,out)):
    assert set(b)=={'index','name','verdict','reason','revised_text'}
    assert b['name']==a['name']
    assert b['verdict'] in ('未否证','已否证','修正')
    assert 0<len(b['reason'])<=300
    assert f'### {i}. {a["name"]}' in report
    if b['verdict']=='未否证':assert b['revised_text']==a['text']
    if b['verdict']=='修正':assert b['revised_text'] and b['revised_text'] in report
    if b['verdict']=='已否证':assert b['revised_text']==''
acc=json.loads((HERE/'accounts.json').read_text())
for name,digest in acc['hashes'].items():
    assert hashlib.sha256((BASE/'前提快照'/name).read_bytes()).hexdigest()==digest
assert hashlib.sha256((BASE/'修正版清单.json').read_bytes()).hexdigest()==acc['candidate_sha256']
assert [x for x in re.findall(r'^### (\d+)\. ',report,re.M)]==list(map(str,range(14)))
assert len(re.findall(r'^结论：\*\*(?:未否证|修正|已否证)\*\*。',report,re.M))==14
links=[]
for target in re.findall(r'\]\(([^)]+)\)',report):
    if '://' in target or target.startswith('#'):continue
    assert (BASE/target).exists(),target
    links.append(target)
for p in HERE.glob('*.py'):ast.parse(p.read_text(),filename=str(p))
assert not (HERE/'__pycache__').exists()
graphs=json.loads((HERE/'small_graph.json').read_text())
assert all(g['population_bound_violations']==g['high_phi_c_idle']==g['nonempty_forward_S_violations']==0 for g in graphs)
probes=json.loads((HERE/'plant_probes.json').read_text())['counts']
assert probes['trials']==probes['cycles']==600 and probes['eligible_cycle_idle']==0
skeleton=json.loads((HERE/'skeleton_probes.json').read_text())
assert len(skeleton)==5 and all('repeated_state_sha256' in r for r in skeleton)
witnesses=json.loads((HERE/'witnesses.json').read_text())
assert witnesses['gate']['period']==[12,17]
assert witnesses['merger']['lengths']==[5,27,12,3]
assert all(x['M_was_empty'] and x['K_to_M']==0 for x in witnesses['merger']['trace'])
start=datetime(2026,9,26,11,24,5,tzinfo=timezone.utc)
now=datetime.now(timezone.utc)
previous_path=HERE/'delivery_audit.json'
previous=json.loads(previous_path.read_text()) if previous_path.exists() else {}
finished=datetime.fromisoformat(previous['finished_utc']) if previous.get('finished_utc') else now
if '--enforce-deadline' in sys.argv:
    finished=now
    assert (finished-start).total_seconds()<3*3600
elapsed=(finished-start).total_seconds()
result=dict(status='passed',items=14,counts={v:sum(r['verdict']==v for r in out) for v in ('未否证','已否证','修正')},
            checked_relative_links=len(links),snapshots_unchanged=True,original_texts_exact=True,
            report_sha256=hashlib.sha256((BASE/'复核86.md').read_bytes()).hexdigest(),
            verdicts_sha256=hashlib.sha256((HERE/'verdicts.json').read_bytes()).hexdigest(),
            elapsed_seconds=elapsed,finished_utc=finished.isoformat(),last_checked_utc=now.isoformat(),
            note='Static delivery checks; mathematical proof reviewed separately in the report.')
(HERE/'delivery_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(result,ensure_ascii=False))
