#!/usr/bin/env python3
"""第五轮校验器复核的定向反例和证据核对；全部输出留在本证据目录。"""
import copy
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
SNAPSHOT = HERE / '被审快照'
SOLVER = SNAPSHOT / '求解器'
ENV = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'TMPDIR': str(HERE / 'tmp')}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def run(name, command):
    result = subprocess.run(command, capture_output=True, env=ENV)
    (HERE / (name + '.stdout.log')).write_bytes(result.stdout)
    (HERE / (name + '.stderr.log')).write_bytes(result.stderr)
    return result


def report_counts(text):
    return {name: int(count) for name, count in re.findall(r'^## (.+?)（(\d+) 项', text, re.M)}


def audit_manifest(rows):
    return {'count': len(rows), 'mismatches': [row['path'] for row in rows
            if not Path(row['path']).is_file() or digest(Path(row['path'])) != row['sha256']]}


def main():
    candidate = json.loads((SOLVER / '数据/候选B/contract.json').read_text())
    catalog = json.loads((SOLVER / '数据/正式静态目录.json').read_text())
    gate = SOLVER / '数据/工具/formal_catalog.py'
    baseline = run('目录回源', [sys.executable, '-B', str(gate)])
    assert baseline.returncode == 0
    results = {'catalog_baseline_exit': baseline.returncode, 'catalog_mutations': [],
               'contract_mutations': []}

    # 四个上轮反例直接回源；不靠候选守恒是否失败来判目录正确性。
    cases = [
        ('unused_recipe_duration', 'recipes', '精炼-蓝铁粉末', ['duration', 'value'], '2'),
        ('used_recipe_input', 'recipes', '研磨-致密蓝铁', ['inputs', '蓝铁粉末', 'value'], '3'),
        ('power_coverage_width', 'units', '供电桩', ['coverage', 'width', 'value'], '13'),
        ('core_port_category', 'units', '协议核心', ['ports', 'input_count', 'category'], '候选'),
    ]
    for name, section, identity, fields, replacement in cases:
        changed = copy.deepcopy(catalog)
        field = next(row for row in changed[section] if row['id'] == identity)
        for key in fields[:-1]:
            field = field[key]
        field[fields[-1]] = replacement
        path = HERE / (name + '.json')
        dump(path, changed)
        result = run(name, [sys.executable, '-B', str(gate), '--catalog', str(path)])
        expected = '.'.join([section, identity, *fields])
        assert result.returncode == 1 and expected in result.stderr.decode()
        results['catalog_mutations'].append({'name': name, 'exit_code': result.returncode,
                                            'diagnostic': result.stderr.decode().strip()})

    # 不依赖 Rust 自带测试的断言：直接调用实际 CLI 并核报告中的具体失败项。
    mutations = [
        ('overload_exact', '端口速率/记录/', lambda c: c['logical_feeds'][0]['planned_rate'].update(
            value='100000000000000000000000000000000000001/100000000000000000000000000000000000000')),
        ('local_balance', '逐机配方守恒/', lambda c: c['logical_feeds'][0]['planned_rate'].update(value='19/20')),
        ('nonore_full_speed', '满速独占/计划标记/', lambda c: next(e for e in c['logical_feeds']
            if e['source'].startswith('M') and e['planned_full_speed']).update(planned_full_speed=False)),
        ('fake_actual_certificate', '契约/实际速率/', lambda c: c['logical_feeds'][0].update(
            proven_actual_rate={'value': '1', 'category': '实测'})),
        ('false_target', '目标/精选荞愈胶囊', lambda c: c['targets']['精选荞愈胶囊'].update(value='3/5')),
        ('false_numeric_category', '契约/数字类别', lambda c: c['source_domain']['left'].update(category='候选')),
        ('missing_same_item_obligation', '契约/多料栏/M152', lambda c: next(m for m in c['machines']
            if m['id'] == 'M152').update(multi_material=None)),
        ('false_fanout_certificate', '扇出/计划分类/', lambda c: c['fanouts'][0].update(certification='已认证')),
        ('unsupported_merger', '契约/运输占位/', lambda c: c['logical_feeds'][0]['via'].update(merger=True)),
    ]
    for name, expected, mutate in mutations:
        changed = copy.deepcopy(candidate)
        mutate(changed)
        path = HERE / (name + '.json')
        dump(path, changed)
        result = run(name, [str(HERE / 'target/debug/topology'), str(path)])
        text = result.stdout.decode()
        failures = text.split('## 能检且不通过', 1)[1].split('## 不能静态检', 1)[0]
        assert result.returncode == 1 and expected in failures
        results['contract_mutations'].append({'name': name, 'exit_code': result.returncode,
                                              'expected_failure_prefix': expected, 'counts': report_counts(text)})

    for name, replacement in [('decimal_string', '1.00000000000000000001'), ('json_float', 0.6),
                               ('zero_denominator', '1/0'), ('negative_denominator', '1/-2')]:
        changed = copy.deepcopy(candidate)
        changed['logical_feeds'][0]['planned_rate']['value'] = replacement
        path = HERE / (name + '.json')
        dump(path, changed)
        result = run(name, [str(HERE / 'target/debug/topology'), str(path)])
        assert result.returncode == 2
        results['contract_mutations'].append({'name': name, 'exit_code': result.returncode,
                                              'diagnostic': result.stderr.decode().strip()})

    data = REPO / '求解器/数据'
    results['reviewed_files'] = audit_manifest(json.loads((HERE / '被审指纹.json').read_text()))
    results['delivery_manifest'] = audit_manifest(json.loads((data / '候选B/交付哈希.json').read_text()))
    for name in ['只读文件指纹', '验证依赖指纹']:
        raw = json.loads((data / '修订验证/r4' / (name + '.json')).read_text())
        raw = raw.get('fingerprints', raw)
        results[name] = audit_manifest([{'path': path, 'sha256': value} for path, value in raw.items()])
    current_report = (HERE / '候选B-独立校验报告.md').read_bytes()
    results['candidate'] = {'counts': report_counts(current_report.decode()),
                            'same_report_bytes': current_report == (data / '候选B/校验报告.md').read_bytes(),
                            'report_sha256': hashlib.sha256(current_report).hexdigest()}
    trace = json.loads((data / '修订验证/r4/黄金轨迹运行记录.json').read_text())
    results['existing_trace'] = {key: trace[key] for key in ['producer', 'status', 'validation_scope', 'open_items']}
    results['existing_trace']['trace_length'] = len(trace['trace'])
    results['existing_trace']['same_bytes_as_shared_report'] = (
        (data / '修订验证/r4/黄金轨迹运行记录.json').read_bytes()
        == (data / '样例/混做粉碎机两下游-运行记录.json').read_bytes())
    results['existing_runtime_regression_same_bytes'] = (
        (data / '修订验证/r4/运行输入回归结果.json').read_bytes()
        == (REPO / '求解器/规格/内核输入修订验证-r3/运行回归结果.json').read_bytes())
    dump(HERE / '独立复核结果.json', results)
    print(json.dumps({key: results[key] for key in ['catalog_baseline_exit', 'candidate',
        'reviewed_files', 'delivery_manifest', '只读文件指纹', '验证依赖指纹']}, ensure_ascii=False))
    print('四个目录反例和十三个契约反例均按预期拒绝。')


if __name__ == '__main__':
    main()
