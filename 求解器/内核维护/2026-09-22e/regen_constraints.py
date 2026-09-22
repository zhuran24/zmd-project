#!/usr/bin/env python3
"""按当前三源重建完整约束/静态投影；其他投影必须保持不变。"""
from pathlib import Path
import hashlib, json, sys
R = Path(__file__).resolve().parents[2]
O = Path(__file__).resolve().parent
sys.path.insert(0, str(R/'数据/工具'))
from formal_catalog import source_snapshot, formal_projection, verify
p = R/'数据/正式静态目录.json'
d = json.loads(p.read_text())
before = json.loads(p.read_text())
old_sha = hashlib.sha256(p.read_bytes()).hexdigest()
assert old_sha == '6e609fbab15104489f7e00a03c64b3f89cd77668de26789622d78be27a0ee3ff'
d['sources'] = source_snapshot()
proj = formal_projection(d['sources'])
for key in ['constraints', 'static_checks']:
    d[key] = proj[key]
d['version'] = '2026-09-22-r23-constraints-72'
assert d['task'] == proj['task']
assert set(before['static_checks']['constants']) - set(d['static_checks']['constants']) == {'plant_trigger'}
assert {k:v for k,v in before['static_checks']['constants'].items() if k != 'plant_trigger'} == d['static_checks']['constants']
assert before['static_checks']['material_flow'] == d['static_checks']['material_flow']
verify(d)
p.write_text(json.dumps(d, ensure_ascii=False, indent=2)+'\n')
verify(json.loads(p.read_text()))
summary = {'version': d['version'], 'old_sha256': old_sha, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest(), 'constraints_before':len(before['constraints']), 'constraints_after':len(d['constraints']), 'constants_before':len(before['static_checks']['constants']), 'constants_after':len(d['static_checks']['constants']), 'unchanged':['task', 'units', 'recipes', 'material_flow', 'other_constants'], 'verify':'pass'}
(O/'catalog-regeneration.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2))
