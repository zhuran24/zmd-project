#!/usr/bin/env python3
"""复算正式投影及当前引用，单列旧版负例；只写本轮审计结果。"""
from pathlib import Path
import ast
import copy
import hashlib
import json
import re
import subprocess
import sys
from run_step import ROOT, OUT, digest, save

sys.path.insert(0, str(ROOT / '数据/工具'))
from formal_catalog import formal_projection, source_snapshot, verify

path = ROOT / '数据/正式静态目录.json'
before = json.loads(subprocess.check_output(['git', 'show', 'HEAD:求解器/数据/正式静态目录.json'], cwd=ROOT))
catalog = json.loads(path.read_text())
rebuilt = copy.deepcopy(before)
rebuilt['sources'] = source_snapshot()
projection = formal_projection(rebuilt['sources'])
rebuilt['constraints'] = projection['constraints']
rebuilt['static_checks'] = projection['static_checks']
rebuilt['version'] = '2026-09-22-r23-constraints-72'
verify(rebuilt)
serialized = (json.dumps(rebuilt, ensure_ascii=False, indent=2) + '\n').encode()
assert serialized == path.read_bytes(), '上一席目录与独立重建字节不一致'
assert catalog['task'] == projection['task'] == before['task']
assert catalog['units'] == before['units'] and catalog['recipes'] == before['recipes']
assert set(before['static_checks']['constants']) - set(catalog['static_checks']['constants']) == {'plant_trigger'}
assert {key: value for key, value in before['static_checks']['constants'].items() if key != 'plant_trigger'} == catalog['static_checks']['constants']
assert before['static_checks']['material_flow'] == catalog['static_checks']['material_flow']
assert len(catalog['constraints']) == 72 and len(catalog['static_checks']['constants']) == 32
old_rules = {rule['name']: rule for rule in before['constraints']}
changed_rules = [rule['name'] for rule in catalog['constraints']
                 if rule['name'] not in old_rules or any(rule[key] != old_rules[rule['name']][key] for key in ['text', 'basis'])]
assert set(changed_rules) == {'矿系不入库', '非成品零入库', '回路守恒', '回路存量', '植株半分', '1113 位置'}
source_hashes = {entry['path']: entry['sha256'] for entry in rebuilt['sources']}
tree = ast.parse((ROOT / '数据/样例/check_examples.py').read_text())
locked_sources = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(target, ast.Name) and target.id == 'SOURCE_HASHES' for target in node.targets))
assert source_hashes == locked_sources
inputs = []
for base in [ROOT / '数据/样例', ROOT / 'crates/kernel/tests/fixtures']:
    for p in sorted(base.rglob('*.json')):
        document = json.loads(p.read_text())
        schema = document.get('schema') if isinstance(document, dict) else None
        refs = []
        if schema in ['kernel-input-v2', 'kernel-input-v3']:
            refs = [('catalog', document['catalog']), ('axis_registry', document['parameters']['axis_registry'])]
        elif schema == 'profile-assignment-v2':
            refs = [(key, document[key]) for key in ['profile_source', 'configuration_source', 'axis_source']]
        if not refs:
            continue
        mismatches = []
        for label, ref in refs:
            actual = digest((p.parent / ref['path']).resolve())
            if actual != ref['sha256']:
                mismatches.append({'reference': label, 'expected': actual, 'actual': ref['sha256']})
        inputs.append({'path': str(p.relative_to(ROOT)), 'schema': schema, 'mismatches': mismatches})
assert not any(row['mismatches'] for row in inputs), inputs

sources = json.loads((ROOT / '数据/候选B/来源清单.json').read_text())
for ref in sources:
    assert digest(Path(ref['path'])) == ref['sha256'], ref

for relative in ['数据/规则覆盖表.md', '规格/规则覆盖表.md']:
    sections = (ROOT / relative).read_text().split('## ')
    for index, source in enumerate(catalog['sources'][:2], 1):
        rows = [line.split('|')[1:-1] for line in sections[index].splitlines() if re.match(r'^\| \d+ \|', line)]
        assert len(rows) == len(source['lines'])
        for number, (row, line) in enumerate(zip(rows, source['lines']), 1):
            assert int(row[0]) == number and row[1].strip() == (line.strip() or '（空行）')
    if relative.startswith('数据'):
        rows = [line for line in sections[3].splitlines() if '`constraints[' in line]
        assert len(rows) == 72
        for index, (row, rule) in enumerate(zip(rows, catalog['constraints'])):
            assert f'`constraints[{index}]`' in row and rule['name'] in row
            assert f"据行 {rule['basis_line']} 完整转录" in row
    else:
        rows = [line.split('|')[1:-1] for line in sections[3].splitlines() if re.match(r'^\| \d+ \|', line)]
        assert len(rows) == 72
        for index, (row, rule) in enumerate(zip(rows, catalog['constraints']), 1):
            assert int(row[0]) == index and row[1].strip() == rule['source_line'] and row[2].strip() == '约束·' + rule['name']
report = (ROOT / '数据/候选B/校验报告.md').read_bytes()
assert report == (OUT / 'candidate-b.log').read_bytes(), '候选报告与本次实际输出不同'
report = report.decode()
for rule in catalog['constraints']:
    assert '正式条目/' + rule['name'] in report and rule['basis'] in report
assert '目录/阈值/plant_trigger' not in report and '能检且不通过（0 项' in report
assert digest(path) in (ROOT / '规格/修订记录.md').read_text()
for source in catalog['sources']:
    assert source['sha256'] in (ROOT / '规格/运行语义.md').read_text()
for relative in ['构造/第一张全厂候选/检查器A/projections.py', '构造/第一张全厂候选/生成/代码/检查器甲.py', '构造/第一张全厂候选/生成/代码/检查器乙.py']:
    ast.parse((ROOT / relative).read_text(), filename=relative)

changed_inputs = []
changed = subprocess.check_output(['git', 'diff', '--name-only', '-z', '--', '数据/样例', 'crates/kernel/tests/fixtures'], cwd=ROOT).decode().split('\0')
for name in filter(None, changed):
    if not name.endswith('.json'):
        continue
    previous = json.loads(subprocess.check_output(['git', 'show', 'HEAD:' + name], cwd=ROOT))
    current = json.loads((ROOT.parent / name).read_text())
    if current['schema'] in ['kernel-input-v2', 'kernel-input-v3']:
        previous['catalog']['sha256'] = current['catalog']['sha256']
        previous['parameters']['axis_registry']['sha256'] = current['parameters']['axis_registry']['sha256']
    else:
        assert current['schema'] == 'profile-assignment-v2', name
        for key in ['profile_source', 'configuration_source', 'axis_source']:
            previous[key]['sha256'] = current[key]['sha256']
    assert previous == current, name
    changed_inputs.append(name)

summary = {'status': 'pass', 'version': rebuilt['version'], 'catalog_sha256': hashlib.sha256(serialized).hexdigest(),
           'independently_rebuilt_from_HEAD_bytes_equal': True, 'constraints_before': len(before['constraints']),
           'constraints_after': len(rebuilt['constraints']), 'constants_before': len(before['static_checks']['constants']),
           'constants_after': len(rebuilt['static_checks']['constants']),
           'unchanged': ['task', 'units', 'recipes', 'material_flow', 'other_constants'],
           'source_hashes': source_hashes, 'source_hashes_checker_matches': True,
           'changed_rules': changed_rules, 'coverage_tables': '114/16/72逐行一致',
           'candidate_report_byte_equal': True, 'catalog_revision_record_matches': True,
           'inputs': inputs, 'changed_inputs_only_reference_sha': changed_inputs, 'candidate_source_count': len(sources)}
save(OUT / 'sync-audit.json', summary)
print(json.dumps({key: value for key, value in summary.items() if key not in ['inputs', 'changed_inputs_only_reference_sha']}, ensure_ascii=False, indent=2))
print('references checked:', len(inputs), 'changed inputs:', len(changed_inputs))
