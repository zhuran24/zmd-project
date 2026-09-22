#!/usr/bin/env python3
"""第三轮第二否证席：只读调用原程序，写入独立证据目录。"""
import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[4]
SAMPLES = ROOT / '求解器/数据/样例'
SPEC = ROOT / '求解器/规格'
sys.dont_write_bytecode = True
sys.path.insert(0, str(SAMPLES))
import check_examples as checker
import runtime_example as runtime
import check_golden_trace as reference
import test_runtime_input as regression


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(name, value):
    (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def capture(call, replacement=None):
    """捕获固定输出，不向被审路径写入；可只替换运行记录读取。"""
    writes = {}
    log = io.StringIO()
    original_load = checker.load_json

    def intercepted_write(path, content, *args, **kwargs):
        writes[str(path.resolve())] = content
        return len(content)

    def intercepted_load(path):
        if replacement is not None and path.resolve() == reference.OUTPUT.resolve():
            return copy.deepcopy(replacement)
        return original_load(path)

    with patch.object(Path, 'write_text', intercepted_write), patch.object(checker, 'load_json', intercepted_load), contextlib.redirect_stdout(log):
        try:
            call()
            result = {'accepted': True}
        except Exception as error:
            result = {'accepted': False, 'error_type': type(error).__name__, 'error': str(error)}
    result['stdout'] = log.getvalue()
    result['writes'] = {path: json.loads(content) for path, content in writes.items()}
    return result


def input_check(data, execute=True):
    try:
        result = {'accepted': True, 'check': checker.check(data, reference.INPUT)}
        if execute:
            ticks = reference.run(data)
            result.update(ticks=len(ticks), completed_batches=ticks[-1]['summary']['completed_batches'])
        return result
    except Exception as error:
        return {'accepted': False, 'error_type': type(error).__name__, 'error': str(error)}


def main():
    formal = [ROOT / name for name in ('《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt')]
    source_files = formal + list(SAMPLES.glob('*.py')) + list(SAMPLES.glob('*.json'))
    source_files += list(SPEC.glob('*.md')) + list(SPEC.glob('*.json')) + [SAMPLES.parent / '正式静态目录.json']
    source_files += list((SPEC / '内核输入修订验证-r3').glob('*'))
    source_files = sorted({p for p in source_files if p.is_file()})
    before = {str(p): sha(p) for p in source_files}
    write_json('读取指纹.json', before)
    data = checker.load_json(reference.INPUT)
    original = checker.load_json(reference.OUTPUT)
    results = {'baseline_input': input_check(data)}
    actual = reference.run(data)
    results['original_full_ticks_equal_recompute'] = original['trace']['ticks'] == actual
    results['original_parameters_equal_input'] = original['parameter_assignment'] == data['parameters']
    results['baseline_regression'] = capture(regression.main)
    regenerated = capture(reference.main)
    results['regeneration'] = regenerated
    coherent = regenerated['writes'][str(reference.OUTPUT.resolve())]
    write_json('只读重生运行记录.json', coherent)
    results['regenerated_equals_original'] = coherent == original
    results['coherent_regression'] = capture(regression.main, coherent)

    # 每个输出反例独立从同一份新重生记录复制。
    def transport_overflow(record):
        slot = next(r for r in record['trace']['ticks'][0]['state']['inventory'] if r['slot'] == 'feed_belt:transport:0')
        slot['contents'][0]['quantity']['value'] = '2'

    def wrong_parameter(record):
        record['parameter_assignment']['fixedness_unproven']['time.domain']['value'] = 'invented_domain'

    def missing_events(record):
        record['trace']['ticks'][3]['events'] = []

    def manufacturing_overflow(record):
        slot = next(r for r in record['trace']['ticks'][2]['state']['inventory'] if r['slot'] == 'crusher:input:0')
        slot['contents'] = [{'item': '源矿', 'quantity': runtime.quantity(999), 'entered_at': runtime.time_value(2)}]

    def wrong_summary(record):
        record['trace']['ticks'][2]['summary']['warehouse_ore'] = '12345'

    output_mutations = [('transport_overflow', transport_overflow), ('wrong_parameter', wrong_parameter), ('missing_events', missing_events), ('manufacturing_overflow', manufacturing_overflow), ('wrong_summary', wrong_summary)]
    results['output_mutations'] = {}
    for name, mutate in output_mutations:
        record = copy.deepcopy(coherent)
        mutate(record)
        write_json('输出反例-' + name + '.json', record)
        results['output_mutations'][name] = capture(regression.main, record)

    # 通用Decision验证器的拒收与运行入口的放行分开记录。
    mutations = [
        ('judgment_unresolved', ('semantic_context', 'judgment_context'), 'status', 'unresolved'),
        ('tick_unresolved', ('semantic_context', 'tick_context'), 'status', 'unresolved'),
        ('withdrawal_unknown', ('environment', 'withdrawal_memory'), 'status', 'unknown'),
        ('tick_missing_basis', ('semantic_context', 'tick_context'), 'basis', None),
        ('connection_missing_basis', ('logistics', 'connection_order'), 'basis', None),
    ]
    results['decision_mutations'] = {}
    for name, location, field, value in mutations:
        variant = copy.deepcopy(data)
        shell = variant['initial_state']['nonwarehouse']['value']
        for key in location:
            shell = shell[key]
        if value is None:
            del shell[field]
        else:
            shell[field] = value
        result = input_check(variant)
        try:
            checker.decision(shell)
            result['generic_decision_validator_rejects'] = False
        except checker.CheckError as error:
            result['generic_decision_validator_rejects'] = True
            result['generic_decision_error'] = str(error)
        results['decision_mutations'][name] = result
        write_json('输入反例-' + name + '.json', variant)

    # 空格身份已解决；只改变真实库存指派，不动机型或参数组合。
    empty = copy.deepcopy(data)
    empty_slot = {'slot': 'empty_extra', 'item': None, 'quantity': runtime.quantity(0), 'empty_identity': runtime.decision(None, '无保留身份')}
    empty['initial_state']['warehouse']['slots'].append(copy.deepcopy(empty_slot))
    seed = empty['initial_state']['nonwarehouse']['value']
    seed['warehouse']['slots'].append(copy.deepcopy(empty_slot))
    next(row for row in empty['settings']['warehouse_assignments'] if row['port'] == 'ore_source:north:1')['slot'] = 'empty_extra'
    results['empty_source'] = {'inconsistent_seed': input_check(empty)}
    write_json('输入反例-empty_source.json', empty)
    fixed_levels = copy.deepcopy(empty)
    for side in fixed_levels['initial_state']['nonwarehouse']['value']['logistics']['poll_memory']['value']['sides']:
        if (side['unit'], side['side']) in {('ore_source', 'output'), ('feed_belt', 'input')}:
            side['current_level'] = None
    results['empty_source']['correct_levels_only'] = input_check(fixed_levels)
    fixed_arbitration = copy.deepcopy(empty)
    fixed_arbitration['initial_state']['nonwarehouse']['value']['semantic_context']['arbitration']['warehouse_empty_slot_order'] = ['empty_extra']
    results['empty_source']['correct_arbitration_only'] = input_check(fixed_arbitration)
    fixed_levels['initial_state']['nonwarehouse']['value']['semantic_context']['arbitration']['warehouse_empty_slot_order'] = ['empty_extra']
    results['empty_source']['fully_corrected'] = input_check(fixed_levels)
    write_json('正确状态-empty_source.json', fixed_levels)
    empty_ticks = reference.run(empty)
    results['empty_source']['after_refresh'] = [s for s in empty_ticks[0]['state']['logistics']['poll_memory']['value']['sides'] if (s['unit'], s['side']) in {('ore_source', 'output'), ('feed_belt', 'input')}]

    # 行跟踪只观察闭包中间位置，不能把原程序尚未刷新过的语义上下文称为完整种子。
    middle = {}
    def trace(frame, event, arg):
        local = frame.f_locals
        if frame.f_code is reference.run.__code__ and event == 'line' and frame.f_lineno == 121 and local.get('t') == 2 and local.get('rounds') == 0 and local.get('i') == 2 and not middle:
            for key in ('t', 'rounds', 'i', 'state', 'usage', 'movements', 'passages', 'records', 'due'):
                middle[key] = copy.deepcopy(local[key])
        return trace
    sys.settrace(trace)
    try:
        reference.run(data)
    finally:
        sys.settrace(None)
    assert middle and middle['records'][-1]['event'] == 'J|2|0|1'
    write_json('闭包中途物理投影.json', middle)
    results['middle_projection'] = {'instant': middle['t'], 'round': middle['rounds'], 'next_template': middle['i'], 'events': [e['event'] for e in middle['records']], 'usage': middle['usage'], 'progress': middle['state']['progress'], 'nonempty': [r for r in middle['state']['inventory'] if r['contents']]}

    # 两个空箱反例的有限几何核；无限排序覆盖由报告中的有限表论证判断。
    catalog = checker.load_json(SAMPLES.parent / '正式静态目录.json')
    box_data = copy.deepcopy(data)
    box_data['layout']['units'] = [
        {'id': uid, 'kind': kind, 'origin': [runtime.quantity(x), runtime.quantity(y)], 'rotation': 'r0', 'port_layout': 0, 'bridge_axes': None, 'occupied_cells': None}
        for uid, kind, x, y in [('core', '协议核心', 50, 50), ('power', '供电桩', 13, 10), ('box_a', '协议储存箱', 10, 10), ('box_b', '协议储存箱', 16, 10)]
    ]
    _, units, _, channels, buffers, area = checker.geometry(box_data, catalog)
    powered = {uid: max(x, 8) < min(x + 3, 20) and max(10, 5) < min(13, 17) for uid, x in [('box_a', 10), ('box_b', 16)]}
    results['periodic_order_witness'] = {'units': len(units), 'area': area, 'channels': channels, 'buffers': buffers, 'powered_positive_area': powered, 'build_times': {'core': -20, 'power': -15, 'box_a': -10, 'box_b': -5}, 'illustrative_prefix': [{'instant': 5*k, 'order': ['box_a', 'box_b'] if k % 2 == 0 else ['box_b', 'box_a']} for k in range(8)], 'scope': '只核几何与排序前缀；完整历史与有限编码排除论证见否证报告'}

    assignment_path = SAMPLES / 'kernel_profile_v1参数赋值.json'
    assignment = checker.load_json(assignment_path)
    projected = capture(lambda: runtime.write_profile(data))
    current_assignment = projected['writes'][str(assignment_path.resolve())]
    saved_without_hash = copy.deepcopy(assignment)
    current_without_hash = copy.deepcopy(current_assignment)
    saved_without_hash['profile_source'].pop('sha256')
    current_without_hash['profile_source'].pop('sha256')
    included = {Path(row['path']).resolve() for row in coherent['fingerprints']}
    results['profile_provenance'] = {'declared': assignment['profile_source'], 'current_sha256': sha(SPEC / '受限模型声明.md'), 'same_except_profile_source_sha256': saved_without_hash == current_without_hash, 'axes_count': len(assignment['axes']), 'projection_fingerprinted': assignment_path.resolve() in included, 'check_examples_fingerprinted': (SAMPLES / 'check_examples.py').resolve() in included, 'fresh_output_profile_fingerprint': [r for r in coherent['fingerprints'] if Path(r['path']).resolve() == (SPEC / '受限模型声明.md').resolve()]}
    write_json('只读重生参数投影.json', current_assignment)
    results['uncovered_axes'] = {axis: next(r for r in coherent['uncovered_axes'] if r['axis'] == axis) for axis in ('time.domain', 'transfer.cooldown_scope', 'polling.level_tie', 'damping.belt_component_rule')}
    results['coverage_structure'] = {'storage_boxes': sum(u['kind'] == '协议储存箱' for u in data['layout']['units']), 'maximum_levels_per_side': max(len(s['levels']) for s in data['initial_state']['nonwarehouse']['value']['logistics']['poll_memory']['value']['sides']), 'transfer_events': sum(e['operation'] == 'transfer' for t in actual for e in t['events']), 'event_counts': [len(t['events']) for t in actual]}
    # 读取后再核字节，外部并行修改也必须单列。
    results['protected_files_count'] = len(before)
    results['source_changes_during_recheck'] = [{'path': name, 'before': digest, 'after': sha(Path(name))} for name, digest in before.items() if sha(Path(name)) != digest]
    write_json('核验结果.json', results)
    brief = {'baseline': results['baseline_regression']['accepted'], 'original_full_ticks_equal_recompute': results['original_full_ticks_equal_recompute'], 'output_mutations_accepted': {k: v['accepted'] for k, v in results['output_mutations'].items()}, 'decision_mutations_accepted': {k: v['accepted'] for k, v in results['decision_mutations'].items()}, 'empty_source': results['empty_source'], 'profile_provenance': results['profile_provenance'], 'source_changes': results['source_changes_during_recheck']}
    print(json.dumps(brief, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
