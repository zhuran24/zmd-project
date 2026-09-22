"""第6轮局部转移回归；按规则不变量另核后态，不是完整执行器。"""
import copy
import itertools
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
SPEC = BASE.parent
RESULTS = []


def check(condition, name):
    assert condition, name
    RESULTS.append(name)


def ordinary_valid(slots):
    # 缓存不传入；从格内容独立检查规则13，不调用具体移动守卫。
    seen = set()
    for slot in slots:
        positive = {item for item, count in slot.items() if count > 0}
        if len(positive) > 1 or seen & positive:
            return False
        if any(count < 0 for count in slot.values()) or sum(slot.values()) > 50:
            return False
        seen |= positive
    return True


def input_target(inputs, output, item):
    if output.get(item, 0):
        return None
    present = [i for i, slot in enumerate(inputs) if slot.get(item, 0)]
    candidates = present or [i for i, slot in enumerate(inputs) if not slot]
    if not candidates:
        return None
    index = candidates[0]
    return index if sum(inputs[index].values()) < 50 else None


def output_batch(state):
    result = copy.deepcopy(state)
    if state['phase'] != 'completed':
        return result
    trial = copy.deepcopy(state['output'])
    for item, count in state['buffer'].items():
        trial[item] = trial.get(item, 0) + count
    if ordinary_valid(state['inputs'] + [trial]):
        result.update(output=trial, buffer={}, phase='idle')
    return result


def recipe_matches(inventory, recipe, quantity_rule, extra_rule):
    # 仅定义本轮full_batch组合；其它完备度没有在这里冒称已实现。
    if extra_rule == 'forbid' and set(inventory) - set(recipe):
        return False
    compare = (lambda left, right: left >= right) if quantity_rule == 'at_least' else (lambda left, right: left == right)
    return all(compare(inventory.get(item, 0), count) for item, count in recipe.items())


def remap(old_ring, old_cursor, new_ring, special=False):
    if not new_ring:
        return None
    if old_cursor in new_ring:
        return old_cursor
    if old_ring:
        start = old_ring.index(old_cursor)
        for offset in range(1, len(old_ring) + 1):
            member = old_ring[(start + offset) % len(old_ring)]
            if member in new_ring:
                return member
    return new_ring[1] if special and len(new_ring) >= 2 else new_ring[0]


def expire_batch(gates, now, old_ring, old_cursor, connection_order):
    result = copy.deepcopy(gates)
    # 只更新各门本地原因，遍历期间不映射轮询指针。
    for gate in result.values():
        if gate['start'] is not None and now - gate['start'] >= 5:
            gate['start'] = None
            gate['count'] = 0
            gate['reasons'] = sorted(set(gate['reasons']) - {'window_exhausted'})
    new_ring = [edge for edge in connection_order if not result[edge]['reasons']]
    return result, new_ring, remap(old_ring, old_cursor, new_ring)


def transfer(box, warehouse, empty_order):
    # 全部计划建立在判前副本上；unsupported和拒收的后效分开。
    original = {'box': copy.deepcopy(box), 'warehouse': copy.deepcopy(warehouse), 'cooldown': 0, 'delivered': {}}
    targets = {}
    for item in box:
        candidates = [key for key, slot in warehouse.items()
                      if (slot['quantity'] and slot['item'] == item)
                      or (not slot['quantity'] and slot['identity'] == item)]
        if len(candidates) > 1:
            return 'invalid', original
        if candidates:
            targets[item] = candidates[0]
    empty = {key for key, slot in warehouse.items() if not slot['quantity'] and slot['identity'] is None}
    if len(empty_order) != len(set(empty_order)) or set(empty_order) != empty:
        return 'invalid', original
    unknown = set(box) - set(targets)
    if len(unknown) >= 2 and empty:
        return 'unsupported:competing_new_species', original
    for item in unknown:
        key = empty_order[0] if empty_order else 'W_new_' + item.encode().hex()
        if key in warehouse and key not in empty:
            return 'invalid', original
        targets[item] = key
    if any(warehouse.get(targets[item], {}).get('quantity', 0) + count > 80000 for item, count in box.items()):
        return 'capacity_rejected', {**original, 'cooldown': 5}
    result = copy.deepcopy(original)
    for item, count in box.items():
        key = targets[item]
        previous = warehouse.get(key, {}).get('quantity', 0)
        result['warehouse'][key] = {'item': item, 'quantity': previous + count, 'identity': item}
    result.update(box={}, cooldown=5, delivered=copy.deepcopy(box))
    return 'success', result


def run():
    before = {'inputs': [{}], 'output': {}, 'buffer': {'源矿': 1}, 'phase': 'working'}
    completed = {**copy.deepcopy(before), 'buffer': {'源石粉末': 1}, 'phase': 'completed'}
    received = copy.deepcopy(completed)
    target = input_target(received['inputs'], received['output'], '源石粉末')
    assert target == 0
    received['inputs'][target]['源石粉末'] = 1
    after = output_batch(received)
    check(after == received and ordinary_valid(after['inputs'] + [after['output']]), 'S3-r6-L2-01：完成→合法外部错料收件→出缓存阻塞，保持completed及整批')
    legacy_after = copy.deepcopy(received)
    legacy_after.update(output={'源石粉末': 1}, buffer={}, phase='idle')
    check(not ordinary_valid(legacy_after['inputs'] + [legacy_after['output']]), '负例：旧充分条件产生的库存被独立规则13检查拒绝')
    check(input_target([{}], {'源石粉末': 1}, '源石粉末') is None, '反向辖域：取货格同种时外部存货拒收，不能新开普通格')
    check(input_target([{}], {}, '源石粉末') == 0, '缓存例外：不因缓存同种而拒收；不把产物作为错料禁收')
    for output_count in (0, 1, 48, 49, 50):
        for batch_count in (1, 2, 3):
            state = {'inputs': [{}], 'output': {'粉末': output_count} if output_count else {}, 'buffer': {'粉末': batch_count}, 'phase': 'completed'}
            result = output_batch(state)
            assert (result['phase'] == 'idle') == (output_count + batch_count <= 50)
            assert ordinary_valid(result['inputs'] + [result['output']])
            assert sum(result['output'].values()) + sum(result['buffer'].values()) == output_count + batch_count
    check(True, '整批边界：同种合并与50容量边缘15组合，物料不丢失不拆批')
    gate_seed = {edge: {'start': 0, 'count': 1, 'reasons': ['window_exhausted']} for edge in ('a', 'b')}
    gate_results = []
    for order in itertools.permutations(('a', 'b')):
        gates, ring, cursor = expire_batch({edge: gate_seed[edge] for edge in order}, 5, [], None, ['a', 'b'])
        assert ring == ['a', 'b'] and cursor == 'a'
        # 固定模板a,b、源有一件、门空且两端均授权a；成功后a再次满窗。
        gates['a'].update(start=5, count=1, reasons=['window_exhausted'])
        ring_after = ['b']
        cursor_after = remap(ring, 'b', ring_after)
        gate_results.append({'inventory': {'a': 1, 'b': 0}, 'ring': ring_after, 'cursor': cursor_after, 'gates': gates})
    check(gate_results[0] == gate_results[1], 'S3-r6-L3-01：门容器两种遍历序均给a收件、仅b存活且指针b的闭包投影')
    sequential = [remap([], None, [order[0]]) for order in itertools.permutations(('a', 'b'))]
    check(sequential == ['a', 'b'], '负例：逐边初始化再保留旧位仍能复现旧分歧')
    check(remap(['b'], 'b', ['a', 'b']) == 'b', '批恢复保留真正旧存活指针，不每次强重置a')
    check(remap(['a', 'b', 'c'], 'b', ['a', 'c']) == 'c', '删除指针成员沿旧环取下一存活成员')
    both = copy.deepcopy(gate_seed); both['b']['reasons'].append('total_exhausted')
    gates, ring, cursor = expire_batch(both, 5, [], None, ['a', 'b'])
    check(ring == ['a'] and gates['b']['reasons'] == ['total_exhausted'], '批维护不解除累计原因；4 tick也不提前恢复')
    assert expire_batch(gate_seed, 4, [], None, ['a', 'b'])[1] == []
    warehouse = {key: {'item': None, 'quantity': 0, 'identity': None} for key in ('W0', 'W1')}
    incoming = {'高容谷地电池': 1, '精选荞愈胶囊': 1}
    for order in itertools.permutations(incoming):
        box = {item: incoming[item] for item in order}
        status, state = transfer(box, warehouse, ['W0', 'W1'])
        assert status == 'unsupported:competing_new_species'
        assert state == {'box': box, 'warehouse': warehouse, 'cooldown': 0, 'delivered': {}}
    check(True, 'S3-r6-L3-02：空格序齐备仍识别多物种竞争，两个物种遍历序均停止且零副作用')
    check(transfer(incoming, {'W0': warehouse['W0']}, ['W0'])[0].startswith('unsupported'), '一个无身份空格同样发生新物种竞争')
    status, state = transfer({'高容谷地电池': 1}, warehouse, ['W0', 'W1'])
    check(status == 'success' and state['warehouse']['W0']['item'] == '高容谷地电池', '单新物种按给定空格序正常落格')
    new_states = [transfer({item: 1 for item in order}, {}, [])[1] for order in itertools.permutations(incoming)]
    check(new_states[0] == new_states[1], '无预声明空格时多新物种规范标签互异，计划与遍历序无关')
    full = {'W0': {'item': '高容谷地电池', 'quantity': 80000, 'identity': '高容谷地电池'}}
    status, state = transfer({'高容谷地电池': 1}, full, [])
    check(status == 'capacity_rejected' and state['cooldown'] == 5 and state['warehouse'] == full, '已定义容量拒收起冷却，与unsupported不发生后继严格区分')
    recipe = {'源矿': 1}
    check(recipe_matches({'源矿': 2}, recipe, 'at_least', 'allow') and not recipe_matches({'源矿': 2}, recipe, 'exact', 'allow'), 'S3-r6-L3-03：2源矿区分足量与恰等，未将exact当合法机制')
    check(recipe_matches({'源矿': 1, '蓝铁块': 1}, recipe, 'exact', 'allow') and not recipe_matches({'源矿': 1, '蓝铁块': 1}, recipe, 'exact', 'forbid'), '额外物种方向可在数量恰等时独立改变结果')
    check(not recipe_matches({'源矿': 1}, {'源矿': 2}, 'at_least', 'allow'), 'full_batch仍拒绝不足量，不因allow而启动缺料批次')
    dispositions = {r['id']: r for r in json.loads((SPEC/'第三轮任务验证/发现处置.json').read_text())}
    for identifier in ('S2-r4-L1-03', 'S2-r5-L1-04'):
        row = dispositions[identifier]
        assert '原发现已明确反对' in row['change']
        assert '不采发现中直接排除closed_touch' not in row['change']
    check(True, 'S3-r6-L1-01：两条处置各自准确记载原发现的反排除边界')
    return {'status': 'PASS', 'scope': '局部转移与反例回归，不是Rust内核或全称认证', 'checks': RESULTS,
            'manufacturing_trace': [before, completed, received, after], 'gate_outcomes': gate_results}


if __name__ == '__main__':
    print(json.dumps(run(), ensure_ascii=False, indent=2))
