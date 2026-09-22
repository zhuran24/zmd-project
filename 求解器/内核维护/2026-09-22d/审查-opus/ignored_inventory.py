"""只读：统计 .gitignore 中逐路径列出的大运行记录（仓库根 .gitignore 的显式 /求解器/ 路径）当前存在数与字节数，按目录分组。"""
import json, collections
from pathlib import Path
root = Path('/home/zhuran24/zmd-research-fresh')
rows = [l.strip() for l in open(root / '.gitignore') if l.strip().startswith('/求解器/') and '*' not in l]
g = collections.Counter(); b = collections.Counter(); missing = []
for r in rows:
    p = root / r.lstrip('/')
    top = '/'.join(r.split('/')[2:5])
    if p.is_file():
        g[top] += 1; b[top] += p.stat().st_size
    else:
        missing.append(r)
print(json.dumps({'listed': len(rows), 'existing': sum(g.values()), 'bytes': sum(b.values()),
                  'by_dir': {k: [g[k], b[k]] for k in sorted(g)}, 'missing': missing}, ensure_ascii=False, indent=1))
