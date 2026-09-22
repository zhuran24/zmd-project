#!/usr/bin/env python3
"""Read-only final consistency and reader review checks."""
import ast,hashlib,json,re,subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parent;ROOT=OUT.parents[2]
def read(name):return json.loads((OUT/name).read_text())
report=OUT.parent/'R3-测试写历史.md';text=report.read_text()
rows=read('file_audit.json');ev=[r for r in rows if '/crates/kernel/evidence/' in r['path']]
old=[r for r in ev if r['base_sha256']];new=[r for r in ev if not r['base_sha256']]
assert (len(ev),len(old),len(new))==(166,159,7)
assert all(r['base_equals_pre'] for r in old)
assert all(all(line.startswith(('a7539f5 ','220f7b6 ')) for line in r['history']) for r in ev)
assert sum(any(c['commit']=='220f7b6' for c in r['changes']) for r in old)==106
assert sum(any(c['commit']=='220f7b6' for c in r['changes']) for r in new)==5
manifest=read('restore_manifest.json');assert manifest['action_executed'] is False
assert {r['path'] for r in manifest['files']}=={r['path'] for r in old}
for r in ev:
    assert r['path'].split('/crates/kernel/evidence/')[1] in text
    assert hashlib.sha256((ROOT.parent/r['path']).read_bytes()).hexdigest()==r['head_sha256']
source_changes=[]
for r in read('static_inventory.json'):
    if hashlib.sha256((ROOT/r['file']).read_bytes()).hexdigest()!=r['sha256']:source_changes.append(r['file'])
assert not source_changes
drift=read('pre_day_hash_drift.json');untracked=[r for r in drift if not r['tracked']]
assert len(drift)==173 and len(untracked)==14
ignored=subprocess.check_output(['git','-C',str(ROOT),'check-ignore','--',*[r['path'] for r in untracked]],text=True).splitlines()
# Git quotePath can quote non-ASCII paths; only the number is relevant here.
assert len(ignored)==14
assert sum(bool(r['existing_exact_copy_candidates']) for r in untracked)==1
assert all(r['still_matches'] for r in read('restoration_verified.json'))
tracked_diff=subprocess.check_output(['git','-C',str(ROOT.parent),'diff','HEAD','--name-only'],text=True)
assert not tracked_diff
status=subprocess.check_output(['git','-C',str(ROOT),'-c','core.quotePath=false','status','--short'],text=True)
head=subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()
assert head==read('git_summary.json')['head']
links=re.findall(r'\]\(([^)]+)\)',text)
assert all((report.parent/link.split('#')[0]).exists() for link in links)
for p in OUT.glob('*.py'):ast.parse(p.read_text(),filename=str(p))
assert all(p.suffix in ('.py','.rs','.json','.md','.log') for p in OUT.rglob('*') if p.is_file())
result=dict(status='pass',head=head,report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),
    evidence_rows=166,restore_rows=159,new_test_rows=7,other_evidence_rows=len(rows)-len(ev),untracked_drift=14,
    source_fingerprints_checked=len(read('static_inventory.json')),source_changes=source_changes,
    tracked_worktree_changes=tracked_diff,worktree_status=status,
    concurrent_untracked_note='Other R1/R2/R4/R5 reports and research directories appeared during audit; not created, reviewed, or modified by R3.',
    historical_tests_executed=0,restoration_executed=False,links_checked=len(links),
    reader_review=['正文和完整166行清单已通读','结论区别代码静态确认与历史覆盖事实','第一轮恢复不与后两轮混淆',
        '159旧文件与7新增文件逐项分开','14无Git版本文件不冒称可用Git恢复','108新增维护文件和2新增参考基线不回退',
        '旧状态与当前状态分别标版本','数字和命令输出一致','源文件行号和真实写点核对','报告及日志链接存在'])
(OUT/'reader_review.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ('worktree_status','reader_review','concurrent_untracked_note')},ensure_ascii=False,indent=2))
