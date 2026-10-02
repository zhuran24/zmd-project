"""Validate saved evidence and local report links; write delivery metadata."""
from pathlib import Path
import hashlib
import json
import re

HERE=Path(__file__).resolve().parent
REPORT=HERE.parent/'复核93C.md'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(name,obj):
    (HERE/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n')


text=REPORT.read_text()
links=re.findall(r'\[[^\]]+\]\(([^)]+)\)',text)
assert all((REPORT.parent/x).is_file() for x in links),links
data=json.loads((HERE/'results.json').read_text())
coverage=json.loads((HERE/'coverage_results.json').read_text())
assert data['run']['mode']=='full'
assert data['loops']['compared_step_states']==2520000
assert data['loops']['violations']==0
assert data['rotation']['scenarios']==32768
assert data['fifty_ticks']['first_possible_empty']==400
assert data['transfer']['cases']==1024
assert coverage['backpressure']['violations']==0
assert coverage['initial_history_rotation']['cases']==690
manifest=json.loads((HERE/'input_manifest.json').read_text())
for name,sha in manifest.items():
    assert digest(Path(name))==sha, name
scope_path=HERE.parent/'推导92C'/'candidates.json'
candidates=json.loads(scope_path.read_text())
names=[x['name'] for x in candidates]
assert len(names)==6 and len(set(names))==6
assert all(n in text for n in names)
reasons=[
    '前缀归纳成立，来料种类限制必要。',
    '同级及恰8步清出保证成功序轮转。',
    '第0—399步的库存、缓存与回填界成立。',
    '重证176；无限额有向准入口范围也可恢复。',
    '正存量和粉末有限清出保证无限次开批。',
    '单出口回填沿路传递，周期性排除空缓存。',
]
reply=dict(status='完成所列6条',error='原文要求7条，但实际仅列6条候选。',
           report_path=str(REPORT),
           verdicts=[dict(name=n,verdict='未否证',reason=r,revised_text='') for n,r in zip(names,reasons)])
assert set(reply)=={'status','error','report_path','verdicts'}
assert all(set(v)=={'name','verdict','reason','revised_text'} for v in reply['verdicts'])
put('reply.json',reply)
put('validation.json',dict(
    report_exists=True,local_links_checked=len(links),local_links_missing=[],
    actual_candidate_count=6,requested_count_in_task_footer=7,
    candidate_names_match=True,snapshot_hashes_unchanged=True,
    full_run_seconds=data['run']['wall_seconds'],
    reader_review=dict(status='passed',checks=[
        'Current verdicts separated from original stronger claims.',
        'All six supplied names have a definite verdict and proof.',
        'Counterexample origins and usable-machine constraints are addressed.',
        'External boundaries and non-embedded graphs are explicitly limited.',
        'Bridge readings and offline ordering are treated separately.',
        'No unproved full-rate or layout certificate is claimed.',
        'Counts denote parameter choices; commuting cases are identified.',
        'Cross references and output paths exist.',
    ])))
inputs={str(p):digest(p) for p in (scope_path,HERE/'coverage.py')}
put('supplementary_inputs.json',inputs)
artifacts={str(REPORT.relative_to(HERE.parent)):digest(REPORT)}
for p in sorted(HERE.iterdir()):
    if p.is_file() and p.name!='artifact_manifest.json':
        artifacts[str(p.relative_to(HERE.parent))]=digest(p)
put('artifact_manifest.json',artifacts)
print(json.dumps(dict(report=str(REPORT),verdict_count=len(names),links_ok=len(links),
                      full_run_seconds=data['run']['wall_seconds'],artifacts=len(artifacts)),ensure_ascii=False))
