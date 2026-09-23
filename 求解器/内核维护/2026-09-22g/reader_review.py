"""对已完成记录的链接、数字、文件指纹和提交范围作最终核对。"""
import json
import re
import subprocess
from guard import OUT, ROOT, REPO, digest, save, active_snapshot, difference

summary = json.loads((OUT / 'summary.json').read_text())
changes = json.loads((OUT / 'changed-files.json').read_text())
text = (OUT / '记录.md').read_text()
assert summary['status'] == 'pass'
assert summary['constraints'] == 72
assert summary['business_file_count'] == len(changes) == 62
assert summary['rust_passed'] == 134 and summary['rust_failed'] == 0
assert summary['python_cases'] == 8
assert summary['relocked_inputs'] == 54
assert summary['audited_reference_documents'] == 56 and summary['audited_reference_fields'] == 114
assert summary['candidate_sources'] == 16
assert summary['history_total_files'] == 3475 and summary['history_ignored_files'] == 1
assert not any(summary['history_diff'].values())
assert summary['history_comparison_count'] == 37
assert summary['catalog_sha256'] == digest(ROOT / '数据/正式静态目录.json')
assert all(digest(REPO / row['path']) == row['after_sha256'] for row in changes)
current = active_snapshot()
initial = json.loads((OUT / 'initial-active.json').read_text())
delta = difference(initial, current)
assert not delta['added'] and not delta['deleted']
assert set(delta['changed']) == {row['path'] for row in changes}
tracked_changes = subprocess.check_output(['git', 'diff', '--name-only', '-z'], cwd=REPO).decode().split('\0')
assert set(filter(None, tracked_changes)) == {row['path'] for row in changes}
assert not subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=REPO)
links = []
for name in ['记录.md', 'changed-files.md']:
    for target in re.findall(r'\]\(([^)]+)\)', (OUT / name).read_text()):
        assert (OUT / target).exists(), (name, target)
        links.append({'document': name, 'target': target})
revision = (ROOT / '规格/修订记录.md').read_text().split('## 2026-09-22 r24：', 1)[1]
assert summary['catalog_sha256'] in revision
assert '../内核维护/2026-09-22g/记录.md' in revision
assert '指定安全集通过' in text and '不重跑对应总自查' in text
assert '本轮未单独运行 topology CLI' in text
assert not re.search(r'^warning:', (OUT / 'cargo-clippy.log').read_text(), re.M)
# Reader pass: dated execution record, current and historical counts separated,
# 62 business files separate from artifacts, expected negative exit separate from failures,
# three existing issue groups retained, all references resolvable.
save('reader-review.json', {'status': 'pass', 'reviewed_documents': ['记录.md', 'changed-files.md',
     '规格/修订记录.md r24', '数据/候选B/验证记录.md'], 'links_checked': len(links),
     'business_files': len(changes), 'scope_matches_git_diff': True, 'index_empty': True,
     'history_comparisons_checked': summary['history_comparison_count'],
     'counts_consistent': True, 'historical_candidate_counts_labeled': True,
     'known_issue_scope_preserved': True, 'record_sha256': digest(OUT / '记录.md')})
artifacts = [{'path': str(p.relative_to(OUT)), 'bytes': p.stat().st_size, 'sha256': digest(p)}
             for p in sorted(OUT.rglob('*')) if p.is_file() and p.name != 'artifacts.json']
save('artifacts.json', artifacts)
print(json.dumps({'status': 'pass', 'business_files': len(changes), 'links_checked': len(links),
                  'record_artifacts': len(artifacts), 'history_diff': summary['history_diff']}, ensure_ascii=False))
