"""第4轮第1席独立复验；只写自身证据目录及其中隔离副本。"""
import copy
import hashlib
import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[4]
SAMPLES = ROOT / '求解器/数据/样例'
SPEC = ROOT / '求解器/规格'
sys.path.insert(0, str(SAMPLES))
import check_examples as checker
import check_golden_trace as trace
import runtime_example as example
import runtime_record as record
import test_runtime_input as regression
import event_order


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def rename(value, old, new):
    if isinstance(value, dict):
        return {key: rename(item, old, new) for key, item in value.items()}
    if isinstance(value, list):
        return [rename(item, old, new) for item in value]
    return new if value == old else value


def main():
    manifest_path = SPEC / '内核输入修订验证-r3/交付清单.json'
    manifest = checker.load_json(manifest_path)
    source_paths = {Path(path) for path in manifest['files']}
    dependencies = record.fingerprints()
    source_paths.update(Path(row['path']) for row in dependencies)
    source_paths.add(ROOT / '候选约束.txt')
    source_paths.update((SPEC / '复核/内核输入' / name) for name in ('复核-r4-覆盖.md', '复核-r4-一致性.md'))
    before = {str(path): digest(path) for path in sorted(source_paths)}
    save(BASE / '读取指纹.json', before)
    for path in sorted(source_paths):
        dest = BASE / '读取快照' / path.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(path.read_bytes())

    data = checker.load_json(trace.INPUT)
    ticks = trace.run(data)
    output = checker.load_json(trace.OUTPUT)
    schema = checker.load_json(SPEC / '内核输出.schema.json')
    record.validate_record(output, data, ticks)
    regression.validate_schema(output, schema, schema)
    results = {'baseline': {'record_accepted': True, 'schema_accepted': True,
               'warehouse_ore': [row['summary']['warehouse_ore'] for row in ticks],
               'dependency_count': len(dependencies),
               'dependency_mismatches': [row for row in output['fingerprints'] if digest(Path(row['path'])) != row['sha256']]}}

    # 只重命名仓库格及其引用，物理条件、参数和黄金摘要保持不变。
    mutated = rename(data, 'warehouse_0', 'crusher:input:0')
    save(BASE / '仓库重名输入.json', mutated)
    checked = checker.check(mutated, trace.INPUT)
    wrong_ticks = trace.run(mutated)
    save(BASE / '仓库重名重算.json', wrong_ticks)
    try:
        record.build_record(mutated, wrong_ticks, checker.load_json(trace.GOLDEN))
    except checker.CheckError as error:
        golden_gate = str(error)
    else:
        golden_gate = '未拒绝'
    results['warehouse_collision'] = {
        'input_check': checked,
        'warehouse_ore': [row['summary']['warehouse_ore'] for row in wrong_ticks],
        'warehouse_loss': 80000 - int(wrong_ticks[-1]['summary']['warehouse_ore']),
        'successful_outbound': sum(move['channel'].startswith('PC|ore_source:')
            for tick in wrong_ticks for move in tick['state']['semantic_context']['tick_context']['value']['movements']),
        'crusher_input_final': next(row['contents'] for row in wrong_ticks[-1]['state']['inventory'] if row['slot'] == 'crusher:input:0'),
        'golden_gate': golden_gate}

    # 真正的磁盘隔离副本；不通过替换读取函数绕过来源绑定。
    isolated = BASE / '事件冲突隔离'
    for row in dependencies:
        source = Path(row['path'])
        dest = isolated / source.relative_to(ROOT)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(source.read_bytes())
    event_input = rename(data, 'build_13', 'J|0|0|0')
    save(isolated / trace.INPUT.relative_to(ROOT), event_input)
    child = r'''
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path('求解器/数据/样例').resolve()))
import check_golden_trace as trace
import runtime_example as example
import runtime_record as record
import test_runtime_input as regression
data=trace.checker.load_json(trace.INPUT)
example.write_profile(data)
trace.main()
output=trace.checker.load_json(trace.OUTPUT)
record.validate_record(output,data)
schema=trace.checker.load_json(Path('求解器/规格/内核输出.schema.json'))
regression.validate_schema(output,schema,schema)
history={row['id']:row for row in output['input_history']['timeline']['events']}
collisions=[{'history':history[event['event']],'runtime':event} for tick in output['trace']['ticks'] for event in tick['events'] if event['event'] in history]
print(json.dumps({'disk_record_accepted':True,'schema_accepted':True,'collisions':collisions,'dependency_mismatches':[row for row in output['fingerprints'] if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()!=row['sha256']]},ensure_ascii=False))
'''
    proc = subprocess.run([sys.executable, '-B', '-c', child], cwd=isolated, text=True, capture_output=True)
    (BASE / '事件冲突隔离.log').write_text(proc.stdout + proc.stderr)
    results['event_collision'] = {'exit_code': proc.returncode}
    if proc.returncode == 0:
        results['event_collision'].update(json.loads(proc.stdout.splitlines()[-1]))
    else:
        results['event_collision']['error'] = proc.stderr

    # 有限探针仅检查实现；不可表示的全称证明写在报告内。
    ab = [{'operation': 'transfer', 'target': 'box_a'}, {'operation': 'transfer', 'target': 'box_b'}]
    ba = list(reversed(ab))
    def wanted(number):
        return ba if number > 0 and number & (number - 1) == 0 else ab
    order = {'schema': 'event-order-v2', 'scope': 'per_instant', 'template_order': ab,
             'repeat_embedding': 'scan_round_then_template',
             'schedule': {'kind': 'finite_table', 'entries': [
                 {'instant': example.time_value(5 * number), 'template_order': wanted(number)} for number in range(65)]}}
    assert all(event_order.order_at(order, example.time_value(5 * number)) == wanted(number) for number in range(65))
    try:
        event_order.order_at(order, example.time_value(325))
    except checker.CheckError as error:
        finite_error = str(error)
    else:
        finite_error = '未拒绝'
    periodic = []
    for width, origin, orders in [('5', '0', [ab, ba]), ('7/3', '-1/2', [ab, ba, ba]), ('13/17', '2/3', [ba, ab, ab, ba])]:
        value = copy.deepcopy(order)
        value['schedule'] = {'kind': 'periodic', 'origin': example.time_value(origin),
                             'slot_width': example.time_value(width), 'orders': orders}
        period = Fraction(width).numerator * len(orders)
        number = 1 << period.bit_length()
        left = event_order.order_at(value, example.time_value(5 * number))
        right = event_order.order_at(value, example.time_value(5 * (number + period)))
        assert left == right and wanted(number) != wanted(number + period)
        periodic.append({'slot_width': width, 'origin': origin, 'period_on_due_index': period,
                         'index': number, 'encoded_same': True, 'required_different': True})
    results['order_coverage'] = {'finite_entries_pass': 65, 'next_instant': 325,
                               'finite_error': finite_error, 'periodic_probes': periodic}
    results['manifest'] = {'file_count': len(manifest['files']), 'hash_count': len(manifest['sha256']),
        'mismatches': [{'path': path, 'declared': declared, 'actual': digest(Path(path))}
                       for path, declared in manifest['sha256'].items() if digest(Path(path)) != declared]}
    after = {str(path): digest(path) for path in sorted(source_paths)}
    results['protected_sources'] = {'count': len(before), 'changed': [path for path in before if before[path] != after[path]]}
    save(BASE / '复验结果.json', results)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    assert proc.returncode == 0
    assert not results['protected_sources']['changed']


if __name__ == '__main__':
    main()
