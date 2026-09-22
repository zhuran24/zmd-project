"""第7轮几何覆盖与仓库连续转移回归；不是完整语义内核。"""
import copy
import importlib.util
import itertools
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
SPEC = BASE.parent
EXAMPLES = SPEC.parent / '数据/样例'
sys.path.insert(0, str(EXAMPLES))
import check_examples as checker
import runtime_example as runtime
import event_order

module_spec = importlib.util.spec_from_file_location('revision6', SPEC / '第6轮修订验证/核对修订回归.py')
revision6 = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(revision6)
RESULTS = []


def check(condition, name):
    assert condition, name
    RESULTS.append(name)


def validate_state(state):
    # 独立检查后态规则13/41及当前候选序定义域，不调用转移的选格逻辑。
    identities = set()
    empty = set()
    for key, slot in state['warehouse'].items():
        assert 0 <= slot['quantity'] <= 80000
        if slot['quantity']:
            assert slot['item'] is not None
            assert slot['identity'] == slot['item']
        else:
            assert slot['item'] is None
        if slot['identity'] is None:
            empty.add(key)
        else:
            assert slot['identity'] not in identities
            identities.add(slot['identity'])
    order = state['warehouse_empty_slot_order']
    assert len(order) == len(set(order)) and set(order) == empty
    assert all(key in state['warehouse'] for key in state['assignments'].values())


def seed(order):
    return {'time': 0, 'box': {}, 'warehouse': {
        key: {'item': None, 'quantity': 0, 'identity': None} for key in order},
        'warehouse_empty_slot_order': list(order), 'cooldown': 0,
        'delivered': {}, 'assignments': {'source_port': order[0]} if order else {}}


def attempt(state):
    # 只拼接单位传输片段；上游供料历史不在此局部测试中冒称已模拟。
    validate_state(state)
    if state['cooldown']:
        return 'not_ready', copy.deepcopy(state)
    status, result = revision6.transfer(state['box'], state['warehouse'], state['warehouse_empty_slot_order'])
    after = {**copy.deepcopy(state), **result}
    # 累计交付是调用方的运行账，局部辅助函数返回本次增量。
    after['delivered'] = copy.deepcopy(state['delivered'])
    for item, count in result['delivered'].items():
        after['delivered'][item] = after['delivered'].get(item, 0) + count
    validate_state(after)
    return status, after


def ready_with_batch(state, incoming):
    result = copy.deepcopy(state)
    result['time'] += 5
    result['cooldown'] = max(0, result['cooldown'] - 5)
    assert not result['box']
    result['box'] = copy.deepcopy(incoming)
    return result


def encode_warehouse_fragment(state):
    # 仅仓库与仲裁的真实输入片段；不是伪造完整StateSeed。
    slots = []
    for key, slot in state['warehouse'].items():
        nonempty = slot['quantity'] > 0
        slots.append({'slot': key, 'item': slot['item'],
                      'quantity': runtime.quantity(slot['quantity'], '算术推论'),
                      'empty_identity': runtime.decision(None if nonempty else slot['identity'],
                          '受限转移定义§4.1；retain_history的编码转换',
                          'not_applicable' if nonempty else 'specified')})
    return {'warehouse': {'slots': slots, 'unlisted': 'empty'}, 'semantic_context': {
        'arbitration': {'level_order': [], 'warehouse_empty_slot_order': state['warehouse_empty_slot_order']}}}


def decode_warehouse_fragment(fragment, original):
    checker.validate_slot_identity(fragment['warehouse'])
    result = copy.deepcopy(original)
    result['warehouse'] = {}
    for slot in fragment['warehouse']['slots']:
        count = checker.quantity(slot['quantity'])
        assert (slot['item'] is None) == (count == 0)
        checker.decision(slot['empty_identity'], {'not_applicable'} if count else {'specified'}, nullable=True)
        result['warehouse'][slot['slot']] = {'item': slot['item'], 'quantity': count,
            'identity': slot['item'] if count else slot['empty_identity']['value']}
    order = fragment['semantic_context']['arbitration']['warehouse_empty_slot_order']
    assert set(runtime.empty_slot_ids(fragment['warehouse'])) == set(order)
    result['warehouse_empty_slot_order'] = copy.deepcopy(order)
    validate_state(result)
    return result


def main():
    catalog = checker.load_json(EXAMPLES.parent / '正式静态目录.json')
    data = checker.load_json(EXAMPLES / '混做粉碎机两下游.json')
    registry = checker.axis_registry()
    row = registry['connection.port_meeting']
    config = checker.load_json(SPEC / '内核配置-v1.json')['axes']['connection.port_meeting']
    check(row['state'] == 'open' and row['group'] == 'fixedness_unproven'
          and config['lifetime'] == 'U' and config['disposition'] == '本版选值',
          'S3-r7-L3-1：轴表、生命周期、配置均不再把相遇谓词标成已定')
    # 两个闭端口线段有且仅有端点相交；不将相交数学事实当合法成边证明。
    first = {(1, 0), (1, 1)}
    second = {(1, 1), (1, 2)}
    check(first & second == {(1, 1)} and first != second,
          '角点反例：不重叠格(0,0)/(1,1)的东/西端口仅交一点，法向相反仍不全长重合')
    for value in ('closed_segment_touch', None):
        changed = copy.deepcopy(data)
        changed['parameters']['fixedness_unproven']['connection.port_meeting'].update(
            status='unresolved' if value is None else 'specified', value=value)
        try:
            checker.geometry(changed, catalog)
        except checker.CheckError as error:
            check('unsupported: connection.port_meeting' in str(error),
                  '几何入口拒绝未支持/未解相遇谓词：' + str(value))
        else:
            raise AssertionError('相遇谓词被静默默认')
    check(len(checker.geometry(data, catalog)[3]) == 11,
          '显式shared_edge_opposite仍重算黄金布局11条PC')
    for name in checker.NAMES:
        before = checker.load_json(BASE / '迁移前样例' / name)
        after = checker.load_json(EXAMPLES / name)
        assert {key: value['value'] for key, value in runtime.axis_values(before).items()} == {
            key: value['value'] for key, value in runtime.axis_values(after).items()}
        for sample in (before, after):
            sample.pop('parameters')
            if sample['initial_state']['nonwarehouse']['status'] == 'specified':
                sample['initial_state']['nonwarehouse']['value']['semantic_context'].pop('parameter_values')
        assert before == after
    check(True, '三个样例迁移前后实际参数值、几何、建造历史和物理初态逐字段相同')
    # 请求§7的表示片段核验；不把非周期排序求值说成双箱实际运行。
    templates = [{'operation': 'transfer', 'target': name} for name in ('box_a', 'box_b')]
    expression = {'schema': 'event-order-v3', 'scope': 'per_instant',
                  'template_order': templates, 'repeat_embedding': 'scan_round_then_template',
                  'schedule': {'kind': 'expression', 'language': 'order-expr-v1', 'expression': {
                      'op': 'if', 'condition': {'op': 'is_power_of_two', 'arg': {
                          'op': 'floor_slot', 'origin': runtime.time_value(0), 'width': runtime.time_value(5)}},
                      'then': {'op': 'permutation', 'order': list(reversed(templates))},
                      'otherwise': {'op': 'permutation', 'order': templates}}}}
    for index in (-1, 0, 1, 2, 3, 4, 8, 1024, 1025, 2**100, 2**100 + 1):
        expected = list(reversed(templates)) if index > 0 and index.bit_count() == 1 else templates
        assert event_order.order_at(expression, runtime.time_value(index * 5)) == expected
    check(True, '请求§7：非周期纯函数在负时刻、0、正二次幂及远期非幂槽按完整模板序求值')
    broken = copy.deepcopy(expression)
    broken['schedule']['expression']['otherwise']['order'] = templates[:1]
    try:
        event_order.order_at(broken, runtime.time_value(5))
    except checker.CheckError:
        check(True, '表达式即使本次选then，也拒绝未访问otherwise的漏模板错误')
    else:
        raise AssertionError('未访问坏分支被放行')

    traces = []
    species = ('高容谷地电池', '精选荞愈胶囊')
    for order in itertools.permutations(('W0', 'W1')):
        for items in itertools.permutations(species):
            initial = seed(order)
            initial['box'] = {items[0]: 1}
            original = copy.deepcopy(initial)
            status, first_state = attempt(initial)
            assert status == 'success' and initial == original
            assert first_state['warehouse_empty_slot_order'] == [order[1]]
            assert first_state['warehouse'][order[0]]['item'] == items[0]
            next_input = ready_with_batch(first_state, {items[1]: 1})
            uninterrupted = attempt(next_input)
            reloaded = attempt(json.loads(json.dumps(next_input, ensure_ascii=False)))
            assert uninterrupted == reloaded and uninterrupted[0] == 'success'
            wire = json.loads(json.dumps(encode_warehouse_fragment(next_input), ensure_ascii=False))
            decoded = decode_warehouse_fragment(wire, next_input)
            assert decoded == next_input and attempt(decoded) == uninterrupted
            final = uninterrupted[1]
            assert final['warehouse_empty_slot_order'] == []
            assert final['warehouse'][order[1]]['item'] == items[1]
            assert final['delivered'] == {items[0]: 1, items[1]: 1}
            assert final['assignments'] == initial['assignments']
            traces.append({'order': order, 'species': items, 'initial': initial,
                           'after_first': first_state, 'after_second': final})
    check(len(traces) == 4, 'S3-r7-L3-2：两空格序×两物种先后，连续两批与JSON重载逐字段一致')
    check(True, '真实Warehouse/Decision及arbitration编码往返后连续结果相同；非空格empty_identity为not_applicable')

    first_state = traces[0]['after_first']
    status, unchanged = attempt(first_state)
    check(status == 'not_ready' and unchanged == first_state, '5 tick冷却未到不产生额外传输或改序')
    stale = ready_with_batch(first_state, {species[1]: 1})
    stale['warehouse_empty_slot_order'] = ['W0', 'W1']
    try:
        validate_state(stale)
    except AssertionError:
        check(True, '旧固定母序负例由独立后态检查拒绝，调用方不能偷偷修序')
    else:
        raise AssertionError('旧序未拒绝')
    check(revision6.transfer(stale['box'], stale['warehouse'], stale['warehouse_empty_slot_order'])[0] == 'invalid',
          '转移入口同样拒绝继承旧母序的错误输入')

    state = seed(['W9', 'W2', 'W7'])
    state['box'] = {species[0]: 1}
    status, after = attempt(state)
    check(status == 'success' and after['warehouse_empty_slot_order'] == ['W2', 'W7'],
          '稳定删项不按id重排幸存空格')
    # 模拟一次已获准普通取货的库存后效，保留历史身份，不模拟其轮询日程。
    after['warehouse']['W9'].update(item=None, quantity=0)
    validate_state(after)
    assert decode_warehouse_fragment(json.loads(json.dumps(encode_warehouse_fragment(after))), after) == after
    status, again = attempt(ready_with_batch(after, {species[0]: 2}))
    check(status == 'success' and again['warehouse']['W9']['quantity'] == 2
          and again['warehouse_empty_slot_order'] == ['W2', 'W7'],
          '已用格清空保留身份且不回候选序，同种再入用历史格')

    full = seed(['W0'])
    full['warehouse']['Wfull'] = {'item': species[0], 'quantity': 80000, 'identity': species[0]}
    full['box'] = {species[0]: 1, species[1]: 1}
    status, rejected = attempt(full)
    check(status == 'capacity_rejected' and rejected == {**full, 'cooldown': 5},
          '容量拒收整箱回滚：不因已拟分配W0而删序或写身份')
    competing = seed(['W0', 'W1'])
    competing['box'] = {item: 1 for item in species}
    status, stopped = attempt(competing)
    check(status == 'unsupported:competing_new_species' and stopped == competing,
          '多物种竞争仍先停：仓库、序、冷却及交付账零副作用')
    empty = seed(['W0'])
    status, empty_after = attempt(empty)
    check(status == 'success' and empty_after == {**empty, 'cooldown': 5},
          '空箱尝试起冷却而不改候选序')
    new = seed([])
    new['box'] = {item: 1 for item in species}
    status, new_after = attempt(new)
    check(status == 'success' and new_after['warehouse_empty_slot_order'] == []
          and len(new_after['warehouse']) == 2,
          '无匿名格时规范新格带种创建，不加入当前空格序')
    # 不依赖枚举顺序的独立库存守恒与容量检查覆盖全部连续轨迹。
    for trace in traces:
        end = trace['after_second']
        validate_state(end)
        assert sum(slot['quantity'] for slot in end['warehouse'].values()) == sum(end['delivered'].values()) == 2
    check(True, '连续序列独立核仓库单种单格、80000容量、交付守恒及取货指派保持')
    report = {'status': 'PASS', 'scope': '局部仓库事务的连续/重载验证及几何读法门禁；非完整StateSeed内核续跑或全规则认证',
              'checks': RESULTS, 'warehouse_traces': traces}
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
