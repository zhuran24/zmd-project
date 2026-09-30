#!/usr/bin/env python3
"""生成一个静态桥接结构例和两个显式初值的有限运行例。"""
import hashlib
import json
from pathlib import Path
import check_examples as checker

BASE = Path(__file__).resolve().parent

def quantity(value, category='候选'):
    return {'value': str(value), 'category': category}

def decision(basis, status='unresolved', value=None):
    return {'status': status, 'value': value, 'basis': [basis]}

def unit(uid, kind, x, y, rotation='r0', port_layout=0):
    return {'id': uid, 'kind': kind, 'origin': [quantity(x), quantity(y)], 'rotation': rotation, 'port_layout': None if kind == '桥接器' else port_layout, 'bridge_axes': None, 'occupied_cells': None}

def make_parameters():
    registry = checker.axis_registry()
    result = {'axis_registry': {'path': '../../规格/选择点参数轴.md', 'sha256': hashlib.sha256(checker.AXIS_PATH.read_bytes()).hexdigest()}, 'profile_id': None, 'fixed': {}, 'offline_mutable': {}, 'fixedness_unproven': {}}
    for name, row in registry.items():
        basis = '选择点参数轴.md §2 ' + name + '；' + row['description']
        value = decision(basis)
        if name in checker.KNOWN_VALUES:
            value = decision(basis, 'specified', checker.KNOWN_VALUES[name])
        elif name == 'connection.port_meeting':
            value = decision(basis + '；合成几何显式采用本版受限读法，不排除角点方向', 'specified', 'shared_edge_opposite')
        elif name == 'connection.build_order':
            value = decision(basis, 'derived', 'construction.selected_order')
        elif name == 'connection.order':
            value = decision(basis, 'derived', 'timeline_connection_history')
        result[row['group']][name] = value
    return result

def build(name, local_units, intents, routes, assertion):
    catalog_path = BASE.parent / '正式静态目录.json'
    catalog = checker.load_json(catalog_path)
    kinds = {row['id']: row for row in catalog['units']}
    items = sorted(checker.INITIAL_ITEMS)
    units = [unit('core', '协议核心', 50, 50)] + local_units
    order = [u['id'] for u in units if u['kind'] != '传送带'] + [u['id'] for u in units if u['kind'] == '传送带']
    by_unit = {u['id']: u for u in units}
    moments = [{'event': f'build_{i}', 'unit': uid, 'placement': {key: by_unit[uid][key] for key in ('kind', 'origin', 'rotation', 'port_layout', 'occupied_cells')}} for i, uid in enumerate(order)]
    events = [{'id': m['event'], 'kind': 'build', 'time': {'kind': 'symbol', 'value': f't_build_{i}'}} for i, m in enumerate(moments)]
    events += [{'id': key, 'kind': key, 'time': {'kind': 'symbol', 'value': 't_' + key}} for key in ('blueprint_complete', 'debug_end')]
    relations = [{'before': a['event'], 'after': b['event'], 'relation': 'strict', 'basis': ['蓝图候选见证，仅先后，不指定 tick 间隔']} for a, b in zip(moments, moments[1:])]
    relations += [{'before': moments[-1]['event'], 'after': 'blueprint_complete', 'relation': 'occurs_before', 'basis': ['全部建成']}, {'before': 'blueprint_complete', 'after': 'debug_end', 'relation': 'occurs_before', 'basis': ['建造完成且调试结束']}]
    anchor = {'event': 'blueprint_complete', 'side': 'after'}
    data = {
        'schema': 'kernel-input-v2', 'purpose': 'synthetic_geometry',
        'catalog': {'path': '../正式静态目录.json', 'sha256': hashlib.sha256(catalog_path.read_bytes()).hexdigest()},
        'timeline': {'events': events, 'relations': relations, 'connection_events': []},
        'layout': {'id': 'built_layout', 'anchor': anchor, 'snapshots': [], 'post_debug': decision('调试终态及全部允许历史尚未认证'), 'base': {'width': quantity(70, '条文直引'), 'height': quantity(70, '条文直引')}, 'units': units, 'physical_channels': None, 'buffer_channels': None},
        'construction': {'mode': 'blueprint_once', 'order_domain': 'all_rule_consistent_orders', 'selected_order': order, 'moments': moments, 'complete_event': 'blueprint_complete'},
        'settings': {'anchor': anchor, 'switches': [{'unit': u['id'], 'function': fn, 'enabled': True} for u in units for fn in kinds[u['kind']]['powered_functions']], 'gates': [{'unit':u['id'],'item':'源矿','total_limit':None,'window_limit':quantity(1)} for u in units if u['kind']=='物品准入口'], 'warehouse_assignments': []},
        'parameters': make_parameters(),
        'initial_state': {'anchor': decision('任务 L6；T11：初始仓库锚点未定'), 'warehouse': {'slots': [{'slot': f'warehouse_{i}', 'item': item, 'quantity': quantity(80000, '条文直引'), 'empty_identity': decision('非空格内容已给；空身份不适用', 'not_applicable')} for i, item in enumerate(items)], 'unlisted': 'empty'}, 'nonwarehouse': decision('T11；不无据设非仓库全空'), 'reachability': decision('任务调试期、操作精度；未提供可达性证明')},
        'debug_operations': [],
        'environment': {'ore_supply': 'task_continuous_sufficient', 'offline': {'event_domain': decision('任务 L13；T10：空离线见证不排除离线'), 'selected_events': []}, 'product_withdrawal': {'policy': decision('任务 L8、L12；T12：成品拿取不可精确计时'), 'selected_events': []}, 'debug_end_event': 'debug_end', 'zero_intervention_after_debug': True},
        'contract_binding': None,
        'scenario': {'name': name, 'recipe_intents': [{'unit': uid, 'recipes': recipes} for uid, recipes in intents], 'expected_paths': [{'name': f'path_{i}', 'physical_channels': [f'PC|{a}|{b}' for a, b in route]} for i, route in enumerate(routes)], 'assertions': [assertion]},
    }
    derived = checker.geometry(data, catalog)
    data['layout']['physical_channels'] = derived[3]
    data['layout']['buffer_channels'] = derived[4]
    ore_slot = next(row['slot'] for row in data['initial_state']['warehouse']['slots'] if row['item'] == '源矿')
    by_id = {u['id']: u for u in units}
    data['settings']['warehouse_assignments'] = [{'port': pid, 'slot': ore_slot} for pid, port in derived[2].items() if port['role'] == 'output' and by_id[port['unit']]['kind'] in ('协议核心', '仓库取货口')]
    rank = {uid: i for i, uid in enumerate(order)}
    for i, channel in enumerate(derived[3]):
        source, target = [derived[2][channel[key]]['unit'] for key in ('source_port', 'target_port')]
        later = max((source, target), key=rank.get)
        event, cause = f'connect_{i}', f'build_{rank[later]}'
        data['timeline']['events'].append({'id': event, 'kind': 'connection_open', 'time': {'kind': 'symbol', 'value': f't_build_{rank[later]}'}})
        data['timeline']['connection_events'].append({'event': event, 'channel': channel['id'], 'action': 'open', 'cause': cause, 'geometry_snapshot': 'built_layout', 'construction_basis': decision('规则接通：较晚建成端', 'specified', {'source_build': f'build_{rank[source]}', 'target_build': f'build_{rank[target]}', 'later_build': cause})})
    if not any(u['kind'] == '协议储存箱' for u in units):
        data['parameters']['fixedness_unproven']['transfer.phase'] = decision('无协议储存箱且调试为空；此结构样例不发生箱体传输', 'not_applicable')
    path = BASE / (name + '.json')
    if name in ("混做粉碎机两下游", "分流器三路轮询"):
        if name == "分流器三路轮询":
            for switch in data["settings"]["switches"]:
                switch["enabled"] = False
        from runtime_example import upgrade, write_profile
        data = upgrade(data, catalog)
        write_profile(data)
    result = checker.check(data, path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))

def main():
    build('桥接器双通路', [
        unit('south_box', '协议储存箱', 10, 7), unit('bridge', '桥接器', 12, 10),
        unit('north_box', '协议储存箱', 12, 11), unit('west_box', '协议储存箱', 9, 10, 'r270'),
        unit('east_box', '协议储存箱', 13, 8, 'r270'), unit('power', '供电桩', 16, 10)], [], [
        [('south_box:north:2', 'bridge:south:0'), ('bridge:north:0', 'north_box:south:0')],
        [('west_box:north:2', 'bridge:west:0'), ('bridge:east:0', 'east_box:south:0')]],
        {'kind': 'bridge_two_lanes', 'unit': 'bridge'})
    build('分流器三路轮询', [
        unit('south_box', '协议储存箱', 19, 2), unit('splitter', '分流器', 21, 5),
        unit('north_box', '协议储存箱', 21, 6), unit('east_box', '协议储存箱', 22, 3, 'r270'),
        unit('west_box', '协议储存箱', 18, 5, 'r90'), unit('power', '供电桩', 25, 3),
        unit('ore_source', '仓库取货口', 19, 0), unit('feed_splitter', '分流器', 20, 1),
        unit('probe_left_source', '仓库取货口', 0, 1, 'r270'), unit('probe_bottom_source', '仓库取货口', 1, 0),
        unit('probe_merger', '汇流器', 2, 2, 'r270'), unit('probe_box', '协议储存箱', 3, 2, 'r270'),
        unit('probe_gate_a', '物品准入口', 1, 3), unit('probe_gate_b', '物品准入口', 3, 1, 'r270'),
        unit('probe_left', '分流器', 1, 2, 'r270'), unit('probe_bottom', '分流器', 2, 1)], [], [
        [('south_box:north:2', 'splitter:south:0'), ('splitter:north:0', 'north_box:south:0')],
        [('south_box:north:2', 'splitter:south:0'), ('splitter:east:0', 'east_box:south:0')],
        [('south_box:north:2', 'splitter:south:0'), ('splitter:west:0', 'west_box:south:0')]],
        {'kind': 'splitter_three_outputs', 'unit': 'splitter'})
    build('混做粉碎机两下游', [
        unit('crusher', '粉碎机', 30, 2), unit('grinder_a', '研磨机', 25, 8), unit('grinder_b', '研磨机', 33, 8), unit('power', '供电桩', 34, 3), unit('ore_source', '仓库取货口', 29, 0), unit('feed_belt', '传送带', 30, 1),
        unit('belt_a0', '传送带', 30, 5), unit('belt_a1', '传送带', 30, 6), unit('belt_a2', '传送带', 30, 7),
        unit('belt_b0', '传送带', 32, 5, port_layout=1), unit('belt_b1', '传送带', 33, 5, 'r270', 2), unit('belt_b2', '传送带', 33, 6), unit('belt_b3', '传送带', 33, 7)],
        [('crusher', ['粉碎-源矿', '粉碎-蓝铁块']), ('grinder_a', ['研磨-致密源石']), ('grinder_b', ['研磨-致密蓝铁'])], [
        [('crusher:north:0', 'belt_a0:south:0'), ('belt_a0:north:0', 'belt_a1:south:0'), ('belt_a1:north:0', 'belt_a2:south:0'), ('belt_a2:north:0', 'grinder_a:south:5')],
        [('crusher:north:2', 'belt_b0:south:0'), ('belt_b0:east:0', 'belt_b1:south:0'), ('belt_b1:west:0', 'belt_b2:south:0'), ('belt_b2:north:0', 'belt_b3:south:0'), ('belt_b3:north:0', 'grinder_b:south:0')]],
        {'kind': 'mixed_two_downstreams', 'unit': 'crusher'})

if __name__ == '__main__':
    main()
