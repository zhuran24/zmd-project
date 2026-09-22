#!/usr/bin/env python3
"""在复核目录内复跑工具，记录退出码、门禁诊断及字节对照。"""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

OUT = Path(__file__).resolve().parent
SNAP = OUT / '输入快照'
RUN = OUT / '隔离运行'
SOLVER = RUN / '求解器'
env = {**os.environ, 'CARGO_HOME': str(OUT / 'cargo-home'), 'CARGO_TARGET_DIR': str(OUT / 'cargo-target'), 'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(OUT)}
results = []


def command(label, args, expected=0, stdin=None):
    process = subprocess.run(args, cwd=RUN, env=env, input=stdin, capture_output=True)
    (OUT / (label + '.stdout.log')).write_bytes(process.stdout)
    (OUT / (label + '.stderr.log')).write_bytes(process.stderr)
    results.append({'项目': label, '命令': list(map(str, args)), '退出码': process.returncode, '期望': expected, '正确': process.returncode == expected})
    assert process.returncode == expected, (label, process.stderr.decode()[-2000:])
    return process


catalog_path = SOLVER / '数据/正式静态目录.json'
gate = SOLVER / '数据/工具/formal_catalog.py'
baseline = catalog_path.read_bytes()
command('独立回源命令', [sys.executable, '-B', str(gate)])
command('Python目录负例', [sys.executable, '-B', str(SOLVER / '数据/工具/test_formal_catalog.py'), '-v'])
cases = [
    ('未用配方耗时', 'recipes', '精炼-蓝铁粉末', ['duration', 'value'], '2'),
    ('研磨投入', 'recipes', '研磨-致密蓝铁', ['inputs', '蓝铁粉末', 'value'], '3'),
    ('研磨产出', 'recipes', '研磨-致密蓝铁', ['outputs', '致密蓝铁粉末', 'value'], '2'),
    ('供电宽度', 'units', '供电桩', ['coverage', 'width', 'value'], '13'),
    ('供电高度', 'units', '供电桩', ['coverage', 'height', 'value'], '13'),
    ('核心类别', 'units', '协议核心', ['ports', 'input_count', 'category'], '候选'),
    ('未用配方类别', 'recipes', '精炼-蓝铁粉末', ['duration', 'category'], '候选'),
]
diagnostics = []
for label, section, identity, path, value in cases:
    changed = json.loads(baseline)
    field = next(row for row in changed[section] if row['id'] == identity)
    for key in path[:-1]:
        field = field[key]
    field[path[-1]] = value
    data = (json.dumps(changed, ensure_ascii=False, indent=2) + '\n').encode()
    (OUT / ('门禁变异-' + label + '.json')).write_bytes(data)
    process = command('门禁变异-' + label, [sys.executable, '-B', str(gate), '--catalog', '-'], 1, data)
    expected = f'{section}.{identity}.' + '.'.join(path)
    diagnostic = process.stderr.decode().strip()
    assert expected in diagnostic
    diagnostics.append({'反例': label, '定位': expected, '诊断': diagnostic, '退出码': process.returncode})
process = command('候选CLI', ['cargo', 'run', '--offline', '--locked', '--manifest-path', str(SOLVER / 'Cargo.toml'), '-p', 'topology', '--', str(SOLVER / '数据/候选B/contract.json')])
(OUT / '重生成校验报告.md').write_bytes(process.stdout)
expected = (SNAP / '求解器/数据/候选B/校验报告.md').read_bytes()
assert process.stdout == expected
command('原始设计副本', [sys.executable, '-B', str(RUN / '原始候选B/design.py')])
design_equal = {name: (RUN / '原始候选B' / name).read_bytes() == (SNAP / '原始候选B' / name).read_bytes() for name in ['machines.csv', 'channels.csv', 'fanout.json']}
assert all(design_equal.values())
# 转换器写入的来源清单绝对路径随隔离根改变；契约本体应逐字节相同。
command('转换器副本', [sys.executable, '-B', str(SOLVER / '数据/工具/convert_candidate_b.py')])
assert (SOLVER / '数据/候选B/contract.json').read_bytes() == (SNAP / '求解器/数据/候选B/contract.json').read_bytes()
assert catalog_path.read_bytes() == baseline
result = {'状态': '通过', '命令结果': results, '门禁负例': diagnostics, '原设计输出与原始资产相同': design_equal, 'CLI报告与被审报告字节相同': True, '副本转换契约字节相同': True, '隔离目录数据未变': True, '报告sha256': hashlib.sha256(process.stdout).hexdigest(), '边界': '工具复现用被审实现；独立数值结论来自先行封存的 recompute.py，未借本脚本推导。'}
(OUT / '工具复现结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({k: v for k, v in result.items() if k not in ['命令结果', '门禁负例']}, ensure_ascii=False, indent=2))
