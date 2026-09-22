#!/usr/bin/env python3
"""第四轮第二否证席的只读基线核验和隔离反例。"""
import copy
import hashlib
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path('/home/zhuran24/zmd-research-fresh')
OUT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    assert path.resolve().is_relative_to(OUT)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def rename(value, old, new):
    # 仅替换恰好相等的字符串值，不替换说明文本中的子串。
    if isinstance(value, dict):
        return {key: rename(child, old, new) for key, child in value.items()}
    if isinstance(value, list):
        return [rename(child, old, new) for child in value]
    return new if value == old else value


def changes(left, right, path='$'):
    if isinstance(left, dict):
        assert set(left) == set(right)
        return [row for key in left for row in changes(left[key], right[key], path + '.' + key)]
    if isinstance(left, list):
        assert len(left) == len(right)
        return [row for index, (a, b) in enumerate(zip(left, right)) for row in changes(a, b, f'{path}[{index}]')]
    return [] if left == right else [{'path': path, 'before': left, 'after': right}]


def isolated_run(root):
    sys.path.insert(0, str(root / '求解器/数据/样例'))
    import check_golden_trace as golden
    import runtime_example as example
    import runtime_record as record
    import test_runtime_input as tests
    checker = golden.checker
    data = checker.load_json(golden.INPUT)
    example.write_profile(data)
    # 使用原生成入口真实落盘，再独立读取并完整重算验收。
    golden.main()
    output = checker.load_json(golden.OUTPUT)
    accepted = record.validate_record(output, data)
    schema = checker.load_json(root / '求解器/规格/内核输出.schema.json')
    tests.validate_schema(output, schema, schema)
    historical = {row['id']: row for row in output['input_history']['timeline']['events']}
    collisions = [{'history': historical[event['event']], 'runtime': event}
                  for tick in output['trace']['ticks'] for event in tick['events']
                  if event['event'] in historical]
    dependencies = [{'path': row['path'], 'match': digest(Path(row['path'])) == row['sha256']}
                    for row in output['fingerprints']]
    assert collisions and all(row['match'] for row in dependencies)
    save(root / '隔离验收结果.json', {'validate_record': accepted, 'schema_check': True,
        'collisions': collisions, 'dependencies': dependencies,
        'output_sha256': digest(golden.OUTPUT)})


def main():
    sys.path.insert(0, str(ROOT / '求解器/数据/样例'))
    import check_golden_trace as golden
    import runtime_record as record
    import test_runtime_input as tests
    from event_order import order_at
    from runtime_example import time_value
    checker = golden.checker
    manifest_path = ROOT / '求解器/规格/内核输入修订验证-r3/交付清单.json'
    manifest = checker.load_json(manifest_path)
    files = {Path(row['path']) for row in record.fingerprints()}
    files.update(Path(path) for path in manifest['files'])
    files.update(ROOT / path for path in [
        '求解器/规格/内核配置-v1.json', '求解器/规格/选择点清单.md',
        '求解器/规格/规则覆盖表.md', '求解器/规格/四件前置义务对照.md',
        '求解器/规格/参数轴-对内核输入请求的答复.md',
        '求解器/规格/复核/内核输入/复核-r4-覆盖.md',
        '求解器/规格/复核/内核输入/复核-r4-一致性.md'])
    before = {str(path): digest(path) for path in sorted(files)}
    save(OUT / '起点指纹.json', before)
    for path in files:
        target = OUT / '被核快照' / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    data = checker.load_json(golden.INPUT)
    base_ticks = golden.run(data)
    baseline = checker.load_json(golden.OUTPUT)
    assert record.validate_record(baseline, data)
    schema = checker.load_json(ROOT / '求解器/规格/内核输出.schema.json')
    tests.validate_schema(baseline, schema, schema)
    result = {'baseline': {'record_accepted': True, 'schema_check': True,
        'summaries': [row['summary'] for row in base_ticks],
        'fingerprint_count': len(baseline['fingerprints'])}}

    # 仓库标签碰撞：所有其它输入字段保持原样。
    altered = rename(data, 'warehouse_0', 'crusher:input:0')
    save(OUT / '仓库标签碰撞输入.json', altered)
    delta = changes(data, altered)
    assert all(row['before'] == 'warehouse_0' and row['after'] == 'crusher:input:0' for row in delta)
    checked = checker.check(altered, golden.INPUT)
    ticks = golden.run(altered)
    observed = []
    for tick in ticks:
        state = tick['state']
        inventory = {row['slot']: row['contents'] for row in state['inventory']}
        warehouse = next(row for row in state['warehouse']['slots'] if row['item'] == '源矿')
        observed.append({'time': tick['time'], 'warehouse_ore': checker.quantity(warehouse['quantity']),
            'crusher_input': inventory['crusher:input:0'], 'crusher_buffer': inventory['crusher:buffer:0']})
    withdrawals = [move for tick in ticks for move in tick['state']['semantic_context']['tick_context']['value']['movements']
                   if move['channel'].startswith('PC|ore_source:')]
    try:
        record.build_record(altered, ticks, checker.load_json(golden.GOLDEN))
    except checker.CheckError as error:
        rejected = str(error)
    else:
        raise AssertionError('原黄金摘要意外放过仓库变体')
    result['warehouse_collision'] = {'check': checked, 'changes': delta, 'states': observed,
        'actual_withdrawals': len(withdrawals), 'golden_rejection': rejected}
    save(OUT / '仓库碰撞完整轨迹.json', ticks)

    # 事件碰撞：复制最小依赖树，在副本中运行未经修改的源码。
    isolated = OUT / '事件碰撞隔离副本'
    dependencies = {Path(row['path']) for row in record.fingerprints()}
    dependencies.add(ROOT / '求解器/规格/内核配置-v1.json')
    for path in dependencies:
        target = isolated / path.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(path.read_bytes())
    altered = rename(data, 'build_13', 'J|0|0|0')
    delta = changes(data, altered)
    assert all(row['before'] == 'build_13' and row['after'] == 'J|0|0|0' for row in delta)
    save(isolated / '求解器/数据/样例/混做粉碎机两下游.json', altered)
    run = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--isolated', str(isolated)],
                         cwd=isolated, capture_output=True, text=True)
    (OUT / '事件碰撞隔离运行.log').write_text(run.stdout + run.stderr)
    assert run.returncode == 0, run.stderr
    result['event_collision'] = {'changes': delta, 'process_returncode': run.returncode,
        'validation': checker.load_json(isolated / '隔离验收结果.json')}

    # 完整不可表示性由报告的代数论证给出；选点仅核对求值实现。
    ab = [{'operation': 'transfer', 'target': target} for target in ('box_a', 'box_b')]
    ba = list(reversed(ab))
    def desired(n):
        return ba if n > 0 and n & (n - 1) == 0 else ab
    value = {'schema': 'event-order-v2', 'scope': 'per_instant', 'template_order': ab,
             'repeat_embedding': 'scan_round_then_template',
             'schedule': {'kind': 'finite_table', 'entries': [
                 {'instant': time_value(5 * n), 'template_order': desired(n)} for n in range(65)]}}
    assert all(order_at(value, time_value(5 * n)) == desired(n) for n in range(65))
    try:
        order_at(value, time_value(325))
    except checker.CheckError as error:
        finite_error = str(error)
    else:
        raise AssertionError('有限表耗尽未拒绝')
    probes = []
    for width, origin, orders in [(Fraction(5), Fraction(0), [ab, ba]),
                                  (Fraction(7, 3), Fraction(-2, 7), [ab, ba, ab]),
                                  (Fraction(13, 17), Fraction(3, 2), [ab, ba, ba, ab])]:
        value['schedule'] = {'kind': 'periodic', 'origin': time_value(origin),
                             'slot_width': time_value(width), 'orders': orders}
        period = width.numerator * len(orders)
        n = 1 << period.bit_length()
        first = order_at(value, time_value(5 * n))
        second = order_at(value, time_value(5 * (n + period)))
        assert first == second and desired(n) != desired(n + period)
        probes.append({'width': str(width), 'origin': str(origin), 'slot_count': len(orders),
            'Q': period, 'n': n, 'encoded_same': True, 'required_same': False})
    result['order_coverage'] = {'finite_table_t325': finite_error,
        'desired_prefix': ['BA' if desired(n) == ba else 'AB' for n in range(9)], 'periodic_probes': probes}

    declared = manifest['sha256']
    rows = [{'path': path, 'declared': sha, 'actual': digest(Path(path)),
             'match': sha == digest(Path(path))} for path, sha in declared.items()]
    result['manifest'] = {'file_count': len(manifest['files']), 'hash_count': len(rows),
        'mismatches': [row for row in rows if not row['match']], 'matches': sum(row['match'] for row in rows)}
    after = {path: digest(Path(path)) for path in before}
    result['source_changes'] = [path for path in before if before[path] != after[path]]
    assert result['source_changes'] == []
    save(OUT / '终点指纹.json', after)
    save(OUT / '独立核验结果.json', result)
    print(json.dumps({'baseline_accepted': True, 'warehouse_withdrawals': len(withdrawals),
        'warehouse_final': observed[-1]['warehouse_ore'], 'event_collision_accepted': True,
        'manifest_mismatches': len(result['manifest']['mismatches']), 'source_changes': []}, ensure_ascii=False))


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == '--isolated':
        isolated_run(Path(sys.argv[2]))
    else:
        main()
