#!/usr/bin/env python3
"""把被测试改写的已跟踪历史证据恢复到入库原件（体检方案 §3.1；13 个原件已丢失的文件不动、不加说明文件）。"""
import hashlib, json, os, subprocess, sys
REPO = '/home/zhuran24/zmd-research-fresh'
RUN = os.path.join(REPO, '求解器/内核维护/2026-09-22f')
os.chdir(REPO)
sha = lambda b: hashlib.sha256(b).hexdigest()
def blob(commit, path):
    return subprocess.run(['git', 'cat-file', 'blob', f'{commit}:{path}'], check=True, capture_output=True).stdout
def read(path):
    with open(path, 'rb') as f: return f.read()
def atomic_write(path, data, expect_before):
    if expect_before is not None and sha(read(path)) != expect_before:
        raise RuntimeError(f'写前复读不符：{path}')
    tmp = path + '.restore-tmp'
    with open(tmp, 'wb') as f:
        f.write(data); f.flush(); os.fsync(f.fileno())
    os.replace(tmp, path)
def backup(path, data):
    dst = os.path.join(RUN, 'history-before-restoration', path)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, 'wb') as f: f.write(data)

journal = {'restored': [], 'skipped': [], 'relocated': [], 'round5_check': [], 'untouched_lost': []}
tracked = set(subprocess.run(['git', 'ls-files', '-z', '--', '求解器/crates/kernel/evidence'], check=True, capture_output=True).stdout.decode().split('\0'))

# 1. manifest 的 159 项：预检、备份、恢复为 f8f6129 字节
man = json.load(open('求解器/内核维护/2026-09-22d/R3-测试写历史/restore_manifest.json'))['files']
plan = []
for e in man:
    p = e['path']; cur = read(p); src = blob('f8f6129', p)
    ok = p in tracked and sha(cur) == e['current_sha256'] and sha(src) == e['expected_sha256']
    (plan if ok else journal['skipped']).append({'path': p, 'reason': None if ok else '预检不符', 'current': sha(cur), 'target': e['expected_sha256'], '_src': src, '_cur': cur})
# 2. 额外 1 项：按样例副本恢复
extra = '求解器/crates/kernel/evidence/round6/revision-r5/cli/分流器三路轮询-absolute.json'
copy = read('求解器/数据/样例/分流器三路轮询-运行记录-v3-kernel.json')
target_extra = '6b1932067958528eeabb961fd2f08a6c8f605243767efa2f3e496d778b4d430c'
if sha(copy) == target_extra:
    cur = read(extra); plan.append({'path': extra, 'current': sha(cur), 'target': target_extra, '_src': copy, '_cur': cur, 'source': '求解器/数据/样例/分流器三路轮询-运行记录-v3-kernel.json'})
else:
    journal['skipped'].append({'path': extra, 'reason': '副本哈希不符'})
for it in plan:
    backup(it['path'], it['_cur'])
for it in plan:
    atomic_write(it['path'], it['_src'], it['current'])
    after = sha(read(it['path']))
    journal['restored'].append({'path': it['path'], 'before': it['current'], 'target': it['target'], 'source': it.get('source', 'f8f6129'), 'after': after, 'ok': after == it['target']})

# 3. a7539f5 新加进旧轮次目录的 7 个文件：提取两个提交的版本后从历史目录移走
added = subprocess.run(['git', '-c', 'core.quotepath=off', 'diff-tree', '--no-commit-id', '--name-only', '--diff-filter=A', '-r', 'a7539f5', '--', '求解器/crates/kernel/evidence'], check=True, capture_output=True, text=True).stdout.split()
for p in added:
    rel = p.split('求解器/crates/kernel/evidence/', 1)[1]
    rec = {'path': p, 'versions': []}
    for c, d in (('a7539f5', '2026-09-22b'), ('220f7b6', '2026-09-22c')):
        b = blob(c, p)
        if c == '220f7b6' and b == blob('a7539f5', p):
            rec['versions'].append({'commit': c, 'note': '与 a7539f5 相同，不另存'}); continue
        dst = os.path.join(REPO, '求解器/内核维护', d, 'cargo-test-outputs', rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        with open(dst, 'wb') as f: f.write(b)
        rec['versions'].append({'commit': c, 'dest': os.path.relpath(dst, REPO), 'sha256': sha(read(dst)), 'blob_sha256': sha(b)})
    cur = read(p); backup(p, cur); rec['current_before_removal'] = sha(cur)
    os.remove(p); rec['removed'] = not os.path.exists(p)
    journal['relocated'].append(rec)

# 4. 更早恢复过的 3 个 round5 文件核对
rv = json.load(open('求解器/内核维护/2026-09-22d/R3-测试写历史/restoration_verified.json'))
for e in (rv if isinstance(rv, list) else rv.get('files', rv.get('restored', []))):
    p = e.get('path'); p = p if p.startswith('求解器/') else '求解器/' + p; exp = e.get('expected_sha256')
    journal['round5_check'].append({'path': p, 'expected': exp, 'now': sha(read(p)) if p and os.path.exists(p) else None})

# 5. 13 个原件丢失的文件：只记当前哈希，不动
for e in json.load(open('求解器/内核维护/2026-09-22d/审查-opus/unresolved_targets.json')):
    p = '求解器/' + e['path']
    if p != extra:
        journal['untouched_lost'].append({'path': p, 'current': sha(read(p)), 'lost_original_sha256': e['before_sha256']})

for k in ('restored', 'skipped'):
    for it in journal[k]:
        it.pop('_src', None); it.pop('_cur', None)
json.dump(journal, open(os.path.join(RUN, 'restore-journal.json'), 'w'), ensure_ascii=False, indent=1)
print('restored', sum(r['ok'] for r in journal['restored']), '/', len(journal['restored']), 'skipped', len(journal['skipped']),
      'relocated', len(journal['relocated']), 'round5', journal['round5_check'], 'lost_untouched', len(journal['untouched_lost']))
