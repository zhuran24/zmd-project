"""只读：把 2026-09-22/before.json 的全部 5906 项与当前字节对比，按顶层目录与是否被 Git 跟踪分组。"""
import hashlib, json, subprocess, collections
from pathlib import Path
solver = Path('/home/zhuran24/zmd-research-fresh/求解器')
b = json.load(open(solver / '内核维护/2026-09-22/before.json'))['files']
tracked = set(subprocess.check_output(['git', '-C', str(solver), '-c', 'core.quotePath=false', 'ls-files', '-z']).decode().split('\0'))
diff = collections.Counter(); missing = []; rows = []
for rel, e in b.items():
    p = solver / rel
    if not p.exists():
        missing.append(rel); continue
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    if h != e['sha256']:
        top = '/'.join(rel.split('/')[:3])
        t = rel in tracked
        diff[(top, t)] += 1
        rows.append({'path': rel, 'tracked': t})
print(json.dumps({'before_entries': len(b), 'missing_now': missing,
                  'changed': len(rows),
                  'by_top_tracked': {f'{k[0]} tracked={k[1]}': v for k, v in sorted(diff.items())}},
                 ensure_ascii=False, indent=1))
json.dump(rows, open(solver / '内核维护/2026-09-22d/审查-opus/full_before_compare.rows.json', 'w'), ensure_ascii=False, indent=1)
