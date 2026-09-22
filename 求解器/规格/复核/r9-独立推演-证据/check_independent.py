"""独立推演的局部复算与来源核对；不执行内核，不证明初态可达。"""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
SPEC = HERE.parent.parent
ROOT = SPEC.parent.parent
PRODUCTS = ('高容谷地电池', '精选荞愈胶囊')
ORES = ('源矿', '蓝铁矿')
checks = []


def check(value, name):
    assert value, name
    checks.append(name)


def dump(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def quantity(value):
    return {'value': str(value), 'category': '候选'}


def time(value):
    return {'kind': 'rational', 'value': quantity(value)}


def decision(value):
    return {'status': 'specified', 'value': value, 'basis': ['字段映射试样，非可运行种子']}


def pending(operation, target, deadline):
    prefix = 'C' if operation == 'manufacture_complete' else 'W'
    return {'event': f'{prefix}|{deadline}|{target}', 'operation': operation,
            'target': target, 'trigger': {'kind': 'at_time', 'value': time(deadline)},
            'predecessors': [], 'status': 'waiting'}


module_spec = importlib.util.spec_from_file_location(
    'cycle_reference_r9', SPEC / '第五轮规格修订/cycle_key_reference.py')
reference = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(reference)

# 此最小试样专门让各种动态时刻同时非空；不作为输入合法性或运行证据。
state = {
    'layout_snapshot': 'fixture_layout', 'settings_anchor': {'event': 'fixture_settings', 'side': 'after'},
    'warehouse': {'unlisted': 'empty', 'slots': [
        {'slot': 'W_ore_a', 'item': ORES[0], 'quantity': quantity(1),
         'empty_identity': {'status': 'not_applicable', 'value': None, 'basis': ['非空格']}},
        {'slot': 'W_ore_b', 'item': ORES[1], 'quantity': quantity(80000),
         'empty_identity': {'status': 'not_applicable', 'value': None, 'basis': ['非空格']}},
        {'slot': 'W_plant', 'item': '荞花', 'quantity': quantity(79998),
         'empty_identity': {'status': 'not_applicable', 'value': None, 'basis': ['非空格']}}
    ]},
    'inventory': [{'slot': 'belt:transport:0', 'contents': [
        {'item': ORES[0], 'quantity': quantity(1), 'entered_at': time(99)}]}],
    'progress': [{'unit': 'machine', 'phase': 'working', 'recipe': 'fixture_recipe',
                  'candidate_recipes': [], 'locked_recipe': 'fixture_recipe',
                  'remaining': time(2), 'cooldowns': []},
                 {'unit': 'box', 'phase': 'idle', 'recipe': None,
                  'candidate_recipes': [], 'locked_recipe': None, 'remaining': None,
                  'cooldowns': [{'slot': None, 'remaining': time(3)}]}],
    'logistics': {'active_channels': ['PC_a'], 'blocked_channels': [],
                  'poll_memory': decision({'schema': 'poll-memory-v1', 'sides': [
                      {'unit': 'fixture', 'side': 'output', 'graded': False,
                       'current_level': 'L', 'levels': [
                           {'id': 'L', 'members': ['PC_a', 'PC_b'], 'next_channel': 'PC_a'}]}]}),
                  'gate_counters': [{'unit': 'gate', 'total_received': quantity(10),
                                     'window_received': quantity(1), 'window_started_at': time(98),
                                     'blocked_reasons': []}],
                  'connection_order': decision([['PC_a'], ['PC_b']])},
    'environment': {'time': time(100), 'stage': 'zero_intervention', 'online': True,
                    'withdrawal_memory': decision({'once_fired': [], 'pending_rules': []})},
    'semantic_context': {
        'arbitration': {'level_order': ['L'], 'warehouse_empty_slot_order': []},
        'parameter_values': [{'axis': 'initialization.build_timing', 'lifetime': 'U',
                             'value': decision({'build_time': time(0)})}],
        'judgment_context': decision({'instant': time(100), 'phase': 'after_closure',
                                      'order_scope': 'global', 'round': 4, 'next_template': 3,
                                      'ordered_events': ['J|100|4|2'], 'next_event': None}),
        'pending_events': decision([pending('manufacture_complete', 'machine', 102),
                                    pending('gate_window_expiry', 'gate', 103)]),
        'tick_context': decision({'window_start': time(100), 'window_end': time(101),
                                  'movements': [], 'port_usage': [{'port': 'p', 'quantity': quantity(1)}],
                                  'internal_passages': []})
    }
}
base_key = reference.key_bytes(reference.cycle_key(state))
for delta in (1, 5, 31, 10**18):
    shifted = deepcopy(state)
    shifted['environment']['time'] = time(100 + delta)
    shifted['inventory'][0]['contents'][0]['entered_at'] = time(99 + delta)
    shifted['logistics']['gate_counters'][0]['window_started_at'] = time(98 + delta)
    semantic = shifted['semantic_context']
    semantic['judgment_context']['value']['instant'] = time(100 + delta)
    for event in semantic['pending_events']['value']:
        deadline = reference.number(event['trigger']['value']) + delta
        event['trigger']['value'] = time(deadline)
        event['event'] = event['event'].split('|')[0] + '|' + str(deadline) + '|' + event['target']
    context = semantic['tick_context']['value']
    context['window_start'], context['window_end'] = time(100 + delta), time(101 + delta)
    check(reference.key_bytes(reference.cycle_key(shifted)) == base_key,
          f'运输年龄、窗口年龄、两类pending及tick边界共同平移{delta}后键相同')
    check(shifted['semantic_context']['parameter_values'] == state['semantic_context']['parameter_values'],
          f'平移{delta}不改变固定建造参数')

mutations = [
    (('inventory', 0, 'contents', 0, 'entered_at'), time(98), '运输年龄'),
    (('progress', 0, 'remaining'), time(1), '制造剩余工作量'),
    (('progress', 1, 'cooldowns', 0, 'remaining'), time(2), '箱冷却'),
    (('logistics', 'gate_counters', 0, 'window_started_at'), time(97), '门窗口年龄'),
    (('logistics', 'gate_counters', 0, 'total_received'), quantity(11), '门累计'),
    (('logistics', 'gate_counters', 0, 'window_received'), quantity(2), '门窗口计数'),
    (('logistics', 'gate_counters', 0, 'blocked_reasons'), ['identity_mismatch'], '门原因'),
    (('logistics', 'poll_memory', 'value', 'sides', 0, 'levels', 0, 'next_channel'), 'PC_b', '轮询游标'),
    (('warehouse', 'slots', 2, 'quantity'), quantity(79999), '植物仓库量'),
    (('semantic_context', 'pending_events', 'value', 0, 'trigger', 'value'), time(104), '待完成截止偏移'),
    (('semantic_context', 'tick_context', 'value', 'port_usage', 0, 'quantity'), quantity(0), '端口额度')
]
for path, value, name in mutations:
    changed = deepcopy(state)
    parent = changed
    for component in path[:-1]:
        parent = parent[component]
    parent[path[-1]] = value
    check(reference.key_bytes(reference.cycle_key(changed)) != base_key, name + '保守保留于键')

for item in PRODUCTS:
    for amount in (0, 1, 79999):
        changed = deepcopy(state)
        changed['warehouse']['slots'].append({
            'slot': 'unassigned_product', 'item': item if amount else None,
            'quantity': quantity(amount),
            'empty_identity': {'status': 'not_applicable', 'value': None, 'basis': ['非空格']}
            if amount else decision(item)})
        check(reference.key_bytes(reference.cycle_key(changed)) == base_key,
              f'成品{item}数量{amount}或历史身份格移出键')

# 局部算术源自规则L13/L36/L41及转移§4，不调用被审自查中的算式。
capacity_cases = []
for amount in (1, 2, 50, 300):
    for stock in (1, 79998, 79999, 80000):
        capacity_cases.append({'stock': stock, 'batch': amount,
                               'accepts': stock <= 80000 - amount})
check(next(c['accepts'] for c in capacity_cases if c['stock'] == 79999 and c['batch'] == 1)
      and not next(c['accepts'] for c in capacity_cases if c['stock'] == 80000 and c['batch'] == 1),
      '两矿正库存的回矿容量守卫不等价')
check(not next(c['accepts'] for c in capacity_cases if c['stock'] == 79999 and c['batch'] == 2),
      '成品未满不蕴含整批两件可收')
check(Fraction(12, 20) == Fraction(3, 5) and Fraction(11, 20) == Fraction('0.55'),
      '周期账率按精确有理数比较')

# 取空是表示转换，保留身份，不产生无身份空格；端口指派会观察到库存变空。
identity_case = {'before': {'slot': 'product_slot', 'item': PRODUCTS[0], 'quantity': 1,
                            'empty_identity': None},
                 'after': {'slot': 'product_slot', 'item': None, 'quantity': 0,
                           'empty_identity': PRODUCTS[0]},
                 'anonymous_order_before': [], 'anonymous_order_after': [],
                 'assigned_source_available_before': True, 'assigned_source_available_after': False}
check(identity_case['after']['empty_identity'] is not None
      and identity_case['anonymous_order_before'] == identity_case['anonymous_order_after'],
      'retain_history取空不进入匿名序，但已指派口可观察库存变化')
dump('独立局部复算.json', {'status': 'PASS', 'checks': checks, 'check_count': len(checks),
                           'capacity_cases': capacity_cases, 'identity_case': identity_case,
                           'scope': '字段映射试样及局部规则算术；非合法StateSeed、非Rust测试或完整可达反例'})

manifest = json.loads((SPEC / '第五轮规格修订-r8/交付清单.json').read_text())
manifest_mismatches = [{'path': path, 'expected': expected,
                        'actual': hashlib.sha256(Path(path).read_bytes()).hexdigest()}
                       for path, expected in manifest['sha256'].items()
                       if hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected]
start = json.loads((HERE / '开工指纹.json').read_text())
changed_sources = [row['path'] for row in start['files']
                   if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest() != row['sha256']]
links = json.loads((SPEC / '第五轮规格修订-r8/交付自审.json').read_text())['links']
missing_links = [row for row in links if not Path(row['target']).exists()]
guard = json.loads((SPEC / '第五轮规格修订-r8/停止条件复算.json').read_text())['truth_table']
guard_errors = [row for row in guard if row['expected_stop'] !=
                (row['new_species_count'] > 1 and bool(row['assigned_empty_slots']))
                or len({row['expected_stop'], row['transfer_stop'], row['reply_stop']}) != 1]
revision = json.loads((HERE / '规格自查重跑.log').read_text())
round5 = json.loads((HERE / '自查结果.json').read_text())
report = {'status': 'PASS' if not (manifest_mismatches or changed_sources or missing_links or guard_errors) else 'FAIL',
          'r8_manifest_entries': len(manifest['sha256']), 'r8_manifest_mismatches': manifest_mismatches,
          'reviewed_sources': len(start['files']), 'sources_changed_during_review': changed_sources,
          'r8_local_links': len(links), 'missing_links': missing_links,
          'r8_guard_cases': len(guard), 'r8_guard_errors': guard_errors,
          'fresh_revision_status': revision['status'], 'fresh_axis_count': revision['axis_count'],
          'fresh_round5_status': round5['status'], 'fresh_round5_count': round5['check_count'],
          'fresh_local_checks': len(checks),
          'not_rerun': ['check_round8.py写回被审目录且会运行schema生成器，故仅阅读脚本和核对现有产物'],
          'scope': '原始字节、现有产物与只读入口重跑；不推断其他席位的写操作'}
dump('复核验证结果.json', report)
assert report['status'] == 'PASS', report
print(json.dumps(report, ensure_ascii=False, indent=2))
