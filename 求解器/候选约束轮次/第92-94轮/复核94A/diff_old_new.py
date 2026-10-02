#!/usr/bin/env python3
"""复核94A：逐条比对候选正文与快照正式条文（字符级差异）。
只读：前提快照/求解约束.txt、推导92A/candidates.json（只读数据，不导入其脚本）。
输出：diff_old_new.json
"""
import difflib, json, hashlib, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
snap = (ROOT / '前提快照' / '求解约束.txt').read_text(encoding='utf-8').splitlines()
cands = json.loads((ROOT / '推导92A' / 'candidates.json').read_text(encoding='utf-8'))

def old_entry(name):
    for i, line in enumerate(snap):
        if line.startswith(name + '：'):
            return i + 1, line[len(name) + 1:]
    return None, None

out = []
for c in cands:
    ln, old = old_entry(c['name'])
    new = c['text']
    rec = dict(name=c['name'], old_line=ln, sha_new=hashlib.sha256(new.encode()).hexdigest()[:16])
    if old is None:
        rec['old'] = None
        rec['ops'] = []
    else:
        sm = difflib.SequenceMatcher(None, old, new, autojunk=False)
        ops = []
        for tag, i1, i2, j1, j2 in sm.get_opcodes():
            if tag != 'equal':
                ops.append(dict(tag=tag, old=old[i1:i2], new=new[j1:j2]))
        rec['ratio'] = round(sm.ratio(), 3)
        rec['ops'] = ops
    out.append(rec)

(pathlib.Path(__file__).parent / 'diff_old_new.json').write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding='utf-8')
for r in out:
    print(r['name'], r.get('old_line'), r.get('ratio'), len(r['ops']))
