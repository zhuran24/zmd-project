#!/usr/bin/env python3
"""第三轮第一否证席的只读复验；所有产物仅写本证据目录。"""
import contextlib
import copy
import hashlib
import io
import json
import sys
from pathlib import Path
from unittest.mock import patch

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[4]
SAMPLES = ROOT / '求解器/数据/样例'
TASKS = Path('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/2a1af1b1-ede2-4b4a-8f95-41e78df48af0/scratchpad/step1')
sys.dont_write_bytecode = True
sys.path.insert(0, str(SAMPLES))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (BASE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


sources = [ROOT / name for name in (
    '《明日方舟：终末地》游戏规则.txt', '求解任务.txt', '求解约束.txt', '候选约束.txt')]
sources += list(SAMPLES.glob('*.py')) + list(SAMPLES.glob('*.json')) + list(SAMPLES.glob('*.md'))
sources += list((ROOT / '求解器/规格').glob('*.md')) + list((ROOT / '求解器/规格').glob('*.json'))
sources += list((ROOT / '求解器/规格/内核输入修订验证-r3').glob('*'))
sources += [ROOT / '求解器/数据/正式静态目录.json']
sources += [TASKS / name for name in ('任务书3.md', '任务书.md', '任务书2.md')]
sources += [BASE.parent / name for name in ('复核-r3-覆盖.md', '复核-r3-可导出性.md', '复核-r3-一致性.md')]
sources = sorted({p.resolve() for p in sources if p.is_file()})
before = {str(p): digest(p) for p in sources}
save('核验前指纹.json', before)

import check_examples as checker
import check_golden_trace as trace
import runtime_example as runtime
import test_runtime_input as regression

original_load = checker.load_json
data = original_load(trace.INPUT)
disk_output = original_load(trace.OUTPUT)
results = {}


def capture_call(function, output_override=None):
    writes = {}
    console = io.StringIO()

    def capture_write(path, content, *args, **kwargs):
        writes[str(path.resolve())] = content
        return len(content)

    def load(path):
        if output_override is not None and Path(path).resolve() == trace.OUTPUT.resolve():
            return copy.deepcopy(output_override)
        return original_load(path)

    try:
        # 被审入口的原写出只进内存，既有记录和回归报告不落盘。
        with patch.object(Path, 'write_text', capture_write), patch.object(checker, 'load_json', load), contextlib.redirect_stdout(console):
            function()
    except Exception as error:
        return {'passed': False, 'error': type(error).__name__ + ': ' + str(error), 'stdout': console.getvalue()}, writes
    return {'passed': True, 'stdout': console.getvalue()}, writes


results['baseline_disk'], disk_writes = capture_call(regression.main)
results['regeneration'], generated_writes = capture_call(trace.main)
assert results['regeneration']['passed'], results['regeneration']
generated = json.loads(generated_writes[str(trace.OUTPUT.resolve())])
save('重新生成的运行记录.json', generated)
results['baseline_regenerated'], _ = capture_call(regression.main, generated)
results['original_trace_equals_recalculation'] = disk_output['trace'] == generated['trace']


def regress_output(name, mutate):
    value = copy.deepcopy(generated)
    mutate(value)
    save(name + '.json', value)
    outcome, writes = capture_call(regression.main, value)
    reports = [json.loads(text) for text in writes.values()]
    outcome['tests'] = len(reports[0]['tests']) if reports else None
    outcome['counterexample_file'] = name + '.json'
    return outcome


def inventory_row(output, tick, slot):
    return next(row for row in output['trace']['ticks'][tick]['state']['inventory'] if row['slot'] == slot)


def overfull_manufacturing(output):
    inventory_row(output, 2, 'crusher:input:0')['contents'] = [{
        'item': '源矿', 'quantity': runtime.quantity(999), 'entered_at': runtime.time_value(2)}]


def bad_summary(output):
    output['trace']['ticks'][2]['summary']['warehouse_ore'] = '12345'


results['output_mutations'] = {
    'K3-r3-L2-01-capacity': regress_output('输出反例-运输格两件', lambda value: inventory_row(value, 0, 'feed_belt:transport:0')['contents'][0]['quantity'].update(value='2')),
    'K3-r3-L2-01-parameter': regress_output('输出反例-伪造时间域', lambda value: value['parameter_assignment']['fixedness_unproven']['time.domain'].update(value='invented_domain')),
    'K3-r3-L2-01-events': regress_output('输出反例-删除末刻事件', lambda value: value['trace']['ticks'][3].update(events=[])),
    'K3-r3-L3-03-capacity': regress_output('输出反例-制造格999件', overfull_manufacturing),
    'K3-r3-L3-03-summary': regress_output('输出反例-摘要失配', bad_summary),
    'K3-r3-L3-03-combined': regress_output('输出反例-制造格及摘要', lambda value: (overfull_manufacturing(value), bad_summary(value))),
}


def check_and_run(value):
    try:
        checked = checker.check(value, trace.INPUT)
        ticks = trace.run(value)
        return {'accepted': True, 'check_status': checked['status'], 'ticks': len(ticks), 'summaries': [tick['summary'] for tick in ticks]}
    except Exception as error:
        return {'accepted': False, 'error': type(error).__name__ + ': ' + str(error)}


def get_seed(value):
    return value['initial_state']['nonwarehouse']['value']


decision_cases = [
    ('判定上下文未解', lambda seed: seed['semantic_context']['judgment_context'], lambda decision: decision.update(status='unresolved')),
    ('端口上下文未解', lambda seed: seed['semantic_context']['tick_context'], lambda decision: decision.update(status='unresolved')),
    ('拿取记忆非法状态', lambda seed: seed['environment']['withdrawal_memory'], lambda decision: decision.update(status='unknown')),
    ('端口上下文缺依据', lambda seed: seed['semantic_context']['tick_context'], lambda decision: decision.pop('basis')),
    ('接通次序缺依据', lambda seed: seed['logistics']['connection_order'], lambda decision: decision.pop('basis')),
]
results['decision_mutations'] = {}
for name, select, mutate in decision_cases:
    value = copy.deepcopy(data)
    selected = select(get_seed(value))
    mutate(selected)
    outcome = check_and_run(value)
    try:
        checker.decision(selected)
        outcome['standalone_decision_rejected'] = False
    except checker.CheckError as error:
        outcome['standalone_decision_rejected'] = True
        outcome['standalone_error'] = str(error)
    save('输入反例-' + name + '.json', value)
    results['decision_mutations'][name] = outcome


empty_source = copy.deepcopy(data)
empty_slot = {'slot': 'empty_extra', 'item': None, 'quantity': runtime.quantity(0), 'empty_identity': runtime.decision(None, '无历史身份的空格')}
empty_source['initial_state']['warehouse']['slots'].append(copy.deepcopy(empty_slot))
get_seed(empty_source)['warehouse']['slots'].append(copy.deepcopy(empty_slot))
next(row for row in empty_source['settings']['warehouse_assignments'] if row['port'].startswith('ore_source:'))['slot'] = 'empty_extra'
save('输入反例-空源错误派生状态.json', empty_source)
results['empty_source_wrong_derived'] = check_and_run(empty_source)
results['empty_source_corrections'] = {}
for fix_current, fix_arbitration in [(True, False), (False, True), (True, True)]:
    value = copy.deepcopy(empty_source)
    seed = get_seed(value)
    if fix_current:
        for side in seed['logistics']['poll_memory']['value']['sides']:
            if (side['unit'], side['side']) in [('ore_source', 'output'), ('feed_belt', 'input')]:
                side['current_level'] = None
    if fix_arbitration:
        seed['semantic_context']['arbitration']['warehouse_empty_slot_order'] = ['empty_extra']
    name = f'current_{fix_current}_arbitration_{fix_arbitration}'
    save('空源修正-' + name + '.json', value)
    results['empty_source_corrections'][name] = check_and_run(value)


profile = original_load(runtime.PROFILE_PATH)
fresh_status, fresh_writes = capture_call(lambda: runtime.write_profile(data))
fresh_profile = json.loads(fresh_writes[str(runtime.PROFILE_PATH.resolve())])
save('只读重建的参数投影.json', fresh_profile)
profile_path = (runtime.PROFILE_PATH.parent / profile['profile_source']['path']).resolve()
fingerprinted = {Path(row['path']).resolve() for row in generated['fingerprints']}
results['profile_provenance'] = {
    'declared': profile['profile_source']['sha256'], 'actual': digest(profile_path),
    'top_level_differences': [key for key in profile if profile[key] != fresh_profile[key]],
    'source_differences': [key for key in profile['profile_source'] if profile['profile_source'][key] != fresh_profile['profile_source'][key]],
    'axis_count': len(profile['axes']), 'axes_identical': profile['axes'] == fresh_profile['axes'],
    'projection_in_fingerprints': runtime.PROFILE_PATH.resolve() in fingerprinted,
    'check_examples_in_fingerprints': Path(checker.__file__).resolve() in fingerprinted,
    'regenerated_profile_fingerprint': [row for row in generated['fingerprints'] if Path(row['path']).resolve() == profile_path],
}

selected_axes = ['time.domain', 'transfer.cooldown_scope', 'polling.level_tie', 'damping.belt_component_rule']
results['coverage_entries'] = [row for row in generated['uncovered_axes'] if row['axis'] in selected_axes]
results['coverage_structure'] = {
    'uncovered_axis_count': len(generated['uncovered_axes']),
    'boxes': [row['id'] for row in data['layout']['units'] if row['kind'] == '协议储存箱'],
    'max_levels_per_side': max(len(side['levels']) for tick in generated['trace']['ticks'] for side in tick['state']['logistics']['poll_memory']['value']['sides']),
    'validation_scope': generated['validation_scope'], 'open_items': generated['open_items'],
}

captured = []


def observe(frame, event, arg):
    # 观察原执行器的下一轮循环入口；不改局部变量或动作顺序。
    if event == 'line' and frame.f_code is trace.run.__code__:
        local = frame.f_locals
        records = local.get('records', [])
        if frame.f_lineno == 120 and records and records[-1]['event'] == 'J|2|0|1' and not captured:
            captured.append(copy.deepcopy({
                'time': local['t'], 'round': local['rounds'], 'last_event': records[-1],
                'next_template': local['i'] + 1, 'events_so_far': records,
                'inventory': local['inv'], 'progress': local['progress'],
                'port_usage': local['usage'], 'movements': local['movements'], 'due': local['due'],
            }))
    return observe


sys.settrace(observe)
try:
    trace.run(data)
finally:
    sys.settrace(None)
save('闭包中途物理投影.json', captured)
results['mid_closure_capture_count'] = len(captured)

after = {str(path): digest(path) for path in sources}
results['source_changes_during_probe'] = [path for path in before if before[path] != after[path]]
save('核验后指纹.json', after)
save('核验结果.json', results)
print(json.dumps({
    'baseline_disk': results['baseline_disk'],
    'baseline_regenerated': results['baseline_regenerated'],
    'output_mutations': {key: {'passed': value['passed'], 'tests': value['tests']} for key, value in results['output_mutations'].items()},
    'decision_mutations': {key: {'accepted': value['accepted'], 'ticks': value.get('ticks'), 'standalone_decision_rejected': value['standalone_decision_rejected']} for key, value in results['decision_mutations'].items()},
    'empty_source_wrong_derived': results['empty_source_wrong_derived']['accepted'],
    'empty_source_corrections': results['empty_source_corrections'],
    'profile_provenance': results['profile_provenance'],
    'source_changes_during_probe': results['source_changes_during_probe'],
    'mid_closure_capture_count': len(captured),
}, ensure_ascii=False, indent=2))
