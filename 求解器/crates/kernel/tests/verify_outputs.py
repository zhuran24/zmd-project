#!/usr/bin/env python3
"""内核输出§3：重新读取落盘记录，核来源、schema、完整差分、增量与篡改反例。"""
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / '数据/样例'))
import check_examples as checker
from check_golden_trace import run
from runtime_record import same, validate_event_identity, validate_state
from checkpoint_delta import decode_trace, encode_trace
from test_runtime_input import validate_schema
from runtime_example import input_path, projection_path, validate_profile
from coverage_audit import expected_coverage


def expected_fingerprints(data, golden_match):
    """内核输出§1：从真实输入与内核入口重建依赖闭包，不信任记录自报的路径集合。"""
    source = input_path(data).resolve()
    catalog_path = (source.parent / data['catalog']['path']).resolve()
    catalog = checker.load_json(catalog_path)
    paths = [('input', source), ('profile', ROOT / '规格/内核配置-v1.json'), ('catalog', catalog_path)]
    paths += [('formal_source', catalog_path.parent / catalog.get('source_root', '.') / row['path'])
              for row in catalog['sources']]
    paths += [('axis_registry', source.parent / data['parameters']['axis_registry']['path']),
              ('profile', ROOT / '规格/受限模型声明.md')]
    paths += [('semantics', ROOT / '规格' / name) for name in
              ('受限转移定义.md', '运行语义.md', '内核输入.md', '内核输出.md')]
    paths.append(('schema', ROOT / '规格/内核输出.schema.json'))
    paths += [('checker', ROOT / 'crates/kernel/src' / name) for name in
              ('value.rs', 'config.rs', 'model.rs', 'catalog.rs', 'input.rs', 'interfaces.rs',
               'engine.rs', 'event_identity.rs', 'warehouse.rs', 'polling.rs', 'transition.rs',
               'output.rs', 'ledger.rs', 'cycle.rs', 'cycle_io.rs', 'digest.rs', 'seed.rs', 'cache.rs', 'lib.rs', 'main.rs')]
    paths += [('checker', ROOT / name) for name in ('Cargo.toml', 'Cargo.lock', 'crates/kernel/Cargo.toml')]
    paths.append(('parameter_projection', projection_path(data)))
    if golden_match:
        paths += [('golden', ROOT / '数据/样例' / name) for name in
                  ('混做粉碎机两下游-黄金轨迹.json', '混做粉碎机两下游-黄金轨迹.md')]
    result, seen = [], set()
    for role, path in paths:
        path = path.resolve()
        if (role, path) not in seen:
            seen.add((role, path))
            result.append({'role': role, 'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return result


def expected_scope(data, ticks):
    """内核输出§3：区间、批数及黄金匹配来自完整重算，逐字段和JSON类型比较。"""
    golden_match = data['scenario']['name'] == '混做粉碎机两下游' and len(ticks) == 4
    if golden_match:
        golden = checker.load_json(ROOT / '数据/样例/混做粉碎机两下游-黄金轨迹.json')
        assert same([t['summary'] for t in ticks], golden['ticks'])
    completed = sum(e['operation'] == 'manufacture_complete' for t in ticks for e in t['events'])
    return {'kind': 'finite_trace', 'from': ticks[0]['time'], 'through': ticks[-1]['time'],
            'golden_match': golden_match, 'initial_history': 'conditional_witness',
            'universal_parameters': False, 'all_reachable_cycles': False, 'target_certified': False,
            'manufacturing_cycles_completed': {'value': str(completed), 'category': '算术推论'}}


def canonical_record_paths(record, base):
    """输出§1：验证原始来源字节，仅规范记录所属的路径，不改参数或轨迹。"""
    canonical = copy.deepcopy(record)
    try:
        for row in canonical['fingerprints']:
            path = (base / row['path']).resolve(strict=True)
            assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256'], ('来源指纹不符', str(path))
            row['path'] = str(path)
        canonical['producer']['path'] = str((base / canonical['producer']['path']).resolve(strict=True))
    except OSError as error:
        raise AssertionError(('来源或producer路径不可访问', str(error))) from error
    return canonical


def verify(path, data, expected):
    """内核输出§1–§3：类型、事件身份、容量、指纹和所有轨迹字段同时核验。"""
    record = checker.load_json(path)
    schema = checker.load_json(ROOT / '规格/内核输出.schema.json')
    validate_schema(record, schema, schema)
    record = canonical_record_paths(record, path.parent)
    assert same(record['producer'], {
        'kind': 'kernel', 'path': str((ROOT / 'crates/kernel/src/lib.rs').resolve()),
        'claim': 'Rust 受限内核的有限条件轨迹；不作全称或完整目标认证'}), 'producer身份不符'
    assert record['status'] == 'completed'
    assert record['execution_mode']=='finite_concrete' and record['port_meeting']=='shared_edge_opposite'
    config = checker.load_json(ROOT / '规格/内核配置-v1.json')
    assert record['profile_id'] == data['parameters']['profile_id'] == config['profile_id'], 'profile身份不符'
    assert record['run_id'] == f"kernel:{input_path(data).stem}:{expected[0]['time']['value']['value']}:{len(expected)}", 'run_id不符'
    assert same(record['open_items'], ['有限轨迹不证明全称参数、初态可达性、全部可达循环或目标。',
                                      '规格疑问见 求解器/规格/内核实现-对规格的疑问.md。']), '未决范围声明不符'
    assert same(data, checker.load_json(input_path(data))), '输入对象与真实来源文件不同'
    validate_profile(data, checker.load_json(projection_path(data)))
    assert same(record['parameter_assignment'], data['parameters'])
    assert same(record['input_history'], {**{k: data[k] for k in ('timeline', 'construction', 'debug_operations', 'environment')}, 'reachability': data['initial_state']['reachability']})
    scope = expected_scope(data, expected)
    assert same(record['fingerprints'], expected_fingerprints(data, scope['golden_match'])), '来源清单不闭合'
    trace = decode_trace(record['trace'])
    if record['trace']['format'] == 'checkpoint_delta':
        assert same(record['trace'], encode_trace(trace, record['trace']['checkpoint_interval']))
    assert same(trace['start_state'], data['initial_state']['nonwarehouse']['value'])
    assert same(trace['ticks'], expected), path
    assert same(trace['end_time'], expected[-1]['time'])
    validate_event_identity(data['timeline'], trace['start_state'], trace['ticks'])
    validate_state(data, trace['start_state'])
    for tick in trace['ticks']:
        validate_state(data, tick['state'])
    statuses = {}
    for row in record['uncovered_axes']:
        statuses[row['coverage_status']] = statuses.get(row['coverage_status'], 0) + 1
    actual_axes = {r['axis']: r for r in record['uncovered_axes']}
    assert len(record['uncovered_axes']) == len(actual_axes), '覆盖轴重复'
    assert same(actual_axes, expected_coverage(data, expected, ROOT)), '覆盖轴全集/处置/实际证据不符'
    assert same(record['validation_scope'], scope), '验证范围与完整重算不符'
    return {'path': str(path), 'ticks': len(expected), 'events': sum(len(t['events']) for t in expected), 'coverage_status_counts': statuses, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    """第四轮§4.7：双样例双编码重算后输出可重复的验收证据。"""
    reports = []
    for name in ('混做粉碎机两下游', '分流器三路轮询'):
        data = checker.load_json(ROOT / f'数据/样例/{name}.json')
        expected = run(data)
        for suffix in ('运行记录-v3-kernel', '运行记录-checkpoint_delta-v3-kernel'):
            reports.append(verify(ROOT / f'数据/样例/{name}-{suffix}.json', data, expected))
    baseline = checker.load_json(ROOT / 'crates/kernel/evidence/round5/protected-baseline.json')
    changes = [p for p, h in baseline.items() if hashlib.sha256(Path(p).read_bytes()).hexdigest() != h]
    assert not changes, changes
    result = {'status': '通过', 'records': reports, 'read_only_baseline_files': len(baseline), 'baseline_changes': changes}
    (ROOT / 'crates/kernel/evidence/round5/record-validation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
