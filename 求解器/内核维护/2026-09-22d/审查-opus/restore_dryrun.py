"""只读复算《代码体检方案》§3.2 恢复块的计划阶段（不写仓库，不备份，不恢复）。"""
import hashlib, json, subprocess, sys
from pathlib import Path

root = Path('/home/zhuran24/zmd-research-fresh')
solver = root / '求解器'
evidence = solver / '内核维护/2026-09-22d/R3-测试写历史'
rows = json.loads((evidence / 'restore_manifest.json').read_text())['files']
sha = lambda b: hashlib.sha256(b).hexdigest()
blob = lambda rev, p: subprocess.check_output(['git', '-C', str(root), 'show', f'{rev}:{p}'])
out = {'rows': len(rows), 'unique_paths': len({r['path'] for r in rows}),
       'resolve_ok': 0, 'expected_matches_source': 0, 'equivalent_equal': 0,
       'current_is_current_sha': 0, 'current_is_expected_sha': 0, 'current_other': [],
       'already_restored': 0, 'head_equals_current': 0, 'blob_220f7b6_equals_current': 0,
       'history_check_fail': []}
for r in rows:
    rel = Path(r['path'])
    assert not rel.is_absolute() and '..' not in rel.parts
    assert rel.as_posix().startswith('求解器/crates/kernel/evidence/')
    p = root / rel
    if p.resolve() == p and p.is_file():
        out['resolve_ok'] += 1
    old = blob(r['source_commit'], r['path'])
    if sha(old) == r['expected_sha256']:
        out['expected_matches_source'] += 1
    if old == blob(r['equivalent_commit'], r['path']):
        out['equivalent_equal'] += 1
    now = p.read_bytes()
    s = sha(now)
    if s == r['current_sha256']:
        out['current_is_current_sha'] += 1
    elif s == r['expected_sha256']:
        out['current_is_expected_sha'] += 1
    else:
        out['current_other'].append(r['path'])
    if now == blob('HEAD', r['path']):
        out['head_equals_current'] += 1
    if now == blob('220f7b6', r['path']):
        out['blob_220f7b6_equals_current'] += 1
    # 该路径在 f8f6129..7da52a7 之间是否有提交改动
    log = subprocess.check_output(['git', '-C', str(root), 'log', '--format=%h',
                                   'f8f6129..7da52a7', '--', r['path']]).decode().split()
    if log:
        out['history_check_fail'].append((r['path'], log))

drift = [r for r in json.loads((evidence / 'pre_day_hash_drift.json').read_text()) if not r['tracked']]
out['untracked_drift'] = len(drift)
key = 'crates/kernel/evidence/round6/revision-r5/cli/分流器三路轮询-absolute.json'
r = next(r for r in drift if r['path'] == key)
p = solver / key
src = solver / '数据/样例/分流器三路轮询-运行记录-v3-kernel.json'
out['untracked_key_exists'] = p.is_file()
out['untracked_key_current_is_after'] = sha(p.read_bytes()) == r['after_sha256']
out['untracked_key_source_matches_before'] = sha(src.read_bytes()) == r['before_sha256']
# 13 项未解决：当前是否存在、当前哈希是否仍等于 after
out['unresolved'] = []
for d in drift:
    if d['path'] == key: continue
    q = solver / d['path']
    cur = sha(q.read_bytes()) if q.is_file() else None
    out['unresolved'].append({'path': d['path'], 'exists': q.is_file(),
                              'current_eq_after': cur == d['after_sha256'],
                              'bytes_before': d.get('bytes'), 'before': d['before_sha256']})
print(json.dumps(out, ensure_ascii=False, indent=1))
