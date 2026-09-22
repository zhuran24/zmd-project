"""只读：在指定 Git 仓库的全部对象中按字节数筛选，再按 SHA-256 匹配 13 个未解决目标。"""
import hashlib, json, subprocess, sys
from pathlib import Path
here = Path(__file__).parent
t = json.load(open(here / 'unresolved_targets.json'))
want = {r['before_sha256']: r['path'] for r in t}
sizes = {r['before_bytes'] for r in t}
res = {}
for repo in sys.argv[1:]:
    try:
        lines = subprocess.check_output(['git', '-C', repo, 'cat-file', '--batch-all-objects',
                                         '--batch-check=%(objectname) %(objecttype) %(objectsize)']).decode().splitlines()
    except subprocess.CalledProcessError as e:
        res[repo] = f'error {e}'; continue
    cands = [l.split()[0] for l in lines if l.split()[1] == 'blob' and int(l.split()[2]) in sizes]
    hits = []
    for oid in cands:
        data = subprocess.check_output(['git', '-C', repo, 'cat-file', 'blob', oid])
        h = hashlib.sha256(data).hexdigest()
        if h in want:
            hits.append({'oid': oid, 'target': want[h]})
    res[repo] = {'objects': len(lines), 'size_candidates': len(cands), 'hits': hits}
print(json.dumps(res, ensure_ascii=False, indent=1))
