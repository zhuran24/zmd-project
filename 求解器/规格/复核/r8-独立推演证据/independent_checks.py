"""独立时差/容量推演及编码扰动；不是合法布局或循环证书。"""
from copy import deepcopy
from fractions import Fraction
from pathlib import Path
import hashlib
import json
import sys

here = Path(__file__).resolve().parent
spec = here.parent.parent
root = spec.parent.parent
sys.path.insert(0, str(spec / '第五轮规格修订'))
from cycle_key_reference import cycle_key, key_bytes, number

checks = []
def check(ok, name):
    assert ok, name
    checks.append(name)

def quantity(value):
    return {'value': str(value), 'category': '候选'}

def time(value):
    return {'kind': 'rational', 'value': quantity(value)}

def decision(value):
    return {'status': 'specified', 'value': value, 'basis': ['独立字段试样，不是运行证书']}

source_path = root / '求解器/数据/样例/混做粉碎机两下游-运行记录-kernel.json'
source_bytes = source_path.read_bytes()
record = json.loads(source_bytes)
state = deepcopy(record['trace']['ticks'][-1]['state'])
state['environment']['stage'] = 'zero_intervention'
context = state['semantic_context']
context['judgment_context']['value']['next_event'] = None
context['arbitration']['warehouse_empty_slot_order'] = []
instant = number(state['environment']['time'])
# 加入非空窗口与箱冷却以免平移检查因空数组而空过；这些行只供编码试样。
state['logistics']['gate_counters'] = [{'unit': 'fixture_gate', 'total_received': quantity(7), 'window_received': quantity(2), 'window_started_at': time(instant - 2), 'blocked_reasons': ['window_exhausted']}]
state['progress'].append({'unit': 'fixture_box', 'phase': 'idle', 'recipe': None, 'candidate_recipes': [], 'locked_recipe': None, 'remaining': None, 'cooldowns': [{'slot': None, 'remaining': time(3)}]})
context['pending_events']['value'].append({'event': 'W|' + str(instant + 3) + '|fixture_gate', 'operation': 'gate_window_expiry', 'target': 'fixture_gate', 'trigger': {'kind': 'at_time', 'value': time(instant + 3)}, 'predecessors': [], 'status': 'waiting'})

def key(value):
    return key_bytes(cycle_key(value))

baseline = key(state)
for delta in [1, 31, 1000003]:
    shifted = deepcopy(state)
    shifted['environment']['time'] = time(instant + delta)
    for slot in shifted['inventory']:
        for content in slot['contents']:
            if content['entered_at'] is not None:
                content['entered_at'] = time(number(content['entered_at']) + delta)
    for gate in shifted['logistics']['gate_counters']:
        gate['window_started_at'] = time(number(gate['window_started_at']) + delta)
    shifted_context = shifted['semantic_context']
    shifted_context['judgment_context']['value']['instant'] = time(instant + delta)
    for edge in ['window_start', 'window_end']:
        shifted_context['tick_context']['value'][edge] = time(number(shifted_context['tick_context']['value'][edge]) + delta)
    for event in shifted_context['pending_events']['value']:
        deadline = number(event['trigger']['value']) + delta
        event['trigger']['value'] = time(deadline)
        event['event'] = ('C' if event['operation'] == 'manufacture_complete' else 'W') + '|' + str(deadline) + '|' + event['target']
    check(key(shifted) == baseline, '非空年龄/窗口/pending平移保持:' + str(delta))

def different(name, mutation):
    changed = deepcopy(state)
    mutation(changed)
    check(key(changed) != baseline, name)

def increase_stock(value, warehouse):
    if warehouse:
        row = next(row for row in value['warehouse']['slots'] if row['item'] == '荞花')
        row['quantity'] = quantity(number(row['quantity']) - 1)
    else:
        row = next(row for row in value['inventory'] if row['contents'])['contents'][0]
        row['quantity'] = quantity(number(row['quantity']) + 1)

different('植物仓库数量必须保留', lambda value: increase_stock(value, True))
different('非仓库数量必须保留', lambda value: increase_stock(value, False))
different('门累计必须保留', lambda value: value['logistics']['gate_counters'][0].update(total_received=quantity(8)))
different('门窗口计数必须保留', lambda value: value['logistics']['gate_counters'][0].update(window_received=quantity(1)))
different('门原因必须保留', lambda value: value['logistics']['gate_counters'][0].update(blocked_reasons=['identity_mismatch']))
different('窗口不能只存模5', lambda value: value['logistics']['gate_counters'][0].update(window_started_at=time(instant - 7)))
different('冷却剩余须保留', lambda value: value['progress'][-1]['cooldowns'][0].update(remaining=time(2)))
different('pending相对截止须保留', lambda value: value['semantic_context']['pending_events']['value'][-1]['trigger'].update(value=time(instant + 4)))

changed = deepcopy(state)
for row in changed['warehouse']['slots']:
    if row['item'] in ['源矿', '蓝铁矿']:
        row['quantity'] = quantity(1)
check(key(changed) == baseline, '正矿代表量可以不同，矿物种与格不删除')
for product in ['高容谷地电池', '精选荞愈胶囊']:
    for amount in [0, 1, 79999, 80000]:
        changed = deepcopy(state)
        changed['warehouse']['slots'].append({'slot': 'fixture_' + product, 'item': product if amount else None, 'quantity': quantity(amount), 'empty_identity': {'status': 'not_applicable', 'value': None, 'basis': ['编码试样']} if amount else decision(product)})
        check(key(changed) == baseline, '成品数量/历史格移出键:' + product + ':' + str(amount))

for name, mutation in [
    ('非空匿名序拒绝', lambda value: value['semantic_context']['arbitration'].update(warehouse_empty_slot_order=['fixture'])),
    ('中途锚点拒绝', lambda value: value['semantic_context']['judgment_context']['value'].update(phase='in_closure')),
    ('未办事件前驱拒绝', lambda value: value['semantic_context']['pending_events']['value'][-1].update(predecessors=['past_event'])),
    ('非at_time触发拒绝', lambda value: value['semantic_context']['pending_events']['value'][-1]['trigger'].update(kind='after_event')),
]:
    changed = deepcopy(state)
    mutation(changed)
    try:
        key(changed)
    except AssertionError:
        check(True, name)
    else:
        raise AssertionError(name)

# 独立公式直接来自规则L23/L64，不调用被审编码或内核。
for now in range(8):
    for elapsed in range(8):
        entered = now - elapsed
        for shift in [1, 31, 1000003]:
            assert (now - entered >= 1) == (now + shift - (entered + shift) >= 1)
            assert (now - entered >= 5) == (now + shift - (entered + shift) >= 5)
check(True, '192组年龄与窗口阈值平移（每组双阈值）')
for remaining in range(1, 6):
    for enabled in [False, True]:
        expected = remaining - int(enabled)
        assert (expected == 0) == (remaining == 1 and enabled)
check(True, '暂停/运行的完成条件由工作量决定，与旧绝对预计截止无关')

capacity_cases = []
for stock in [1, 79998, 79999, 80000]:
    for batch in [1, 2, 50, 300]:
        capacity_cases.append({'stock': stock, 'batch': batch, 'ore_available': stock > 0, 'under_capacity': stock < 80000, 'accepts_whole_batch': stock + batch <= 80000, 'representative_accepts': batch <= 80000})
check(any(row['under_capacity'] and not row['accepts_whole_batch'] for row in capacity_cases), '未满不蕴含整箱可收')
check(79999 + 1 <= 80000 and not (80000 + 1 <= 80000), '回矿容量依赖不能由充分供矿删除')
# retain_history清空后不进入匿名集合；释放身份则产生可分配给他物的格。
for retained in [True, False]:
    empty = {'item': None, 'quantity': 0, 'history': '高容谷地电池' if retained else None}
    anonymous = empty['item'] is None and empty['quantity'] == 0 and empty['history'] is None
    assert anonymous == (not retained)
check(True, '取空保留/释放身份导致匿名集合不同')

result = {'status': 'PASS', 'scope': '字段编码与局部守卫；试样不是D域完整输入、可达布局或Rust循环证书', 'source_record_sha256': hashlib.sha256(source_bytes).hexdigest(), 'check_count': len(checks), 'checks': checks, 'capacity_cases': capacity_cases}
(here / '独立检查结果.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'status': result['status'], 'check_count': len(checks), 'scope': result['scope']}, ensure_ascii=False))
