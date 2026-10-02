#!/usr/bin/env python3
"""记录本席读入材料与输出文件的 SHA-256。"""
import hashlib, json, os, glob
here = os.path.dirname(os.path.abspath(__file__))
rnd = os.path.dirname(here)
files = sorted(glob.glob(os.path.join(rnd, '前提快照', '*'))) + [os.path.join(rnd, '临时规则.md'), os.path.join(rnd, '推导95G.md'),
         os.path.join(rnd, '推导95G', 'geometry_a.json'), os.path.join(rnd, '推导95G', 'geometry_b.json')]
files += sorted(glob.glob(os.path.join(here, '*.py'))) + sorted(glob.glob(os.path.join(here, '*.json')))
out = {}
for f in files:
    if f.endswith('manifest.json'):
        continue
    out[os.path.relpath(f, rnd)] = hashlib.sha256(open(f, 'rb').read()).hexdigest()
json.dump(out, open(os.path.join(here, 'manifest.json'), 'w'), ensure_ascii=False, indent=1)
print(len(out))
